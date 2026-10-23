# fgnw_modern_infra

Brings up and seeds the **modern-infra container stack** of the `xl` range variant (LOE 5,
[`docs/MODERN-INFRA.md`](../../../docs/MODERN-INFRA.md)) on the `modern-infra` Debian VM: a local
container registry, a deliberately vulnerable web app (DVWA), a LocalStack AWS-API emulator and a
real OpenEMR with its MariaDB backend, all themed as Konoha services. The outcome is the Compose
stack running under `fgnw_modern_infra_root`, the LocalStack bucket `konoha-cloud-backup` plus an
over-broad IAM user seeded, and OpenEMR populated with the synthetic patient roster.

It is called by [`FGNW-modern-infra.yml`](../../FGNW-modern-infra.yml), whose first play installs
Docker with `geerlingguy.docker`; `deploy-tasks/phase4-content.yml` runs that play only when the
variant enables `modern_infra` (`xl`). The role depends on that earlier role's output (Docker
Engine and the `docker compose` plugin) without declaring it in `meta/main.yml`, because
`geerlingguy.docker` is installed from `blueprints/FGNW/requirements.yml`, not shipped in this tree.

## What it does

1. Creates `fgnw_modern_infra_root` (root:root, `0755`).
2. Copies `content/modern-infra/docker-compose.yml` there (`0644`); a change notifies the
   `Recreate modern-infra stack` handler (`docker compose up -d --force-recreate` at the end of the play).
3. Copies `localstack-seed.sh` (`0755`), `patient-seed.csv` and `openemr-seed-patients.py` (`0644`).
4. Runs `docker compose up -d` in the root (compose pulls any image that is missing); the task reports
   `changed` when its standard output contains `Started` or `Created`.
5. Waits up to 30 x 10 s for `http://localhost:4566/_localstack/health` to answer 200 (errors ignored),
   then runs `bash localstack-seed.sh` only when it did: creates the S3 bucket and a manifest object,
   the `konoha-it-svc` IAM user with an `s3:*` policy, and its access keys (left in `/tmp` on purpose).
6. Waits up to 300 s for TCP 8443 (OpenEMR behind self-signed TLS; best effort), then runs
   `python3 openemr-seed-patients.py`, which registers an OAuth2 client against OpenEMR's REST API and
   creates a patient per row of `patient-seed.csv`.

The services, images and ports are listed in `docs/MODERN-INFRA.md`.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `fgnw_modern_infra_root` | no | `/opt/modern-infra` | Host directory holding the Compose file and seed scripts; working directory of every `docker compose` and seed command. |

`__compose_up`, `__localstack_health`, `__localstack_seed` and `__openemr_seed` are internal
registered results, not inputs.

## Privilege and platforms

- The role sets no `become` of its own; it needs root (writes under `/opt`, talks to the Docker
  socket) and gets it from the caller play's play-level `become: true`.
- Platform: Debian 12 (the Ludus Debian template, VLAN 99, contained like every other range VM).
- Prerequisites the role does not install: Docker Engine with the `docker compose` plugin
  (`geerlingguy.docker` in the same play), `bash`, `curl` and the `awslocal` CLI for the LocalStack
  seed, `python3` for the OpenEMR seed, and the container images reachable from the host when
  `docker compose up` runs.

## Idempotence

**No.** The file deployment converges and `docker compose up -d` reports a change only when a
container is created or started, but both seed steps run on every invocation and report `changed`
whenever their script exits 0; neither script checks for what an earlier run already created.

## Failure and rollback

A failing `docker compose up -d` (for example an image that cannot be pulled) fails the play. The
two readiness waits and the two seed steps are best effort (`ignore_errors` and `failed_when: false`):
a seed that fails leaves the stack running and the play green, with its exit code and output in the
registered `__localstack_seed` and `__openemr_seed` results. The LocalStack seed is skipped when the
health check never returned 200. Nothing is rolled back: the role never runs `docker compose down`,
and a half-seeded LocalStack or OpenEMR is left as its script left it.

## Example invocation

From `FGNW-modern-infra.yml` (the whole play file):

```yaml
- name: Install Docker on modern-infra
  hosts: modern-infra
  become: true
  roles:
    - geerlingguy.docker
- name: Bring up the modern-infra container stack + seed it
  hosts: modern-infra
  become: true
  tasks:
    - name: "Modern-infra: bring up and seed the container stack"
      ansible.builtin.include_role:
        name: fgnw_modern_infra
```
