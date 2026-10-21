Research into deployable health/EHR databases suitable for the FGNW cyber range.
All candidates must be free to use (or have a free trial).
Requirements covered per candidate:

- Download link and dependencies
- Required OS
- Integration interface (web / application)
- Associated CVEs (direct and derivative)
- NPC activity simulation through the interface
- Normal operational processes (access, new entries, backups)
- Adversary exploitation and exfiltration techniques
Source referenced: <https://libguides.csu.edu.au/Medicine/articles> (see §
the *Academic Health Databases — Contextual Note*
at the end of this document for commentary on those sources).

---

| | OpenEMR | OpenMRS | GNU Health |
| --- | --- | --- | --- |
| **Cost** | Free (AGPL) | Free (MPL 2.0) | Free (GPL 3) |
| **OS** | Linux / Windows / macOS | Linux preferred | Linux / BSD only |
| **Deployment** | Docker (5 min) | Docker (5 min) | Manual (1–2 hrs) |
| **Interface** | Web + REST API + Patient Portal | Web + REST + FHIR | Web (Tryton) + REST |
| **NPC tooling** | ✅ Official demo-data-generator + full REST API | ✅ REST/FHIR scriptable | ⚠️ Possible but manual |
| **CVE richness (red-team value)** | ⭐⭐⭐ Very high — unauth SQLi, auth bypass, IDOR | ⭐⭐ High — SSTI RCE, Zip Slip, traversal | ⭐ Low public CVE count |
| **Backup tooling** | Built-in GUI + CLI | CLI only | `pg_dump` CLI |
| **PHI exfiltration realism** | ✅ Full patient data tables, document store, audit logs | ✅ FHIR data exposed | ✅ Complete HIS data |
| **FGNW fit** | ✅ Best fit | ✅ Good fit | ⚠️ Linux-only, harder deploy |

The `xl` range's `modern-infra` stack deploys **OpenEMR**, pinned to `7.0.2` to
expose CVE-2024-22611; OpenMRS and GNU Health were evaluated against it here and
are not deployed. OpenEMR runs in Docker and needs no internet once the image is
pulled — compatible with `--testing` containment.

---
The most widely deployed open-source Electronic Health Record (EHR) and practice
management system. ONC-certified, actively maintained, extremely well-documented.

- **Download:** <https://www.open-emr.org/downloads/> or
  `docker pull openemr/openemr:latest`
- **GitHub:** <https://github.com/openemr/openemr>
- **Dependencies:**
  - Web server: Apache 2.4+ or Nginx 1.22+
  - PHP 8.2–8.5
  - MariaDB 10.6–11.8 (preferred) or MySQL 5.7–8.4
  - Docker + Docker Compose (recommended deployment)
  - curl, zip, unzip, git
**Minimal Docker Compose example:**

```yaml
services:
  openemr-db:
    image: mariadb:10.6
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_USER: openemr
      MYSQL_PASSWORD: openemr
      MYSQL_DATABASE: openemr
    volumes:
      - ./mysql_data:/var/lib/mysql
  openemr:
    image: openemr/openemr:7.0.2
    environment:
      OE_USER: admin
      OE_PASS: pass
      MYSQL_HOST: openemr-db
      MYSQL_ROOT_PASS: root
      OE_SITE: default
    ports:
      - "8080:80"
      - "8443:443"
    depends_on:
      - openemr-db
```

- **Preferred:** Ubuntu 22.04 / 24.04, Debian 12
- Also supported: AlmaLinux 9, Windows Server 2019/2022, macOS 13+
- Runs on any OS with Docker support
**Minimum hardware for a range VM:**

| Resource | Minimum | Recommended |
| --- | --- | --- |
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 50 GB SSD | 100 GB |

- **Web UI** — browser (Chrome/Chromium preferred), port 80/443
- **REST API** documented via Swagger/OpenAPI at `<host>/swagger`
- **FHIR API** — SMART on FHIR endpoints available
- **Patient Portal** — separate login at `<host>/portal`; patients view records,
  request appointments, message providers
- **Direct database** — MariaDB accessible on port 3306 (typically internal only)

