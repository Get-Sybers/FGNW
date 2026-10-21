"""Download and checksum-verify an ISO into Proxmox storage, idempotently.
There is no ansible-core module for the Proxmox storage `download-url` API, and
the community.proxmox collection (where the Proxmox modules now live, having been
split out of community.general) is not guaranteed present on every Ludus build
host. This small stdlib-only module fills that one gap so the role stays on
ansible-core alone. It is the rule-9 equivalent of proxmox-iso's
iso_download_pve=true: Proxmox itself fetches the file and verifies the checksum,
so the multi-GB transfer never touches the build host and unverified media is
never written.
"""
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r"""
---
module: proxmox_iso_download
short_description: Download and verify an ISO into Proxmox storage (idempotent)
description:
  - Ensures an ISO named O(filename) exists in Proxmox O(storage) on O(node).
  - If absent, calls the Proxmox C(download-url) storage API so the node fetches
    the file directly and verifies it against O(checksum) before storing it.
  - Idempotent - if the ISO is already present it reports C(changed=false) and
    does nothing. Supports check mode.
options:
  api_host:
    description: Proxmox API base URL, e.g. V(https://pve.example:8006).
    required: true
    type: str
  api_user:
    description:
      - For token auth, the token id C(user@realm!tokenid).
      - For ticket auth, the login C(user@realm).
    required: true
    type: str
  api_token_secret:
    description: API token secret. When set, token auth is used.
    type: str
  api_password:
    description: Password for ticket auth, used only when O(api_token_secret) is unset.
    type: str
  validate_certs:
    description: Whether to verify the Proxmox TLS certificate.
    type: bool
    default: true
  node:
    description: Proxmox node name that owns the storage.
    required: true
    type: str
  storage:
    description: Storage identifier that must allow C(iso) content.
    required: true
    type: str
  url:
    description: Source URL the Proxmox node downloads the ISO from.
    required: true
    type: str
  filename:
    description: Filename to store the ISO under (the C(.iso) volume name).
    required: true
    type: str
  checksum:
    description: Expected digest as V(algo:hex) (algo one of sha256, sha512, sha1, md5).
    required: true
    type: str
  timeout:
    description: Seconds to wait for the download task to finish.
    type: int
    default: 3600
author:
  - Get-Sybers
"""
EXAMPLES = r"""
- name: Ensure the OpenCore ISO is present and verified
  proxmox_iso_download:
    api_host: "https://pve.example:8006"
    api_user: "svc@pam!packer"
    api_token_secret: "{{ pve_token_secret }}"
    validate_certs: false
    node: pve
    storage: nas-iso
    url: "https://example/OpenCore.iso"
    filename: "OpenCore.iso"
    checksum: "sha256:abc123..."
"""
RETURN = r"""
volid:
  description: The Proxmox volume id of the ISO (present or newly downloaded).
  returned: success
  type: str
  sample: "nas-iso:iso/OpenCore.iso"
"""
import json
import ssl
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from ansible.module_utils.basic import AnsibleModule
VALID_ALGOS = ("sha256", "sha512", "sha384", "sha224", "sha1", "md5")
def _ssl_ctx(validate_certs):
    if validate_certs:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
class ProxmoxAPI:
    def __init__(self, module):
        self.module = module
        self.base = module.params["api_host"].rstrip("/") + "/api2/json"
        self.ctx = _ssl_ctx(module.params["validate_certs"])
        self.headers = {}
        self._auth()
    def _auth(self):
        p = self.module.params
        if p["api_token_secret"]:
            self.headers["Authorization"] = (
                "PVEAPIToken=%s=%s" % (p["api_user"], p["api_token_secret"]))
            return
        if not p["api_password"]:
            self.module.fail_json(msg="No api_token_secret and no api_password - cannot authenticate.")
        data = urlencode({"username": p["api_user"], "password": p["api_password"]}).encode()
        try:
            resp = urlopen(Request(self.base + "/access/ticket", data=data),
                           context=self.ctx, timeout=30)
            body = json.loads(resp.read().decode())["data"]
        except (HTTPError, URLError, ValueError) as exc:
            self.module.fail_json(msg="Ticket auth failed: %s" % exc)
        self.headers["Cookie"] = "PVEAuthCookie=%s" % body["ticket"]
        self.headers["CSRFPreventionToken"] = body["CSRFPreventionToken"]
    def request(self, method, path, data=None):
        url = self.base + path
        payload = urlencode(data).encode() if data else None
        req = Request(url, data=payload, method=method, headers=dict(self.headers))
        try:
            resp = urlopen(req, context=self.ctx, timeout=60)
            return json.loads(resp.read().decode())
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            self.module.fail_json(
                msg="Proxmox API %s %s -> HTTP %s: %s" % (method, path, exc.code, detail))
        except (URLError, ValueError) as exc:
            self.module.fail_json(msg="Proxmox API %s %s failed: %s" % (method, path, exc))
