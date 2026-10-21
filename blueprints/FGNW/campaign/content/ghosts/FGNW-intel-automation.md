---
Intel tip emails are automatically generated and distributed when the system
catches phishing attempts or enumeration activity. This closes the loop between
attack simulation and user awareness behaviour — characters receive real
context-aware warnings based on what was actually caught.

---
When a phishing email is caught by the mail filter, an intel briefing is
automatically generated and sent to all shinobi in the targeted village.
**Subject:** `THREAT INTEL: Phishing attempt intercepted — [Date]`
**Body auto-populates with:**

- Sender address used
- Subject line of the phishing email
- What it was pretending to be
- Who it was targeting
- Recommended action
**When Konan's phishing email is caught:**

> *Intercepted: An email posing as the Hokage office requested immediate
> identity verification. Sender domain was `hokage-office.gov.leaf.phish` —
> note the extra suffix. All Leaf jonin are reminded never to verify
> credentials via email. Origin traced to Hidden Rain Village.*
**When Deidara's attempt is caught:**
> *A suspicious email containing an attachment titled `explosion_art_preview.jpg`
> was intercepted before delivery. The attachment contained an unknown payload.
> Do not open unsolicited attachments from unknown senders — even if the subject
> line says ART IS AN EXPLOSION.*
**When Sasori's multi-hop attempt is caught:**
> *A highly sophisticated redirect chain was identified posing as the mission
> board portal. Three separate domains were chained before the final credential
> harvesting page. This indicates an advanced persistent threat actor. Jonin
> and above are advised to verify mission board URLs manually.*
**When Tobi's attempt is caught:**
> *An unusually cheerful email was intercepted claiming to be from the Hokage's
> office. The sender signed off as "a good boy." Origin traced to an unknown
> endpoint consistent with known Akatsuki obfuscation patterns. Do not engage.*
**When Itachi's attempt is caught:**
> *A highly targeted spear-phishing email was intercepted, addressed personally
> to an ANBU operative by name and rank. The email contained accurate internal
> information suggesting prior reconnaissance. ANBU command has been notified.
> All operatives should assume their identities are known to this actor.*

---
When enumeration is detected against a village portal, a threat intel bulletin
is automatically sent to all active duty shinobi and their jonin leaders.
**Subject:** `RECON ALERT: Directory enumeration detected — [Village] — [Date]`
**Body auto-populates with:**

- Source village or unknown origin
- Accounts or directories targeted
- Time and volume of attempts
- Threat level assessment
**When Zetsu's account runs enumeration:**

> *Our sensors detected systematic querying of the public shinobi directory
> between 02:00 and 04:00. Attempts came from an unregistered endpoint with
> no village attribution. 47 usernames were probed in sequence. This is
> consistent with known Akatsuki intelligence-gathering behaviour. All active
> operatives should assume their username is now known to hostile parties.*
**When Hidden Rock probes Hidden Leaf after a summit announcement:**
> *Following yesterday's Hokage press release, elevated traffic from Hidden
> Rock IP ranges was observed against our public mission board. 23 queries in
> 4 hours, focused on jonin-level personnel listings. This is consistent with
> historical Iwa grudge-monitoring behaviour. No breach occurred. Intel
> division is monitoring.*
**When Hidden Cloud enumerates Hidden Sand:**
> *Hidden Cloud village probed the Sand public directory for 12 minutes
> following the inter-village summit announcement. Queries focused on
> Kazekage guard detail personnel. Gaara's office has been notified. Sand
> shinobi are reminded to set their mission board profiles to restricted
> visibility.*
**When Akatsuki runs a spray attack:**
> *A low-and-slow password spray was detected across multiple village portals
> overnight. Attempts used common credential patterns including variations of
> village mottos and Hokage names. No accounts were successfully compromised.
> All shinobi are advised to update passwords immediately. Avoid predictable
> patterns such as WillOfFire1 or Believe1t.*
**When Black Zetsu enumerates separately from White Zetsu:**
> *Two simultaneous enumeration sessions were detected originating from the
> same endpoint but exhibiting entirely different behavioural patterns. One
> session was methodical and silent. The other was erratic and high volume.
> Both sessions targeted the same personnel directories. This is an
> unprecedented dual-pattern threat. Intel division is investigating.*

---
Each intel tip writes itself based on what was caught:

| Caught Detail | Auto-populates into tip |
| --- | --- |
| Sender domain | Warning about that specific spoofed domain |
| Target username | Personal alert sent directly to that user |
| Target role / rank | Tip scoped to that rank level only |
| Attack origin village | Diplomatic context added automatically |
| Time of attempt | Pattern noted — early morning, late night, etc |
| Volume of attempts | Spray vs targeted classification |
| Attachment type | Specific file type warning issued |
| Redirect chain detected | Advanced persistent threat flag raised |
| Credential pattern used | Password policy reminder triggered |
| Repeated origin | Escalation to Kage office triggered |

---

| Trigger | Recipients |
| --- | --- |
| Single phishing email caught | Targeted user + their team leader |
| Phishing campaign (3+ emails) | All shinobi in that village |
| Low-volume enumeration | Jonin and above only |
| High-volume enumeration | All active shinobi |
| Cross-village recon detected | Kage office + intelligence division |
| Akatsuki origin confirmed | Allied Shinobi Forces broadcast to all villages |
| Spear-phish targeting named operative | That operative + ANBU command only |
| Spray attack across multiple villages | All Kage + joint intel summit convened |