| Process | Method |
| --- | --- |
| Patient registration | Web UI → Patients → New Patient |
| Patient search | Patients → Find Patient |
| Clinical encounter / new entry | Encounter menu → Add Encounter → SOAP / structured note |
| Prescriptions & medication orders | Fee Sheet → Add Rx |
| Lab orders and results | Lab module within encounter |
| Scheduling appointments | Calendar / Appointment module |
| Secure messaging | Secure Messaging (provider-to-patient, provider-to-provider) |
| User management | Admin → ACL → Users → Add/edit roles |
| Database backup (GUI) | Admin → System → Backup → Create Backup → saves `emr_backup.tar` |
| Database backup (CLI) | `mysqldump --opt openemr \| gzip > openemr.sql.gz` then `tar -cf emr_backup.tar openemr.sql.gz openemr.tar.gz` |
| Restore | `./contrib/util/restore` script; re-point `sites/default/sqlconf.php` for new host |
| Upgrade / patching | Admin → System → Upgrade; or replace Docker image tag |
| Audit logs | Admin → Reports → Audit Log |

The backup file (`emr_backup.tar`) contains both a compressed SQL dump
(`openemr.sql.gz`) and the web application directory (`openemr.tar.gz`).
It must be treated as regulated PHI.
OpenEMR ships **official tooling** for realistic synthetic activity:
**1. Demo Data Generator (official):**

```bash
git clone https://github.com/openemr/demo-data-generator
cd demo-data-generator
virtualenv venv && source venv/bin/activate
pip install .
demodata patients --count 50 > patients.sql
mysql -u openemr_user -p openemr_db < patients.sql
```

Generates realistic fictitious patient records (names, DOB, demographics,
insurance IDs, diagnoses) directly importable into the OpenEMR database.
**2. REST API scripting (Python pseudocode):**

```python
import requests
session = requests.Session()
session.post('http://openemr/interface/main/main_screen.php',
             data={'authUser': 'clinician', 'clearPass': 'clinician'})
result = session.get('http://openemr/apis/api/patient/search?name=Smith')
pid = result.json()[0]['id']
session.post(f'http://openemr/apis/api/patient/{pid}/vitals',
             data={'blood_pressure': '118/76', 'temperature': '36.7'})
```

**3. Multi-role demo accounts** (each maps to a different access tier):

| Account | Password | Role |
| --- | --- | --- |
| admin | pass | System administrator |
| physician | physician | Attending physician |
| clinician | clinician | Clinical staff |

Driving all three in parallel produces realistic multi-tier audit log traffic.

| CVE | Version | CVSS | Type | Detail |
| --- | --- | --- | --- | --- |
| **CVE-2024-22611** | 7.0.2 | 9.8 Critical | Unauthenticated SQL injection | Via `Pharmacy.class.php`; PoC public on GitHub |
| **CVE-2026-24898** | < 7.0.4 | Critical | Auth bypass in MedEx API | Unauthenticated token theft → full PHI access |
| **CVE-2025-67645** | < 7.0.4 | High | IDOR / broken access control | Low-priv user modifies other users' profiles via `pid` manipulation |
| **CVE-2023-54347** | 7.0.1 | 7.5 High | No rate-limiting on login | Brute-force of any account without lockout |
| **CVE-2026-39931** | 7.2 | 7.2 High | Authenticated SQLi in `backup.php` import | Requires auth; targets DB import feature |

**Derivative risk from the underlying stack:**

- **MariaDB / MySQL CVEs** — unpatched DB engine may expose the backend directly
  if port 3306 is reachable from the range
- **Apache / Nginx CVEs** — path traversal or HTTP request smuggling could bypass
  OpenEMR authentication at the web-server layer
- **PHP CVEs** — deserialization or file inclusion issues if PHP is below its
  current patch level

1. **Unauthenticated SQLi (CVE-2024-22611):** Directly dump `patient_data`,
   `form_vitals`, and `openemr_postcalendar_events` tables via the pharmacy
   endpoint — no credentials needed. PoC is public.
2. **Auth bypass (CVE-2026-24898):** Steal session token from the MedEx API;
   replay to enumerate all patients and download attached documents.
3. **Brute-force (CVE-2023-54347):** No account lockout; enumerate weak passwords
   against `admin` or any known username using an automated tool.
4. **IDOR privilege escalation (CVE-2025-67645):** Log in as a low-privilege
   account, change admin's email to attacker-controlled via `pid` manipulation,
   trigger password reset → full admin takeover.
5. **Webshell persistence:** Upload a malicious file through the document
   attachment feature if upload validation is weak; webshell gives persistent RCE
   inside the web root.
6. **Session token harvest:** Active session tokens are stored in OpenEMR's log
   tables; an attacker with DB read access can replay them to access additional
   modules or pivot to connected file servers.
7. **Bulk PHI exfiltration:** Once DB access is established,
   `SELECT * FROM patient_data` exports the full patient roster. Stage with
   `mysqldump`, compress, then exfiltrate over HTTPS or via DNS tunnelling.
