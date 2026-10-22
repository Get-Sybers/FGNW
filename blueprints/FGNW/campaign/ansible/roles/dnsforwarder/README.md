# dnsforwarder

Cross-village name resolution for the range's domain controllers. On every DC the role
publishes a DNS conditional forwarder for each other AD domain of the range, pointing at that
domain's DC, and registers the forest's `mail` A record when the forest's mail server is up. The
outcome is that a host in one village resolves the names, and the mail server, of every other
village.

## What it does

1. Keeps only the entries of `dnsforwarder_domains` whose `dc_host` is a host of the current
   inventory, and prints which domains are skipped for lack of a DC in this run.
2. `ansible.windows.win_dns_zone` creates a `forwarder` zone for each remaining domain other
   than the DC's own (`ansible_facts['domain']`), forwarding to `hostvars[dc_host]['ansible_host']`.
3. Looks the DC's own domain up in `dnsforwarder_mail_owa_vlan_octet`. When the domain has an
   entry, the role composes the mail server's address as `10.<range>.<octet>.20`, where
   `<range>` is the second octet of the DC's own `ansible_host`, and probes TCP 5986 on it for
   three seconds.
4. When the probe answers, `ansible.windows.win_dns_record` registers `mail.<domain>` as an A
   record for that address in the DC's own zone. A domain without an entry in the map, or a mail
   host that does not answer on 5986, gets no record from this role.

The `dnsforwarder_domains` default lists the six domains of the regular range; the small range
(three DCs) gets only the forwarders whose DC its inventory carries.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `dnsforwarder_domains` | no | the six range domains with their DCs (`defaults/main.yml`) | List of `{name, dc_host}`: a DNS domain and the inventory hostname of its domain controller. |
| `dnsforwarder_mail_owa_vlan_octet` | no | `konohagakure.fire.ninja: 10`, `sunagakure.wind.ninja: 20`, `otogakure.ninja: 30`, `akatsuki.dark: 87` | Map of a DNS domain to the third octet of the VLAN its mail server (host `.20`) lives in. |

Both inputs have defaults, so [`dnsforwarder.yml`](../../dnsforwarder.yml) passes nothing;
`meta/argument_specs.yml` types and describes them.

The role also reads, without declaring them as inputs, `ansible_facts['domain']` (the play
gathers facts) and the `ansible_host` of the DC and of every `dc_host`. Those have to be IPv4
addresses: the mail address is derived from the DC's second octet and the forwarder address is
the other DC's `ansible_host` itself.

## Privilege and platforms

- Runs as the WinRM connection user on each domain controller, without `become`; that user
  administers the DNS server (a local administrator on the DC).
- Windows Server domain controllers running the DNS Server role.

## Idempotence

Yes. `win_dns_zone` and `win_dns_record` change only what differs; the inventory filtering is a
`set_fact` and the probe carries `changed_when: false`, so a second run reports no change.

## Failure and rollback

A forwarder zone that cannot be created fails the host. The mail-record steps never fail the
play: the probe and the record registration both carry `failed_when: false`, so a mail server
that is down or a registration error leaves the record absent and the run continues. Nothing is
rolled back; zones already created stay in place.

## Example invocation

[`dnsforwarder.yml`](../../dnsforwarder.yml), which `deploy-tasks/phase4-content.yml` runs with
both the AD-build inventory and the provider inventory (the `dc` group comes from the first, the
`ansible_host` addresses from the second):

```yaml
- name: Set up cross-village DNS conditional forwarders between all domains
  hosts: dc
  roles:
    - dnsforwarder
```
