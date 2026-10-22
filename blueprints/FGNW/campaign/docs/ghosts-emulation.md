How the campaign drives believable user activity on the range workstations, and how the
generated content that feeds it is regenerated.
User emulation runs from the **ghost9 CT** — GHOSTS 9.3.0 (API v9) as a `get_sybers.lxc`
container created pre-containment in Phase 1b from the published ghost9 template
(`ghcr.io/get-sybers/lxc/ghost9`, with n8n and Grafana as native services) by
the `get_sybers.lxc` collection's `deploy_ghost9_range` play; API `http://10.<range>.99.51:5000/api`, UI `:4200`. It
drives one **flagship workstation per domain population** — capped at 5 per domain — each
mapped to a named character persona.
Per-host behaviour comes from a GHOSTS timeline rendered by
`ansible/templates/FGNW-ghosts.timeline.json.j2`, applied by
`ansible/FGNW-ghosts-activity.yml` (`hosts: ghosts_clients`, per-host persona lookup). The
attacker sinkhole the personas can be steered toward is on VLAN 99 (`.99.50`). Operator-facing
behaviour is written up in [`../content/ghosts/persona-behaviour.md`](../content/ghosts/persona-behaviour.md).
The timeline template reads three generated files. **Regenerate rather than hand-editing** when
a source input changes; each script is run from the blueprint root.
The per-persona baseline: character, AD domain/NetBIOS, homepage, OWA-inbox presence, and the
browse URL set. Generated from `content/www/FGNW_user_homepage_mapping.csv` (per-character
homepage + favourites) plus the inbox key set from `content/OWA/user-inboxes.yml`, keyed by
GHOSTS-client inventory hostname.
> Note: `has_owa_inbox` is captured from `user-inboxes.yml`'s key set **at generation time** and
> does not auto-update — regenerate this file whenever `user-inboxes.yml` changes (see below).

```python
import csv, yaml, collections
hostmap = collections.OrderedDict([
 ('konoha-ws1',('naruto.uzumaki','konohagakure.fire.ninja','KONOHA')),
 ('konoha-ws2',('shikamaru.nara','konohagakure.fire.ninja','KONOHA')),
 ('konoha-ws3',('kakashi.hatake','konohagakure.fire.ninja','KONOHA')),
 ('konoha-ws4',('tsunade','konohagakure.fire.ninja','KONOHA')),
 ('konoha-ws5',('might.guy','konohagakure.fire.ninja','KONOHA')),
 ('oto-ws1',('orochimaru','otogakure.ninja','OTO')),
 ('akatsuki-ws1',('pain','akatsuki.dark','AKATSUKI')),
 ('akatsuki-ws2',('zetsu','akatsuki.dark','AKATSUKI')),
 ('suna-ws1',('gaara','sunagakure.wind.ninja','SUNA')),
])
rows={r['sAMAccountName']:r for r in csv.DictReader(open('content/www/FGNW_user_homepage_mapping.csv'))}
inboxes=set(yaml.safe_load(open('content/OWA/user-inboxes.yml'))['user_inboxes'])
MAXFAV=8; out={'ghosts_personas':{}}
for host,(sam,dom,nb) in hostmap.items():
    r=rows[sam]; favs=[x.strip() for x in r['favourites'].split('|') if x.strip()]
    seen=set(); urls=[]
    for u in [r['wWWHomePage'].strip()]+favs:
        if u not in seen: seen.add(u); urls.append(u)
        if len(urls)>=1+MAXFAV: break
    out['ghosts_personas'][host]={'character':r['displayName'],'sam':sam,'ad_domain':dom,
      'netbios':nb,'homepage':'http://'+r['wWWHomePage'].strip(),'has_owa_inbox':sam in inboxes,
      'browse_urls':['http://'+u for u in urls]}
yaml.safe_dump(out,open('content/ghosts/persona-timelines.yml','w'),default_flow_style=False,sort_keys=False,width=120)
```