8. **Backup file theft:** `Admin → Backup` produces a single `.tar` containing the
   entire DB dump. If the attacker can reach the backup storage path they obtain
   everything in one artefact.

---
Java/Tomcat-based, module-driven EMR. Widely deployed in resource-constrained
environments. FHIR-native in recent versions. Good secondary target for variety
(Java stack vs. PHP stack).

- **Download:** <https://openmrs.org/download/> or Docker Hub
  `openmrs/openmrs-reference-application-distro:demo`
- **Dependencies:** Java 8+ (bundled in Docker), MySQL/MariaDB, Apache Tomcat
  (bundled in Docker), Chrome for UI
**Quick start:**

```bash
docker run -d --name openmrs -p 8080:8080 \
  openmrs/openmrs-reference-application-distro:demo
```

- Preferred: Ubuntu LTS (any current)
- Supported: Any Linux, macOS, Windows with Docker
**Minimum hardware:**

| Resource | Minimum | Recommended |
| --- | --- | --- |
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 100 GB | 100+ GB with RAID |

- **Web UI** — browser, port 8080 by default
- **REST API** — `/openmrs/ws/rest/v1/`
- **FHIR API** — `/openmrs/ws/fhir2/`
- Patient registration and search
- Clinical observations and diagnoses
- Concept dictionary management (clinical codes)
- Module installation via Admin UI or `POST /ws/rest/v1/module`
- Visit and encounter management
- DB backup via `mysqldump`; no built-in GUI backup tool
FHIR and REST APIs are scriptable in any language. Sample patient datasets
are available from the OpenMRS wiki. Activity generation is slightly more complex
than OpenEMR (no dedicated demo-data tool), but FHIR bundles can be posted directly
to seed encounters, observations, and patient records.

| CVE | Versions | Severity | Type |
| --- | --- | --- | --- |
| **CVE-2026-41258** | 2.7.0–2.7.8, 2.8.0–2.8.5 | Critical | SSTI (Velocity) → RCE via concept reference range criteria |
| **CVE-2026-40076** | ≤ 2.7.8, 2.8.0–2.8.5 | High | Zip Slip in module upload REST endpoint → arbitrary file write → RCE via JSP |
| **CVE-2026-40075** | ≤ 2.7.8, 2.8.0–2.8.5 | High | Directory traversal in `/moduleResources/{moduleid}` → unauthenticated arbitrary file read |

**Adversary techniques:**

1. **Unauthenticated file read (CVE-2026-40075):** Read `/etc/passwd`, DB config
   files, or private keys from the server filesystem with no credentials.
2. **Zip Slip RCE (CVE-2026-40076):** Authenticated module upload with a crafted
   `.omod` ZIP → write a JSP webshell to the web root → RCE.
3. **SSTI RCE (CVE-2026-41258):** Authenticated "Manage Concepts" privilege →
   inject a Velocity template expression → arbitrary Java reflection → RCE
   triggered on any observation validation.
4. **PHI exfiltration:** Once RCE is achieved, dump the `obs`, `patient`, and
   `person` MySQL tables for full patient and clinical data.

---
Comprehensive Hospital Information System (HIS) built on Python / PostgreSQL /
Tryton. Covers clinical care, hospital management, lab, pharmacy, and demographics.
Strong data model; realistic PHI simulation. Higher deployment complexity and
Linux-only — third-priority option.

- **Download:** <https://ftp.gnu.org/gnu/health/>
- **Dependencies:** GNU/Linux (Debian / Ubuntu recommended), PostgreSQL ≥ 15,
  Python ≥ 3.10, Gunicorn, Tryton 7.0, optional Nginx reverse proxy, NTP

```bash
apt-get install postgresql patch python3-pip unoconv
```

- **Linux only** — Debian, Ubuntu, openSUSE, Void Linux, or BSD (FreeBSD/OpenBSD)
- Not natively supported on Windows
- Web-based Tryton client and browser interface
- REST API available for programmatic access
- Full patient lifecycle: registration, appointments, encounters, lab orders,
  pharmacy, billing
- Role-based access: physicians, nurses, receptionists, lab technicians
- DB backup via `pg_dump`; application maintenance via `gnuhealth-control`
API-scriptable; community-provided synthetic patient generators. Activity
generation is more complex than OpenEMR (Tryton ORM layer) — acceptable but
not as turnkey.
No high-profile CVEs are publicly attributed to GNU Health core (small attack
surface relative to OpenEMR / OpenMRS).
**Derivative risk:**
- **PostgreSQL CVEs** — privilege escalation or SQLi if parameterisation breaks
  in custom code
