# OWA: real Exchange, not simulated

Outlook Web App on this range is a full **Exchange Server 2019** install: real
mail behind it — a mail store, mailboxes, and transport. Every task the
real-Exchange plays run is prefixed `real-exchange |`.

The Leaf forest's mail VM — `konoha-mail` — runs real Exchange 2019 and is a
member of the `exchange_servers` group (defined in `inventory-infra.yml`, not
`inventory.yml` — a frequent gotcha when running the plays by hand). The Sand
forest's `suna-mail` is a macOS host running Postfix/Dovecot (Phase 4d), not
Exchange; the Sound and Akatsuki forests have no mail server.

Real Exchange is used rather than a static OWA skin because the campaign depends
on genuine mail behaviour: real SMTP bounce semantics — a message to an
unprovisioned address returns a genuine NDR, which an Akatsuki throwaway-sender
beat relies on and which only a real transport produces.

- `campaign/ansible/FGNW-exchange.yml` — domain-join, Exchange install,
  mail-enable groups
- `campaign/ansible/FGNW-exchange-seed-mail.yml` — mailbox content (the
  character-quote corpus + LOE 2 alerts)
- `campaign/ansible/FGNW-owa-cert.yml` — the `mail.<domain>` certificate and
  workstation trust
- `campaign/deploy-tasks/phase4b-exchange.yml` — the phase that sequences them
