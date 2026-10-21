Directory realizer for the FGNW AD-build layer. Self-loads the AD contract bundled in
`files/config.json` and, keyed by the `domain` role_var, realizes
`domains[domain].{organisation_units, groups, users}` on that domain's DC: it creates the
OUs, the groups (per scope), the users (with their group memberships) and the declared
nested-group memberships, then ensures the built-in Administrator is a Domain Admin. It runs
at the Ludus `user-defined-roles` stage (S2), once per DC. Rule 8 (one task, one action)
throughout — an absent contract section is an empty dict whose loop simply does nothing, so
no action task carries a `when:`.
The campaign orchestration that used to load `config.json` into a `lab` fact and pass
`ad_users` / `ad_ou` / `ad_groups` per DC does not exist at the `user-defined-roles` stage, so
this role loads the contract itself and derives this DC's directory data from `domain` alone.
`main.yml` is the only entry point; the files below are internal includes it runs **in this
order** (load-bearing: a group can be a member of another group, and a user can be placed in a
group, only once those objects exist). They consume the `ad_users` / `ad_ou` / `ad_groups`
facts `main.yml` derives, so they are not independently invocable.

| include | what it does |
| --- | --- |
| `ous.yml` | create every organisational unit the contract declares |
| `groups.yml` | create the groups, one task per scope (universal / global / domainlocal) |
| `users.yml` | preflight-validate then create the users (with their `groups.add`) |
| `memberships.yml` | add each group's declared members (the contract's members are nested groups) |
| name | default purpose |

| --- | --- | --- |
| `domain` | — (**required**) | FQDN selecting `domains[domain]` from the contract (e.g. `konohagakure.fire.ninja`). No default; injected per DC via `role_vars`. |
| `ad_contract_file` | `config.json` | Filename, under the role's `files/`, of the AD contract to load. Override only to point at an alternative bundled contract. |
`ad_users`, `ad_ou` and `ad_groups` are **not** inputs — `main.yml` sets them from the loaded
contract, so they are excluded from `meta/argument_specs.yml`.
This role builds a **deliberately populated and attackable** directory; it hardens nothing.

- **Known-plaintext credentials, baked in.** Every user is created from the passwords carried
  in cleartext in `files/config.json`, giving a large set of accounts with fixed, discoverable
  passwords — ready-made targets for password spraying and credential reuse across the forest.
- **Passwords never rotate.** Users are created `password_never_expires: true` with
  `update_password: on_create`, so a captured password stays valid for the life of the range.
- **Privileged and nested group paths.** Contract groups nest inside one another (e.g.
  `Konoha Jonin` contains `Team 7`, `Team 8`, …) and some accounts are placed directly in
  privileged groups (e.g. `hiruzen.sarutobi` in `Domain Admins`), producing realistic
  nested-group privilege-escalation paths. The role additionally ensures the built-in
  `Administrator` is a Domain Admin.
- **Recon-rich objects.** Users carry descriptive `description` / `city` attributes (and some
  are left `enabled: false` as "missing-nin"), populating the directory with the kind of
  enumerable metadata an attacker reads with a single LDAP query.
It does not touch host controls such as the firewall — those are separate host `vulns` in the
contract, applied elsewhere, not by this role.