- **Python / Tryton CVEs** — framework-level vulnerabilities
- **Security advisories:** <https://ftp.gnu.org/gnu/health/security/security_advisories.html>
Its relative obscurity limits the public PoC library. Useful if a more
defensive/blue-team perspective is desired, or as a secondary target with fewer
known chains.

---

This section describes who uses a clinical EHR, what data they touch, what a
realistic session looks like, what seed data must exist before that session is
possible, and how the whole picture fits together for a convincing simulation.
OpenEMR (the system `modern-infra` deploys) is used as the reference throughout

---

| Role | System account | Data they read | Data they create / modify |
| --- | --- | --- | --- |
| **Receptionist / Admin clerk** | Low-privilege staff account | Patient demographics, appointment calendar, insurance details | New patient registration, appointment bookings, insurance updates |
| **Nurse / Allied health** | Clinical staff account | Patient demographics, allergies, current medications, vitals history | Vitals (BP, temp, weight, O₂ sat), triage notes, medication administration records |
| **Attending physician** | Physician account | Full patient record, lab results, imaging reports, prior encounters, medication history | SOAP notes, diagnoses (ICD-10 codes), prescriptions, lab/imaging orders, referrals |
| **Pharmacist** | Pharmacy account | Active prescriptions, medication list, drug interaction flags | Dispense records, medication reconciliation |
| **Lab technician** | Lab account | Lab orders attached to encounters | Lab results (CBC, metabolic panel, culture) linked back to encounter |
| **System administrator** | Admin account | All of the above plus system config, user ACLs, audit logs | User accounts, role permissions, system settings, backup/restore |
| **Patient (portal)** | Patient portal account | Own demographics, upcoming appointments, past encounter summaries, lab results released by provider, secure messages | Appointment requests, messages to care team, personal health questionnaires |

---

1. Log in to OpenEMR web UI with receptionist credentials.
2. Navigate to **Calendar** → locate today's appointment for the patient.
3. Click **Check In** → confirm or update demographics (address, phone, insurance).
4. Print or email appointment confirmation if required.
5. Hand off to nursing staff.
6. **Data touched:** `patient_data`, `openemr_postcalendar_events`, `insurance_data`
7. Log in with clinical staff credentials.
8. Navigate to **Patients → Find Patient** → search by name or DOB.
9. Open the patient's chart → review allergy list and current medications.
10. Open the current encounter (or create a new one: **Encounter → Add Encounter**).
11. Record vitals: BP, heart rate, temperature, weight, O₂ saturation.
12. Add a brief triage note in the SOAP note field.
13. **Data touched:** `patient_data`, `lists` (allergies/medications), `form_vitals`,
   `form_soap`, `openemr_postcalendar_events`
14. Log in with physician credentials.
15. Open the patient's chart from the appointment queue or patient search.
16. Review prior encounters, lab results, and imaging reports.
17. Complete the SOAP note: Subjective (patient history), Objective (exam findings),
   Assessment (ICD-10 diagnosis codes), Plan (treatment, Rx, referrals).
18. Order labs: **Fee Sheet → Add Lab Order** → select panel (e.g. CBC, BMP).
19. Prescribe medication: **Add Rx** → drug name, dose, frequency, duration.
20. Save and close encounter.
21. **Data touched:** `form_soap`, `form_encounter`, `billing_codes` (ICD-10 / CPT),
   `prescriptions`, `procedure_order`, `patient_data`
22. Log in with lab account.
23. Navigate to **Procedures → Pending Orders** → locate outstanding order.
24. Enter results against each ordered test (numeric values + reference ranges).
25. Mark order as complete; result becomes visible to ordering physician.
26. **Data touched:** `procedure_order`, `procedure_result`, `patient_data`
27. Log in with admin credentials.
28. Navigate to **Admin → System → Backup → Create Backup**.
29. Download `emr_backup.tar` to secure storage (or schedule via cron):

    ```bash
    mysqldump --opt openemr | gzip > /backups/openemr-$(date +%Y%m%d).sql.gz
    ```

30. Verify backup integrity by checking file size and testing a restore to a non-production instance quarterly.
31. **Data touched:** full database export + web files archive
32. Log in to `<host>/portal` with patient-specific credentials (issued by receptionist).
33. View upcoming appointments and past visit summaries.
34. Read released lab results and care plan notes.
35. Send a secure message to their care team.
36. **Data touched:** `portal_*` tables, read-only access to `form_soap` (provider-released entries), `openemr_postcalendar_events`

---
A meaningful simulation requires the following data to exist *before* NPCs start
operating. This is the seed dataset.
This must be present before any patient or clinical data can be created.

