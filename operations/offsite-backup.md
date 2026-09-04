# RaidBench Encrypted Offsite Backup

Last updated: 2026-08-02

## Design

RaidBench uses two independent backup layers:

1. `raidbench-backup.timer` creates a verified SQLite snapshot on the VPS.
2. `raidbench-offsite-backup.timer` encrypts the latest verified snapshot with restic and uploads it to
   the private Cloudflare R2 bucket `raidbench-backups`.

The upload job never reads the live SQLite database or its WAL files. It refuses to upload when the
latest local snapshot fails `PRAGMA integrity_check`.

## Cloudflare R2 Boundary

- Storage class: Standard.
- Public access: disabled.
- API permission: Object Read & Write.
- Token scope: the `raidbench-backups` bucket only.
- S3 endpoint: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.

Do not use an account-wide R2 administrator token for the VPS.

## VPS Secrets

Create `/opt/raidbench/secrets/offsite-backup.env` from
`deploy/offsite-backup.env.example` and set mode `600`. Store the restic repository password in
`/opt/raidbench/secrets/restic-password`, also with mode `600`.

The repository password must also be retained outside the VPS. RaidBench keeps an owner recovery copy
on the local Mac, outside the repository. Losing this password makes the encrypted backup unrecoverable.

## Initial Activation

```bash
apt-get update
apt-get install -y restic
install -m 0755 scripts/backup_offsite.sh /opt/raidbench/bin/backup_offsite.sh
install -m 0644 deploy/raidbench-offsite-backup.service /etc/systemd/system/
install -m 0644 deploy/raidbench-offsite-backup.timer /etc/systemd/system/
systemctl daemon-reload
set -a
. /opt/raidbench/secrets/offsite-backup.env
set +a
restic snapshots || restic init
systemctl start raidbench-backup.service
systemctl start raidbench-offsite-backup.service
systemctl enable --now raidbench-offsite-backup.timer
```

Never print the environment file, access keys, or repository password in a terminal recording or
operations report.

## Retention And Verification

The offsite job keeps 14 daily, 8 weekly, and 12 monthly snapshots. After each upload it prunes expired
data and verifies repository structure plus a random five-percent data subset.

```bash
systemctl status raidbench-offsite-backup.timer
journalctl -u raidbench-offsite-backup.service -n 100 --no-pager
```

## Restore Drill

Restore into an empty temporary directory; never overwrite the production database during a drill.

```bash
set -a
. /opt/raidbench/secrets/offsite-backup.env
set +a
restore_dir="$(mktemp -d /tmp/raidbench-restore.XXXXXX)"
restic restore latest --target "${restore_dir}"
restored_db="$(find "${restore_dir}" -type f -name 'raidbench-*.db' | head -n 1)"
python3 - "${restored_db}" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
try:
    print(connection.execute("PRAGMA integrity_check").fetchone()[0])
finally:
    connection.close()
PY
rm -rf "${restore_dir}"
```

Acceptance requires `ok` from the restored database, not only a successful upload message.