---
These behaviours are built into the emulation and fire automatically when
an intel tip is delivered to that character's account.

| Character | Behaviour |
| --- | --- |
| Naruto | Receives the alert, clicks the original phishing link anyway, triggers a second alert |
| Shikamaru | Reads it, cross-references with previous alerts, files an analysis report |
| Kakashi | Reads it three hours late, still identifies the pattern everyone missed |
| Sakura | Forwards it to her whole team with detailed annotations |
| Sai | Replies asking what emotions a phishing email is supposed to make you feel |
| Guy Sensei | Reply-alls with encouragement about youthful vigilance defeating all attacks |
| Ibiki | Already knew, already traced it, already filed a counter-intel report before the alert sent |
| Tsunade | Reads it, sends it to Shizune to action, goes back to gambling |
| Gaara | Reads it at 3am, has already dispatched a response team |
| Temari | Forwards it to Sand intel and files a cross-village diplomatic note |
| Killer B | Acknowledges the threat in rap verse — IT cannot parse the response |
| A (Raikage) | Replies in full caps, immediately calls an emergency session |
| Tobi | Somehow receives his own phishing alert and replies asking who sent it |
| Itachi | Does not reply — has already neutralised the threat silently |
| Konan | Receives an alert about her own phishing attempt, does not open it |
| Deidara | Replies complaining that his art was flagged as malicious |

---

```yaml
FROM: intel@konoha-portal.leaf
TO: all-jonin@konoha-portal.leaf
SUBJECT: THREAT INTEL: Phishing attempt intercepted — Day 47
A suspicious attachment was intercepted. Do not open files from
unknown senders.
---
FROM: might.guy@konoha-portal.leaf
TO: all-jonin@konoha-portal.leaf
SUBJECT: RE: THREAT INTEL: Phishing attempt intercepted — Day 47
THIS IS EXACTLY WHY WE MUST TRAIN OUR MINDS AS HARD AS OUR BODIES.
YOUTHFUL VIGILANCE IS THE GREATEST FIREWALL. I WILL BE SENDING MY
WEEKLY TIPS EARLIER THIS WEEK IN RESPONSE TO THIS THREAT.
---
FROM: kakashi.hatake@konoha-portal.leaf
TO: all-jonin@konoha-portal.leaf
SUBJECT: RE: RE: THREAT INTEL: Phishing attempt intercepted — Day 47
...
---
FROM: ibiki.morino@konoha-portal.leaf
TO: all-jonin@konoha-portal.leaf
SUBJECT: RE: RE: RE: THREAT INTEL: Phishing attempt intercepted — Day 47
Please take this thread offline. I already handled it at 04:00.
```

---

```yaml
FROM: intel@alliedshinnobiforces.org
TO: all-kage@fivekagehq.com
SUBJECT: URGENT BROADCAST: Coordinated spray attack detected — All villages
A low-and-slow credential spray was detected simultaneously across
Konoha, Suna, Kumo, Kiri and Iwa portals overnight. Attack pattern
is consistent with Akatsuki operational signatures. No villages were
breached. All shinobi should update credentials immediately.
---
FROM: a.raikage@kumo-portal.cloud
TO: all-kage@fivekagehq.com
SUBJECT: RE: URGENT BROADCAST
WHO DID THIS. I WILL FIND THEM PERSONALLY.
---
FROM: gaara@suna-portal.sand
TO: all-kage@fivekagehq.com
SUBJECT: RE: URGENT BROADCAST
Sand intel logged the same pattern at 02:17. We have already
updated all operative credentials and rotated guard assignments.
Awaiting joint response coordination.
---
FROM: mei.terumi@kiri-portal.mist
TO: all-kage@fivekagehq.com
SUBJECT: RE: URGENT BROADCAST
Mist concurs. Our hunter-nin division is tracing the origin.
We will share findings when available.
---
FROM: onoki@iwa-portal.rock
TO: all-kage@fivekagehq.com
SUBJECT: RE: URGENT BROADCAST
I have been dealing with threats like this since before most of
you were born. We rotated our credentials before the attack
completed. This is not our first war.
```

---

```yaml
FROM: intel@konoha-portal.leaf
TO: naruto.uzumaki@konoha-portal.leaf
SUBJECT: THREAT INTEL: Phishing attempt targeting your account — Day 51
A phishing email was intercepted before it reached your inbox.
You do not need to take any action. Do not click any links claiming
to be from the Hokage office today.
---
[SYSTEM LOG — 4 minutes later]
USER: naruto.uzumaki
ACTION: Clicked link in quarantined phishing email
SOURCE: Accessed quarantine folder manually to find the email
---
FROM: intel@konoha-portal.leaf
TO: naruto.uzumaki@konoha-portal.leaf
CC: kakashi.hatake@konoha-portal.leaf
SUBJECT: SECONDARY ALERT: Quarantine breach by internal user — Day 51
A quarantined phishing email was accessed and the link was
activated by the original target. Kakashi-sensei, please advise.
---
FROM: kakashi.hatake@konoha-portal.leaf
TO: naruto.uzumaki@konoha-portal.leaf
SUBJECT: RE: SECONDARY ALERT
Naruto.
```

---
*End of document.*
