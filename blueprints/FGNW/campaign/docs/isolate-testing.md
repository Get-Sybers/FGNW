The FGNW range runs **contained**: Ludus testing mode (`ludus testing start`, Phase `2` of
`deploy.yml`) seals every VM off from everything outside the range network. This document
covers the two consequences of that model that bite operators who run a collector outside
the range — a Velociraptor server, a SIEM, anything the VMs must still report to — and the
versioned allow-list that keeps the exception explicit. Mechanics are stated from the Ludus
playbooks that implement the mode (`testing.yml`, `tasks/firewall/firewall-management.yml`),
not from the CLI's help text.

## What `ludus testing start` does

- **Snapshots** every VM whose config has `testing.snapshot` true or unset (this blueprint sets
  `testing: {snapshot: true, block_internet: true}` on every VM), as `ludus_automated_clean_snapshot`,
  with RAM when `defaults.snapshot_with_RAM` is true.
- **Removes the router's default external rule** (`User Default: External Rule`, source
  `10.<N>.0.0/16` → destination `! 10.<N>.0.0/16`) from `LUDUS_USER_RULES`. The router's `FORWARD`
  policy is DROP, so from that moment every packet leaving the range network is dropped unless a
  rule in `LUDUS_TESTING` accepts it. Only VMs with `testing.block_internet: false` get a blanket
  accept there; this blueprint has none.
- **Blocks DNS** from the contained VMs on the router's resolver.
- Leaves inter-VLAN traffic, the WireGuard path and the Ludus host's NAT untouched.

`ludus testing allow -i <ip>` appends one rule to `LUDUS_TESTING` — source `10.<N>.0.0/16`,
destination `<ip>`, all protocols and ports, for every VM in the range. `-d <domain>` resolves
the domain on the Ludus host, adds the same rule for its address and pins the name in the
router's DNS. `ludus testing status` lists everything currently allowed.

## The allow does not persist

`ludus testing stop` flushes `LUDUS_TESTING` entirely and re-adds the default external rule;
`testing start` rebuilds the chain from the range config alone — it carries nothing over from
the previous testing session. So it is `testing start` → `testing allow` **every time** the range
is contained:

```bash
ludus testing start
ludus testing allow -i <velociraptor-ip>
ludus testing status
```

The clean way to keep that versioned is a file in the blueprint — one IP or domain per line,
starting at column 1 — and `ludus testing allow -f`:

```bash
ludus testing allow -f blueprints/FGNW/testing-allow.txt
```

`blueprints/FGNW/testing-allow.txt` is the operator's own and is **gitignored** (it names the
operator's collectors, which do not belong in the public tree); `testing-allow.txt.example`
beside it is the template to copy. Because the file is not in git, it is never present in the
copy `ludus source sync` keeps under `/opt/ludus/sources/`: keep it in your own checkout (or
anywhere else) and pass that path to `-f`. The CLI extracts entries with regexes anchored at
the start of a line, so lines that begin with anything else (`#` comments, blank lines) are
ignored.

If any campaign or role step that needs Nexus runs while testing is on, `192.0.2.2` belongs in
that file too, because Nexus sits outside `10.<N>.0.0/16` and is blocked the same way. When the
range is contained by `deploy.yml`, Phase `2` already allow-lists it (`phase2-containment.yml`
passes `ludus_testing_allow_ips: [192.0.2.2]` to `get_sybers.range.ludus_testing`); a range
contained by hand with `ludus testing start` has no such carve-out until the file is applied.

## Install the client before you isolate

`testing stop` reverts every VM to the snapshot taken at `testing start`. A Velociraptor client
installed during testing vanishes on stop; one installed at deploy time (a Ludus role in the
range config, applied at the `user-defined-roles` stage of Phase `1`) is inside the snapshot and
survives every stop/start cycle. The same holds for anything else the collector needs on the
guest — a CA certificate the client must trust, an agent configuration, a service account.

Order of operations for a collector outside the range, then:

1. Put the client in the range config as a role, so `ludus range deploy` installs it before
   Phase `2`.
2. `ludus testing start` (or `deploy.yml` from Phase `2`).
3. `ludus testing allow -f <your testing-allow.txt>` — the clients reconnect on their own once
   the rule is in.
4. `ludus testing status` to confirm the entry; from any VM, a request to the collector's
   port should now answer (for a Velociraptor frontend, `curl -skI https://<ip>:8000/` returns
   `HTTP/2 404` for `/`).