**Flagship overrides** are layered on top by the hand-authored
`content/ghosts/persona-overrides.yml` (not generated): a per-character **signature handler**
(obsession sites at a `pace` of obsessive/normal/idle) and an **activity window**
(`active_hours.start`/`active_hours.end`), encoding the personalities in
[`../content/ghosts/FGNW-user-emulation-behaviour.md`](../content/ghosts/FGNW-user-emulation-behaviour.md).
The template merges overrides with safe defaults, so un-overridden hosts still work.
> YAML gotcha: `active_hours` keys are `start`/`end`, not `on`/`off` — YAML parses `on`/`off`
> as booleans, turning the keys into `True`/`False`.
`email-relationships.yml` is the "who emails whom" graph for all characters, derived from real AD
signals in `content/AD/characters.csv` — `manager`, direct reports, and shared *specific* group
membership (a team/clan/council, excluding the broad village group everyone shares), falling back
to same-department peers only where no closer tie exists. Every edge carries its reason
(`manager`, `direct_report`, `team: <group>`, `department_fallback`).
`user-inboxes.yml` is then regenerated so each quote from `content/OWA/email-content.csv` is
delivered to one of the *sending* character's real correspondents (round-robin per sender against
their edge list) rather than to their own inbox. Hand-authored exceptions already in the file
(the intel-portal alerts and the Danzo invites) are extracted by their `from_address` marker and
re-merged verbatim. The sender-forest map is authoritative from `ad/NARUTO/data/config.json` (an
account's real AD domain, not its `characters.csv` village — a defector like Orochimaru lives in
`otogakure.ninja` despite a Leaf village tag).
Run from the blueprint root; `email-relationships.yml` first, since the inbox regen reads it:

```python
import csv, json, collections
rows = list(csv.DictReader(open('content/AD/characters.csv')))
profiles = {}
for r in rows:
    sam = r['sAMAccountName'].strip()
    if not sam: continue
    groups = [g.strip() for g in r['groups'].split('|') if g.strip()]
    profiles[sam] = {'department': r['department'], 'manager': r['manager'].strip(),
                      'specific_groups': groups[1:] if len(groups) > 1 else []}
sams = set(profiles.keys())
group_index = collections.defaultdict(set)
for sam, p in profiles.items():
    for g in p['specific_groups']: group_index[g].add(sam)
reports_index = collections.defaultdict(set)
for sam, p in profiles.items():
    if p['manager']: reports_index[p['manager']].add(sam)
dept_index = collections.defaultdict(set)
for sam, p in profiles.items(): dept_index[p['department']].add(sam)
def build_edges(sam):
    p = profiles[sam]; edges = []; seen = set()
    if p['manager'] and p['manager'] in sams:
        edges.append((p['manager'], 'manager')); seen.add(p['manager'])
    for r in sorted(reports_index.get(sam, set())):
        if r not in seen: edges.append((r, 'direct_report')); seen.add(r)
    for g in p['specific_groups']:
        for peer in sorted(group_index[g]):
            if peer != sam and peer not in seen: edges.append((peer, f'team: {g}')); seen.add(peer)
    if not edges:
        for peer in sorted(dept_index.get(p['department'], set()))[:10]:
            if peer != sam: edges.append((peer, 'department_fallback')); seen.add(peer)
    return edges
graph = {sam: build_edges(sam) for sam in sorted(sams)}
with open('content/ghosts/email-relationships.yml', 'w') as f:
    f.write('email_relationships:\n')
    for sam in sorted(graph):
        edges = graph[sam]
        if not edges: f.write(f'  {sam}: []\n'); continue
        f.write(f'  {sam}:\n')
        for to, rel in edges:
            f.write(f'  - to: {to}\n    relationship: {json.dumps(rel)}\n')
import re, yaml
current = yaml.safe_load(open('content/OWA/user-inboxes.yml'))['user_inboxes']
exceptions = collections.defaultdict(list)
for sam, msgs in current.items():
    for m in msgs:
        if (m['from_address'] == 'intel@konoha-portal.leaf'
                or (m['from_address'] == 'danzo.shimura@konohagakure.fire.ninja' and sam != 'danzo.shimura')):
            exceptions[sam].append(m)
graph = yaml.safe_load(open('content/ghosts/email-relationships.yml'))['email_relationships']
prof = {r['sAMAccountName'].strip(): r for r in rows if r['sAMAccountName'].strip()}
_doms = json.load(open('ad/NARUTO/data/config.json'))['lab']['domains']
sam2dom = {sam: fqdn for fqdn, d in _doms.items() for sam in d.get('users', {})}
MAIL_FORESTS = {'konohagakure.fire.ninja', 'sunagakure.wind.ninja', 'otogakure.ninja', 'akatsuki.dark'}
def sender_forest(sam):
    dom = sam2dom.get(sam)
    return dom if dom in MAIL_FORESTS else 'konohagakure.fire.ninja'
new_inboxes = collections.defaultdict(list); rr = collections.defaultdict(int)
with open('content/OWA/email-content.csv') as f:
    for row in csv.DictReader(f):
        sam = row['sAMAccountName'].strip(); quote = re.sub(r'\s+', ' ', row['quote']).strip()
        if not sam or not quote: continue
        cands = graph.get(sam, [])
        recipient = cands[rr[sam] % len(cands)]['to'] if cands else sam
        rr[sam] += 1
        new_inboxes[recipient].append({
            'body': quote, 'from_address': f'{sam}@{sender_forest(sam)}',
            'from_name': prof.get(sam, {}).get('displayName', row['character_name']),
            'subject': quote if len(quote) <= 80 else quote[:80] + '...'})
for sam, msgs in exceptions.items(): new_inboxes[sam].extend(msgs)
with open('content/OWA/user-inboxes.yml', 'w') as f:
    f.write('user_inboxes:\n')
    for sam in sorted(new_inboxes):
        f.write(f'  {sam}:\n')
        for m in new_inboxes[sam]:
            for k in ('body', 'from_address', 'from_name', 'subject'):
                f.write(f'  - {k}: {json.dumps(m[k], ensure_ascii=False)}\n' if k == 'body'
                        else f'    {k}: {json.dumps(m[k], ensure_ascii=False)}\n')
```

