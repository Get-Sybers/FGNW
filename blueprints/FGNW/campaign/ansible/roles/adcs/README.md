# adcs

Active Directory Certificate Services for a Windows host of the range. The role installs the
ADCS features, configures the host as an **Enterprise Root CA** under the forest-root credential
the play supplies, enables certificate web enrollment and refreshes group policy. The outcome is
a working enterprise CA the forest trusts; the play [`adcs.yml`](../../adcs.yml) then publishes
its ESC1 template on it.

## What it does

1. `ansible.windows.win_feature` installs `AD-Certificate`, `ADCS-Cert-Authority` and
   `ADCS-Web-Enrollment` with their management tools; `ansible.windows.win_reboot` reboots the
   host only when the feature install asks for it.
2. `ansible.windows.win_powershell` runs `Install-AdcsCertificationAuthority -CAType
   EnterpriseRootCA` with the common name `ca_common_name`: RSA 2048 on the Microsoft Software
   Key Storage Provider, SHA-256, five years of validity, authenticated with
   `adcs_domain_username` / `adcs_domain_password`. A CA that is already installed is reported
   as unchanged.
3. When `adcs_ca_web_enrollment` is true, `Install-AdcsWebEnrollment` enables the web-enrollment
   endpoint, with the same already-installed handling.
4. `gpupdate /force` refreshes group policy so the host picks up the new CA; the step is always
   reported as unchanged.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ca_common_name` | yes | none | Common name of the Enterprise Root CA (the caller passes `Sunagakure Root CA`). |
| `adcs_domain_username` | yes | none | Account that configures the CA, in `DOMAIN\user` form; an Enterprise Admin of the forest root, because an Enterprise CA writes the forest's Configuration partition. |
| `adcs_domain_password` | yes | none | Password of that account. Secret: the play supplies it; the role never defaults it (`no_log` in the spec). |
| `adcs_ca_web_enrollment` | no | `true` | Enable the certificate web-enrollment endpoint after the CA is configured. |

`meta/argument_specs.yml` carries the same four inputs. The three without a default are
required, so the role fails at include time when one is missing; `defaults/main.yml` lists them
commented out and the play passes them.

## Privilege and platforms

- Runs as the WinRM connection user, without `become`; that user is a local administrator, which
  the feature install and the reboot need. The CA configuration step authenticates separately
  with `adcs_domain_username` / `adcs_domain_password` through `-Credential`.
- Windows Server in a forest that is already built. In this repository the `[adcs]` group of the
  AD-build inventory names `dc04` (the Sand child DC, `suna-dc1`); `inventory-small` leaves the
  group empty, so the small range never runs the role.

## Idempotence

Yes. The feature install is idempotent by module; both ADCS configuration steps treat an
"already installed" exception as unchanged and raise anything else; the reboot happens only when
the feature install requires one. The closing `gpupdate /force` runs on every pass and is always
reported as unchanged.

## Failure and rollback

A failing step stops the role on that host: a feature that cannot be installed, a reboot that
does not come back, or a CA configuration error other than "already installed"
(`error_action: stop`). Nothing is rolled back: installed features stay installed and a
half-configured CA stays as the failing step left it; a re-run resumes from the last successful
step.

## Example invocation

From [`adcs.yml`](../../adcs.yml), which targets the `[adcs]` group of the AD-build inventory
and loads the domain data model as `lab`:

```yaml
- name: Install ADCS on Sand CA host(s)
  hosts: adcs
  gather_facts: false
  vars_files:
    - "{{ data_path }}/config.json"
  vars:
    data_path: ../ad/NARUTO/data
    adcs_forest_root_domain: wind.ninja
    adcs_domain_username: "{{ adcs_forest_root_domain }}\\Administrator"
    adcs_domain_password: "{{ lab.domains[adcs_forest_root_domain].adcs_domain_password }}"
    ca_common_name: Sunagakure Root CA
    adcs_ca_web_enrollment: true
  tasks:
    - name: Install Enterprise Root CA role/services
      ansible.builtin.include_role:
        name: adcs
      vars:
        adcs_domain_username: "{{ adcs_domain_username }}"
        adcs_domain_password: "{{ adcs_domain_password }}"
      no_log: true
```
