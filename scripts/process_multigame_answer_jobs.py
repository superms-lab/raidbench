#!/usr/bin/env python3
"""Process privacy-minimized Palworld answer jobs through author and independent QA Agents."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
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

from backend.multigame_jobs import (
    LIVE_GAME_NAME,
    LIVE_PRODUCT_ID,
    MultiGameJobError,
    RESULT_SCHEMA_VERSION,
    answer_fingerprint,
    parse_time,
    read_json_file,
    validate_job_shape,
    validate_result_envelope,
    write_json_atomic,
)
from scripts.prepare_shadow_benchmarks import normalize_excerpt
from scripts.run_shadow_answer_benchmarks import (
    paid_answer_errors,
    resolve_runtime,
    reviewed_paid_answer,
    validate_candidate,
    validate_closed_evidence,
    validate_review,
)


DEFAULT_QUEUE_ROOT = ROOT / "private-data" / "answer-jobs"
DEFAULT_ARTIFACT_ROOT = ROOT / "private-data" / "answer-job-artifacts"
DEFAULT_SOURCE_DATABASE = ROOT / "local" / "raidbench.local.db"
AUTHOR_SCHEMA = ROOT / "schemas" / "agents" / "live-answer.schema.json"
REVIEW_SCHEMA = ROOT / "schemas" / "agents" / "live-answer-review.schema.json"


class LiveAnswerWorkerError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_project_json(relative: str) -> dict[str, Any]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LiveAnswerWorkerError(f"Expected a JSON object in {relative}.")
    return value


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
        raise LiveAnswerWorkerError(f"No current publisher snapshot exists for {source_id}.")
    return row


def prepare_case(job: dict[str, Any], source_database: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    catalog = read_project_json("content/multigame-products.json")
    product = next((item for item in catalog["products"] if item["id"] == job["productId"]), None)
    if not product or product.get("id") != LIVE_PRODUCT_ID or product.get("status") != "ready_live":
        raise LiveAnswerWorkerError("The controlled Palworld product is not currently live.")
    policy = read_project_json("content/answer-quality-policy.json")
    blueprints = read_project_json("content/multigame-shadow-blueprints.json")
    blueprint = next(item for item in blueprints["blueprints"] if item["productId"] == LIVE_PRODUCT_ID)
    source_registry = read_project_json("content/source-registry.json")
    source_by_id = {item["id"]: item for item in source_registry["sources"]}
    gates = read_project_json("content/multigame-activation-gates.json")
    activation = next(item for item in gates["products"] if item["productId"] == LIVE_PRODUCT_ID)

    now = datetime.now(timezone.utc)
    official_evidence: list[dict[str, Any]] = []
    connection = sqlite3.connect(source_database)
    connection.row_factory = sqlite3.Row
    try:
        for index, source_id in enumerate(blueprint["evidenceSourceIds"], start=1):
            source = source_by_id[source_id]
            snapshot = latest_snapshot(connection, source_id)
            fetched_at = parse_time(snapshot["fetched_at"])
            age_hours = (now - fetched_at).total_seconds() / 3600
            if age_hours < -0.25 or age_hours > float(activation["maximumEvidenceAgeHours"]):
                raise LiveAnswerWorkerError("Current publisher evidence is outside the paid-answer freshness window.")
            official_evidence.append({
                "evidenceId": f"ev_palworld_official_{index}",
                "sourceId": source_id,
                "sourceType": "official",
                "title": snapshot["title"] or source.get("notes") or source_id,
                "url": source["url"],
                "retrievedAt": snapshot["fetched_at"],
                "contentHash": snapshot["content_hash"] or hashlib.sha256(str(snapshot["body_sample"]).encode("utf-8")).hexdigest(),
                "supports": "Publisher-controlled update context only; use no claim beyond the captured excerpt.",
                "excerpt": normalize_excerpt(snapshot["body_sample"]),
            })
    finally:
        connection.close()

    customer_evidence = {
        "evidenceId": "ev_palworld_customer_input",
        "sourceId": "customer-input",
        "sourceType": "customer_input",
        "title": "Player-supplied request context",
        "url": "",
        "retrievedAt": job["submittedAt"],
        "supports": "Only the player-provided state and values in this request.",
        "excerpt": json.dumps(job["inputs"], ensure_ascii=False, sort_keys=True),
    }
    source_date = min(parse_time(item["retrievedAt"]) for item in official_evidence).date().isoformat()
    version_scope = f"Player-reported Palworld {job['inputs']['gameVersion']}; publisher source check {source_date}"
    case = {
        "caseId": job["jobId"],
        "productId": job["productId"],
        "gameId": job["gameId"],
        "game": job["game"],
        "gameVersion": version_scope,
        "patchSensitive": True,
        "answerFocus": (
            "Controlled player observations can support naming the measured workflow or progression boundary "
            "described in this request as the first bottleneck to test. Identify one observation-supported boundary, "
            "prioritize practical next actions, state assumptions and limitations, and define a one-variable "
            "verification checklist. Do not claim a Palworld mechanic, underlying cause, or guaranteed outcome."
        ),
        "category": "supported",
        "expectedDisposition": "answer_candidate",
        "expectedReasonCode": "",
        "questionText": job["questionText"],
        "inputs": job["inputs"],
        "evidenceFresh": True,
        "evidence": [*official_evidence, customer_evidence],
        "benchmarkKey": hashlib.sha256(job["jobId"].encode("utf-8")).hexdigest()[:32],
        "evidenceFingerprint": hashlib.sha256(
            json.dumps(
                [{"sourceId": item["sourceId"], "contentHash": item["contentHash"]} for item in official_evidence],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:32],
        "evidenceOldestAt": min(item["retrievedAt"] for item in official_evidence),
    }
    evidence_errors = validate_closed_evidence(case, policy)
    if evidence_errors:
        raise LiveAnswerWorkerError("; ".join(evidence_errors))
    return case, product, policy


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
    input_list = "\n".join(f"- `{path.resolve()}`" for path in inputs)
    prompt = f"""Use ${skill} for this isolated RaidBench customer-answer stage.

