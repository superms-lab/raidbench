#!/usr/bin/env python3
"""Export privacy-minimized production status for the private owner dashboard."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PRODUCT_ID = "palworld-base-progression-review"


def scalar(connection: sqlite3.Connection, query: str, parameters: tuple = ()) -> int:
    return int(connection.execute(query, parameters).fetchone()[0])


def execute(database: Path, queue_root: Path, release_link: Path) -> dict:
    connection = sqlite3.connect(database)
    try:
        queued = scalar(connection, "SELECT COUNT(*) FROM questions WHERE question_type = ? AND status = 'queued'", (PRODUCT_ID,))
        delivered = scalar(connection, "SELECT COUNT(*) FROM questions WHERE question_type = ? AND status = 'ready'", (PRODUCT_ID,))
        held = scalar(connection, "SELECT COUNT(*) FROM questions WHERE question_type = ? AND status = 'needs_review'", (PRODUCT_ID,))
        credits = scalar(connection, "SELECT COALESCE(SUM(credits_charged), 0) FROM questions WHERE question_type = ?", (PRODUCT_ID,))
        debits = scalar(connection, "SELECT COUNT(*) FROM credit_ledger WHERE idempotency_key LIKE 'queued-answer:qst_%'")
        deliveries = scalar(connection, "SELECT COUNT(*) FROM delivery_records WHERE action_id = ?", (PRODUCT_ID,))
        unsafe = scalar(
            connection,
            """
            SELECT COUNT(*) FROM questions
            WHERE question_type = ? AND (
              (status != 'ready' AND credits_charged != 0)
              OR (status = 'ready' AND (qa_status != 'approved' OR credits_charged != credits_cost))
            )
            """,
            (PRODUCT_ID,),
        )
    finally:
        connection.close()
    release = ""
    try:
        release = str(release_link.resolve(strict=True))
    except OSError:
        release = "unresolved"
    return {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "productId": PRODUCT_ID,
        "release": release,
        "status": "healthy" if unsafe == 0 and debits == deliveries == delivered else "attention_required",
        "metrics": {
            "queued": queued,
            "delivered": delivered,
            "heldWithoutCharge": held,
            "creditsCharged": credits,
            "debitRows": debits,
            "deliveryRows": deliveries,
            "unsafeRows": unsafe,
            "inboxFiles": len(list((queue_root / "inbox").glob("job_*.json"))),
            "outboxFiles": len(list((queue_root / "outbox").glob("job_*.json"))),
            "rejectedFiles": len(list((queue_root / "rejected").glob("job_*.json"))),
        },
        "privacy": "No customer email, question text, payment identifier, or answer content is exported.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the private RaidBench multi-game live status.")
    parser.add_argument("--database", type=Path, default=Path("/opt/raidbench/data/raidbench.db"))
    parser.add_argument("--queue-root", type=Path, default=Path("/opt/raidbench/jobs"))
    parser.add_argument("--release-link", type=Path, default=Path("/opt/raidbench/app"))
    args = parser.parse_args()
    try:
        report = execute(args.database, args.queue_root, args.release_link)
    except (OSError, sqlite3.Error) as error:
        print(json.dumps({"status": "unavailable", "error": str(error)}, ensure_ascii=True))
        return 1
    print(json.dumps(report, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
