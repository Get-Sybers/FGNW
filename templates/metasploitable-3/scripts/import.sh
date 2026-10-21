#!/usr/bin/env bash
# Every PROXMOX_*, SOURCE_*, VM_*, SSH_*, ANSIBLE_*, LUDUS_NAT_INTERFACE and
# TEMPLATE_DESCRIPTION value arrives from the Packer shell-local provisioner's
# environment_vars (see the .pkr.hcl beside this script).
# shellcheck disable=SC2154
set -euo pipefail
curl_insecure=()
if [[ ${PROXMOX_INSECURE:-true} == "true" ]]; then
  curl_insecure=(-k)
fi
api() {
  local method="$1" path="$2"
  shift 2
  curl -sS "${curl_insecure[@]}" -X "$method" \
    -H @- \
    "${PROXMOX_URL%/}${path}" "$@" << EOF
${AUTH_HEADERS}
EOF
}
wait_task() {
  local upid="$1"
  while true; do
    local status
    status=$(api GET "/nodes/${PROXMOX_HOST}/tasks/${upid}/status" | jq -r '.data.status')
    [[ $status == "stopped" ]] && break
    sleep 5
  done
  local exitstatus
  exitstatus=$(api GET "/nodes/${PROXMOX_HOST}/tasks/${upid}/status" | jq -r '.data.exitstatus')
  if [[ $exitstatus != "OK" ]]; then
    echo "Task ${upid} failed: ${exitstatus}" >&2
    # shellcheck disable=SC2310 # best-effort log dump: a failed read must not mask the task failure
    api GET "/nodes/${PROXMOX_HOST}/tasks/${upid}/log" | jq -r '.data[].t' >&2 || true
    exit 1
  fi
}
echo "[1/9] Authenticating to Proxmox API at ${PROXMOX_URL}..."
echo "      creds available: PVE_TOKEN_SECRET=${PVE_TOKEN_SECRET:+set} PROXMOX_PASSWORD=${PROXMOX_PASSWORD:+set}" >&2
echo "      [debug] cred-ish env var names present: $(compgen -e | grep -iE 'proxmox|pve|token|pm_api' | tr '\n' ' ')" >&2
if [[ -n ${PVE_TOKEN_SECRET:-} ]]; then
  AUTH_HEADERS="Authorization: PVEAPIToken=${PVE_TOKEN_USER:-}=${PVE_TOKEN_SECRET}"
  echo "      using PVE API token auth (${PVE_TOKEN_USER:-<no-user>})" >&2
else
  auth_resp=$(printf '%s' "${PROXMOX_PASSWORD}" \
    | curl -sS "${curl_insecure[@]}" -X POST "${PROXMOX_URL%/}/access/ticket" \
      --data-urlencode "username=${PROXMOX_USERNAME}" \
      --data-urlencode "password@-")
  PVE_TICKET=$(echo "$auth_resp" | jq -r '.data.ticket')
  PVE_CSRF=$(echo "$auth_resp" | jq -r '.data.CSRFPreventionToken')
  if [[ $PVE_TICKET == "null" || -z $PVE_TICKET ]]; then
    echo "Proxmox authentication failed (no API token in env, and ticket auth failed): $auth_resp" >&2
    exit 1
  fi
  printf -v AUTH_HEADERS 'Cookie: PVEAuthCookie=%s\nCSRFPreventionToken: %s' "$PVE_TICKET" "$PVE_CSRF"
fi
WORKDIR=$(mktemp -d /tmp/ludus-metasploitable-import.XXXXXX)
trap 'rm -rf "$WORKDIR"' EXIT
echo "[2/9] Downloading source image from ${SOURCE_URL}..."
archive_path="${WORKDIR}/source.download"
curl -sS -fL --retry 3 -o "$archive_path" "${SOURCE_URL}"
echo "    Downloaded $(du -h "$archive_path" | cut -f1)"
if [[ -z ${SOURCE_CHECKSUM:-} ]]; then
  echo "ERROR: SOURCE_CHECKSUM is not set. Refusing to import an unverified disk image." >&2
  echo "       Set source_checksum in the template, or record the digest of the" >&2
  echo "       copy you already hold: sha256sum <file>" >&2
  exit 1
fi
checksum_algo="${SOURCE_CHECKSUM%%:*}"
checksum_want="${SOURCE_CHECKSUM#*:}"
case "$checksum_algo" in
  sha256) checksum_got=$(sha256sum "$archive_path" | cut -d" " -f1) ;;
  sha512) checksum_got=$(sha512sum "$archive_path" | cut -d" " -f1) ;;
  sha1) checksum_got=$(sha1sum "$archive_path" | cut -d" " -f1) ;;
  md5) checksum_got=$(md5sum "$archive_path" | cut -d" " -f1) ;;
  *)
    echo "ERROR: unsupported checksum algorithm '${checksum_algo}'." >&2
    exit 1
    ;;
esac
if [[ ${checksum_got,,} != "${checksum_want,,}" ]]; then
  echo "ERROR: checksum mismatch — refusing to import." >&2
  echo "       expected ${checksum_algo}:${checksum_want,,}" >&2
  echo "       got      ${checksum_algo}:${checksum_got,,}" >&2
  exit 1