Read only these closed input artifacts:
{input_list}

Do not browse, edit files, access another job, access customer identity or commerce data, send messages, or perform external actions.
Return only the JSON object required by the supplied output schema. Do not wrap it in Markdown.
"""
    command = [
        codex_bin, "exec", "--enable", "use_legacy_landlock", "--ephemeral",
        "--sandbox", "read-only", "--cd", str(ROOT), "--skip-git-repo-check",
        "--output-schema", str(schema), "--output-last-message", str(output),
        "--json", "--color", "never", "--model", runtime["model"],
        "--config", f'model_reasoning_effort="{runtime["reasoningEffort"]}"', "-",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    events.write_text(result.stdout, encoding="utf-8")
    if result.stderr:
        events.with_suffix(".stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise LiveAnswerWorkerError(f"${skill} failed with exit code {result.returncode}.")
    return read_json_file(output)


def shadow_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    converted = copy.deepcopy(candidate)
    converted["stage"] = "shadow_answer"
    converted["authorAgentId"] = "shadow-answer-author"
    return converted


def shadow_review(review: dict[str, Any]) -> dict[str, Any]:
    converted = copy.deepcopy(review)
    converted["stage"] = "shadow_answer_qa"
    converted["reviewerAgentId"] = "shadow-answer-independent-reviewer"
    return converted


def held_result(job: dict[str, Any], reason_code: str, reason: str) -> dict[str, Any]:
    safe_reason = re.sub(r"\bev_[a-z0-9_]+\b", "the supplied evidence", str(reason), flags=re.IGNORECASE)
    safe_reason = re.sub(r"/(?:workspace|opt|data)/\S+", "the private review system", safe_reason)
    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "jobId": job["jobId"],
        "questionId": job["questionId"],
        "productId": job["productId"],
        "requestSignature": job["requestSignature"],
        "status": "held_without_charge",
        "reasonCode": reason_code,
        "reason": safe_reason.strip()[:1000],
        "processedAt": utc_now(),
        "answerFingerprint": "",
        "answer": {},
    }


def process_job(
    job: dict[str, Any],
    *,
    source_database: Path,
    case_dir: Path,
    codex_bin: str,
    node_bin: str,
    runtime: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    validate_job_shape(job)
    if datetime.now(timezone.utc) >= parse_time(job["expiresAt"]):
        return held_result(job, "worker_timeout", "The independent review window expired before processing completed. No credits were charged.")
    try:
        case, product, policy = prepare_case(job, source_database)
    except (LiveAnswerWorkerError, MultiGameJobError, OSError, sqlite3.Error):
        return held_result(
            job,
            "evidence_unavailable",
            "Current publisher evidence was unavailable or outside the paid-answer freshness window. No credits were charged.",
        )

    case_dir.mkdir(parents=True, exist_ok=False)
    case_input = case_dir / "case-input.json"
    write_json_atomic(case_input, {
        "mode": {
            "name": "customer_delivery_candidate",
            "creditsCharged": 0,
            "customerDelivery": False,
            "releaseRequiresIndependentQa": True,
        },
        "case": case,
        "product": product,
        "policy": policy,
        "verifiedCalculation": None,
    })

    candidate_path = case_dir / "01-answer-candidate.json"
    candidate = run_agent_stage(
        skill="raidbench-live-answer",
        schema=AUTHOR_SCHEMA,
        inputs=[case_input],
        output=candidate_path,
        events=case_dir / "01-answer-candidate.events.jsonl",
        codex_bin=codex_bin,
        runtime=runtime,
        timeout=timeout,
    )
    candidate_for_validation = shadow_candidate(candidate)
    candidate_errors = validate_candidate(case, candidate_for_validation, policy)
    if candidate_errors:
        return held_result(job, "author_contract_failed", "The draft did not pass the paid-answer contract. No credits were charged.")

    review_path = case_dir / "02-independent-review.json"
    review = run_agent_stage(
        skill="raidbench-live-answer-qa",
        schema=REVIEW_SCHEMA,
        inputs=[case_input, candidate_path],
        output=review_path,
        events=case_dir / "02-independent-review.events.jsonl",
        codex_bin=codex_bin,
        runtime=runtime,
        timeout=timeout,
    )
    review_for_validation = shadow_review(review)
    review_errors = validate_review(case, candidate_for_validation, review_for_validation)
    if review_errors:
        return held_result(job, "review_contract_failed", "Independent QA did not satisfy the release contract. No credits were charged.")
    if candidate["disposition"] == "no_charge":
        return held_result(
            job,
            "insufficient_supported_evidence",
            candidate.get("noChargeReason") or "The supplied context cannot support the complete paid review. No credits were charged.",
        )
    if review["decision"] != "approve":
        return held_result(
            job,
            "independent_qa_blocked",
            "Independent QA could not verify the complete promised review. No credits were charged.",
        )

    answer = reviewed_paid_answer(case, candidate_for_validation, review_for_validation, policy)
    answer["answerId"] = f"ans_{job['questionId']}"
    answer["orderId"] = job["questionId"]
    answer["qa"]["authorAgentId"] = "multigame-answer-author"
    answer["qa"]["reviewerAgentId"] = "multigame-answer-independent-reviewer"
    answer_path = case_dir / "03-reviewed-answer.json"
    write_json_atomic(answer_path, answer)
    contract_errors = paid_answer_errors(answer_path, node_bin)
    if contract_errors:
        return held_result(job, "paid_answer_contract_failed", "The reviewed answer failed the final release validator. No credits were charged.")

    result = {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "jobId": job["jobId"],
        "questionId": job["questionId"],
        "productId": job["productId"],
        "requestSignature": job["requestSignature"],
        "status": "approved",
        "reasonCode": "",
        "reason": "",
        "processedAt": utc_now(),
        "answerFingerprint": answer_fingerprint(answer),
        "answer": answer,
    }
    final_errors = validate_result_envelope(job, result, policy)
    if final_errors:
        return held_result(job, "production_import_contract_failed", "The reviewed answer failed the production import contract. No credits were charged.")
    return result


def execute(args: argparse.Namespace) -> dict[str, int]:
    inbox = args.queue_root / "inbox"
    outbox = args.queue_root / "outbox"
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    pending = [path for path in sorted(inbox.glob("job_*.json")) if not (outbox / path.name).exists()]
    summary = {
        "discovered": len(list(inbox.glob("job_*.json"))),
        "processed": 0,
        "approved": 0,
        "heldWithoutCharge": 0,
    }
    if not pending:
        return summary
    codex_bin = shutil.which(args.codex_bin)
    node_bin = shutil.which(args.node_bin)
    if not codex_bin:
        raise LiveAnswerWorkerError(f"Codex executable not found: {args.codex_bin}")
    if not node_bin:
        raise LiveAnswerWorkerError(f"Node executable not found: {args.node_bin}")
    login = subprocess.run([codex_bin, "login", "status"], text=True, capture_output=True, check=False, timeout=30)
    if login.returncode != 0:
        raise LiveAnswerWorkerError("Codex is not logged in for customer-answer execution.")
    runtime = resolve_runtime(args.model)

    for path in pending:
        destination = outbox / path.name
        if summary["processed"] >= args.max_jobs:
            break
        job = read_json_file(path)
        case_dir = args.artifact_root / job.get("jobId", path.stem)
        if case_dir.exists():
            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            case_dir = args.artifact_root / f"{job.get('jobId', path.stem)}-{suffix}"
        result = process_job(
            job,
            source_database=args.source_database,
            case_dir=case_dir,
            codex_bin=codex_bin,
            node_bin=node_bin,
            runtime=runtime,
            timeout=args.timeout,
        )
        write_json_atomic(destination, result)
        summary["processed"] += 1
        if result["status"] == "approved":
            summary["approved"] += 1
        else:
            summary["heldWithoutCharge"] += 1
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the isolated RaidBench customer-answer Agent worker.")
    parser.add_argument("--queue-root", type=Path, default=DEFAULT_QUEUE_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--source-database", type=Path, default=DEFAULT_SOURCE_DATABASE)
    parser.add_argument("--max-jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--node-bin", default="node")
    parser.add_argument("--model", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = execute(args)
    except (LiveAnswerWorkerError, MultiGameJobError, OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps(summary, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
