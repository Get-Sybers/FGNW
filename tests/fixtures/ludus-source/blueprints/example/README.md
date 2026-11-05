# LudusPlusPlus example

One Debian 13 VM cloned from this source's `ludusplusplus-debian-13-x64-server-template`.
It exists to prove the source installs and deploys end to end; copy it to start a real lab.

## Quick start

```bash
ludus source add https://github.com/Get-Sybers/LudusPlusPlus --templates ludusplusplus-debian-13-x64-server-template --blueprints example
ludus templates build -n ludusplusplus-debian-13-x64-server-template
ludus blueprint apply <sourceID>/example
ludus range deploy
```

`<sourceID>` is printed by `ludus source list` (derived as `<userID>-Get-Sybers-LudusPlusPlus` unless you pass `--id`).

## VM details

| VM name | Hostname | Template | IP | Role |
|---|---|---|---|---|
| `{{ range_id }}-lpp-debian13` | lpp-debian13 | ludusplusplus-debian-13-x64-server-template | 10.X.10.10 | base Debian host |

Replace `X` with your range's second octet (`ludus range list`).

## Credentials

| Account | Username | Password | Scope |
|---|---|---|---|
| OS user (sudo) | debian | debian | Ludus default for Debian templates |