| Data item | Where entered | Notes |
| --- | --- | --- |
| Facility / practice name, address, phone | Admin → Practice → Facilities | Required for encounter headers and prescriptions |
| Provider (physician) records | Admin → Users → Add User (role: physician) | Each physician needs a profile with DEA number, NPI, specialty |
| Staff records | Admin → Users | Nurses, receptionists, lab techs — each with appropriate role/ACL |
| Insurance payers | Admin → Insurance Companies | At least 2–3 payers (e.g. Medicare, private fund, self-pay) |
| Fee schedule / billing codes | Admin → Fee Schedules | CPT and ICD-10 code lists; required for encounter billing |
| Pharmacy details | Admin → Pharmacy | At least one dispensing pharmacy for Rx routing |

Each patient record requires:

| Field | Example |
| --- | --- |
| Full name | Jane Doe |
| Date of birth | 1972-04-15 |
| Sex / gender | Female |
| Address and phone | 12 Example St, Sydney NSW 2000 |
| Medicare / insurance number | 1234 56789 1 |
| Emergency contact | John Doe, 0400 000 000 |
| Primary care provider | Dr A. Smith |
| Allergy list | Penicillin (rash); NKDA if none |
| Current medications | Metformin 500 mg BD; Ramipril 5 mg OD |

**Generate with the official tool:**

```bash
demodata patients --count 50 > patients.sql
mysql -u openemr -p openemr < patients.sql
```

Each patient should have at least 3–5 prior encounters to look like an established
practice rather than a fresh install.

| Data item | Minimum content |
| --- | --- |
| Past encounters (per patient) | Date, provider, chief complaint, SOAP note, ICD-10 diagnosis |
| Vitals history | One set of vitals per encounter (BP, temp, weight) |
| Medications | 1–2 chronic medications per patient |
| Lab results | At least one completed lab panel (e.g. annual bloods: CBC + BMP) |
| Immunisation records | Flu vaccine, COVID-19 vaccine dates |
| Appointments | 2–3 past + 1–2 future appointments per patient |

The audit log starts empty. Before red-team activity begins, a baseline of normal
access patterns should exist. Achieve this by running simulated user sessions (see
§ Simulation below) for at least a 48-hour window prior to the exercise. This gives
the blue team a normal-traffic baseline to compare against during the exercise.

---
When a user accesses or modifies patient data, the following database tables are
involved. Understanding these is essential for designing realistic NPC scripts and
for identifying what an adversary would target.

| Action | Primary tables written / read |
| --- | --- |
| Patient registration / demographics update | `patient_data` |
| Appointment booking | `openemr_postcalendar_events` |
| Insurance update | `insurance_data`, `insurance_companies` |
| Allergy entry | `lists` (`type = 'allergy'`) |
| Medication list update | `lists` (`type = 'medication'`) |
| Encounter creation | `form_encounter` |
| Vitals recording | `form_vitals` |
| SOAP note | `form_soap` |
| ICD-10 diagnosis | `billing_codes`, `code_types` |
| Lab order | `procedure_order` |
| Lab result entry | `procedure_result` |
| Prescription | `prescriptions` |
| Document / attachment upload | `documents`, `categories` |
| Secure message | `pnotes` (provider notes / secure messages) |
| Audit log entry (auto) | `log` |
| User login | `log`, `session_*` |
| Backup | full DB dump + `openemr/sites/default/documents/` |

---

```text

GHOSTS NPC engine
      │
      ├── Persona: Receptionist (low-priv)
      │       └── Drives: check-in flow, appointment search, demographics update
      │
      ├── Persona: Nurse (clinical staff)
      │       └── Drives: vitals entry, triage note, allergy review
      │
      ├── Persona: Physician (high-priv)
      │       └── Drives: full SOAP note, Rx, lab order, result review
      │
      └── Persona: System Admin (admin)
              └── Drives: user account changes, backup, audit log review

```

Each persona is a GHOSTS NPC handler that logs into OpenEMR over HTTP and performs
realistic sequences of actions on a schedule — mimicking shift patterns (morning
08:00–16:00, evening 14:00–22:00) with randomised inter-action delays.
GHOSTS natively supports **browser-based web handlers** (Playwright or Selenium).
Each NPC is given a timeline of tasks. A nurse's timeline might be:

```text

08:05  Log in
08:07  Find Patient "Sarah Mitchell" (pid 22)
08:09  Open encounter
08:10  Record vitals: BP 132/84, Temp 37.1, Weight 68 kg, O2 98%
08:12  Add triage note
08:13  Log out
14:30  Log in
14:32  Find Patient "James Okafor" (pid 31)
...

```

