A trimmed cut of the Fourth Great Ninja War range for when you don't want the
full footprint. It keeps the campaign's core attack surface and drops the
expensive extras (three of four mail servers, the Wind/Sand forest, Akatsuki, most Leaf
workstations).
`small` is not a separate config file. There is one `range-config.yml` — the 23-VM superset —
and `campaign/deploy.yml` cuts the small variant out of it at deploy time:

```bash
ansible-playbook deploy.yml -e range_variant=small
```

Its VM set and its per-VM sizes are declared in that file's `ludus_extensions.variants` block
(`include.small`, `target_node.small`, `overrides.small`). See
[`RANGE-CONFIG-VARIANTS.md`](RANGE-CONFIG-VARIANTS.md) for the selection model, and
[`DEPLOY.md`](DEPLOY.md) for the canonical phase-by-phase sequence — DEPLOY.md wins if the two
ever disagree. The manual walkthrough below is kept for the topology/footprint reference and the
AD-inventory-swap mechanics.

| variant | VMs | RAM | vCPU | placement |
| --- | --- | --- | --- | --- |
| `xl` | 23 | 112 GB | 50 | across all 3 nodes |
| regular (default) | 22 | 104 GB | 46 | across all 3 nodes |
| **`small`** | **9** | **64 GB** | **26** | **one node** |

(+ ~1 GB Ludus router either way.) Small is deliberately single-node: `target_node.small` is
`{"*": null}`, which strips `target_node` from every VM so they all land on `defaults.target_node`.
Because it runs alone on one node it is *not* a same-size subset — eight of its nine VMs are given
more RAM and/or vCPU than the distributed variants (that is what `overrides.small` is for).

| host | dict_key | domain | VLAN | RAM/vCPU | role in the lab |
| --- | --- | --- | --- | --- | --- |
| fire-dc1 | dc01 | `fire.ninja` | 10 | 8 GB / 4 | Land of Fire forest root (2 real users — Fire Daimyo + Madam Shijimi) |
| konoha-dc1 | dc02 | `konohagakure.fire.ninja` | 10 | 8 GB / 4 | Leaf child domain (users) |
| konoha-mail | srv-konoha | (Leaf member) | 10 | 12 GB / 2 | Mail server — real Exchange 2019 (70 Leaf mailboxes, quote/alert corpus seeded). Deployed by default in Phase 4b, see below |
| konoha-ws1 | srv03 | (Leaf member) | 10 | 6 GB / 2 | Naruto — GHOSTS workstation / lateral target / personal-desktop decoy content |
| oto-dc1 | dc05 | `otogakure.ninja` | 30 | 8 GB / 4 | Sound external forest (trust partner) |
| oto-ws1 | srv08 | (Sound member) | 30 | 6 GB / 2 | Orochimaru — GHOSTS workstation |
| ninjasploitable | — | — | 90 | 4 GB / 2 | vulnerable "Ichiraku" web target (webshell pivot) |
| attacker | — | — | 99 | 4 GB / 2 | tool-cache + noise-domain sinkhole + 144 themed sites |
| kali | — | — | 99 | 8 GB / 4 | attacker desktop |

The GHOSTS API/UI server is not on this list because it is not a VM in any variant — it is
the `ghost9` CT (GHOSTS 9.3.0, a `get_sybers.lxc` container created from the published ghost9
template), placed by Phase 1b from the root-level `ludus_extensions.ghost9` block and present
in the small range too (API `:5000`, UI `:4200`, Grafana `:3000`, n8n `:5678` on VLAN 99 `.51`).
AD is **native** here as everywhere else: the small variant inherits the superset's `domain:`
blocks and `ludus_windows_utils` roles, so `ludus range deploy` promotes `fire.ninja`, builds the
`konohagakure` child, joins the members and forms the `fire ↔ oto` trust without a separate step.
**Kept:** the `fire.ninja ↔ otogakure.ninja` cross-forest trust (the FGNW-CAMPAIGN.md
centrepiece — PtH, `sidhistory.ps1`, kerberoast, password spray), the Leaf child
domain, GHOSTS user-emulation on both surviving villages, Leaf + Sound decoy docs
(both now 100% authored, no placeholders), the ninjasploitable webshell, and the
attacker web/sinkhole infra.
**Dropped:** three of four mail-server VMs (`suna-mail`/`oto-mail`/`dark-mail`, −24 GB —
`konoha-mail` itself stays, see above), the Wind/Sand forest (wind-dc1,
suna-dc1/ws1/owa), the whole Akatsuki domain, and Leaf workstations 2–5.
**Mail:** `konoha-mail` runs **real Exchange 2019** — the default mail mechanism for the small
range: 70 Leaf mailboxes, distribution groups mail-enabled, cross-forest send connectors, a real
OWA login page, and the character-quote/LOE 2 alert corpus delivered via SMTP.
`FGNW-exchange.yml` and `FGNW-exchange-seed-mail.yml` run against `konoha-mail` **by default in
Phase 4b** (see DEPLOY.md).
There is **no `network:` section** — same as the full range. Both inherit Ludus's
default inter-VLAN policy (VLANs within a range route to each other), which is what
lets VLAN 10 reach VLAN 30 for the cross-forest trust and cross-village DNS. Ludus
auto-provisions the per-range router and only the VLANs these VMs declare
(10/30/90/99). Nothing extra to configure. Cross-village **DNS** (conditional
forwarders) is still the post-deploy `dnsforwarder.yml` step, not Ludus networking.
As `range-admin`:

