The full `FGNW` range is 22 VMs / ~104 GB (xl is 23 / ~112 GB) — too large to
stand up just to check that a subsystem works. These are **small, single-purpose sub-range
configs** that each deploy only the VMs needed to exercise one thing, so you can validate the range
piece-by-piece on a modest RAM budget.

- **Run one at a time.** A Ludus user has a single range, so deploy → verify → `ludus range rm` → next.
- **Deploy as `range-admin`** (admin; the custom roles are installed there):
  `export LUDUS_API_KEY='<RA key>'; ludus range config set -f tests/<file>.yml; ludus range deploy`
  then poll `ludus range list`.
- **VLANs / IPs match the real range** so the `FGNW-*.yml` playbooks and the
  `providers/ludus/inventory.yml` IPs line up unchanged (`10.<octet>.<vlan>.<last>`).
- Ludus also builds the per-range router, so each test is (VMs listed + 1 router).

| Test | VMs | RAM | Verifies |
| --- | --- | --- | --- |
| **test5-rain-village** | rain-oracle | ~2 GB | The **Oracle Linux 9** template on the Hidden Rain / Amegakure VLAN (40): `rain-oracle` is a `[linux_infra]` village server that answers SSH and reports Oracle Linux 9. |
| **test5-sand-oracle** | suna-oracle | ~2 GB | The **Sand `suna-oracle`** host (Oracle Linux 9, VLAN 20 `.21`, `[linux_infra]`) on the cloud-init-fixed template — specifically that it lands on its **static IP** rather than falling back to DHCP. |

- **test5-rain-village** — `rain-oracle` answers SSH and `cat /etc/oracle-release` reports Oracle
  Linux 9.x.
- **test5-sand-oracle** — `ssh localuser@10.<o>.20.21` succeeds, which is itself the assertion: the
  regression this catches is the host coming up on a DHCP address instead of `.21`.
  `cat /etc/oracle-release` reports Oracle Linux 9.x.
