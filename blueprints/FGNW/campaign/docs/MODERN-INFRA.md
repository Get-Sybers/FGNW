# Modern infrastructure (LOE 5, `xl` variant)

The `xl` range variant adds one VM, `modern-infra`, and a set of modern
enterprise artifacts the three Windows forests and the attacker net do not carry
on their own: a container host, a cloud-API emulator, a real EHR, a
forced-install browser-extension layer, and admin-activity telemetry for the
Domain-Admin personas. `modern-infra` is listed in
`ludus_extensions.variants.include.xl_extra`, so the `small` and `regular`
deploys leave it out; deploy it with `ansible-playbook deploy.yml
-e range_variant=xl` (see [`RANGE-CONFIG-VARIANTS.md`](RANGE-CONFIG-VARIANTS.md)).

## The `modern-infra` VM

Debian 12 on VLAN 99 (`ip_last_octet: 52`, beside `attacker`/`kali`/`ghost9`),
8 GB RAM / 4 vCPU. `FGNW-modern-infra.yml` installs Docker (`geerlingguy.docker`)
and applies the `fgnw_modern_infra` role, which templates the Compose file under
`fgnw_modern_infra_root` (`/opt/modern-infra`), brings the stack up, and seeds
it. The VM is contained like every other range VM (Phase 2), so its services are
reachable only inside the range.

## The container stack (`content/modern-infra/docker-compose.yml`)

| Service | Image | Themed as | Purpose |
| --- | --- | --- | --- |
| `registry` | `registry:2` | Konoha tools registry | a local container registry to enumerate and pull from (port 5000) |
| `vulnerable-app` | `vulnerables/web-dvwa` | Konoha internal tools portal | a deliberately vulnerable web app for container-security practice (port 8081) |
| `localstack` | `localstack/localstack` | Konoha cloud backup | an AWS-API emulator (`SERVICES=s3,iam,sts,cloudtrail`) answering real `aws` CLI/SDK calls (port 4566) |
| `openemr` + `openemr-mysql` | `openemr/openemr:7.0.2`, `mariadb:10.11` | Konoha Regional Medical Center | a real EHR with a MariaDB backend (port 8443) |

The LocalStack bucket ("Konoha cloud backup") is seeded with an S3 bucket and an
over-broad IAM user, and doubles as the exfil destination for the risky browser
extension below — a realistic cloud-storage-abuse path (T1567.002). OpenEMR is
pinned to `7.0.2` and seeded with synthetic patient records derived from
`content/AD/characters.csv`; the research behind the EHR choice is in
[`research/HEALTH-DATABASE-RESEARCH.md`](research/HEALTH-DATABASE-RESEARCH.md).

## Browser extensions (`fgnw_browser_extensions`)

Applied to the GHOSTS workstations via Edge's `ExtensionInstallForcelist` policy:

- two benign extensions for baseline realism (uBlock Origin, Grammarly), the way
  a real enterprise manages browsers;
- one **risky** extension, "Konoha Form Helper", sideloaded from an `update.xml`
  hosted on the `attacker` VM (`fgnw_browser_extensions_attacker_ip`), with broad
  host permissions — the initial-access/persistence vector whose payload PUTs
  page-visit data to the LocalStack S3 bucket above.

## Admin activity

`content/ghosts/persona-overrides.yml` carries an `admin_activity` block for the
Domain-Admin-tier personas (Naruto, Tsunade), layered on their GHOSTS timeline:
real privileged commands (`Get-ADUser`/`Get-ADGroupMember`, `gpupdate /force`,
RDP and PowerShell remoting) executed on the interactive session and logged by
the Sysmon/ACSC event-logging on every Windows VM — a privileged-activity
baseline distinct from the BAU browsing/email noise.