```bash
ansible-playbook deploy.yml -e range_variant=small
```

That renders the small variant out of `range-config.yml` into your own `users/` tree, sets it, and
deploys. The tracked config is never edited, so there is nothing to "switch back" — a plain
`ansible-playbook deploy.yml` gives you the regular 22-VM range again.
The full deploy sequence, resume knobs, and the Phase-1 `rangeState=ERROR` retry behavior live in
**DEPLOY.md**, which is canonical.
AD promotion, the Konoha child domain, member joins and the `fire ↔ oto` forest trust are **native**:
they run during `ludus range deploy` (Phase 1), not as a separate step — see the native `domain:`
and `roles:` blocks in [`range-config.yml`](../../range-config.yml).
Phase 3 is only the attack-primitive + owned-content tail, run against the already-native AD against
the two trimmed inventories (`ad/NARUTO/data/inventory-small` +
`ad/NARUTO/providers/ludus/inventory-small.yml`): `tgtdelegation.yml → ad-data.yml` (the
`fgnw_ad_mgmt` directory content) `→ lat.yml → reboot.yml`, plus `adcs.yml`. The
tracked `ad/NARUTO/data/config.json` is never modified — the phase copies the variant's AD data model
(small: `config-small.json`) into the run's own temp dir and repoints the chain with `-e data_path=`.
`deploy-tasks/phase3-ad.yml` drives this; see [`DEPLOY.md`](DEPLOY.md)'s Phase 3 for the exact
small-range command sequence.
Run with the small providers inventory
(`-i ../ad/NARUTO/providers/ludus/inventory-small.yml`; `dnsforwarder.yml` also needs
`-i ../ad/NARUTO/data/inventory-small`):

- `FGNW-attacker-web.yml` — attacker nginx + tool list.
- `FGNW-ninjasploitable-content.yml` — themes ninjasploitable as the Leaf mission-report intake
  (`/reports/intake.php`); Leaf personas browse it and the LOE 3 campaign uses it as a webshell primitive.
- `dnsforwarder.yml` — cross-village conditional forwarders (fire/konoha/oto only). Also registers the
  friendly `mail.<forest-domain>` OWA DNS name for each forest that has an `-owa` server (UNTESTED).
- `FGNW-persona-autologon.yml` — run before `FGNW-decoy-content.yml`
  below if you want Naruto's personal-workstation decoy files (see next bullet) to land in his
  *real* Windows profile rather than one Windows creates fresh on his actual first logon. Same
  ordering note as `DEPLOY.md`'s Phase 3.
- `FGNW-ghosts-activity.yml` — GHOSTS timelines for konoha-ws1 + oto-ws1.
- `FGNW-decoy-content.yml` — plants **Leaf** (konoha-dc1), **Sound** (oto-dc1), and
  **Naruto's own personal workstation** (konoha-ws1 — duplicate downloads, a cleartext
  passwords file, notepad reminders; a *different* mechanism from the Leaf/Sound shared-drive
  plays, see that playbook's own comments) decoy content. Sand/Akatsuki targets aren't in this
  range, so those two village-drive plays don't apply — the FGNW-workstation play does, since
  `konoha-ws1` is in this range's roster.
**Exchange runs by default in Phase 4b:** `FGNW-exchange.yml` (install + mailboxes + group
mail-enable + cross-forest send connectors) and `FGNW-exchange-seed-mail.yml` (real SMTP delivery
of the quote corpus) both run against `konoha-mail` as a default part of the small-range deploy — see
the Mail status note above and DEPLOY.md. `FGNW-exchange-seed-mail.yml`'s send is **not
idempotent**, but it now skips any forest that carries the end-of-seed marker
(`C:\ProgramData\FGNW\seed-mail.done`) written by a previous successful seed — so a resume does
not duplicate messages. Pass `-e force_reseed=true` to deliver the corpus again anyway.
**Skip** (their targets aren't deployed): `FGNW-browser-defaults.yml` OWA bits, and anything
Wind/Sand/Akatsuki-specific.
- Changing the small VM set means editing `ludus_extensions.variants.include.small` in
  `range-config.yml`, and keeping `data/inventory-small`,
  `providers/ludus/inventory-small.yml` and `config-small.json` in step with it. A name in
  `include.small` that is not a real VM in the config fails the deploy in preflight rather than
  silently dropping a host.
- Sizes are the other half: a VM that needs to be bigger (or smaller) only in the small range gets
  an entry in `ludus_extensions.variants.overrides.small`, not a second copy of the VM.
