#!/usr/bin/env python3
"""Import independently reviewed Palworld answers into the production account database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.multigame_jobs import (
    JOB_TIMEOUT_MINUTES,
    MultiGameJobError,
    canonical_json,
    parse_time,
    read_json_file,
    validate_result_envelope,
    validate_signed_job,
    write_json_atomic,
)
from backend.store import (
    InsufficientCreditsError,
    StoreError,
    complete_queued_question,
    connect,
    hold_queued_question,
)


DEFAULT_DATABASE = Path(os.environ.get("RAIDBENCH_DB_PATH", "/data/raidbench.db"))
DEFAULT_QUEUE_ROOT = Path(os.environ.get("RAIDBENCH_JOB_QUEUE_DIR", "/jobs"))


class AnswerImportError(RuntimeError):
    pass


def read_policy() -> dict[str, Any]:
    value = json.loads((ROOT / "content" / "answer-quality-policy.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AnswerImportError("The active paid-answer policy is invalid.")
    return value


def validate_database_match(connection: sqlite3.Connection, job: dict[str, Any]) -> None:
    row = connection.execute(
        "SELECT game, question_type, question_text, input_json, credits_cost, credits_charged, status FROM questions WHERE id = ?",
        (job["questionId"],),
    ).fetchone()
    if not row:
        raise AnswerImportError("The signed job does not match a stored question.")
    expected = {
        "game": job["game"],
        "questionType": job["productId"],
        "questionText": job["questionText"],
        "inputs": job["inputs"],
        "creditsCost": int(job["creditsQuoted"]),
    }
    actual = {
        "game": row["game"],
        "questionType": row["question_type"],
        "questionText": row["question_text"],
        "inputs": json.loads(row["input_json"]),
        "creditsCost": int(row["credits_cost"]),
    }
    if canonical_json(actual) != canonical_json(expected):
        raise AnswerImportError("The signed job no longer matches the stored question.")
    if row["status"] == "ready":
        return
    if row["status"] != "queued" or int(row["credits_charged"]) != 0:
        raise AnswerImportError("The stored question is no longer eligible for Agent delivery.")


def move_artifact(source: Path, destination_dir: Path) -> None:
    if not source.exists():
        return
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    if destination.exists():
        if source.read_bytes() == destination.read_bytes():
            source.unlink()
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = destination_dir / f"{source.stem}-{timestamp}{source.suffix}"
    source.replace(destination)


def expire_old_questions(connection: sqlite3.Connection, queue_root: Path, timeout_minutes: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    rows = connection.execute(
        "SELECT id, submitted_at FROM questions WHERE status = 'queued' AND credits_charged = 0"
    ).fetchall()
    expired = 0
    for row in rows:
        try:
            is_expired = parse_time(row["submitted_at"]) <= cutoff
        except MultiGameJobError:
            is_expired = True
        if not is_expired:
            continue
        hold_queued_question(
            connection,
            row["id"],
            "The independent review did not finish within the delivery window. No credits were charged; the reserved credits are available again.",
        )
        job_name = f"job_{row['id']}.json"
        move_artifact(queue_root / "inbox" / job_name, queue_root / "archive")
        move_artifact(queue_root / "outbox" / job_name, queue_root / "archive")
        expired += 1
    return expired


def import_result(
    connection: sqlite3.Connection,
    job: dict[str, Any],
    result: dict[str, Any],
    policy: dict[str, Any],
) -> str:
    validate_database_match(connection, job)
    errors = validate_result_envelope(job, result, policy)
    if errors:
        raise AnswerImportError("; ".join(errors))
    if result["status"] == "held_without_charge":
        hold_queued_question(connection, job["questionId"], result["reason"])
        return "held_without_charge"
    try:
        complete_queued_question(connection, job["questionId"], result["answer"])
    except InsufficientCreditsError:
        hold_queued_question(
            connection,
            job["questionId"],
            "The account balance changed before delivery. No credits were charged for this request.",
        )
        return "held_without_charge"
    return "approved"


def execute(database: Path, queue_root: Path, signing_secret: str, timeout_minutes: int) -> dict[str, int]:
    if len(signing_secret) < 32:
        raise AnswerImportError("RAIDBENCH_JOB_SIGNING_SECRET must contain at least 32 characters.")
    for directory in ("inbox", "outbox", "archive", "rejected"):
        (queue_root / directory).mkdir(parents=True, exist_ok=True)
    policy = read_policy()
    summary = {"found": 0, "approved": 0, "heldWithoutCharge": 0, "rejected": 0, "expired": 0}
    connection = connect(database)
    try:
        summary["expired"] = expire_old_questions(connection, queue_root, timeout_minutes)
        for result_path in sorted((queue_root / "outbox").glob("job_*.json")):
            summary["found"] += 1
            job_path = queue_root / "inbox" / result_path.name
            job: dict[str, Any] | None = None
            try:
                job = read_json_file(job_path)
                validate_signed_job(job, signing_secret)
                result = read_json_file(result_path)
                outcome = import_result(connection, job, result, policy)
            except (AnswerImportError, MultiGameJobError, StoreError, OSError, ValueError, sqlite3.Error) as error:
                summary["rejected"] += 1
                if isinstance(job, dict) and job.get("questionId"):
                    try:
                        hold_queued_question(
                            connection,
                            str(job["questionId"]),
                            "The Agent result failed the production release checks. No credits were charged.",
                        )
                    except StoreError:
                        pass
                write_json_atomic(queue_root / "rejected" / f"{result_path.stem}.error.json", {
                    "rejectedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "artifact": result_path.name,
                    "error": str(error)[:2000],
                })
                move_artifact(result_path, queue_root / "rejected")
                if job_path.exists():
                    move_artifact(job_path, queue_root / "rejected")
                continue
            summary["approved" if outcome == "approved" else "heldWithoutCharge"] += 1
            move_artifact(job_path, queue_root / "archive")
            move_artifact(result_path, queue_root / "archive")
    finally:
        connection.close()
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import reviewed RaidBench customer answers.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--queue-root", type=Path, default=DEFAULT_QUEUE_ROOT)
    parser.add_argument("--timeout-minutes", type=int, default=JOB_TIMEOUT_MINUTES)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = execute(
            args.database,
            args.queue_root,
            os.environ.get("RAIDBENCH_JOB_SIGNING_SECRET", ""),
            args.timeout_minutes,
        )
    except (AnswerImportError, MultiGameJobError, OSError, ValueError, sqlite3.Error) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps(summary, ensure_ascii=True, separators=(",", ":")))
    return 0 if summary["rejected"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
