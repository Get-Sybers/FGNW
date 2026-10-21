Ludus template for **Metasploitable3**, Ubuntu 14.04 flavor (`metasploitable3-ub1404`).
This template uses the same Packer `null` source + `scripts/import.sh` pattern as
`../metasploitable-2` (import a pre-built disk via the Proxmox API). See
`../metasploitable-2/README.md` for the full step-by-step.
Rapid7 builds Metasploitable3 itself with Vagrant + Packer + Chef
(github.com/rapid7/metasploitable3), which needs its own hypervisor (VirtualBox
or VMware) for Vagrant to drive. Re-running that whole pipeline nested inside
this Proxmox host isn't practical here (no nested VirtualBox set up on this
node). Instead this template takes Rapid7's own **published output** of that
pipeline - the `rapid7/metasploitable3-ub1404` box on Vagrant Cloud - and imports
it the same way `metasploitable-2` imports its vmdk. It's
still "the real Metasploitable3," just consuming Rapid7's build artifact instead
of re-deriving it.
`scripts/import.sh` treats the `.box` file as a gzipped tar (Vagrant's format) and
pulls the `.vmdk` out of it before uploading to Proxmox - same as unzipping
metasploitable-2's zip, just a different archive type
(`source_archive_type = "vagrant-box"`).
Rapid7 also publishes a Windows Server 2008 flavor under the same Vagrant Cloud
account (`rapid7/metasploitable3-win2k8`). It isn't built here - the network/
credential/provisioning assumptions in `scripts/import.sh` and
`ansible/provision.yml` (Linux SSH, apt, `/etc/ssh`) don't carry over to a
Windows guest. If you need the Windows flavor, it would need its own template
following this same import pattern but with WinRM-based provisioning instead
(more like how the `win*` templates in `templates/` are provisioned).

```bash
ludus templates add -d templates/metasploitable-3
ludus templates build -n metasploitable-3-ub1404-x64-server-template
```

(The registered template name is `metasploitable-3-ub1404-x64-server-template` -
the `vm_name` variable's default - not the directory name `metasploitable-3`;
same for `build`/`rm`/`status` and anywhere else you reference it by name.)
`vagrant` / `vagrant`.

- The default `source_url` pins Rapid7's `0.1.12-weekly` box version (the
  `current_version` on Vagrant Cloud as of this writing - confirmed live via
  `https://app.vagrantup.com/api/v1/box/rapid7/metasploitable3-ub1404`). Rapid7
  publishes **no checksum** for this box (`checksum_type: "none"` in their own
  metadata), so there's nothing to pin/verify beyond trusting the source - if
  that matters for your use case, download and inspect it yourself first and
  point `source_url` at it - but see the next caveat for how to actually set that.
- `ludus templates build` has **no flag to pass extra `-var`s**, and Packer's
  `*.auto.pkrvars.hcl` auto-loading only applies in directory-mode invocation, not
  when packer is pointed at a specific `.pkr.hcl` file (confirmed live) - which is
  how the Ludus server always invokes it. To override `source_url` (e.g. to a
  local `file:///...` path, or a newer box version), edit the `default` directly
  in `metasploitable-3.pkr.hcl` before `ludus templates add` - see
  `../metasploitable-2/README.md` for a worked example.
- The shared engine (`scripts/import.sh`, `ansible/provision.yml`) is
  **verified end-to-end** against Metasploitable2 - see
  `../metasploitable-2/README.md`'s Caveats section for the 5 real bugs that
  surfaced testing it there (all fixed, same script here). This template's own
  vagrant-box extraction path and Ubuntu 14.04-specific behavior are untested -
  watch the first real build closely via `ludus templates logs`. The box is
  larger than metasploitable-2's zip, so expect the download/upload/import steps
  to take longer.
- Everything else in `../metasploitable-2/README.md`'s Caveats section applies
  here too (agent=0, import-from being PVE 8.1+ only, etc).
