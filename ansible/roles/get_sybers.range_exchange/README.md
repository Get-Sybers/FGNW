Installs and configures **real Exchange Server 2019** on an FGNW `-mail` VM. It derives the
host's forest identity from its VM name, joins the machine to the **forest root** (Exchange
Setup's schema/AD prep must run from the schema master's own domain, not the child domain the
VM is natively joined to), installs Exchange, registers the org's Accepted Domain, mail-enables
the forest's AD groups, and builds the cross-forest send-connector mesh. It runs on each
`-mail` VM at the Ludus `user-defined-roles` stage (S2), **last** in the role order — AD, DNS
and the native child-domain join must already be up. Host identity is derived from
`inventory_hostname`, so no `role_vars` are required.
The actual Exchange install is delegated to the **third-party role
`aleemladha.ludus_exchange`** (installed from its GitHub repository by the blueprint's
`requirements.yml`), `include_role`'d from `install.yml`. It is deliberately **not** a
`meta/main.yml` dependency: a meta dependency would run it *before* this role's forest-root
join, which would break Setup. It is instead invoked at the right point in the sequence and
only needs to be installed alongside this role. The baked ISO/prereqs marker in the
`win2022-exchange2019` template makes its `not exchange_installed.exists` gate self-skip the
download and prerequisite installs, so the deploy-time work is Setup only. **This role does not
modify `aleemladha.ludus_exchange`.**
`main.yml` is the only entry point; it derives the host's forest facts (the `_rex_*`
`set_fact`s) and then runs the includes below **in order**. Because they consume those derived
facts, they are not independently invocable.

| include | what it does |
| --- | --- |
| `join.yml` | leave the child domain, free the stale forest-wide SPN, join the forest root |
| `install.yml` | install Exchange via `aleemladha.ludus_exchange`, then register the org's Authoritative Accepted Domain |
| `org-config.yml` | mail-enable every AD group as a distribution group, then build the cross-forest send-connector mesh |
| name | default purpose |

| --- | --- | --- |
| `range_exchange_admin_password` | `password` | Shared lab domain-admin (forest-root Administrator) password. |
| `range_exchange_domainjoin_map` | see `defaults/main.yml` | Forest-ROOT join target (domain + DC IP) per `-mail` host. |
| `range_exchange_child_domain_map` | see `defaults/main.yml` | The child domain each host is natively joined to (drives the leave→root switch). |
| `range_exchange_org_map` | see `defaults/main.yml` | Per-forest org label + primary SMTP (mail) domain. |
| `range_exchange_forest_root_map` | see `defaults/main.yml` | Forest root each host joins and authenticates against. |
| `range_exchange_orgs` | see `defaults/main.yml` | Cross-forest send-connector mesh: each org's SMTP domain + mail-server IP. |
| `range_exchange_iso_url` | Exchange 2019 CU15 ISO URL | Passed to `aleemladha.ludus_exchange`; self-skipped when baked prereqs are present. |
| `range_exchange_nexus_dotnet` | Nexus `ndp48…` URL | .NET 4.8 prereq URL (self-skipped when baked). |
| `range_exchange_nexus_vcredist` | Nexus `vcredist2013_x64` URL | VC++ 2013 prereq URL (self-skipped when baked). |
| `range_exchange_nexus_rewrite` | Nexus `rewrite_amd64` URL | IIS URL Rewrite prereq URL (self-skipped when baked). |
| `range_exchange_nexus_ucma` | Nexus `UcmaRuntimeSetup` URL | UCMA 4.0 runtime prereq URL (self-skipped when baked). |
The maps are keyed by the `-mail` suffix derived from the VM name; the `_rex_*` variables are
`set_fact` intermediates, not inputs, and are excluded from `meta/argument_specs.yml`.
Standing up Exchange is itself the point: it adds a large, historically vulnerable service to
the range and wires it for cross-forest mail. It hardens nothing.

- **A full Exchange 2019 attack surface** — OWA, ECP, Autodiscover, EWS and Exchange remote
  PowerShell — on every `-mail` VM. Exchange is a perennial source of RCE/priv-esc primitives,
  which is exactly why it is here.
- **A shared, weak, known domain-admin credential** (`password`) is used as the forest-root
  Administrator for the join, Setup and every configuration step, across all four forests.
- **An open cross-forest send-connector mesh.** Every org gets a send connector to every other
  org's SMTP domain, plus an Authoritative Accepted Domain, so mail (including spoofed mail)
  flows freely between forests — a ready lateral/phishing path.
- **Every AD group mail-enabled** as a distribution group, turning the whole directory's group
  structure into enumerable mail recipients.
Deliberately **not** done: no Exchange hardening, no split-permission model, no connector
authentication restrictions.
