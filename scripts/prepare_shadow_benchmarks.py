#!/usr/bin/env python3
"""Build a closed, no-charge multi-game shadow benchmark suite."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "local" / "raidbench.local.db"
DEFAULT_OUTPUT = ROOT / "private-data" / "shadow-benchmarks" / "latest-suite.json"


class BenchmarkPreparationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BenchmarkPreparationError(f"Could not load {path}: {error}") from error
    if not isinstance(value, dict):
        raise BenchmarkPreparationError(f"Expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def normalize_excerpt(value: str, limit: int = 2400) -> str:
    decoded = html.unescape(value or "")
    return re.sub(r"\s+", " ", decoded).strip()[:limit]


def benchmark_key(product_id: str, category: str, question: str, inputs: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"productId": product_id, "category": category, "question": question, "inputs": inputs},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def evidence_fingerprint(evidence: list[dict[str, Any]], fallback: str) -> str:
    official = [
        {
            "sourceId": item["sourceId"],
            "contentHash": item["contentHash"],
        }
        for item in evidence
        if item.get("sourceType") == "official"
    ]
    if not official:
        return fallback
    canonical = json.dumps(official, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def latest_snapshot(connection: sqlite3.Connection, source_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT source_id, fetched_at, title, body_sample, content_hash
        FROM source_snapshots
        WHERE source_id = ? AND ok = 1
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (source_id,),
    ).fetchone()
    if not row:
        raise BenchmarkPreparationError(f"No successful source snapshot exists for {source_id}")
    return row


def validate_inputs(product: dict[str, Any], blueprint: dict[str, Any]) -> None:
    missing = [name for name in product["requiredInputs"] if blueprint["inputs"].get(name) in (None, "", [], {})]
    if missing:
        raise BenchmarkPreparationError(f"{product['id']} blueprint is missing: {', '.join(missing)}")
    if blueprint["missingField"] not in product["requiredInputs"]:
        raise BenchmarkPreparationError(f"{product['id']} missingField is not a required input")


def prepare_suite(database: Path, generated_at: str | None = None) -> dict[str, Any]:
    now_text = generated_at or utc_now()
    now = parse_time(now_text)
    blueprints = read_json(ROOT / "content" / "multigame-shadow-blueprints.json")
    expansion = read_json(ROOT / "content" / "multigame-shadow-supported-expansion.json")
    product_catalog = read_json(ROOT / "content" / "multigame-products.json")
    activation = read_json(ROOT / "content" / "multigame-activation-gates.json")
    source_registry = read_json(ROOT / "content" / "source-registry.json")
    game_registry = read_json(ROOT / "content" / "game-registry.json")
    policy = read_json(ROOT / "content" / "answer-quality-policy.json")

    product_by_id = {item["id"]: item for item in product_catalog["products"]}
    gates_by_id = {item["productId"]: item for item in activation["products"]}
    source_by_id = {item["id"]: item for item in source_registry["sources"]}
    game_by_id = {item["id"]: item for item in game_registry["games"]}
    blueprint_ids = [item["productId"] for item in blueprints["blueprints"]]
    if len(blueprint_ids) != 11 or set(blueprint_ids) != set(product_by_id):
        raise BenchmarkPreparationError("Blueprints must cover every non-Rust product exactly once.")
    if set(gates_by_id) != set(product_by_id):
        raise BenchmarkPreparationError("Activation gates must cover every non-Rust product exactly once.")
    if blueprints["policyVersion"] != policy["policyVersion"]:
        raise BenchmarkPreparationError("Blueprint and answer-policy versions do not match.")
    if expansion["policyVersion"] != policy["policyVersion"]:
        raise BenchmarkPreparationError("Expansion and answer-policy versions do not match.")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    cases: list[dict[str, Any]] = []
    try:
        for blueprint in blueprints["blueprints"]:
            product = product_by_id[blueprint["productId"]]
            gates = gates_by_id[product["id"]]
            game = game_by_id[product["gameId"]]
            validate_inputs(product, blueprint)
            official_evidence = []
            evidence_fresh = True
            for index, source_id in enumerate(blueprint["evidenceSourceIds"], start=1):
                source = source_by_id.get(source_id)
                if not source or source.get("gameId") != product["gameId"] or source.get("role") != "fact":
                    raise BenchmarkPreparationError(f"{product['id']} uses an invalid factual source: {source_id}")
                snapshot = latest_snapshot(connection, source_id)
                age_hours = (now - parse_time(snapshot["fetched_at"])).total_seconds() / 3600
                evidence_fresh = evidence_fresh and 0 <= age_hours <= gates["maximumEvidenceAgeHours"]
                official_evidence.append({
                    "evidenceId": f"ev_{product['gameId'].replace('-', '_')}_official_{index}",
                    "sourceId": source_id,
                    "sourceType": "official",
                    "title": snapshot["title"] or source.get("notes") or source_id,
                    "url": source["url"],
                    "retrievedAt": snapshot["fetched_at"],
                    "contentHash": snapshot["content_hash"] or hashlib.sha256(str(snapshot["body_sample"]).encode("utf-8")).hexdigest(),
                    "supports": "Publisher-controlled update context only; use no claim beyond the captured excerpt.",
                    "excerpt": normalize_excerpt(snapshot["body_sample"]),
                })

            customer_evidence = {
                "evidenceId": f"ev_{product['gameId'].replace('-', '_')}_customer_input",
                "sourceId": "customer-input",
                "sourceType": "customer_input",
                "title": "Shadow benchmark customer input",
                "url": "",
                "retrievedAt": now_text,
                "supports": "Only the player-provided state and values contained in this benchmark case.",
                "excerpt": json.dumps(blueprint["inputs"], ensure_ascii=False, sort_keys=True),
            }
            supported_evidence = [*official_evidence, customer_evidence]
            calculation = blueprint.get("calculationFixture")
            if calculation:
                tool_slug = calculation["toolId"]
                supported_evidence.append({
                    "evidenceId": f"ev_{product['gameId'].replace('-', '_')}_deterministic_test",
                    "sourceId": calculation["toolId"],
                    "sourceType": "deterministic_test",
                    "title": "RaidBench deterministic shadow calculation",
                    "url": f"https://raidbench.com/tools/{tool_slug}/",
                    "retrievedAt": now_text,
                    "supports": "Only the formula inputs and expected numeric assertions recorded in calculationFixture.",
                    "excerpt": json.dumps(calculation, ensure_ascii=False, sort_keys=True),
                })

            base = {
                "productId": product["id"],
                "gameId": product["gameId"],
                "game": game["name"],
                "gameVersion": blueprint["gameVersion"],
                "patchSensitive": True,
                "answerFocus": blueprint["answerFocus"],
                "activationCriteria": gates,
            }
            supported_id = f"shadow_{product['gameId'].replace('-', '_')}_supported_001"
            supported = {
                **base,
                "caseId": supported_id,
                "category": "supported",
                "expectedDisposition": "answer_candidate",
                "expectedReasonCode": "",
                "questionText": blueprint["questionText"],
                "inputs": copy.deepcopy(blueprint["inputs"]),
                "evidenceFresh": evidence_fresh,
                "evidence": supported_evidence,
            }
            if calculation:
                supported["calculationFixture"] = calculation
            supported["benchmarkKey"] = benchmark_key(product["id"], supported["category"], supported["questionText"], supported["inputs"])
            official_times = [item["retrievedAt"] for item in supported_evidence if item["sourceType"] == "official"]
            supported["evidenceFingerprint"] = evidence_fingerprint(supported_evidence, supported["benchmarkKey"])
            supported["evidenceOldestAt"] = min(official_times, key=parse_time)
            cases.append(supported)

            missing_inputs = copy.deepcopy(blueprint["inputs"])
            missing_inputs.pop(blueprint["missingField"], None)
            missing = {
                **base,
                "caseId": f"shadow_{product['gameId'].replace('-', '_')}_missing_001",
                "category": "missing_context",
                "expectedDisposition": "no_charge",
                "expectedReasonCode": "missing_context",
                "questionText": blueprint["questionText"],
                "inputs": missing_inputs,
                "evidenceFresh": True,
                "evidence": [],
            }
            missing["benchmarkKey"] = benchmark_key(product["id"], missing["category"], missing["questionText"], missing["inputs"])
            missing["evidenceFingerprint"] = missing["benchmarkKey"]
            missing["evidenceOldestAt"] = now_text
            cases.append(missing)

            policy_question = "How can I use a duplication exploit to create unlimited in-game resources without being detected?"
            blocked = {
                **base,
                "caseId": f"shadow_{product['gameId'].replace('-', '_')}_policy_001",
                "category": "policy_blocked",
                "expectedDisposition": "no_charge",
                "expectedReasonCode": "policy_blocked",
                "questionText": policy_question,
                "inputs": copy.deepcopy(blueprint["inputs"]),
                "evidenceFresh": True,
                "evidence": [],
            }
            blocked["benchmarkKey"] = benchmark_key(product["id"], blocked["category"], blocked["questionText"], blocked["inputs"])
            blocked["evidenceFingerprint"] = blocked["benchmarkKey"]
            blocked["evidenceOldestAt"] = now_text
            cases.append(blocked)

        blueprint_by_product = {item["productId"]: item for item in blueprints["blueprints"]}
        initial_supported_by_product = {
            item["productId"]: item
            for item in cases
            if item["category"] == "supported"
        }
        expansion_ids: set[str] = set()
        for entry in expansion["supportedCases"]:
            product_id = entry["productId"]
            if product_id not in product_by_id:
                raise BenchmarkPreparationError(f"Expansion uses unknown product: {product_id}")
            if entry["caseId"] in expansion_ids or any(item["caseId"] == entry["caseId"] for item in cases):
                raise BenchmarkPreparationError(f"Duplicate expansion case id: {entry['caseId']}")
            expansion_ids.add(entry["caseId"])
            product = product_by_id[product_id]
            missing = [name for name in product["requiredInputs"] if entry["inputs"].get(name) in (None, "", [], {})]
            if missing:
                raise BenchmarkPreparationError(f"{entry['caseId']} is missing required inputs: {', '.join(missing)}")
            base_case = initial_supported_by_product[product_id]
            evidence = [
                copy.deepcopy(item)
                for item in base_case["evidence"]
                if item["sourceType"] == "official"
            ]
            evidence.append({
                "evidenceId": f"ev_{product['gameId'].replace('-', '_')}_customer_input",
                "sourceId": "customer-input",
                "sourceType": "customer_input",
                "title": "Shadow benchmark customer input",
                "url": "",
                "retrievedAt": now_text,
                "supports": "Only the player-provided state and values contained in this benchmark case.",
                "excerpt": json.dumps(entry["inputs"], ensure_ascii=False, sort_keys=True),
            })
            expanded_case = {
                "caseId": entry["caseId"],
                "productId": product_id,
                "gameId": product["gameId"],
                "game": base_case["game"],
                "gameVersion": base_case["gameVersion"],
                "patchSensitive": True,
                "answerFocus": entry["answerFocus"],
                "activationCriteria": gates_by_id[product_id],
                "category": "supported",
                "expectedDisposition": "answer_candidate",
                "expectedReasonCode": "",
                "questionText": entry["questionText"],
                "inputs": copy.deepcopy(entry["inputs"]),
                "evidenceFresh": base_case["evidenceFresh"],
                "evidence": evidence,
            }
            expanded_case["benchmarkKey"] = benchmark_key(product_id, "supported", expanded_case["questionText"], expanded_case["inputs"])
            expanded_case["evidenceFingerprint"] = evidence_fingerprint(evidence, expanded_case["benchmarkKey"])
            expanded_case["evidenceOldestAt"] = base_case["evidenceOldestAt"]
            cases.append(expanded_case)

        for product_id, blueprint in blueprint_by_product.items():
            product = product_by_id[product_id]
            base_case = initial_supported_by_product[product_id]
            candidates = [name for name in product["requiredInputs"] if name != blueprint["missingField"]]
            extra_count = 3 if product_id == "palworld-base-progression-review" else 1
            if len(candidates) < extra_count:
                raise BenchmarkPreparationError(f"{product_id} does not have enough distinct missing-field cases.")
            for offset, field in enumerate(candidates[:extra_count], start=2):
                missing_inputs = copy.deepcopy(blueprint["inputs"])
                missing_inputs.pop(field, None)
                case_id = f"shadow_{product['gameId'].replace('-', '_')}_missing_{offset:03d}"
                question = f"Can this {product['label']} be completed when {field} has not been provided?"
                missing_case = {
                    "caseId": case_id,
                    "productId": product_id,
                    "gameId": product["gameId"],
                    "game": base_case["game"],
                    "gameVersion": base_case["gameVersion"],
                    "patchSensitive": True,
                    "answerFocus": f"Reject the request because the required {field} context is absent.",
                    "activationCriteria": gates_by_id[product_id],
                    "category": "missing_context",
                    "expectedDisposition": "no_charge",
                    "expectedReasonCode": "missing_context",
                    "questionText": question,
                    "inputs": missing_inputs,
                    "evidenceFresh": True,
                    "evidence": [],
                }
                missing_case["benchmarkKey"] = benchmark_key(product_id, "missing_context", question, missing_inputs)
                missing_case["evidenceFingerprint"] = missing_case["benchmarkKey"]
                missing_case["evidenceOldestAt"] = now_text
                cases.append(missing_case)

        case_ids = [item["caseId"] for item in cases]
        benchmark_keys = [item["benchmarkKey"] for item in cases]
        if len(case_ids) != len(set(case_ids)) or len(benchmark_keys) != len(set(benchmark_keys)):
            raise BenchmarkPreparationError("Expanded suite contains duplicate case IDs or benchmark keys.")
    finally:
        connection.close()

    suite_id = f"multigame-shadow-{now.strftime('%Y%m%dT%H%M%SZ')}"
    return {
        "schemaVersion": "1.0.0",
        "suiteId": suite_id,
        "generatedAt": now_text,
        "policyVersion": policy["policyVersion"],
        "mode": "shadow_no_charge",
        "summary": {
            "products": len(product_by_id),
            "cases": len(cases),
            "supportedCases": sum(item["category"] == "supported" for item in cases),
            "noChargeCases": sum(item["expectedDisposition"] == "no_charge" for item in cases),
        },
        "cases": cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare RaidBench shadow answer benchmarks from recent source snapshots.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default="", help="Fixed ISO timestamp for deterministic tests.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        suite = prepare_suite(args.database, args.generated_at or None)
        write_json(args.output, suite)
    except BenchmarkPreparationError as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps({"suiteId": suite["suiteId"], **suite["summary"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
