#!/usr/bin/env python3
"""Run no-charge multi-game answer benchmarks with independent Agent QA."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.multigame_products import ProductRoutingError, route_multigame_request


DEFAULT_SUITE = ROOT / "private-data" / "shadow-benchmarks" / "latest-suite.json"
DEFAULT_DATABASE = ROOT / "local" / "raidbench.shadow.db"
DEFAULT_ARTIFACT_ROOT = ROOT / "private-data" / "shadow-benchmarks" / "runs"
DEFAULT_REPORT = ROOT / "local" / "multigame-shadow-readiness.json"
DEFAULT_RUNTIME = ROOT / "config" / "codex_agent_runtime.json"
SCHEMA = ROOT / "local" / "raidbench-shadow-schema.sql"
AUTHOR_SCHEMA = ROOT / "schemas" / "agents" / "shadow-answer.schema.json"
REVIEW_SCHEMA = ROOT / "schemas" / "agents" / "shadow-answer-review.schema.json"
PEER_REVIEW_SCHEMA = ROOT / "schemas" / "agents" / "shadow-answer-peer-review.schema.json"
ALLOWED_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
COMPLETED_STATUSES = {"pass", "safe_hold"}


class ShadowBenchmarkError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(10)}"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ShadowBenchmarkError(f"Could not load {path}: {error}") from error
    if not isinstance(value, dict):
        raise ShadowBenchmarkError(f"Expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(shadow_benchmark_results)")}
    if "evidence_fingerprint" not in columns:
        connection.execute("ALTER TABLE shadow_benchmark_results ADD COLUMN evidence_fingerprint TEXT NOT NULL DEFAULT ''")
    if "evidence_oldest_at" not in columns:
        connection.execute("ALTER TABLE shadow_benchmark_results ADD COLUMN evidence_oldest_at TEXT NOT NULL DEFAULT ''")
    if "peer_reviewer_decision" not in columns:
        connection.execute("ALTER TABLE shadow_benchmark_results ADD COLUMN peer_reviewer_decision TEXT NOT NULL DEFAULT 'not_run'")
    if "reviewer_agreement" not in columns:
        connection.execute("ALTER TABLE shadow_benchmark_results ADD COLUMN reviewer_agreement INTEGER NOT NULL DEFAULT 0")
    if "answer_fingerprint" not in columns:
        connection.execute("ALTER TABLE shadow_benchmark_results ADD COLUMN answer_fingerprint TEXT NOT NULL DEFAULT ''")
    attempt_columns = {row["name"] for row in connection.execute("PRAGMA table_info(shadow_benchmark_attempts)")}
    if "peer_reviewer_decision" not in attempt_columns:
        connection.execute("ALTER TABLE shadow_benchmark_attempts ADD COLUMN peer_reviewer_decision TEXT NOT NULL DEFAULT 'not_run'")
    if "reviewer_agreement" not in attempt_columns:
        connection.execute("ALTER TABLE shadow_benchmark_attempts ADD COLUMN reviewer_agreement INTEGER NOT NULL DEFAULT 0")
    readiness_columns = {row["name"] for row in connection.execute("PRAGMA table_info(product_qa_readiness)")}
    if "reviewer_case_count" not in readiness_columns:
        connection.execute("ALTER TABLE product_qa_readiness ADD COLUMN reviewer_case_count INTEGER NOT NULL DEFAULT 0")
    delivery_columns = {row["name"] for row in connection.execute("PRAGMA table_info(delivery_gate_results)")}
    if "benchmark_key" not in delivery_columns:
        connection.execute("ALTER TABLE delivery_gate_results ADD COLUMN benchmark_key TEXT NOT NULL DEFAULT ''")
    if "delivery_code_fingerprint" not in delivery_columns:
        connection.execute("ALTER TABLE delivery_gate_results ADD COLUMN delivery_code_fingerprint TEXT NOT NULL DEFAULT ''")
    return connection


def resolve_runtime(model_override: str = "") -> dict[str, str]:
    config = read_json(DEFAULT_RUNTIME)
    model = (model_override or str(config.get("primary_model") or "")).strip()
    effort = str(config.get("reasoning_effort") or "").strip()
    allowed_models = {str(config.get("primary_model") or ""), *[str(item) for item in config.get("fallback_models", [])]}
    if not model or model not in allowed_models:
        raise ShadowBenchmarkError("The requested model is outside the approved RaidBench runtime contract.")
    if effort not in ALLOWED_REASONING_EFFORTS:
        raise ShadowBenchmarkError(f"Unsupported reasoning effort: {effort}")
    return {"model": model, "reasoningEffort": effort, "runtimeId": str(config.get("runtime_id") or "")}


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError as error:
        raise ShadowBenchmarkError(f"Artifact must remain inside the project: {path}") from error


def validate_suite(suite: dict[str, Any], products: dict[str, dict[str, Any]]) -> None:
    if suite.get("mode") != "shadow_no_charge" or suite.get("policyVersion") is None:
        raise ShadowBenchmarkError("Suite is not a no-charge shadow benchmark.")
    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) < 33:
        raise ShadowBenchmarkError("The suite must contain the 33-case baseline or a larger validated expansion.")
    case_ids = [str(item.get("caseId") or "") for item in cases]
    keys = [str(item.get("benchmarkKey") or "") for item in cases]
    if "" in case_ids or len(case_ids) != len(set(case_ids)):
        raise ShadowBenchmarkError("Suite case IDs must be non-empty and unique.")
    if "" in keys or len(keys) != len(set(keys)):
        raise ShadowBenchmarkError("Suite benchmark keys must be non-empty and unique.")
    by_product: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        product_id = str(case.get("productId") or "")
        if product_id not in products:
            raise ShadowBenchmarkError(f"Unknown benchmark product: {product_id}")
        if int(case.get("creditsCharged", 0)) != 0:
            raise ShadowBenchmarkError(f"{case['caseId']} attempts to charge credits.")
        by_product.setdefault(product_id, []).append(case)
    if set(by_product) != set(products):
        raise ShadowBenchmarkError("Suite must cover every non-Rust product.")
    for product_id, items in by_product.items():
        categories = {item.get("category") for item in items}
        if len(items) < 3 or not {"supported", "missing_context", "policy_blocked"}.issubset(categories):
            raise ShadowBenchmarkError(f"{product_id} must retain supported, missing-context, and policy-blocked baseline cases.")


def deterministic_route(case: dict[str, Any]) -> dict[str, Any]:
    try:
        return route_multigame_request({
            "productId": case["productId"],
            "gameId": case["gameId"],
            "questionText": case["questionText"],
            "inputs": case["inputs"],
        }, implemented_handlers={case["productId"]})
    except ProductRoutingError as error:
        raise ShadowBenchmarkError(f"{case['caseId']} failed request validation: {error}") from error


def validate_closed_evidence(case: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors = []
    evidence = case.get("evidence") or []
    allowed = set(policy["criticalClaimRules"]["allowedSourceTypes"])
    authoritative = set(policy["criticalClaimRules"]["authoritativeSourceTypes"])
    evidence_ids = [item.get("evidenceId") for item in evidence if isinstance(item, dict)]
    if len(evidence_ids) != len(set(evidence_ids)) or any(not item for item in evidence_ids):
        errors.append("Evidence IDs are missing or duplicated.")
    if len(evidence) < policy["criticalClaimRules"]["minimumEvidenceItems"]:
        errors.append("The closed evidence set is too small.")
    if not any(item.get("sourceType") in authoritative for item in evidence):
        errors.append("The closed evidence set has no authoritative item.")
    if not any(item.get("sourceType") == "customer_input" for item in evidence):
        errors.append("The closed evidence set has no customer-input record.")
    for item in evidence:
        if item.get("sourceType") not in allowed:
            errors.append(f"Disallowed evidence type: {item.get('sourceType')}")
        if item.get("sourceType") != "customer_input" and not str(item.get("url") or "").startswith("https://"):
            errors.append(f"Non-HTTPS evidence URL: {item.get('evidenceId')}")
        if not str(item.get("excerpt") or "").strip():
            errors.append(f"Empty evidence excerpt: {item.get('evidenceId')}")
    if case.get("evidenceFresh") is not True:
        errors.append("One or more publisher snapshots exceed the product freshness gate.")
    return errors


def calculation_report(suite_path: Path, case: dict[str, Any], node_bin: str) -> dict[str, Any] | None:
    if not case.get("calculationFixture"):
        return None
    result = subprocess.run(
        [node_bin, str(ROOT / "scripts" / "evaluate-shadow-calculations.mjs"), "--suite", str(suite_path), "--case", case["caseId"], "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise ShadowBenchmarkError(result.stderr.strip() or result.stdout.strip() or "Shadow calculation failed.")
    report = json.loads(result.stdout)
    if not report.get("passed") or len(report.get("results", [])) != 1:
        raise ShadowBenchmarkError(f"{case['caseId']} calculation assertions failed.")
    return report["results"][0]


def stage_prompt(skill: str, paths: list[Path]) -> str:
    inputs = "\n".join(f"- `{relative_to_root(path)}`" for path in paths)
    return f"""Use ${skill} for this isolated RaidBench shadow-answer stage.

