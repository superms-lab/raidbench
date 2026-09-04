#!/usr/bin/env bash

set -euo pipefail

umask 077

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD_FILE:?RESTIC_PASSWORD_FILE is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"

export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"
export RESTIC_CACHE_DIR="${RESTIC_CACHE_DIR:-/var/cache/raidbench-restic}"

backup_dir="${RAIDBENCH_BACKUP_DIR:-/opt/raidbench/data/backups}"
reference_data="${RAIDBENCH_REFERENCE_DATA_FILE:-/opt/raidbench/data/rust-raid-data.json}"
lock_file="${RAIDBENCH_OFFSITE_LOCK_FILE:-/run/lock/raidbench-offsite-backup.lock}"

exec 9>"${lock_file}"
if ! flock -n 9; then
  echo "A RaidBench offsite backup is already running." >&2
  exit 0
fi

latest_backup="$(find "${backup_dir}" -maxdepth 1 -type f -name 'raidbench-*.db' -printf '%T@ %p\n' \
  | sort -nr \
  | sed -n '1s/^[^ ]* //p')"

if [[ -z "${latest_backup}" ]]; then
  echo "No verified RaidBench SQLite backup was found in ${backup_dir}." >&2
  exit 1
fi

python3 - "${latest_backup}" <<'PY'
import sqlite3
import sys

path = sys.argv[1]
connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
try:
    result = connection.execute("PRAGMA integrity_check").fetchone()
finally:
    connection.close()

if not result or result[0] != "ok":
    raise SystemExit(f"SQLite integrity check failed for {path}")
PY

targets=("${latest_backup}")
if [[ -f "${reference_data}" ]]; then
  targets+=("${reference_data}")
fi

restic backup \
  --host raidbench-production \
  --tag raidbench \
  --tag sqlite-verified \
  "${targets[@]}"

restic forget \
  --host raidbench-production \
  --tag raidbench \
  --keep-daily 14 \
  --keep-weekly 8 \
  --keep-monthly 12 \
  --prune

restic check --read-data-subset=5%
