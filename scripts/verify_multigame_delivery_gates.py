#!/usr/bin/env python3
"""Verify hidden multi-game answers against the production delivery code in an isolated database."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.store import (
    account_summary,
    connect,
    create_verified_question,
    get_or_create_demo_customer,
    grant_demo_order,
    init_database,
    list_questions,
)
from scripts.run_shadow_answer_benchmarks import connect_database, evaluate_readiness, read_json, utc_now, write_json


DEFAULT_SHADOW_DATABASE = ROOT / "local" / "raidbench.shadow.db"
DEFAULT_OUTPUT = ROOT / "local" / "multigame-delivery-gates.json"
DEFAULT_READINESS = ROOT / "local" / "multigame-shadow-readiness.json"


class DeliveryGateError(RuntimeError):
    pass


def delivery_code_fingerprint() -> str:
    digest = hashlib.sha256()
    for relative in (
        "backend/store.py",
        "local/raidbench-local-schema.sql",
        "content/skus.json",
        "content/multigame-products.json",
    ):
        digest.update(relative.encode("utf-8"))
        digest.update((ROOT / relative).read_bytes())
    return digest.hexdigest()


def find_answer_file(artifact_dir: str) -> Path:
    directory = ROOT / artifact_dir
    for name in ("04-reviewed-paid-answer.json", "03-reviewed-paid-answer.json"):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    raise DeliveryGateError(f"Reviewed answer is missing from {artifact_dir}")


def verify_product_delivery(answer: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
    if product.get("status") not in {"hidden_pending_qa", "ready_live"}:
        raise DeliveryGateError("Delivery gates require a hidden or controlled-live product.")
    with tempfile.TemporaryDirectory(prefix="raidbench-delivery-gate-") as temporary:
        database = Path(temporary) / "delivery.db"
        init_database(
            database,
            ROOT / "local" / "raidbench-local-schema.sql",
            ROOT / "content" / "skus.json",
            ROOT / "content" / "multigame-products.json",
        )
        with closing(connect(database)) as connection:
            customer = get_or_create_demo_customer(connection)
            grant_demo_order(connection, customer["id"], "credits-command-450", f"delivery-credit-{product['id']}")
            starting_balance = account_summary(connection, customer["id"])["creditBalance"]
            connection.execute(
                "UPDATE credit_actions SET status = 'ready_private_demo' WHERE id = ?",
                (product["id"],),
            )
            idempotency_key = f"delivery-answer-{product['id']}"
            question = create_verified_question(
                connection,
                customer["id"],
                product["id"],
                product["id"],
                str(answer.get("customerQuestion") or "Shadow delivery verification"),
                answer.get("intake", {}).get("customerFacts", {}),
                answer,
                idempotency_key,
                game=str(answer.get("game") or product["gameId"]),
            )
            balance_after_first = account_summary(connection, customer["id"])["creditBalance"]
            replay = create_verified_question(
                connection,
                customer["id"],
                product["id"],
                product["id"],
                str(answer.get("customerQuestion") or "Shadow delivery verification"),
                answer.get("intake", {}).get("customerFacts", {}),
                answer,
                idempotency_key,
                game=str(answer.get("game") or product["gameId"]),
            )
            balance_after_replay = account_summary(connection, customer["id"])["creditBalance"]
            questions = list_questions(connection, customer["id"])
            debit_count = connection.execute(
                "SELECT COUNT(*) AS count FROM credit_ledger WHERE customer_id = ? AND entry_type = 'answer_debit'",
                (customer["id"],),
            ).fetchone()["count"]
            delivery_count = connection.execute(
                "SELECT COUNT(*) AS count FROM delivery_records WHERE customer_id = ? AND action_id = ?",
                (customer["id"], product["id"]),
            ).fetchone()["count"]

    expected_balance = starting_balance - int(product["credits"])
    delivery_passed = (
        question["status"] == "ready"
        and question["game"] == answer.get("game")
        and question["answer"] == answer
        and len(questions) == 1
        and delivery_count == 1
    )
    idempotency_passed = (
        replay["id"] == question["id"]
        and balance_after_first == expected_balance
        and balance_after_replay == expected_balance
        and debit_count == 1
    )
    return {
        "productId": product["id"],
        "credits": int(product["credits"]),
        "firstBalance": starting_balance,
        "balanceAfterFirst": balance_after_first,
        "balanceAfterReplay": balance_after_replay,
        "questionCount": len(questions),
        "debitCount": debit_count,
        "deliveryCount": delivery_count,
        "idempotencyPassed": idempotency_passed,
        "inAccountDeliveryPassed": delivery_passed,
    }


def execute(shadow_database: Path, output: Path, readiness_report: Path) -> dict[str, Any]:
    products = read_json(ROOT / "content" / "multigame-products.json")["products"]
    product_by_id = {item["id"]: item for item in products}
    connection = connect_database(shadow_database)
    code_fingerprint = delivery_code_fingerprint()
    existing_delivery = {
        row["product_id"]: dict(row)
        for row in connection.execute("SELECT * FROM delivery_gate_results").fetchall()
    }
    rows = connection.execute(
        """
        SELECT * FROM shadow_benchmark_results
        WHERE actual_disposition = 'qa_approved' AND deterministic_status = 'pass'
        ORDER BY product_id, updated_at DESC
        """
    ).fetchall()
    latest_by_product: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = dict(row)
        latest_by_product.setdefault(value["product_id"], value)

    results = []
    try:
        for product in products:
            benchmark = latest_by_product.get(product["id"])
            if not benchmark:
                results.append({
                    "productId": product["id"],
                    "status": "no_approved_answer",
                    "idempotencyPassed": False,
                    "inAccountDeliveryPassed": False,
                })
                continue
            answer_path = find_answer_file(benchmark["artifact_dir"])
            answer = read_json(answer_path)
            answer_fingerprint = hashlib.sha256(answer_path.read_bytes()).hexdigest()
            existing = existing_delivery.get(product["id"])
            if (
                existing
                and existing["benchmark_key"] == benchmark["benchmark_key"]
                and existing["answer_fingerprint"] == answer_fingerprint
                and existing["delivery_code_fingerprint"] == code_fingerprint
                and bool(existing["idempotency_passed"])
                and bool(existing["in_account_delivery_passed"])
            ):
                details = json.loads(existing["details_json"] or "{}")
                details.update({
                    "productId": product["id"],
                    "status": "unchanged_pass",
                    "benchmarkKey": benchmark["benchmark_key"],
                    "answerFingerprint": answer_fingerprint,
                    "verifiedAt": existing["verified_at"],
                    "idempotencyPassed": True,
                    "inAccountDeliveryPassed": True,
                })
                results.append(details)
                continue
            result = verify_product_delivery(answer, product)
            result.update({
                "status": "pass" if result["idempotencyPassed"] and result["inAccountDeliveryPassed"] else "failed",
                "benchmarkKey": benchmark["benchmark_key"],
                "answerFingerprint": answer_fingerprint,
                "verifiedAt": utc_now(),
            })
            connection.execute(
                "UPDATE shadow_benchmark_results SET answer_fingerprint = ? WHERE benchmark_key = ?",
                (answer_fingerprint, benchmark["benchmark_key"]),
            )
            connection.execute(
                """
                INSERT INTO delivery_gate_results (
                  product_id, benchmark_key, answer_fingerprint, idempotency_passed,
                  delivery_code_fingerprint, in_account_delivery_passed, first_balance, balance_after_first,
                  balance_after_replay, question_count, verified_at, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                  benchmark_key=excluded.benchmark_key,
                  answer_fingerprint=excluded.answer_fingerprint,
                  delivery_code_fingerprint=excluded.delivery_code_fingerprint,
                  idempotency_passed=excluded.idempotency_passed,
                  in_account_delivery_passed=excluded.in_account_delivery_passed,
                  first_balance=excluded.first_balance,
                  balance_after_first=excluded.balance_after_first,
                  balance_after_replay=excluded.balance_after_replay,
                  question_count=excluded.question_count,
                  verified_at=excluded.verified_at,
                  details_json=excluded.details_json
                """,
                (
                    product["id"], benchmark["benchmark_key"], answer_fingerprint,
                    int(result["idempotencyPassed"]), code_fingerprint, int(result["inAccountDeliveryPassed"]),
                    result["firstBalance"], result["balanceAfterFirst"], result["balanceAfterReplay"],
                    result["questionCount"], result["verifiedAt"],
                    json.dumps(result, ensure_ascii=True, separators=(",", ":")),
                ),
            )
            results.append(result)
        readiness = evaluate_readiness(connection, readiness_report)
    finally:
        connection.close()

    report = {
        "generatedAt": utc_now(),
        "mode": "isolated_ephemeral_commerce_database",
        "summary": {
            "products": len(products),
            "testedProducts": sum(item["status"] != "no_approved_answer" for item in results),
            "passedProducts": sum(item["status"] in {"pass", "unchanged_pass"} for item in results),
            "productionOrdersCreated": 0,
            "productionCreditsCharged": 0,
            "readinessEligibleProducts": readiness["summary"]["eligibleProducts"],
        },
        "products": results,
    }
    write_json(output, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify multi-game in-account delivery and idempotency in isolated temporary databases.")
    parser.add_argument("--shadow-database", type=Path, default=DEFAULT_SHADOW_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--readiness-report", type=Path, default=DEFAULT_READINESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = execute(args.shadow_database, args.output, args.readiness_report)
    except (DeliveryGateError, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps(report["summary"]))
    return 0 if report["summary"]["passedProducts"] == report["summary"]["testedProducts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