Repeating this pattern across 10–15 NPCs (2–3 of each role) produces a realistic
access log. The key properties that make it look genuine:

- Actions are in logical order (find patient → open chart → open encounter → record)
- Timing has variance (not every action takes exactly 2 minutes)
- Personas access *different* patients, not always the same one
- Admin NPC runs a weekly backup and checks audit logs
- Patient portal NPC logs in, reads a result, sends a message, logs out
OpenEMR's web UI can be fully driven by a Playwright/Selenium script without
needing any API key configuration — GHOSTS' browser handler is sufficient.
If GHOSTS browser handlers are not available in the range build at exercise time,
a **Python + Requests fallback** can drive the same flows through the OpenEMR
REST API. The OpenEMR REST API covers all the data manipulation flows listed above
(patient CRUD, encounter CRUD, vitals, Rx, documents) and requires only an OAuth2
bearer token obtained at login.
As a last resort, pre-seeded **static SQL snapshots** can be loaded to give the
appearance of an active system (historical data present, believable audit log),
even if live NPC traffic is not running. This is less convincing for a live
exercise but adequate for a CTF-style scenario.

---

This section covers the administrative side of a clinical practice: HR
communications, appointment workflows, and the catalogue of **deliberately
insecure behaviours** that make the range realistic and give the red team genuine
footholds. Each scenario below is a named NPC behaviour that can be scripted in
GHOSTS and maps to a specific, observable artefact on the range

---

The clinical database (OpenEMR) handles patient records, but day-to-day
administration in a small-to-medium practice also involves:

| Tool | Purpose | Deployment |
| --- | --- | --- |
| **Exchange / Outlook Web App** | Email: appointment invites, test result notifications, HR comms | Already in FGNW range via Exchange role |
| **OpenEMR Secure Messaging** | In-system provider-to-patient / provider-to-provider messages | Built into OpenEMR web UI |
| **OpenEMR Patient Portal** | Patient-facing appointment requests and result access | Built into OpenEMR |
| **Nextcloud / SMB Share** | Shared documents: admin notes, password files, HR forms | SMB share via FGNW `share` tag or Nextcloud container |
| **Microsoft Teams / web collab doc** | "Collaboration document" where staff share credentials | Simulated via a Nextcloud `.docx` or plaintext file on the share |

All of these can run inside `--testing` containment — no internet access is
required after initial image pulls.

---
**What happens:**
The HR clerk sends an appointment reminder to a patient by email. The email
is generated from the OpenEMR appointment calendar and forwarded through Exchange.
**NPC script steps:**

1. Clerk logs into OpenEMR → Calendar → finds patient appointment for next week.
2. Copies patient name, appointment date/time, and provider name.
3. Opens OWA (Outlook Web App) → composes email to patient's registered address.
4. Email body: "Dear [Patient Name], this is a reminder of your appointment with
   Dr [Provider] on [Date] at [Time]. Please reply to confirm."
5. Sends email.
**Insecure behaviour introduced:** The email body contains the patient's full
name, provider name, and appointment date — PHI in plaintext in an email thread.
If a red-team actor has compromised a mail account they can harvest appointment
schedules for all patients.
**Data referenced:** `openemr_postcalendar_events`, `patient_data`
(name, email), `users` (provider name)

---
**What happens:**
The patient (a GHOSTS NPC playing the patient persona) replies to the appointment
reminder confirming attendance.
**NPC script steps:**

1. Patient NPC logs into OWA with their personal email account (or patient portal).
2. Replies to the appointment reminder: "Confirmed, I will attend."
3. HR clerk NPC reads the reply → opens OpenEMR → updates appointment status
   to **Confirmed**.
**Data referenced:** `openemr_postcalendar_events` (status field),
Exchange mailbox of HR clerk.

---
**What happens:**
After a lab result is filed, the physician (or admin on their behalf) notifies the
patient by email that results are ready to view in the patient portal. In many
practices this is done *incorrectly* — the result values are included in the email
body rather than behind the portal login.
**NPC script steps:**

1. Physician NPC files lab results in OpenEMR (Flow D from the previous section).
2. Physician (or clerk) NPC opens OWA → composes email to patient.
3. **Insecure version:** Email body includes the result values: "Your HbA1c came
   back at 7.2%, which is within the target range."
4. Sends email.
**Insecure behaviour introduced:** Lab result values (clinical PHI) transmitted
in plaintext email. Red team with mail access can exfiltrate clinical data without
ever touching OpenEMR.
**Data referenced:** `procedure_result`, `patient_data` (email),
Exchange sent items.