fi
echo "    Verified ${checksum_algo} OK"
echo "[3/9] Extracting disk image (type: ${SOURCE_ARCHIVE_TYPE})..."
mkdir -p "${WORKDIR}/extracted"
case "${SOURCE_ARCHIVE_TYPE}" in
  zip)
    unzip -o -q "$archive_path" -d "${WORKDIR}/extracted"
    ;;
  vagrant-box)
    tar -xzf "$archive_path" -C "${WORKDIR}/extracted"
    ;;
  raw)
    cp "$archive_path" "${WORKDIR}/extracted/"
    ;;
  *)
    echo "Unknown SOURCE_ARCHIVE_TYPE: ${SOURCE_ARCHIVE_TYPE}" >&2
    exit 1
    ;;
esac
disk_file=$(find "${WORKDIR}/extracted" -iname "${SOURCE_DISK_GLOB}" | sort | head -n1)
if [[ -z $disk_file ]]; then
  echo "No disk image matching '${SOURCE_DISK_GLOB}' found inside the downloaded archive" >&2
  exit 1
fi
echo "    Found disk image: ${disk_file} ($(du -h "$disk_file" | cut -f1))"
echo "[4/9] Checking storage '${PROXMOX_STORAGE_POOL}' allows 'import' content (precondition — never mutated here)..."
current_content=$(api GET "/storage/${PROXMOX_STORAGE_POOL}" | jq -r '.data.content')
if [[ ",${current_content}," != *,import,* ]]; then
  echo "Storage '${PROXMOX_STORAGE_POOL}' does not allow 'import' content." >&2
  echo "This build will not modify cluster storage config (issue #153)." >&2
  echo "Enable it once, as the operator, then re-run the build:" >&2
  echo "  pvesh set /storage/${PROXMOX_STORAGE_POOL} --content ${current_content},import" >&2
  exit 1
fi
echo "    OK: '${PROXMOX_STORAGE_POOL}' already allows 'import' (content: ${current_content})"
echo "[5/9] Uploading disk image to Proxmox storage (large file, this can take a while)..."
upload_resp=$(
  curl -sS "${curl_insecure[@]}" -X POST \
    -H @- \
    -F "content=import" \
    -F "filename=@${disk_file}" \
    "${PROXMOX_URL%/}/nodes/${PROXMOX_HOST}/storage/${PROXMOX_STORAGE_POOL}/upload" << EOF
Cookie: PVEAuthCookie=${PVE_TICKET}
CSRFPreventionToken: ${PVE_CSRF}
EOF
)
upload_upid=$(echo "$upload_resp" | jq -r '.data')
if [[ -z $upload_upid || $upload_upid == "null" ]]; then
  echo "Upload failed to start: $upload_resp" >&2
  exit 1
fi
wait_task "$upload_upid"
echo "[6/9] Locating imported volume..."
base=$(basename "$disk_file")
volid=$(api GET "/nodes/${PROXMOX_HOST}/storage/${PROXMOX_STORAGE_POOL}/content?content=import" \
  | jq -r --arg base "$base" '.data[] | select(.volid | endswith($base)) | .volid' | head -n1)
if [[ -z $volid ]]; then
  echo "Could not find an imported volume ending in '${base}' on storage '${PROXMOX_STORAGE_POOL}'" >&2
  exit 1
fi
echo "    volid: ${volid}"
echo "[7/9] Creating VM..."
vmid=$(api GET "/cluster/nextid" | jq -r '.data')
mac=$(printf 'BC:24:11:%02X:%02X:%02X' $((RANDOM % 256)) $((RANDOM % 256)) $((RANDOM % 256)))
disk_args=()
if [[ ${GUEST_DISK_BUS:-scsi} == "ide" ]]; then
  disk_args+=(--data-urlencode "ide0=${PROXMOX_STORAGE_POOL}:0,import-from=${volid},format=${PROXMOX_STORAGE_FORMAT}")
  disk_args+=(--data-urlencode "boot=order=ide0")
else
  disk_args+=(--data-urlencode "scsihw=virtio-scsi-single")
  disk_args+=(--data-urlencode "scsi0=${PROXMOX_STORAGE_POOL}:0,import-from=${volid},format=${PROXMOX_STORAGE_FORMAT},discard=on")
  disk_args+=(--data-urlencode "boot=order=scsi0")
fi
create_resp=$(api POST "/nodes/${PROXMOX_HOST}/qemu" \
  --data-urlencode "vmid=${vmid}" \
  --data-urlencode "name=${VM_NAME}" \
  --data-urlencode "memory=${VM_MEMORY}" \
  --data-urlencode "cores=${VM_CORES}" \
  --data-urlencode "cpu=${GUEST_CPU_TYPE:-host}" \
  --data-urlencode "ostype=l26" \
  "${disk_args[@]}" \
  --data-urlencode "net0=${GUEST_NIC_MODEL:-virtio}=${mac},bridge=${LUDUS_NAT_INTERFACE}" \
  --data-urlencode "agent=0" \
  --data-urlencode "pool=${PROXMOX_POOL}" \
  --data-urlencode "description=${TEMPLATE_DESCRIPTION}")
