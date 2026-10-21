# ADCS / ESC1 on the Sand forest

The range runs an Active Directory Certificate Services Enterprise CA on
`suna-dc1` (the Sand child DC, VLAN 20, `.10`), so there is no dedicated ADCS
member server and no extra VM — `range-config.yml` and the four-file AD lockstep
carry no ADCS host of their own. The CA publishes a deliberately vulnerable
**ESC1** template, giving the range a real certificate-based
privilege-escalation path for training and detection. That weakness is range
content by design, reviewed under the range rubric, not a defect.

## What ships

- `ansible/roles/adcs` — the clean-room role: installs `AD-Certificate` +
  `ADCS-Cert-Authority`, then
  `Install-AdcsCertificationAuthority -CAType EnterpriseRootCA`, and enables
  Web-Enrollment when `adcs_ca_web_enrollment` is true (the default).
- `ansible/adcs.yml` — the play. It runs the `adcs` role against the `[adcs]`
  group with forest-root Enterprise-Admin credentials, validates `CertSvc` and
  `certutil -ping`, then creates and publishes the ESC1 template.
- `ad/NARUTO/data/inventory` puts the Sand child DC in `[adcs]` as `dc04`
  (`suna-dc1`'s `dict_key`). `inventory-small`'s `[adcs]` group is empty, so
  `adcs.yml` is a no-op on the small range.
- `deploy-tasks/phase3-ad.yml` runs `adcs.yml` after the Phase-3 content tail,
  once the forest exists. Phase 3 runs inside the contained range (containment
  is Phase 2), so anything the step needs from outside is already cached in
  Nexus or allow-listed.

## Forest-root credentials

Enterprise CA registration writes the forest Configuration partition, so the
credential is a `wind.ninja` (forest-root) Enterprise/Schema Admin, not the
child-domain admin — the same constraint as Exchange schema prep. `adcs.yml`
sources it from `config.json`'s `wind.ninja` domain admin
(`adcs_forest_root_domain: wind.ninja`), never hardcoded, and the CA common name
is `Sunagakure Root CA`.

## The ESC1 template

`adcs.yml` creates and publishes `SunaVulnUser` after the CA is up:

- duplicated from the `User` template;
- `msPKI-Certificate-Name-Flag` includes **`ENROLLEE_SUPPLIES_SUBJECT`** (the
  enrollee names an arbitrary SAN, e.g. a Domain Admin);
- a **Client Authentication** EKU, so the certificate is usable for auth;
- **Enroll** granted to low-privileged users;
- published to the CA with `certutil -setcatemplates` / `Add-CATemplate`.

Publishing is best-effort: if it does not land (it needs a minted enterprise
OID), the play warns and continues — the CA stays healthy and only the optional
ESC1 path is affected.

## Detection and verification

The ESC1 path yields template-modification and enrollment events (4886/4887)
and an abnormal SAN in the issued certificate — blue-team content alongside the
range's Kerberoast/AS-REP primitives. To confirm the CA and template:

- CA reachable: `certutil -ping`, or the CA appears in `pkiview`.
- Template enrollable: from a low-privileged Sand user, request `SunaVulnUser`
  with an alternate SAN.
- `certipy find` flags `SunaVulnUser` as ESC1 where certipy is in the range
  tooling.