> `persona-timelines.yml` reads `user-inboxes.yml`'s key set, so regenerate **both together**
> whenever either's source changes — regenerating one is not independent of the other.
Per-character jutsu + quotes, backing the themed-site content pass (`ansible/roles/fgnw_themed_sites/`).
Merges `content/ninjutsu.txt` (per-character jutsu, plus a "General / Misc" bucket) with the quote
corpus in `content/OWA/email-content.csv` (the same MIT-licensed `animequotes` set the OWA inboxes
draw from — `credits.md` covers it). A small alias table folds the CSV's free-text `character_name`
variants onto `ninjutsu.txt`'s canonical names.

```python
import csv, re, yaml
from collections import defaultdict
with open('content/ninjutsu.txt') as f:
    lines = [l.rstrip('\n') for l in f]
blocks, block = [], []
for l in lines:
    if l.strip() == '':
        if block: blocks.append(block); block = []
    else:
        block.append(l)
if block: blocks.append(block)
jutsu_by_char, jutsu_order, general_techniques = {}, [], []
i = 0
while i < len(blocks):
    name = blocks[i][0].strip()
    techs = blocks[i+1] if i+1 < len(blocks) else []
    if name == 'General / Misc':
        general_techniques = list(techs)
    else:
        jutsu_by_char[name] = list(techs); jutsu_order.append(name)
    i += 2
alias_to_canonical = {
    'Hatake Kakashi': 'Kakashi Hatake', 'Kabuto Yakushi': 'Kabuto',
    'Pain': 'Pain / Nagato', 'Nagato': 'Pain / Nagato',
    'Might Guy': 'Rock Lee / Might Guy', 'Rock Lee': 'Rock Lee / Might Guy',
    'Ohnoki': 'Ōnoki',
}
quote_only_canonical = {
    'Tsunade', 'Iruka Umino', 'Zabuza Momochi', 'Kisame Hoshigaki', 'Hinata Hyuuga',
    'Neji Hyuuga', 'Nara Shikamaru', 'Shikaku Nara', 'Tobi', 'Obito Uchiha',
    'Anko Mitarashi', 'Jiraiya', 'Ōnoki',
}
def canon(name): return alias_to_canonical.get(name, name)
quotes_by_char = defaultdict(list)
with open('content/OWA/email-content.csv') as f:
    for row in csv.DictReader(f):
        cname = canon(row['character_name'].strip())
        if cname not in jutsu_by_char and cname not in quote_only_canonical:
            continue
        q = re.sub(r'\s+', ' ', row['quote']).strip()
        if q: quotes_by_char[cname].append(q)
def pick_quotes(cname, n=3, maxlen=200):
    cands = quotes_by_char.get(cname, [])
    pool = [q for q in cands if len(q) <= maxlen] or cands
    out = []
    for q in pool:
        trimmed = q if len(q) <= maxlen else q[:maxlen-1].rsplit(' ',1)[0] + '…'
        if trimmed not in out: out.append(trimmed)
        if len(out) >= n: break
    return out
all_names = jutsu_order + sorted(quote_only_canonical - set(jutsu_by_char.keys()))
profiles = {n: {'jutsu': list(jutsu_by_char.get(n, [])), 'quotes': pick_quotes(n)} for n in all_names}
yaml.safe_dump({'character_profiles': profiles, 'general_techniques': general_techniques},
                open('content/www/character-profiles.yml', 'w'),
                default_flow_style=False, sort_keys=False, width=100, allow_unicode=True)
```
