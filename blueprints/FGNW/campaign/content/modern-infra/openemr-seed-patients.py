"""LOE 5 (docs/MODERN-INFRA.md), item 7 -- seeds OpenEMR with synthetic patient records
derived from content/modern-infra/patient-seed.csv (itself generated from the real
content/AD/characters.csv roster -- see that CSV's own header comment for the age-mapping rules
and the "populated domains only" filter).
Uses OpenEMR's own REST API (OAuth2 password-grant registration, then the FHIR-adjacent
/apis/default/api/patient endpoint) -- this is OpenEMR's documented, real integration path, not a
direct-DB-write shortcut. Run on the modern-infra VM after the openemr container reports healthy.
NEEDS LIVE ITERATION, same as every other heavy integration in this blueprint (e.g.
aleemladha.ludus_exchange, see docs/OWA-REAL-VS-SIMULATED.md) -- OpenEMR's OAuth2 client
registration flow has version-specific quirks (redirect_uri handling, scope string exact format)
that are only reliably discoverable by running it against a live instance. Written and reviewed
against OpenEMR 7.0.x's documented API, not yet exercised against a running container.
"""
import csv
import json
import sys
import time
import urllib.request
import urllib.error
BASE_URL = "https://localhost:8443"
ADMIN_USER = "admin"
ADMIN_PASS = "AnsibleAutomation123!"
SEED_CSV = "patient-seed.csv"
import ssl
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
def api_request(method, path, token=None, body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as resp:
        return json.loads(resp.read())
def register_oauth_client():
    """OpenEMR's site-specific OAuth2 client registration (RFC 7591 dynamic registration)."""
    body = {
        "application_type": "private",
        "redirect_uris": [f"{BASE_URL}/oauth-callback"],
        "client_name": "FGNW-modern-infra-seed",
        "token_endpoint_auth_method": "client_secret_post",
        "scope": "openid offline_access api:oemr user/patient.read user/patient.write",
    }
    resp = api_request("POST", "/oauth2/default/registration", body=body)
    return resp["client_id"], resp["client_secret"]
def get_token(client_id, client_secret):
    body = {
        "grant_type": "password",
        "client_id": client_id,
        "client_secret": client_secret,
        "username": ADMIN_USER,
        "password": ADMIN_PASS,
        "scope": "openid offline_access api:oemr user/patient.read user/patient.write",
        "user_role": "users",
    }
    resp = api_request("POST", "/oauth2/default/token", body=body)
    return resp["access_token"]
def create_patient(token, row):
    given, surname = row["given_name"], row["surname"]
    sex = "Male" if row["gender"].strip().lower().startswith("m") else "Female"
    dob_year = 2026 - int(row["age"])
    body = {
        "title": "",
        "fname": given,
        "lname": surname,
        "DOB": f"{dob_year}-01-01",
        "sex": sex,
        "street": f"{row['village']} — see AD account {row['sAMAccountName']} for full record",
        "city": row["village"],
        "postal_code": "00000",
        "country_code": "JP",
    }
    resp = api_request("POST", "/apis/default/api/patient", token=token, body=body)
    return resp.get("data", {}).get("pid")
def create_encounter_note(token, pid, chief_complaint):
    """One free-text encounter note per patient, seeded from the character's real AD
    `description` field (see patient-seed.csv's own header) -- keeps the medical narrative
    grounded in data already in this repo rather than inventing new clinical detail."""
    body = {
        "pid": pid,
        "reason": chief_complaint,
        "date": "2026-01-15",
        "onset_date": "2026-01-15",
        "provider_id": 1,
        "facility_id": 1,
    }
    try:
        api_request("POST", f"/apis/default/api/patient/{pid}/encounter", token=token, body=body)
    except urllib.error.HTTPError:
        pass
def main():
    print("Registering OAuth2 client...")
    client_id, client_secret = register_oauth_client()
    print("Requesting access token...")
    token = get_token(client_id, client_secret)
    with open(SEED_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"Seeding {len(rows)} patients from {SEED_CSV}...")
    created, failed = 0, 0
    for row in rows:
        try:
            pid = create_patient(token, row)
            if pid:
                create_encounter_note(token, pid, row["chief_complaint_source"])
                created += 1
            else:
                failed += 1
        except urllib.error.HTTPError as e:
            print(f"  FAILED {row['sAMAccountName']}: {e.code} {e.reason}", file=sys.stderr)
            failed += 1
        time.sleep(0.2)
    print(f"Done: {created} created, {failed} failed.")
if __name__ == "__main__":
    main()