Read only these closed input artifacts:
{inputs}

Do not browse, edit files, access customer or payment data, send messages, or perform external actions.
Return only the JSON object required by the supplied output schema. Do not wrap it in Markdown.
"""


def run_agent_stage(
    *,
    skill: str,
    schema: Path,
    inputs: list[Path],
    output: Path,
    events: Path,
    codex_bin: str,
    runtime: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    command = [
        codex_bin,
        "exec",
        "--enable",
        "use_legacy_landlock",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--cd",
        str(ROOT),
        "--skip-git-repo-check",
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(output),
        "--json",
        "--color",
        "never",
        "--model",
        runtime["model"],
        "--config",
        f'model_reasoning_effort="{runtime["reasoningEffort"]}"',
        "-",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        input=stage_prompt(skill, inputs),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    events.write_text(result.stdout, encoding="utf-8")
    if result.stderr:
        events.with_suffix(".stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise ShadowBenchmarkError(f"${skill} failed with exit code {result.returncode}.")
    return read_json(output)


def collect_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in collect_text(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in collect_text(item)]
    return []


def validate_candidate(case: dict[str, Any], candidate: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors = []
    if candidate.get("caseId") != case["caseId"] or candidate.get("stage") != "shadow_answer":
        errors.append("Candidate case or stage does not match.")
    if candidate.get("authorAgentId") != "shadow-answer-author":
        errors.append("Candidate author identity is invalid.")
    if candidate.get("versionScope") != case["gameVersion"]:
        errors.append("Candidate version scope does not exactly match the benchmark case.")
    disposition = candidate.get("disposition")
    claims = candidate.get("claims") if isinstance(candidate.get("claims"), list) else []
    calculations = candidate.get("calculations") if isinstance(candidate.get("calculations"), list) else []
    if disposition == "no_charge":
        if not str(candidate.get("noChargeReason") or "").strip():
            errors.append("No-charge candidate lacks a reason.")
        if claims or calculations:
            errors.append("No-charge candidate must not contain claims or calculations.")
        return errors
    if disposition != "answer_candidate":
        return [*errors, "Candidate disposition is invalid."]
    if candidate.get("noChargeReason"):
        errors.append("Answer candidate must not carry a no-charge reason.")
    if not claims or not any(item.get("critical") is True for item in claims):
        errors.append("Answer candidate requires at least one critical claim.")

    evidence_by_id = {item["evidenceId"]: item for item in case.get("evidence", [])}
    authoritative = set(policy["criticalClaimRules"]["authoritativeSourceTypes"])
    claim_ids = [item.get("claimId") for item in claims]
    if len(claim_ids) != len(set(claim_ids)) or any(not item for item in claim_ids):
        errors.append("Candidate claim IDs are missing or duplicated.")
    calculation_by_id = {item.get("calculationId"): item for item in calculations}
    expected_assertions = {
        item["calculationId"]: item
        for item in (case.get("calculationFixture") or {}).get("assertions", [])
    }
    if set(calculation_by_id) != set(expected_assertions):
        errors.append("Candidate calculations do not exactly match the verified fixture assertions.")

    for claim in claims:
        evidence_ids = claim.get("evidenceIds") if isinstance(claim.get("evidenceIds"), list) else []
        evidence = [evidence_by_id[item] for item in evidence_ids if item in evidence_by_id]
        if len(evidence) != len(evidence_ids):
            errors.append(f"{claim.get('claimId')} references unknown evidence.")
        if claim.get("critical") is True:
            if claim.get("status") != "verified":
                errors.append(f"{claim.get('claimId')} is critical but not verified.")
            if len(evidence) < policy["criticalClaimRules"]["minimumEvidenceItems"]:
                errors.append(f"{claim.get('claimId')} has insufficient evidence.")
            if not any(item.get("sourceType") in authoritative for item in evidence):
                errors.append(f"{claim.get('claimId')} lacks authoritative evidence.")
        evidence_types = {item.get("sourceType") for item in evidence}
        if claim.get("claimType") == "numeric":
            if not {"deterministic_test", "in_game_test"}.intersection(evidence_types):
                errors.append(f"{claim.get('claimId')} lacks deterministic numeric evidence.")
            if claim.get("calculationId") not in calculation_by_id:
                errors.append(f"{claim.get('claimId')} lacks a verified calculation.")
        if claim.get("claimType") == "mechanic" and claim.get("critical") is True:
            if not {"official", "official_wiki", "in_game_test"}.intersection(evidence_types):
                errors.append(f"{claim.get('claimId')} lacks game evidence.")
        if claim.get("claimType") == "customer_context" and "customer_input" not in evidence_types:
            errors.append(f"{claim.get('claimId')} lacks customer input.")

    for calculation_id, expected in expected_assertions.items():
        actual = calculation_by_id.get(calculation_id) or {}
        if actual.get("passed") is not True:
            errors.append(f"{calculation_id} is not marked as passing.")
        for field in ("expected", "actual"):
            try:
                value = float(actual.get(field))
            except (TypeError, ValueError):
                errors.append(f"{calculation_id}.{field} is not numeric.")
                continue
            if abs(value - float(expected["expected"])) > float(expected["tolerance"]):
                errors.append(f"{calculation_id}.{field} differs from the deterministic fixture.")
        if float(actual.get("tolerance", -1)) != float(expected["tolerance"]):
            errors.append(f"{calculation_id} changed the calculation tolerance.")

    normalized_text = " ".join(" ".join(collect_text(candidate)).lower().split())
    for phrase in policy.get("forbiddenOutcomePhrases", []):
        if phrase.lower() in normalized_text:
            errors.append(f"Candidate contains forbidden wording: {phrase}")
    if re.search(r"\bev_[a-z0-9_]+\b", str(candidate.get("answerText") or ""), re.IGNORECASE):
        errors.append("Customer-facing answer text exposes an internal evidence ID.")
    return errors


def validate_review(
    case: dict[str, Any],
    candidate: dict[str, Any],
    review: dict[str, Any],
    *,
    expected_stage: str = "shadow_answer_qa",
    expected_reviewer: str = "shadow-answer-independent-reviewer",
) -> list[str]:
    errors = []
    if review.get("caseId") != case["caseId"] or review.get("stage") != expected_stage:
        errors.append("Review case or stage does not match.")
    if review.get("reviewerAgentId") != expected_reviewer:
        errors.append("Independent reviewer identity is invalid.")
    claims = candidate.get("claims") or []
    claim_ids = {item.get("claimId") for item in claims}
    reviewed_ids = {item.get("claimId") for item in review.get("claimReviews") or []}
    if claim_ids != reviewed_ids:
        errors.append("Review does not cover exactly the candidate claims.")
    evidence_ids = {item.get("evidenceId") for item in case.get("evidence") or []}
    for item in review.get("claimReviews") or []:
        if not set(item.get("evidenceIds") or []).issubset(evidence_ids):
            errors.append(f"Review for {item.get('claimId')} references unknown evidence.")

    if candidate.get("disposition") == "no_charge":
        if review.get("decision") not in {"no_charge", "block"}:
            errors.append("A no-charge candidate review must agree with no_charge or explicitly block the refusal.")
        return errors

    if review.get("decision") == "approve":
        required_true = ("criticalClaimsVerified", "calculationTestsPassed", "versionChecked", "limitationsConfirmed", "productPromiseSatisfied")
        if any(review.get(field) is not True for field in required_true):
            errors.append("Approved review did not affirm every required QA check.")
        if review.get("blockers"):
            errors.append("Approved review contains blockers.")
        if any(item.get("status") != "supported" for item in review.get("claimReviews") or []):
            errors.append("Approved review contains an unsupported claim.")
    elif review.get("decision") != "block":
        errors.append("Answer candidate review decision must be approve or block.")
    return errors


def reviewed_paid_answer(case: dict[str, Any], candidate: dict[str, Any], review: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    evidence_by_id = {item["evidenceId"]: item for item in case["evidence"]}
    claims = []
    for claim in candidate["claims"]:
        expanded = {key: value for key, value in claim.items() if key != "evidenceIds"}
        expanded["evidence"] = [
            {key: evidence_by_id[evidence_id][key] for key in ("evidenceId", "sourceType", "title", "url", "retrievedAt", "supports")}
            for evidence_id in claim["evidenceIds"]
        ]
        claims.append(expanded)
    calculation_inputs = (case.get("calculationFixture") or {}).get("inputs", {})
    calculations = [{**item, "inputs": calculation_inputs} for item in candidate["calculations"]]
    reviewed_at = utc_now()
    return {
        "policyVersion": policy["policyVersion"],
        "answerId": f"ans_shadow_{case['benchmarkKey']}",
        "orderId": f"shadow_no_charge_{case['benchmarkKey']}",
        "game": case["game"],
        "gameVersion": candidate["versionScope"],
        "generatedAt": reviewed_at,
        "patchSensitive": case["patchSensitive"],
        "customerQuestion": case["questionText"],
        "intake": {"status": "complete", "missingFields": [], "customerFacts": case["inputs"]},
        "claims": claims,
        "calculations": calculations,
        "answerText": candidate["answerText"],
        "limitations": candidate["limitations"],
        "qa": {
            "authorAgentId": candidate["authorAgentId"],
            "reviewerAgentId": review["reviewerAgentId"],
            "decision": review["decision"],
            "criticalClaimsVerified": review["criticalClaimsVerified"],
            "calculationTestsPassed": review["calculationTestsPassed"],
            "versionChecked": review["versionChecked"],
            "reviewedAt": reviewed_at,
            "reviewNotes": review["reviewNotes"],
        },
        "delivery": {
            "status": "ready" if review["decision"] == "approve" else "blocked",
            "correctionWindowDays": policy["correctionPolicy"]["factualErrorCorrectionWindowDays"],
            "updatePolicy": policy["correctionPolicy"]["laterGameUpdate"],
        },
    }


def paid_answer_errors(answer_path: Path, node_bin: str) -> list[str]:
    result = subprocess.run(
        [node_bin, str(ROOT / "scripts" / "validate-paid-answer.mjs"), str(answer_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode == 0:
        return []
    return [line.removeprefix("- ") for line in result.stderr.splitlines() if line.startswith("- ")]


def store_result(connection: sqlite3.Connection, run_id: str, case: dict[str, Any], result: dict[str, Any]) -> None:
    now = utc_now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            INSERT INTO shadow_benchmark_results (
              benchmark_key, case_id, product_id, game_id, category,
              expected_disposition, actual_disposition, expected_reason_code, actual_reason_code,
              author_status, reviewer_decision, peer_reviewer_decision, reviewer_agreement,
              deterministic_status, critical_failure,
              evidence_fingerprint, evidence_oldest_at,
              answer_fingerprint,
              credits_charged, attempts, latest_run_id, artifact_dir, error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?, ?, ?)
            ON CONFLICT(benchmark_key) DO UPDATE SET
              case_id=excluded.case_id,
              product_id=excluded.product_id,
              game_id=excluded.game_id,
              category=excluded.category,
              expected_disposition=excluded.expected_disposition,
              actual_disposition=excluded.actual_disposition,
              expected_reason_code=excluded.expected_reason_code,
              actual_reason_code=excluded.actual_reason_code,
              author_status=excluded.author_status,
              reviewer_decision=excluded.reviewer_decision,
              peer_reviewer_decision=excluded.peer_reviewer_decision,
              reviewer_agreement=excluded.reviewer_agreement,
              deterministic_status=excluded.deterministic_status,
              critical_failure=excluded.critical_failure,
              evidence_fingerprint=excluded.evidence_fingerprint,
              evidence_oldest_at=excluded.evidence_oldest_at,
              answer_fingerprint=excluded.answer_fingerprint,
              credits_charged=0,
              attempts=shadow_benchmark_results.attempts+1,
              latest_run_id=excluded.latest_run_id,
              artifact_dir=excluded.artifact_dir,
              error=excluded.error,
              updated_at=excluded.updated_at
            """,
            (
                case["benchmarkKey"], case["caseId"], case["productId"], case["gameId"], case["category"],
                case["expectedDisposition"], result["actualDisposition"], case.get("expectedReasonCode", ""),
                result.get("actualReasonCode", ""), result.get("authorStatus", "not_run"),
                result.get("reviewerDecision", "not_run"), result.get("peerReviewerDecision", "not_run"),
                int(bool(result.get("reviewerAgreement"))), result["deterministicStatus"],
                int(bool(result.get("criticalFailure"))), case["evidenceFingerprint"], case["evidenceOldestAt"],
                result.get("answerFingerprint", ""),
                run_id, result.get("artifactDir", ""),
                result.get("error", ""), now, now,
            ),
        )
        connection.execute(
            """
            INSERT INTO shadow_benchmark_attempts (
              id, run_id, benchmark_key, case_id, product_id, expected_disposition,
              actual_disposition, deterministic_status, reviewer_decision,
              peer_reviewer_decision, reviewer_agreement,
              credits_charged, artifact_dir, error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                new_id("sha"), run_id, case["benchmarkKey"], case["caseId"], case["productId"],
                case["expectedDisposition"], result["actualDisposition"], result["deterministicStatus"],
                result.get("reviewerDecision", "not_run"), result.get("peerReviewerDecision", "not_run"),
                int(bool(result.get("reviewerAgreement"))), result.get("artifactDir", ""),
                result.get("error", ""), now,
            ),
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def evaluate_readiness(connection: sqlite3.Connection, report_path: Path) -> dict[str, Any]:
    products = read_json(ROOT / "content" / "multigame-products.json")["products"]
    gates = {item["productId"]: item for item in read_json(ROOT / "content" / "multigame-activation-gates.json")["products"]}
    rows = [dict(row) for row in connection.execute("SELECT * FROM shadow_benchmark_results").fetchall()]
    delivery_by_product = {
        row["product_id"]: dict(row)
        for row in connection.execute("SELECT * FROM delivery_gate_results").fetchall()
    }
    reports = []
    for product in products:
        criteria = gates[product["id"]]
        product_rows = [row for row in rows if row["product_id"] == product["id"]]
        supported = [row for row in product_rows if row["expected_disposition"] == "answer_candidate"]
        no_charge = [row for row in product_rows if row["expected_disposition"] == "no_charge"]
        supported_passed = sum(row["actual_disposition"] == "qa_approved" and row["deterministic_status"] == "pass" for row in supported)
        no_charge_correct = sum(row["actual_disposition"] == "no_charge" and row["deterministic_status"] == "pass" for row in no_charge)
        supported_safe_holds = sum(row["actual_disposition"] == "no_charge" and row["deterministic_status"] == "safe_hold" for row in supported)
        supported_qa_blocked = sum(row["actual_disposition"] == "qa_blocked" and row["deterministic_status"] == "safe_hold" for row in supported)
        failed_cases = sum(row["deterministic_status"] in {"failed", "error"} for row in product_rows)
        critical_failures = sum(int(row["critical_failure"]) for row in product_rows)
        supported_rate = supported_passed / len(supported) if supported else 0
        no_charge_rate = no_charge_correct / len(no_charge) if no_charge else 0
        dual_reviewed = [row for row in supported if row.get("peer_reviewer_decision") not in {None, "", "not_run"}]
        reviewer_rate = (
            sum(int(row.get("reviewer_agreement") or 0) for row in dual_reviewed) / len(dual_reviewed)
            if dual_reviewed
            else (1.0 if criteria["minimumInterReviewerCases"] == 0 else None)
        )
        delivery = delivery_by_product.get(product["id"], {})
        delivery_matches_answer = any(
            row["benchmark_key"] == delivery.get("benchmark_key")
            and row["actual_disposition"] == "qa_approved"
            and row.get("answer_fingerprint")
            and row["answer_fingerprint"] == delivery.get("answer_fingerprint")
            for row in supported
        )
        idempotency_passed = delivery_matches_answer and bool(delivery.get("idempotency_passed"))
        in_account_delivery_passed = delivery_matches_answer and bool(delivery.get("in_account_delivery_passed"))
        now = datetime.now(timezone.utc)
        approved_evidence_fresh = bool(supported_passed) and all(
            row["actual_disposition"] != "qa_approved"
            or (
                bool(row.get("evidence_oldest_at"))
                and 0 <= (now - datetime.fromisoformat(row["evidence_oldest_at"].replace("Z", "+00:00"))).total_seconds() / 3600 <= criteria["maximumEvidenceAgeHours"]
            )
            for row in supported
        )
        gates_report = [
            {"id": "shadow_cases", "observed": len(product_rows), "required": criteria["minimumShadowCases"], "passed": len(product_rows) >= criteria["minimumShadowCases"]},
            {"id": "supported_cases", "observed": len(supported), "required": criteria["minimumSupportedCases"], "passed": len(supported) >= criteria["minimumSupportedCases"]},
            {"id": "supported_qa_rate", "observed": supported_rate, "required": criteria["minimumSupportedQaPassRate"], "passed": len(supported) >= criteria["minimumSupportedCases"] and supported_rate >= criteria["minimumSupportedQaPassRate"]},
            {"id": "no_charge_cases", "observed": len(no_charge), "required": criteria["minimumNoChargeCases"], "passed": len(no_charge) >= criteria["minimumNoChargeCases"]},
            {"id": "no_charge_accuracy", "observed": no_charge_rate, "required": criteria["minimumNoChargeAccuracy"], "passed": len(no_charge) >= criteria["minimumNoChargeCases"] and no_charge_rate >= criteria["minimumNoChargeAccuracy"]},
            {"id": "critical_drift_window", "observed": {"cases": len(product_rows), "criticalFailures": critical_failures}, "required": {"cases": criteria["criticalDriftWindowCases"], "maximumCriticalDrift": criteria["maximumCriticalDrift"]}, "passed": len(product_rows) >= criteria["criticalDriftWindowCases"] and critical_failures <= criteria["maximumCriticalDrift"]},
            {"id": "reviewer_agreement", "observed": {"cases": len(dual_reviewed), "rate": reviewer_rate}, "required": {"cases": criteria["minimumInterReviewerCases"], "rate": criteria["minimumInterReviewerAgreementRate"]}, "passed": len(dual_reviewed) >= criteria["minimumInterReviewerCases"] and reviewer_rate is not None and reviewer_rate >= criteria["minimumInterReviewerAgreementRate"]},
            {"id": "evidence_freshness", "observed": approved_evidence_fresh, "required": True, "passed": approved_evidence_fresh},
            {"id": "idempotency", "observed": idempotency_passed, "required": criteria["idempotencyRequired"], "passed": idempotency_passed},
            {"id": "in_account_delivery", "observed": in_account_delivery_passed, "required": criteria["inAccountDeliveryRequired"], "passed": in_account_delivery_passed},
        ]
        decision = "ready_live" if all(item["passed"] for item in gates_report) else "hold"
        connection.execute(
            """
            INSERT INTO product_qa_readiness (
              product_id, decision, shadow_cases, supported_cases, supported_qa_passed,
              no_charge_cases, no_charge_correct, critical_failures, reviewer_case_count,
              reviewer_agreement_rate, idempotency_passed, in_account_delivery_passed,
              gate_results_json, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
              decision=excluded.decision, shadow_cases=excluded.shadow_cases,
              supported_cases=excluded.supported_cases, supported_qa_passed=excluded.supported_qa_passed,
              no_charge_cases=excluded.no_charge_cases, no_charge_correct=excluded.no_charge_correct,
              critical_failures=excluded.critical_failures, reviewer_case_count=excluded.reviewer_case_count,
              reviewer_agreement_rate=excluded.reviewer_agreement_rate,
              idempotency_passed=excluded.idempotency_passed,
              in_account_delivery_passed=excluded.in_account_delivery_passed,
              gate_results_json=excluded.gate_results_json, evaluated_at=excluded.evaluated_at
            """,
            (
                product["id"], decision, len(product_rows), len(supported), supported_passed,
                len(no_charge), no_charge_correct, critical_failures, len(dual_reviewed), reviewer_rate,
                int(idempotency_passed), int(in_account_delivery_passed),
                json.dumps(gates_report, ensure_ascii=True, separators=(",", ":")), utc_now(),
            ),
        )
        reports.append({
            "productId": product["id"],
            "gameId": product["gameId"],
            "label": product["label"],
            "decision": decision,
            "shadowCases": len(product_rows),
            "supportedCases": len(supported),
            "supportedQaPassed": supported_passed,
            "supportedQaPassRate": supported_rate,
            "supportedSafeHolds": supported_safe_holds,
            "supportedQaBlocked": supported_qa_blocked,
            "noChargeCases": len(no_charge),
            "noChargeCorrect": no_charge_correct,
            "noChargeAccuracy": no_charge_rate,
            "criticalFailures": critical_failures,
            "failedCases": failed_cases,
            "dualReviewedCases": len(dual_reviewed),
            "reviewerAgreementRate": reviewer_rate,
            "idempotencyPassed": idempotency_passed,
            "inAccountDeliveryPassed": in_account_delivery_passed,
            "gateResults": gates_report,
        })
    report = {
        "generatedAt": utc_now(),
        "mode": "shadow_no_charge",
        "summary": {
            "products": len(reports),
            "eligibleProducts": sum(item["decision"] == "ready_live" for item in reports),
            "distinctCases": len(rows),
            "qaApprovedAnswers": sum(item["supportedQaPassed"] for item in reports),
            "correctNoChargeCases": sum(item["noChargeCorrect"] for item in reports),
            "supportedSafeHolds": sum(
                row["actual_disposition"] == "no_charge" and row["expected_disposition"] == "answer_candidate"
                for row in rows
            ),
            "supportedQaBlocked": sum(
                row["actual_disposition"] == "qa_blocked" and row["deterministic_status"] == "safe_hold"
                for row in rows
            ),
            "failedCases": sum(row["deterministic_status"] in {"failed", "error"} for row in rows),
            "creditsCharged": sum(int(row["credits_charged"]) for row in rows),
        },
        "products": reports,
    }
    write_json(report_path, report)
    return report


def run_supported_case(
    *,
    suite_path: Path,
    case: dict[str, Any],
    product: dict[str, Any],
    policy: dict[str, Any],
    case_dir: Path,
    execute_agents: bool,
    codex_bin: str,
    node_bin: str,
    runtime: dict[str, str] | None,
    timeout: int,
) -> dict[str, Any]:
    route = deterministic_route(case)
    if route["reasonCode"] not in {"", "product_pending_qa"} or route["missingInputs"]:
        return {"actualDisposition": "no_charge", "actualReasonCode": route["reasonCode"], "deterministicStatus": "failed", "criticalFailure": True, "error": "Complete shadow case failed deterministic intake."}
    evidence_errors = validate_closed_evidence(case, policy)
    if evidence_errors:
        return {"actualDisposition": "no_charge", "actualReasonCode": "evidence_unavailable", "deterministicStatus": "safe_hold", "criticalFailure": False, "error": "; ".join(evidence_errors)}
    calculation = calculation_report(suite_path, case, node_bin)
    if not execute_agents:
        return {"actualDisposition": "pending_agent", "actualReasonCode": "", "deterministicStatus": "pending", "criticalFailure": False}
    if runtime is None:
        raise ShadowBenchmarkError("Agent runtime is required for execution.")

    case_dir.mkdir(parents=True, exist_ok=False)
    case_input = case_dir / "case-input.json"
    write_json(case_input, {
        "mode": {"name": "shadow_no_charge", "creditsCharged": 0, "customerDelivery": False},
        "case": case,
        "product": product,
        "policy": policy,
        "verifiedCalculation": calculation,
    })
    candidate_path = case_dir / "01-shadow-answer.json"
    candidate = run_agent_stage(
        skill="raidbench-shadow-answer",
        schema=AUTHOR_SCHEMA,
        inputs=[case_input],
        output=candidate_path,
        events=case_dir / "01-shadow-answer.events.jsonl",
        codex_bin=codex_bin,
        runtime=runtime,
        timeout=timeout,
    )
    candidate_errors = validate_candidate(case, candidate, policy)
    if candidate_errors:
        return {"actualDisposition": "qa_blocked", "actualReasonCode": "author_contract_failed", "authorStatus": "contract_failed", "reviewerDecision": "not_run", "deterministicStatus": "failed", "criticalFailure": True, "artifactDir": relative_to_root(case_dir), "error": "; ".join(candidate_errors)}

    review_path = case_dir / "02-shadow-answer-review.json"
    review = run_agent_stage(
        skill="raidbench-shadow-answer-qa",
        schema=REVIEW_SCHEMA,
        inputs=[case_input, candidate_path],
        output=review_path,
        events=case_dir / "02-shadow-answer-review.events.jsonl",
        codex_bin=codex_bin,
        runtime=runtime,
        timeout=timeout,
    )
    review_errors = validate_review(case, candidate, review)
    if review_errors:
        return {"actualDisposition": "qa_blocked", "actualReasonCode": "review_contract_failed", "authorStatus": candidate["disposition"], "reviewerDecision": review.get("decision", "invalid"), "deterministicStatus": "failed", "criticalFailure": True, "artifactDir": relative_to_root(case_dir), "error": "; ".join(review_errors)}

    peer_decision = "not_run"
    reviewer_agreement = False
    if product.get("deliveryClass") == "complex_match_review":
        peer_path = case_dir / "03-shadow-answer-peer-review.json"
        peer_review = run_agent_stage(
            skill="raidbench-shadow-answer-peer-qa",
            schema=PEER_REVIEW_SCHEMA,
            inputs=[case_input, candidate_path],
            output=peer_path,
            events=case_dir / "03-shadow-answer-peer-review.events.jsonl",
            codex_bin=codex_bin,
            runtime=runtime,
            timeout=timeout,
        )
        peer_errors = validate_review(
            case,
            candidate,
            peer_review,
            expected_stage="shadow_answer_peer_qa",
            expected_reviewer="shadow-answer-peer-reviewer",
        )
        if peer_errors:
            return {"actualDisposition": "qa_blocked", "actualReasonCode": "peer_review_contract_failed", "authorStatus": candidate["disposition"], "reviewerDecision": review["decision"], "peerReviewerDecision": peer_review.get("decision", "invalid"), "reviewerAgreement": False, "deterministicStatus": "failed", "criticalFailure": True, "artifactDir": relative_to_root(case_dir), "error": "; ".join(peer_errors)}
        peer_decision = peer_review["decision"]
        reviewer_agreement = peer_decision == review["decision"]
        if not reviewer_agreement:
            return {"actualDisposition": "qa_blocked", "actualReasonCode": "reviewer_disagreement", "authorStatus": candidate["disposition"], "reviewerDecision": review["decision"], "peerReviewerDecision": peer_decision, "reviewerAgreement": False, "deterministicStatus": "safe_hold", "criticalFailure": False, "artifactDir": relative_to_root(case_dir), "error": "Independent reviewers reached different decisions."}

    review_meta = {
        "reviewerDecision": review["decision"],
        "peerReviewerDecision": peer_decision,
        "reviewerAgreement": reviewer_agreement,
    }
    if candidate["disposition"] == "no_charge":
        if review["decision"] != "no_charge":
            return {"actualDisposition": "qa_blocked", "actualReasonCode": "no_charge_disputed", "authorStatus": "no_charge", **review_meta, "deterministicStatus": "safe_hold", "criticalFailure": False, "artifactDir": relative_to_root(case_dir), "error": "; ".join(review.get("blockers") or [])}
        return {"actualDisposition": "no_charge", "actualReasonCode": "insufficient_supported_evidence", "authorStatus": "no_charge", **review_meta, "deterministicStatus": "safe_hold", "criticalFailure": False, "artifactDir": relative_to_root(case_dir)}
    if review["decision"] != "approve":
        return {"actualDisposition": "qa_blocked", "actualReasonCode": "independent_qa_blocked", "authorStatus": "answer_candidate", **review_meta, "deterministicStatus": "safe_hold", "criticalFailure": False, "artifactDir": relative_to_root(case_dir), "error": "; ".join(review.get("blockers") or [])}

    answer = reviewed_paid_answer(case, candidate, review, policy)
    answer_path = case_dir / ("04-reviewed-paid-answer.json" if peer_decision != "not_run" else "03-reviewed-paid-answer.json")
    write_json(answer_path, answer)
    validation_errors = paid_answer_errors(answer_path, node_bin)
    if validation_errors:
        return {"actualDisposition": "qa_blocked", "actualReasonCode": "paid_answer_contract_failed", "authorStatus": "answer_candidate", **review_meta, "deterministicStatus": "failed", "criticalFailure": True, "artifactDir": relative_to_root(case_dir), "error": "; ".join(validation_errors)}
    answer_fingerprint = hashlib.sha256(answer_path.read_bytes()).hexdigest()
    return {"actualDisposition": "qa_approved", "actualReasonCode": "", "authorStatus": "answer_candidate", **review_meta, "deterministicStatus": "pass", "criticalFailure": False, "answerFingerprint": answer_fingerprint, "artifactDir": relative_to_root(case_dir)}


def execute(args: argparse.Namespace) -> int:
    suite_path = args.suite if args.suite.is_absolute() else ROOT / args.suite
    database = args.database if args.database.is_absolute() else ROOT / args.database
    artifact_root = args.artifact_root if args.artifact_root.is_absolute() else ROOT / args.artifact_root
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    relative_to_root(suite_path)
    relative_to_root(artifact_root)
    suite = read_json(suite_path)
    policy = read_json(ROOT / "content" / "answer-quality-policy.json")
    products = {item["id"]: item for item in read_json(ROOT / "content" / "multigame-products.json")["products"]}
    validate_suite(suite, products)
    if suite["policyVersion"] != policy["policyVersion"]:
        raise ShadowBenchmarkError("Suite and active answer-policy versions differ.")

    codex_bin = shutil.which(args.codex_bin) if args.execute else ""
    node_bin = shutil.which(args.node_bin)
    if not node_bin:
        raise ShadowBenchmarkError(f"Node executable not found: {args.node_bin}")
    runtime = None
    if args.execute:
        if not codex_bin:
            raise ShadowBenchmarkError(f"Codex executable not found: {args.codex_bin}")
        login = subprocess.run([codex_bin, "login", "status"], text=True, capture_output=True, check=False, timeout=30)
        if login.returncode != 0:
            raise ShadowBenchmarkError("Codex is not logged in for shadow-answer execution.")
        runtime = resolve_runtime(args.model)

    connection = connect_database(database)
    for case in suite["cases"]:
        connection.execute(
            """
            UPDATE shadow_benchmark_results
            SET evidence_fingerprint = ?, evidence_oldest_at = ?
            WHERE benchmark_key = ? AND (evidence_fingerprint = '' OR evidence_fingerprint = ?)
            """,
            (case["evidenceFingerprint"], case["evidenceOldestAt"], case["benchmarkKey"], case["evidenceFingerprint"]),
        )
    run_id = new_id("shr")
    run_started = utc_now()
    connection.execute(
        "INSERT INTO shadow_runs (id, suite_id, mode, status, started_at) VALUES (?, ?, ?, 'running', ?)",
        (run_id, suite["suiteId"], "agent" if args.execute else "validation_only", run_started),
    )
    run_dir = artifact_root / run_id
    if args.execute:
        run_dir.mkdir(parents=True, exist_ok=False)
    processed = 0
    skipped = 0
    infrastructure_errors = 0
    supported_started = 0
    try:
        for case in suite["cases"]:
            if args.product and case["productId"] not in set(args.product):
                continue
            existing = connection.execute(
                "SELECT deterministic_status,evidence_fingerprint FROM shadow_benchmark_results WHERE benchmark_key = ?",
                (case["benchmarkKey"],),
            ).fetchone()
            if args.pending_only and existing and existing["deterministic_status"] in COMPLETED_STATUSES and existing["evidence_fingerprint"] == case["evidenceFingerprint"]:
                skipped += 1
                continue
            if case["category"] == "supported" and args.max_supported >= 0 and supported_started >= args.max_supported:
                skipped += 1
                continue

            try:
                if case["expectedDisposition"] == "no_charge":
                    route = deterministic_route(case)
                    passed = route["reasonCode"] == case["expectedReasonCode"] and route["creditsCharged"] == 0
                    result = {
                        "actualDisposition": "no_charge" if passed else "routing_mismatch",
                        "actualReasonCode": route["reasonCode"],
                        "deterministicStatus": "pass" if passed else "failed",
                        "criticalFailure": not passed,
                        "error": "" if passed else "No-charge routing did not match the expected reason.",
                    }
                else:
                    supported_started += 1
                    case_dir = run_dir / case["caseId"] if args.execute else artifact_root / "validation-only" / case["caseId"]
                    result = run_supported_case(
                        suite_path=suite_path,
                        case=case,
                        product=products[case["productId"]],
                        policy=policy,
                        case_dir=case_dir,
                        execute_agents=args.execute,
                        codex_bin=codex_bin or args.codex_bin,
                        node_bin=node_bin,
                        runtime=runtime,
                        timeout=args.timeout,
                    )
                store_result(connection, run_id, case, result)
                processed += 1
                print(json.dumps({"caseId": case["caseId"], "actual": result["actualDisposition"], "status": result["deterministicStatus"], "creditsCharged": 0}))
            except (ShadowBenchmarkError, subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as error:
                infrastructure_errors += 1
                result = {"actualDisposition": "error", "actualReasonCode": "pipeline_error", "deterministicStatus": "error", "criticalFailure": False, "error": str(error)}
                store_result(connection, run_id, case, result)
                processed += 1
                print(json.dumps({"caseId": case["caseId"], "actual": "error", "status": "error", "creditsCharged": 0, "error": str(error)}))

        report = evaluate_readiness(connection, report_path)
        summary = {"processed": processed, "skipped": skipped, "infrastructureErrors": infrastructure_errors, **report["summary"]}
        connection.execute(
            "UPDATE shadow_runs SET status = ?, completed_at = ?, summary_json = ? WHERE id = ?",
            ("failed" if infrastructure_errors else "completed", utc_now(), json.dumps(summary, ensure_ascii=True, separators=(",", ":")), run_id),
        )
        print(json.dumps({"runId": run_id, **summary, "report": str(report_path)}))
        return 1 if infrastructure_errors else 0
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RaidBench no-charge shadow answer benchmarks.")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--execute", action="store_true", help="Run the author and independent-review Codex stages.")
    parser.add_argument("--pending-only", action="store_true", help="Skip benchmark keys that already reached pass or safe hold.")
    parser.add_argument("--max-supported", type=int, default=-1, help="Maximum supported cases to send through both Agents; -1 means all.")
    parser.add_argument("--product", action="append", default=[], help="Product ID to run; repeat for multiple products.")
    parser.add_argument("--model", default="")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--node-bin", default="node")
    parser.add_argument("--timeout", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    try:
        return execute(parse_args())
    except (ShadowBenchmarkError, sqlite3.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