create_upid=$(echo "$create_resp" | jq -r '.data')
if [[ -z $create_upid || $create_upid == "null" ]]; then
  echo "VM create failed: $create_resp" >&2
  exit 1
fi
wait_task "$create_upid"
echo "    Created VM ${vmid} (${VM_NAME}), MAC ${mac}"
echo "    Removing spent import volume '${volid}' (its data is now copied into the VM's own disk)..."
# shellcheck disable=SC2310 # the spent import volume is best-effort cleanup; the VM already owns its disk
api DELETE "/nodes/${PROXMOX_HOST}/storage/${PROXMOX_STORAGE_POOL}/content/${volid}" > /dev/null || true
echo "[8/9] Starting VM and waiting for a DHCP lease + SSH..."
api POST "/nodes/${PROXMOX_HOST}/qemu/${vmid}/status/start" > /dev/null
mac_lower=$(echo "$mac" | tr '[:upper:]' '[:lower:]')
ip=""
for _ in $(seq 1 60); do
  ip=$(grep -i "$mac_lower" /var/lib/misc/dnsmasq.leases 2> /dev/null | awk '{print $3}' | tail -n1 || true)
  [[ -n $ip ]] && break
  sleep 5
done
if [[ -z $ip ]]; then
  echo "Timed out waiting for a DHCP lease for ${mac} on the build network" >&2
  exit 1
fi
echo "    VM ${vmid} leased ${ip}"
ssh_extra_opts=()
if [[ ${SSH_LEGACY_CRYPTO:-true} == "true" ]]; then
  ssh_extra_opts=(
    -o HostKeyAlgorithms=+ssh-rsa
    -o PubkeyAcceptedKeyTypes=+ssh-rsa
    -o KexAlgorithms=+diffie-hellman-group1-sha1
    -o Ciphers=+aes128-cbc
  )
fi
ssh_ok=false
for _ in $(seq 1 30); do
  if sshpass -p "${SSH_PASSWORD}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=5 "${ssh_extra_opts[@]}" "${SSH_USERNAME}@${ip}" true 2> /dev/null; then
    ssh_ok=true
    break
  fi
  sleep 5
done
if [[ $ssh_ok != "true" ]]; then
  echo "Timed out waiting for SSH on ${ip}" >&2
  exit 1
fi
echo "[9/9] Provisioning over SSH, then shutting down and converting to a Ludus template..."
ssh_common_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
if [[ ${SSH_LEGACY_CRYPTO:-true} == "true" ]]; then
  ssh_common_args="${ssh_common_args} -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa -o KexAlgorithms=+diffie-hellman-group1-sha1 -o Ciphers=+aes128-cbc"
fi
echo "Installing the shared get_sybers.templates collection (requirements.yml)..."
ansible-galaxy collection install -r "${ANSIBLE_REQUIREMENTS}" -p "${ANSIBLE_COLLECTIONS_PATH}" --no-deps --force
ANSIBLE_LOCAL_TEMP="${ANSIBLE_HOME}/tmp" \
  ANSIBLE_PERSISTENT_CONTROL_PATH_DIR="${ANSIBLE_HOME}/pc" \
  ANSIBLE_SSH_CONTROL_PATH_DIR="${ANSIBLE_HOME}/cp" \
  ANSIBLE_COLLECTIONS_PATH="${ANSIBLE_COLLECTIONS_PATH}" \
  ansible-playbook -i "${ip}," -u "${SSH_USERNAME}" \
  --extra-vars "ansible_password=${SSH_PASSWORD} ansible_sudo_pass=${SSH_PASSWORD} ansible_python_interpreter=auto_silent" \
  --ssh-common-args="${ssh_common_args}" \
  "${ANSIBLE_PLAYBOOK}"
api POST "/nodes/${PROXMOX_HOST}/qemu/${vmid}/status/stop" > /dev/null
stopped=false
for _ in $(seq 1 30); do
  st=$(api GET "/nodes/${PROXMOX_HOST}/qemu/${vmid}/status/current" | jq -r '.data.status')
  if [[ $st == "stopped" ]]; then
    stopped=true
    break
  fi
  sleep 5
done
if [[ $stopped != "true" ]]; then
  echo "VM ${vmid} did not reach 'stopped' state in time; refusing to convert it to a template" >&2
  exit 1
fi
template_resp=$(api POST "/nodes/${PROXMOX_HOST}/qemu/${vmid}/template")
template_err=$(echo "$template_resp" | jq -r '.message // empty')
if [[ -n $template_err ]]; then
  echo "Converting VM ${vmid} to a template failed: ${template_err}" >&2
  exit 1
fi
template_upid=$(echo "$template_resp" | jq -r '.data')
if [[ -n $template_upid && $template_upid != "null" ]]; then
  wait_task "$template_upid"
fi
echo "Done. Template '${VM_NAME}' is VM ${vmid} on node ${PROXMOX_HOST}."
