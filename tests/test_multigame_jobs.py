from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from backend.multigame_jobs import (
    MultiGameJobError,
    answer_fingerprint,
    build_signed_job,
    export_signed_job,
    validate_result_envelope,
    validate_signed_job,
    write_json_atomic,
)
from backend.multigame_products import route_multigame_request
from backend.store import (
    InsufficientCreditsError,
    account_summary,
    complete_queued_question,
    connect,
    create_queued_question,
    create_verified_question,
    get_or_create_demo_customer,
    grant_demo_order,
    init_database,
)
from scripts.import_multigame_answer_jobs import execute as import_answers


SIGNING_SECRET = "phase8-test-signing-secret-with-32-bytes"


def request_payload() -> dict:
    return {
        "productId": "palworld-base-progression-review",
        "gameId": "palworld",
        "questionText": "Produced ore reaches the work area while nearby storage stays flat. Which handoff should I test first?",
        "inputs": {
            "gameVersion": "1.0.3",
            "serverType": "Dedicated server, no production-changing mods",
            "currentGoal": "Move one measured ore batch into storage",
            "baseOrProgressionState": "Ore at the work area rises from 40 to 120 while storage remains at 200 during a twenty-minute observation.",
            "observedProblem": "Production rises but the recorded destination storage does not change.",
        },
    }


