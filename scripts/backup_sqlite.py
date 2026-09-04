#!/usr/bin/env python3
"""Create and verify a rolling SQLite backup for RaidBench."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keep", type=int, default=14)
    args = parser.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"Database does not exist: {args.db}")
    args.out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = args.out / f"raidbench-{timestamp}.db"

    source = sqlite3.connect(str(args.db), timeout=20)
    backup = sqlite3.connect(str(destination))
    try:
        source.backup(backup)
        result = backup.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError("SQLite backup integrity check failed.")
    finally:
        backup.close()
        source.close()
    destination.chmod(0o600)

    backups = sorted(args.out.glob("raidbench-*.db"), reverse=True)
    for expired in backups[max(1, args.keep):]:
        expired.unlink()
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