---
**What happens:**
An HR clerk receives a referral or intake form by email, intends to enter it into
OpenEMR, but instead saves the email attachment (a PDF or `.docx` containing
patient name, DOB, Medicare number, and clinical summary) to a shared network
folder rather than importing it into the EHR.
**NPC script steps:**

1. Clerk NPC receives email with patient intake form attachment in OWA.
2. Downloads the attachment.
3. Saves to `\\FILESERVER\HR\Intake Forms\2026\` (or the equivalent SMB share
   path used in the FGNW range) instead of uploading to OpenEMR
   (Admin → Files → Documents).
4. The file sits on the filesystem, unencrypted, accessible to anyone with share
   access — and is never entered into OpenEMR.
**Insecure behaviour introduced:**

- PHI on the filesystem, outside the EHR's access controls and audit logging
- File is readable by any user with share access — not just clinical staff
- No audit trail of who accessed the document after it was saved
**Artefact on range:** `\\FILESERVER\HR\Intake Forms\2026\patient-intake-[name].docx`
containing real-looking patient PHI seed data.
**Red-team value:** Any user with read access to the HR share can enumerate
patient records without interacting with OpenEMR at all. This is a common real-world
finding in healthcare environments.

---
**What happens:**
Staff maintain a shared "Admin Passwords" document on the file server or a
Nextcloud collaborative document so that locum staff and new starters can access
systems without going through IT.
**NPC script steps:**

1. Admin NPC opens the shared document: `\\FILESERVER\Admin\staff-passwords.docx`
   (or Nextcloud equivalent).
2. Adds or updates an entry: `OpenEMR admin: pass`, `OWA HR clerk: Welcome1!`,
   `Nextcloud admin: admin123`.
3. Saves the document.
4. A second NPC (e.g. a locum physician) opens the same document, reads the
   credentials, and logs into OpenEMR using them.
**Insecure behaviour introduced:**

- Cleartext credentials stored in a world-readable file on the network
- Multiple accounts sharing a single known password
- No MFA; no password rotation
**Artefact on range:**

```text

\\FILESERVER\Admin\staff-passwords.docx
  OpenEMR admin login:      admin / pass
  OWA HR login:             hr.clerk / Welcome1!
  Nextcloud admin:          admin / admin123
  OpenEMR pharmacy:         pharmacy / pharmacy1

```

**Red-team value:** Single document gives full credential set for every system.
This is a high-priority target for any attacker with share access — and it
represents a genuine, widespread real-world insecure practice

---

The following complete the picture for every database-layer action the
administration persona performs in OpenEMR:

| Use case | UI path | Tables involved |
| --- | --- | --- |
| Add a new staff user | Admin → User/Groups → Add User → assign role (Receptionist, Nurse, etc.) | `users`, `gacl_*` (ACL) |
| Reset a user's password | Admin → User/Groups → find user → Edit → set new password | `users` |
| View who has accessed a patient record | Admin → Reports → Audit Log → filter by patient pid | `log` |
| Bulk-download patient list | Admin → Reports → Patient List → Export CSV | `patient_data` |
| Upload a document to a patient record | Patient chart → Documents → Upload File | `documents`, `categories` |
| Create a new insurance company record | Admin → Insurance Companies → Add | `insurance_companies` |
| Add a new facility / location | Admin → Practice → Facilities → Add | `facility` |
| Edit fee schedule | Admin → Fee Schedules | `fee_sheet`, `billing_codes` |
| Run a financial report | Reports → Financial Summary | `payments`, `billing`, `ar_activity` |
| Generate a superbill | Fee Sheet → Print Superbill | `form_encounter`, `billing_codes`, `patient_data` |
| Schedule a bulk backup | Cron: `mysqldump openemr \| gzip > /backups/$(date +%F).sql.gz` | Full DB |
| Import data from external source | Admin → Backup/Restore → Import SQL | Full DB |
| Send mass appointment reminders | Reports → Appointments → filter upcoming → export → compose mail merge | `openemr_postcalendar_events`, `patient_data` |

---
The following table summarises every deliberately insecure artefact placed on
the range by the admin/HR NPC flows above. Each is a realistic finding for a
red team conducting an internal assessment of a healthcare organisation.

| Artefact | Location | Content | How a red team finds it |
| --- | --- | --- | --- |
| Patient PHI in email threads | Exchange mailbox of HR clerk | Patient name, appointment date/time, test result values | Compromise HR clerk mail account → search inbox/sent for clinical keywords |
| Patient intake forms on filesystem | `\\FILESERVER\HR\Intake Forms\2026\` | Name, DOB, Medicare number, clinical summary (PDF/DOCX) | Enumerate SMB share; no special privilege needed if HR share is widely accessible |
| Plaintext credential document | `\\FILESERVER\Admin\staff-passwords.docx` | OpenEMR admin, OWA, Nextcloud credentials in cleartext | Enumerate SMB share; open document; immediately pivot to every system |
| Unencrypted backup file | `/backups/` on the OpenEMR host or a network path | Full `mysqldump` of OpenEMR database — all PHI | Compromise OpenEMR host or backup share; single file gives entire DB |
| Audit log with access patterns | OpenEMR Admin → Reports → Audit Log | Every login, patient access, data modification with username and timestamp | Requires OpenEMR admin credentials; once obtained, reveals all user activity |
| Patient portal credentials sent by email | Exchange mailbox of patients / clerk | Portal username and temporary password in email body | Compromise any mailbox in the chain |

---

```text

