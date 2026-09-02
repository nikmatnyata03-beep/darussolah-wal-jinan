#!/usr/bin/env bash
set -euo pipefail

: "${SUPABASE_DB_URL:?SUPABASE_DB_URL is required}"
: "${SUPABASE_URL:?SUPABASE_URL is required}"
: "${SUPABASE_SERVICE_ROLE_KEY:?SUPABASE_SERVICE_ROLE_KEY is required}"
: "${BACKUP_S3_URI:?BACKUP_S3_URI is required}"

if [[ -n "${SUPABASE_STORAGE_BUCKETS:-}" ]]; then
  IFS=',' read -r -a raw_buckets <<< "${SUPABASE_STORAGE_BUCKETS}"
elif [[ -n "${SUPABASE_STORAGE_BUCKET:-}" ]]; then
  raw_buckets=("${SUPABASE_STORAGE_BUCKET}")
else
  printf '%s\n' 'SUPABASE_STORAGE_BUCKET or SUPABASE_STORAGE_BUCKETS is required' >&2
  exit 1
fi

buckets=()
for bucket in "${raw_buckets[@]}"; do
  bucket="$(printf '%s' "$bucket" | xargs)"
  [[ -n "$bucket" ]] || { printf '%s\n' 'Storage bucket names cannot be empty' >&2; exit 1; }
  buckets+=("$bucket")
done

command -v pg_dump >/dev/null || { printf '%s\n' 'pg_dump is required' >&2; exit 1; }
command -v python >/dev/null || { printf '%s\n' 'python is required' >&2; exit 1; }
command -v aws >/dev/null || { printf '%s\n' 'aws CLI is required' >&2; exit 1; }

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
workdir="$(mktemp -d)"
archive="${workdir}/darussolah-${timestamp}.tar.gz"
trap 'rm -rf "$workdir"' EXIT

mkdir -p "${workdir}/storage"
pg_dump --format=custom --no-owner --no-privileges --file="${workdir}/database.dump" "${SUPABASE_DB_URL}"

for bucket in "${buckets[@]}"; do
  [[ "$bucket" =~ ^[A-Za-z0-9._-]+$ ]] || {
    printf 'invalid Storage bucket name: %s\n' "$bucket" >&2
    exit 1
  }
  python scripts/backup_storage.py --bucket "$bucket" --output "${workdir}/storage/${bucket}"
done

BACKUP_TIMESTAMP="$timestamp" BACKUP_BUCKETS="$(IFS=,; printf '%s' "${buckets[*]}")" \
  python - "${workdir}/metadata.json" <<'PY'
import json
import os
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(json.dumps({
    "created_at": os.environ["BACKUP_TIMESTAMP"],
    "storage_buckets": [item for item in os.environ["BACKUP_BUCKETS"].split(",") if item],
}, indent=2) + "\n", encoding="utf-8")
PY

python - "${workdir}" > "${workdir}/checksums.txt" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "checksums.txt")
for path in files:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    print(f"{digest.hexdigest()}  {path.relative_to(root)}")
PY

tar -C "${workdir}" -czf "${archive}" database.dump storage metadata.json checksums.txt

aws_args=()
if [[ -n "${AWS_ENDPOINT_URL:-}" ]]; then
  aws_args+=(--endpoint-url "${AWS_ENDPOINT_URL}")
fi
aws "${aws_args[@]}" s3 cp "${archive}" "${BACKUP_S3_URI%/}/darussolah-${timestamp}.tar.gz" --only-show-errors
printf 'backup uploaded: darussolah-%s.tar.gz\n' "$timestamp"
