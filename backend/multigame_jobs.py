from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


JOB_SCHEMA_VERSION = "1.0.0"
RESULT_SCHEMA_VERSION = "1.0.0"
LIVE_PRODUCT_ID = "palworld-base-progression-review"
LIVE_GAME_ID = "palworld"
LIVE_GAME_NAME = "Palworld"
JOB_TIMEOUT_MINUTES = 30
MAX_FILE_BYTES = 256_000
SAFE_OFFICIAL_HOSTS = {
    "pocketpair.jp",
    "www.pocketpair.jp",
    "store.steampowered.com",
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,160}$")
INTERNAL_EVIDENCE_PATTERN = re.compile(r"\bev_[a-z0-9_]+\b", re.IGNORECASE)


class MultiGameJobError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise MultiGameJobError(f"Invalid ISO timestamp: {value}") from error
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def answer_fingerprint(answer: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(answer).encode("utf-8")).hexdigest()


def _unsigned_job(job: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in job.items() if key != "requestSignature"}


def sign_job(job: dict[str, Any], secret: str) -> str:
    if len(secret) < 32:
        raise MultiGameJobError("The answer-job signing secret must contain at least 32 characters.")
    return hmac.new(
        secret.encode("utf-8"),
        canonical_json(_unsigned_job(job)).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_signed_job(
    question: dict[str, Any],
    routed: dict[str, Any],
    secret: str,
) -> dict[str, Any]:
    submitted_at = parse_time(question["submittedAt"])
    job = {
        "schemaVersion": JOB_SCHEMA_VERSION,
        "jobId": f"job_{question['id']}",
        "questionId": question["id"],
        "productId": routed["productId"],
        "gameId": routed["gameId"],
        "game": routed["game"],
        "questionText": routed["questionText"],
        "inputs": routed["inputs"],
        "creditsQuoted": int(routed["creditsQuoted"]),
        "submittedAt": submitted_at.isoformat(),
        "expiresAt": (submitted_at + timedelta(minutes=JOB_TIMEOUT_MINUTES)).isoformat(),
    }
    job["requestSignature"] = sign_job(job, secret)
    validate_signed_job(job, secret)
    return job


def validate_job_shape(job: dict[str, Any]) -> None:
    required = {
        "schemaVersion", "jobId", "questionId", "productId", "gameId", "game",
        "questionText", "inputs", "creditsQuoted", "submittedAt", "expiresAt",
        "requestSignature",
    }
    if not isinstance(job, dict) or set(job) != required:
        raise MultiGameJobError("The answer job does not match the signed contract.")
    if job["schemaVersion"] != JOB_SCHEMA_VERSION:
        raise MultiGameJobError("Unsupported answer-job schema version.")
    if not ID_PATTERN.fullmatch(str(job["jobId"])) or not ID_PATTERN.fullmatch(str(job["questionId"])):
        raise MultiGameJobError("The answer job contains an invalid identifier.")
    if job["jobId"] != f"job_{job['questionId']}":
        raise MultiGameJobError("The answer job and question identifiers do not match.")
    if (job["productId"], job["gameId"], job["game"]) != (LIVE_PRODUCT_ID, LIVE_GAME_ID, LIVE_GAME_NAME):
        raise MultiGameJobError("The answer job is outside the controlled Palworld launch.")
    if not isinstance(job["inputs"], dict) or len(canonical_json(job["inputs"])) > 24_000:
        raise MultiGameJobError("The answer-job inputs are invalid or too large.")
    if not 20 <= len(str(job["questionText"]).strip()) <= 2000:
        raise MultiGameJobError("The answer-job question length is invalid.")
    if int(job["creditsQuoted"]) != 80:
        raise MultiGameJobError("The answer-job credit quote is invalid.")
    if parse_time(job["expiresAt"]) <= parse_time(job["submittedAt"]):
        raise MultiGameJobError("The answer-job expiry is invalid.")
    if not re.fullmatch(r"^[a-f0-9]{64}$", str(job["requestSignature"])):
        raise MultiGameJobError("The answer-job signature format is invalid.")


def validate_signed_job(job: dict[str, Any], secret: str) -> None:
    validate_job_shape(job)
    expected = sign_job(job, secret)
    if not hmac.compare_digest(expected, str(job["requestSignature"])):
        raise MultiGameJobError("The answer-job signature is invalid.")


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if len(payload.encode("utf-8")) > MAX_FILE_BYTES:
        raise MultiGameJobError("The answer-job artifact exceeds the size limit.")
    temporary.write_text(payload, encoding="utf-8")
    os.chmod(temporary, 0o640)
    temporary.replace(path)


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise MultiGameJobError(f"Missing or oversized answer-job artifact: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MultiGameJobError(f"Invalid answer-job JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise MultiGameJobError(f"Answer-job artifact must be an object: {path.name}")
    return value


def export_signed_job(queue_root: Path, job: dict[str, Any]) -> Path:
    destination = queue_root / "inbox" / f"{job['jobId']}.json"
    if destination.exists():
        existing = read_json_file(destination)
        if canonical_json(existing) != canonical_json(job):
            raise MultiGameJobError("An existing answer job has different signed content.")
        return destination
    write_json_atomic(destination, job)
    return destination


def _valid_iso(value: Any) -> bool:
    try:
        parse_time(str(value))
        return True
    except MultiGameJobError:
        return False


def _official_host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in SAFE_OFFICIAL_HOSTS


def validate_result_envelope(
    job: dict[str, Any],
    result: dict[str, Any],
    policy: dict[str, Any],
    *,
    now: datetime | None = None,
) -> list[str]:
    errors: list[str] = []
    now = now or datetime.now(timezone.utc)
    required = {
        "schemaVersion", "jobId", "questionId", "productId", "requestSignature",
        "status", "reasonCode", "reason", "processedAt", "answerFingerprint", "answer",
    }
    if not isinstance(result, dict) or set(result) != required:
        return ["The Agent result does not match the import contract."]
    if result.get("schemaVersion") != RESULT_SCHEMA_VERSION:
        errors.append("Unsupported Agent-result schema version.")
    for key in ("jobId", "questionId", "productId", "requestSignature"):
        if result.get(key) != job.get(key):
            errors.append(f"Agent result does not match the signed job field: {key}.")
    if not _valid_iso(result.get("processedAt")):
        errors.append("Agent result has an invalid processing timestamp.")
    status = result.get("status")
    if status == "held_without_charge":
        if not str(result.get("reason") or "").strip():
            errors.append("A no-charge result must explain the evidence or QA gap.")
        if result.get("answer") not in ({}, None) or result.get("answerFingerprint"):
            errors.append("A no-charge result must not carry a deliverable answer.")
        return errors
    if status != "approved":
        return [*errors, "Agent result status is invalid."]

    answer = result.get("answer")
    if not isinstance(answer, dict):
        return [*errors, "Approved Agent result does not contain an answer object."]
    if result.get("answerFingerprint") != answer_fingerprint(answer):
        errors.append("Approved answer fingerprint does not match its content.")
    required_answer = {
        "policyVersion", "answerId", "orderId", "game", "gameVersion", "generatedAt",
        "patchSensitive", "customerQuestion", "intake", "claims", "calculations",
        "answerText", "limitations", "qa", "delivery",
    }
    missing = sorted(required_answer - set(answer))
    if missing:
        return [*errors, f"Approved answer is missing fields: {', '.join(missing)}."]
    if answer.get("policyVersion") != policy.get("policyVersion"):
        errors.append("Approved answer uses the wrong quality policy.")
    if answer.get("game") != LIVE_GAME_NAME or answer.get("customerQuestion") != job.get("questionText"):
        errors.append("Approved answer does not match the signed game or question.")
    intake = answer.get("intake") or {}
    if intake.get("status") != "complete" or intake.get("missingFields") or intake.get("customerFacts") != job.get("inputs"):
        errors.append("Approved answer intake does not exactly match the signed player inputs.")
    if not str(job["inputs"].get("gameVersion") or "").lower() in str(answer.get("gameVersion") or "").lower():
        errors.append("Approved answer does not retain the player-reported game version.")
    if not _valid_iso(answer.get("generatedAt")):
        errors.append("Approved answer has an invalid generation timestamp.")
    if len(str(answer.get("answerText") or "").strip()) < 80:
        errors.append("Approved answer text is too short for the paid product promise.")
    if INTERNAL_EVIDENCE_PATTERN.search(str(answer.get("answerText") or "")):
        errors.append("Approved answer exposes an internal evidence identifier.")
    limitations = answer.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        errors.append("Approved answer does not state its limitations.")

    qa = answer.get("qa") or {}
    if qa.get("authorAgentId") != "multigame-answer-author":
        errors.append("Approved answer has an invalid author identity.")
    if qa.get("reviewerAgentId") != "multigame-answer-independent-reviewer":
        errors.append("Approved answer has an invalid independent reviewer identity.")
    if qa.get("decision") != "approve":
        errors.append("Approved answer lacks an approve decision.")
    for field in ("criticalClaimsVerified", "calculationTestsPassed", "versionChecked"):
        if qa.get(field) is not True:
            errors.append(f"Approved answer QA did not affirm {field}.")
    if not _valid_iso(qa.get("reviewedAt")):
        errors.append("Approved answer has an invalid review timestamp.")
    delivery = answer.get("delivery") or {}
    if delivery.get("status") != "ready":
        errors.append("Approved answer is not marked ready for account delivery.")
    required_window = int(policy.get("correctionPolicy", {}).get("factualErrorCorrectionWindowDays", 14))
    if int(delivery.get("correctionWindowDays", 0)) < required_window:
        errors.append("Approved answer has an insufficient correction window.")

    claims = answer.get("claims")
    if not isinstance(claims, list) or not claims or not any(item.get("critical") is True for item in claims if isinstance(item, dict)):
        errors.append("Approved answer has no independently verified critical claim.")
        claims = []
    rules = policy.get("criticalClaimRules", {})
    allowed_types = set(rules.get("allowedSourceTypes", []))
    authoritative_types = set(rules.get("authoritativeSourceTypes", []))
    minimum_evidence = int(rules.get("minimumEvidenceItems", 2))
    required_authoritative = int(rules.get("requiredAuthoritativeEvidenceItems", 1))
    max_age_hours = float(rules.get("patchSensitiveEvidenceMaxAgeHoursAtDelivery", 72))
    seen_claims: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("Approved answer contains an invalid claim.")
            continue
        claim_id = str(claim.get("claimId") or "")
        if not claim_id or claim_id in seen_claims:
            errors.append("Approved answer has a missing or duplicate claim identifier.")
        seen_claims.add(claim_id)
        if claim.get("status") in {"conflict", "unsupported"}:
            errors.append(f"Claim {claim_id} has a blocking status.")
        evidence = claim.get("evidence") if isinstance(claim.get("evidence"), list) else []
        if claim.get("critical") is True:
            if claim.get("status") != "verified" or len(evidence) < minimum_evidence:
                errors.append(f"Critical claim {claim_id} lacks verified evidence.")
            if sum(item.get("sourceType") in authoritative_types for item in evidence if isinstance(item, dict)) < required_authoritative:
                errors.append(f"Critical claim {claim_id} lacks authoritative evidence.")
        evidence_types: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                errors.append(f"Claim {claim_id} contains invalid evidence.")
                continue
            source_type = str(item.get("sourceType") or "")
            evidence_types.add(source_type)
            if source_type not in allowed_types:
                errors.append(f"Claim {claim_id} uses a disallowed evidence type.")
            if source_type == "official" and not _official_host_allowed(str(item.get("url") or "")):
                errors.append(f"Claim {claim_id} uses an unapproved official source URL.")
            if source_type == "customer_input" and item.get("url"):
                errors.append(f"Claim {claim_id} exposes a URL for private player input.")
            if not _valid_iso(item.get("retrievedAt")):
                errors.append(f"Claim {claim_id} has an invalid evidence timestamp.")
            elif answer.get("patchSensitive") is True:
                age = (now - parse_time(str(item["retrievedAt"]))).total_seconds() / 3600
                if age < -0.25 or age > max_age_hours:
                    errors.append(f"Claim {claim_id} uses stale or future evidence.")
        if claim.get("claimType") == "customer_context" and "customer_input" not in evidence_types:
            errors.append(f"Customer-context claim {claim_id} lacks player-input evidence.")
        if claim.get("claimType") == "mechanic" and claim.get("critical") is True and not {"official", "official_wiki", "in_game_test"}.intersection(evidence_types):
            errors.append(f"Critical mechanic claim {claim_id} lacks game evidence.")

    release_text = " ".join([
        str(answer.get("answerText") or ""),
        *[str(item.get("text") or "") for item in claims if isinstance(item, dict)],
    ]).lower()
    for phrase in policy.get("forbiddenOutcomePhrases", []):
        if str(phrase).lower() in release_text:
            errors.append(f"Approved answer contains forbidden outcome wording: {phrase}.")
    return errors
