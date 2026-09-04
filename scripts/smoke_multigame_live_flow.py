#!/usr/bin/env python3
"""Run one no-money, end-to-end Palworld queue and delivery smoke test."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.multigame_jobs import build_signed_job, export_signed_job, write_json_atomic
from backend.multigame_products import route_multigame_request
from backend.store import (
    account_summary,
    connect,
    create_queued_question,
    get_or_create_demo_customer,
    grant_demo_order,
    init_database,
)
from scripts.import_multigame_answer_jobs import execute as import_answers
from scripts.process_multigame_answer_jobs import process_job
from scripts.run_shadow_answer_benchmarks import resolve_runtime


def request_payload() -> dict:
    return {
        "productId": "palworld-base-progression-review",
        "gameId": "palworld",
        "questionText": "Produced ore accumulates at the work area while nearby storage stays unchanged. Which handoff should I test first?",
        "inputs": {
            "gameVersion": "1.0",
            "serverType": "Dedicated server with no production-changing mods reported",
            "currentGoal": "Move produced ore into storage during one twenty-minute controlled observation",
            "baseOrProgressionState": "Player records work-area ore rising from 40 to 120 while destination storage remains at 200; assignments and layout stay unchanged",
            "observedProblem": "Production increases but the recorded destination storage does not",
        },
    }


def execute(root: Path, source_database: Path, timeout: int) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = root / f"phase8-live-smoke-{timestamp}"
    queue_root = run_root / "queue"
    artifact_root = run_root / "artifacts"
    database = run_root / "commerce.db"
    run_root.mkdir(parents=True, exist_ok=False)
    secret = "phase8-isolated-smoke-signing-secret-only"

    init_database(
        database,
        ROOT / "local" / "raidbench-local-schema.sql",
        ROOT / "content" / "skus.json",
        ROOT / "content" / "multigame-products.json",
    )
    routed = route_multigame_request(
        request_payload(),
        implemented_handlers={"palworld-base-progression-review"},
    )
    with closing(connect(database)) as connection:
        customer = get_or_create_demo_customer(connection)
        grant_demo_order(connection, customer["id"], "credits-command-450", f"{timestamp}-credits")
        question = create_queued_question(
            connection,
            customer["id"],
            routed["productId"],
            routed["questionText"],
            routed["inputs"],
            f"{timestamp}-question",
            routed["game"],
        )
        queued = account_summary(connection, customer["id"])
    job = build_signed_job(question, routed, secret)
    job_path = export_signed_job(queue_root, job)

    codex_bin = shutil.which("codex")
    node_bin = shutil.which("node")
    if not codex_bin or not node_bin:
        raise RuntimeError("Codex and Node are required for the live-flow smoke test.")
    result = process_job(
        job,
        source_database=source_database,
        case_dir=artifact_root / job["jobId"],
        codex_bin=codex_bin,
        node_bin=node_bin,
        runtime=resolve_runtime(),
        timeout=timeout,
    )
    write_json_atomic(queue_root / "outbox" / job_path.name, result)
    imported = import_answers(database, queue_root, secret, 30)
    repeated = import_answers(database, queue_root, secret, 30)

    with closing(connect(database)) as connection:
        delivered = connection.execute(
            "SELECT status, qa_status, credits_cost, credits_charged FROM questions WHERE id = ?",
            (question["id"],),
        ).fetchone()
        final_account = account_summary(connection, customer["id"])
        debit_count = connection.execute(
            "SELECT COUNT(*) count FROM credit_ledger WHERE idempotency_key = ?",
            (f"queued-answer:{question['id']}",),
        ).fetchone()["count"]
        delivery_count = connection.execute(
            "SELECT COUNT(*) count FROM delivery_records WHERE action_id = 'palworld-base-progression-review'",
        ).fetchone()["count"]
    report = {
        "mode": "isolated_no_money_smoke",
        "runRoot": str(run_root),
        "agentResult": result["status"],
        "queuedAccount": {
            "creditBalance": queued["creditBalance"],
            "reservedCredits": queued["reservedCredits"],
            "availableCredits": queued["availableCredits"],
        },
        "import": imported,
        "idempotentReplay": repeated,
        "storedQuestion": dict(delivered),
        "finalAccount": {
            "creditBalance": final_account["creditBalance"],
            "reservedCredits": final_account["reservedCredits"],
            "availableCredits": final_account["availableCredits"],
        },
        "debitCount": int(debit_count),
        "deliveryCount": int(delivery_count),
        "productionOrdersCreated": 0,
        "productionCreditsCharged": 0,
    }
    expected = {
        "agentResult": "approved",
        "storedStatus": "ready",
        "creditsCharged": 80,
        "finalBalance": 370,
        "debitCount": 1,
        "deliveryCount": 1,
    }
    observed = {
        "agentResult": report["agentResult"],
        "storedStatus": report["storedQuestion"]["status"],
        "creditsCharged": report["storedQuestion"]["credits_charged"],
        "finalBalance": report["finalAccount"]["creditBalance"],
        "debitCount": report["debitCount"],
        "deliveryCount": report["deliveryCount"],
    }
    report["passed"] = observed == expected and repeated["found"] == 0
    report["expected"] = expected
    report["observed"] = observed
    write_json_atomic(run_root / "smoke-report.json", report)
    if not report["passed"]:
        raise RuntimeError(f"Live-flow smoke test failed: {json.dumps(observed, sort_keys=True)}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a no-money Palworld customer-answer smoke test.")
    parser.add_argument("--root", type=Path, default=ROOT / "private-data" / "phase8-smoke")
    parser.add_argument("--source-database", type=Path, default=Path(os.environ.get("RAIDBENCH_LOCAL_DB_PATH", ROOT / "local" / "raidbench.local.db")))
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    try:
        report = execute(args.root, args.source_database, args.timeout)
    except Exception as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