HR Clerk (shifts 08:00–17:00, Mon–Fri)
  08:05  Log into OWA
  08:10  Send appointment reminders for tomorrow's patients (Flow A)
  08:30  Check inbox — read confirmation replies (Flow B)
  09:00  Receive patient intake email → download → save to \\FILESERVER\HR\  (Flow D)
  10:30  Log into OpenEMR → update appointment confirmations
  12:00  Open \\FILESERVER\Admin\staff-passwords.docx → check/update entry (Flow E)
  14:00  Log into OpenEMR → run Patient List report → export CSV
  16:30  Compose and send test result notifications for results filed today (Flow C)
  17:00  Log out
Admin / IT (1 session per day)
  09:00  Log into OpenEMR as admin
  09:05  Check Audit Log for overnight access
  09:15  Run mysqldump backup → save to /backups/
  09:30  Open \\FILESERVER\Admin\staff-passwords.docx → review
  09:45  Log out

```

Variance (randomised ±10 minutes on each action) and occasional skipped actions
prevent the NPC traffic from looking mechanical in the logs

---

The CSU Library source lists the following academic literature databases.
These are **subscription-based research bibliographies, not deployable software** —
they cannot run inside the FGNW range. This section records what each is, why it
is not a range candidate, and where it may still be relevant to the range's
scenario.

| Database | Publisher / Platform | What it is | Range relevance |
| --- | --- | --- | --- |
| **CINAHL Plus with Full-Text** | EBSCO | International nursing and allied health journal index; web UI via EBSCOhost | Not deployable. Scenario flavour only — operators could reference it in NPC cover stories for nursing staff |
| **Cochrane Library** | Cochrane Collaboration | Systematic reviews and meta-analyses; free access in Australia; web-based | Not deployable. High credibility as a fictional source cited in NPC clinical notes |
| **Emcare** | Ovid | Nursing and allied health evidence-based clinical content; 1 concurrent user licence | Not deployable (licensed, Ovid-hosted) |
| **Health Collection** | Informit | Australian full-text allied health, nursing, aged care, indigenous health, mental health | Not deployable (Informit-hosted, subscription) |
| **MEDLINE ALL (1946–present)** | Ovid / NLM | Major international medicine and veterinary medicine journal index with MeSH headings | Not deployable. MEDLINE is the canonical source for clinical bibliography; useful as a prop in clinician NPC personas |
| **PsycINFO (1806–present)** | APA / ProQuest | Psychological, social, behavioural, and health science journal and citation database | Not deployable (APA-licensed). Relevant if the range includes a mental health clinic scenario |
| **Scopus** | Elsevier | Multi-subject abstract and citation database; known for bibliometric features | Not deployable (Elsevier subscription). No direct security relevance |
| **UpToDate** | Wolters Kluwer | Evidence-based point-of-care clinical reference: drug information, medical calculators, patient handouts; continuously updated | Not deployable (subscription, cloud-hosted). High realism value as the tool a clinician NPC would consult during a patient encounter — can be referenced in GHOSTS NPC scripts |

The CSU source documents *what health professionals use to find clinical
literature*. The range requires*what health systems run to store and manage
patient data*. These are different things:

- **Literature databases** (CINAHL, Cochrane, MEDLINE, etc.) → consumed by
  clinicians; no self-hosted option; no CVE attack surface
- **EHR / HIS platforms** (OpenEMR, OpenMRS, GNU Health) → run the operational
  database; deployable; carry real CVE attack surface; generate realistic
  clinical workflow traffic
The academic databases above are nonetheless useful for **scenario dressing**:
NPC GHOSTS scripts can reference CINAHL or UpToDate as the tool a nurse or doctor
is browsing, creating a believable cover story layered on top of the actual
OpenEMR target.