def existing_volid(api, node, storage, filename):
    out = api.request("GET", "/nodes/%s/storage/%s/content?content=iso" % (node, storage))
    for item in (out.get("data") or []):
        volid = item.get("volid", "")
        if volid.endswith("/" + filename):
            return volid
    return None
def main():
    module = AnsibleModule(
        argument_spec=dict(
            api_host=dict(type="str", required=True),
            api_user=dict(type="str", required=True),
            api_token_secret=dict(type="str", no_log=True),
            api_password=dict(type="str", no_log=True),
            validate_certs=dict(type="bool", default=True),
            node=dict(type="str", required=True),
            storage=dict(type="str", required=True),
            url=dict(type="str", required=True),
            filename=dict(type="str", required=True),
            checksum=dict(type="str", required=True),
            timeout=dict(type="int", default=3600),
        ),
        supports_check_mode=True,
    )
    p = module.params
    if ":" not in p["checksum"]:
        module.fail_json(msg='checksum must be "algo:hex" (e.g. sha256:abc...).')
    algo, _, digest = p["checksum"].partition(":")
    algo = algo.lower()
    digest = digest.strip().lower()
    if algo not in VALID_ALGOS:
        module.fail_json(msg="Unsupported checksum algorithm %r (use one of %s)."
                             % (algo, ", ".join(VALID_ALGOS)))
    if not digest:
        module.fail_json(msg="checksum has no digest after the algorithm.")
    api = ProxmoxAPI(module)
    volid = existing_volid(api, p["node"], p["storage"], p["filename"])
    if volid:
        module.exit_json(changed=False, volid=volid,
                         msg="ISO already present: %s" % volid)
    target_volid = "%s:iso/%s" % (p["storage"], p["filename"])
    if module.check_mode:
        module.exit_json(changed=True, volid=target_volid,
                         msg="Would download %s to %s" % (p["url"], target_volid))
    start = api.request("POST", "/nodes/%s/storage/%s/download-url" % (p["node"], p["storage"]),
                        data={
                            "content": "iso",
                            "filename": p["filename"],
                            "url": p["url"],
                            "checksum": digest,
                            "checksum-algorithm": algo,
                        })
    upid = start.get("data")
    if not upid or upid == "null":
        module.fail_json(msg="download-url did not start a task: %s" % json.dumps(start))
    deadline = time.time() + p["timeout"]
    while True:
        st = api.request("GET", "/nodes/%s/tasks/%s/status" % (p["node"], upid)).get("data", {})
        if st.get("status") == "stopped":
            break
        if time.time() > deadline:
            module.fail_json(msg="Timed out after %ss waiting for download task %s"
                                 % (p["timeout"], upid))
        time.sleep(5)
    if st.get("exitstatus") != "OK":
        log = api.request("GET", "/nodes/%s/tasks/%s/log" % (p["node"], upid)).get("data", [])
        tail = " | ".join(line.get("t", "") for line in log[-10:])
        module.fail_json(msg="Download/verify failed (%s). Task log: %s"
                             % (st.get("exitstatus"), tail))
    module.exit_json(changed=True, volid=target_volid,
                     msg="Downloaded and verified %s (%s)" % (target_volid, algo))
if __name__ == "__main__":
    main()
