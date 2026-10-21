#!/usr/bin/env bash
set -euo pipefail
ENDPOINT="http://localhost:4566"
echo "Waiting for LocalStack to be healthy..."
for _ in $(seq 1 30); do
  if curl -sf "${ENDPOINT}/_localstack/health" > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
echo "Creating S3 bucket: konoha-cloud-backup"
awslocal s3 mb s3://konoha-cloud-backup
echo "Seeding bucket with a plausible 'backup' object (so it isn't empty on first enumeration)"
cat > /tmp/village-backup-manifest.txt << 'EOF'
KONOHA IT -- CLOUD BACKUP MANIFEST
Nightly sync job, automated. Do not delete objects manually -- restore chain depends on
sequential upload order. Contact IT if a restore is needed.
EOF
awslocal s3 cp /tmp/village-backup-manifest.txt s3://konoha-cloud-backup/manifests/latest.txt
rm -f /tmp/village-backup-manifest.txt
echo "Creating IAM user with an overly broad policy (intentional misconfiguration)"
awslocal iam create-user --user-name konoha-it-svc
awslocal iam put-user-policy \
  --user-name konoha-it-svc \
  --policy-name AllS3Access \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:*","Resource":"*"}]}'
awslocal iam create-access-key --user-name konoha-it-svc > /tmp/konoha-it-svc-keys.json
echo "IAM access keys written to /tmp/konoha-it-svc-keys.json on this host (intentionally"
echo "discoverable -- a red-team exercise finding this file is the point, not a leak to fix)."
echo "LocalStack seed complete."