def approved_answer(job: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    timestamp = now.replace(microsecond=0).isoformat()
    source_time = (now - timedelta(hours=1)).replace(microsecond=0).isoformat()
    answer = {
        "policyVersion": "raidbench-paid-answer-v2",
        "answerId": f"ans_{job['questionId']}",
        "orderId": job["questionId"],
        "game": "Palworld",
        "gameVersion": "Player-reported Palworld 1.0.3; publisher source check 2026-09-04",
        "generatedAt": timestamp,
        "patchSensitive": True,
        "customerQuestion": job["questionText"],
        "intake": {"status": "complete", "missingFields": [], "customerFacts": job["inputs"]},
        "claims": [{
            "claimId": "claim_observed_handoff",
            "claimType": "customer_context",
            "critical": True,
            "text": "The first measured gap is between accumulated work-area output and unchanged destination storage.",
            "status": "verified",
            "calculationId": "",
            "assumptions": ["The two recorded counts refer to the same storage and observation window."],
            "conflictNotes": "",
            "evidence": [
                {
                    "evidenceId": "ev_palworld_official_1",
                    "sourceType": "official",
                    "title": "Pocketpair game news",
                    "url": "https://www.pocketpair.jp/en/game-news/",
                    "retrievedAt": source_time,
                    "supports": "Publisher update context for the version-scoped review.",
                },
                {
                    "evidenceId": "ev_palworld_customer_input",
                    "sourceType": "customer_input",
                    "title": "Player-supplied request context",
                    "url": "",
                    "retrievedAt": job["submittedAt"],
                    "supports": "The before-and-after counts and unchanged destination reported by the player.",
                },
            ],
        }],
        "calculations": [],
        "answerText": (
            "Treat the production-to-storage handoff as the first measured bottleneck, not as a proven pathing bug. "
            "Run one matched twenty-minute test after changing only the transport assignment or route condition, "
            "then compare work-area output and the same destination storage before changing anything else."
        ),
        "limitations": [
            "The supplied observations do not establish a specific simulation, pathing, or server mechanic as the cause."
        ],
        "qa": {
            "authorAgentId": "multigame-answer-author",
            "reviewerAgentId": "multigame-answer-independent-reviewer",
            "decision": "approve",
            "criticalClaimsVerified": True,
            "calculationTestsPassed": True,
            "versionChecked": True,
            "reviewedAt": timestamp,
            "reviewNotes": "The recommendation is limited to the measured player-supplied handoff.",
        },
        "delivery": {
            "status": "ready",
            "correctionWindowDays": 14,
            "updatePolicy": "Recheck after a later game update or server-setting change.",
        },
    }
    return answer


def approved_result(job: dict, now: datetime | None = None) -> dict:
    answer = approved_answer(job, now)
    return {
        "schemaVersion": "1.0.0",
        "jobId": job["jobId"],
        "questionId": job["questionId"],
        "productId": job["productId"],
        "requestSignature": job["requestSignature"],
        "status": "approved",
        "reasonCode": "",
        "reason": "",
        "processedAt": (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat(),
        "answerFingerprint": answer_fingerprint(answer),
        "answer": answer,
    }


class MultiGameJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "commerce.db"
        self.queue = self.root / "jobs"
        init_database(
            self.database,
            ROOT / "local" / "raidbench-local-schema.sql",
            ROOT / "content" / "skus.json",
            ROOT / "content" / "multigame-products.json",
        )
        self.connection = connect(self.database)
        self.customer = get_or_create_demo_customer(self.connection)
        grant_demo_order(self.connection, self.customer["id"], "credits-command-450", "phase8-credit-order")
        self.routed = route_multigame_request(
            request_payload(),
            implemented_handlers={"palworld-base-progression-review"},
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def queue_question(self, key: str = "phase8-question") -> tuple[dict, dict]:
        question = create_queued_question(
            self.connection,
            self.customer["id"],
            self.routed["productId"],
            self.routed["questionText"],
            self.routed["inputs"],
            key,
            self.routed["game"],
        )
        job = build_signed_job(question, self.routed, SIGNING_SECRET)
        export_signed_job(self.queue, job)
        return question, job

    def test_signed_job_contains_no_customer_or_payment_identity(self) -> None:
        _, job = self.queue_question()
        validate_signed_job(job, SIGNING_SECRET)
        serialized = json.dumps(job)
        self.assertNotIn(self.customer["email"], serialized)
        self.assertNotIn("customerId", serialized)
        self.assertNotIn("paypal", serialized.lower())
        tampered = json.loads(serialized)
        tampered["creditsQuoted"] = 81
        with self.assertRaises(MultiGameJobError):
            validate_signed_job(tampered, SIGNING_SECRET)

    def test_reservation_protects_balance_and_delivery_debits_once(self) -> None:
        question, job = self.queue_question()
        summary = account_summary(self.connection, self.customer["id"])
        self.assertEqual(summary["creditBalance"], 450)
        self.assertEqual(summary["reservedCredits"], 80)
        self.assertEqual(summary["availableCredits"], 370)

        rust_answer = {
            "evidence": [],
            "title": "Test Rust answer",
        }
        create_verified_question(
            self.connection,
            self.customer["id"],
            "rust-instant-raid-answer",
            "instant",
            "Rust raid cost request",
            {"targetId": "sheet-door"},
            rust_answer,
            "phase8-rust-answer",
        )
        ledger = self.connection.execute(
            "SELECT balance_after FROM credit_ledger WHERE idempotency_key = 'answer:phase8-rust-answer'"
        ).fetchone()
        self.assertEqual(ledger["balance_after"], 440)
        self.assertEqual(account_summary(self.connection, self.customer["id"])["availableCredits"], 360)

        answer = approved_answer(job)
        first = complete_queued_question(self.connection, question["id"], answer)
        repeated = complete_queued_question(self.connection, question["id"], answer)
        self.assertEqual(first["id"], repeated["id"])
        self.assertEqual(first["creditsCharged"], 80)
        self.assertEqual(account_summary(self.connection, self.customer["id"])["creditBalance"], 360)
        self.assertEqual(account_summary(self.connection, self.customer["id"])["reservedCredits"], 0)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) count FROM credit_ledger WHERE idempotency_key = ?",
            (f"queued-answer:{question['id']}",),
        ).fetchone()["count"], 1)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) count FROM delivery_records WHERE action_id = 'palworld-base-progression-review'"
        ).fetchone()["count"], 1)

    def test_reservations_prevent_oversubmission(self) -> None:
        self.connection.execute("DELETE FROM credit_ledger")
        grant_demo_order(self.connection, self.customer["id"], "credits-scout-120", "phase8-small-order")
        self.queue_question("phase8-first-reservation")
        with self.assertRaises(InsufficientCreditsError):
            self.queue_question("phase8-second-reservation")

    def test_importer_validates_and_archives_approved_answer(self) -> None:
        question, job = self.queue_question()
        policy = json.loads((ROOT / "content" / "answer-quality-policy.json").read_text())
        result = approved_result(job)
        self.assertEqual(validate_result_envelope(job, result, policy), [])
        write_json_atomic(self.queue / "outbox" / f"{job['jobId']}.json", result)

        self.connection.close()
        imported = import_answers(self.database, self.queue, SIGNING_SECRET, 30)
        repeated = import_answers(self.database, self.queue, SIGNING_SECRET, 30)
        self.connection = connect(self.database)
        self.assertEqual(imported["approved"], 1)
        self.assertEqual(imported["rejected"], 0)
        self.assertEqual(repeated["found"], 0)
        row = self.connection.execute("SELECT status, credits_charged FROM questions WHERE id = ?", (question["id"],)).fetchone()
        self.assertEqual(dict(row), {"status": "ready", "credits_charged": 80})
        self.assertEqual(len(list((self.queue / "archive").glob("job_*.json"))), 2)

    def test_invalid_agent_result_is_held_without_charge(self) -> None:
        question, job = self.queue_question()
        result = approved_result(job)
        result["answer"]["customerQuestion"] = "A different unsigned question"
        write_json_atomic(self.queue / "outbox" / f"{job['jobId']}.json", result)

        self.connection.close()
        imported = import_answers(self.database, self.queue, SIGNING_SECRET, 30)
        self.connection = connect(self.database)
        row = self.connection.execute("SELECT status, credits_charged FROM questions WHERE id = ?", (question["id"],)).fetchone()
        self.assertEqual(imported["rejected"], 1)
        self.assertEqual(dict(row), {"status": "needs_review", "credits_charged": 0})
        self.assertEqual(account_summary(self.connection, self.customer["id"])["creditBalance"], 450)

    def test_expired_job_releases_reserved_credits(self) -> None:
        question, _ = self.queue_question()
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.connection.execute("UPDATE questions SET submitted_at = ? WHERE id = ?", (old, question["id"]))
        self.connection.close()
        imported = import_answers(self.database, self.queue, SIGNING_SECRET, 30)
        self.connection = connect(self.database)
        row = self.connection.execute("SELECT status, credits_charged FROM questions WHERE id = ?", (question["id"],)).fetchone()
        self.assertEqual(imported["expired"], 1)
        self.assertEqual(dict(row), {"status": "needs_review", "credits_charged": 0})
        self.assertEqual(account_summary(self.connection, self.customer["id"])["reservedCredits"], 0)


if __name__ == "__main__":
    unittest.main()
