from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from scripts.prepare_shadow_benchmarks import prepare_suite
from scripts.run_shadow_answer_benchmarks import (
    connect_database,
    deterministic_route,
    evaluate_readiness,
    reviewed_paid_answer,
    store_result,
    validate_candidate,
    validate_closed_evidence,
    validate_review,
    validate_suite,
)


class ShadowBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp = Path(self.temp_dir.name)
        self.source_db = self.temp / "sources.db"
        connection = sqlite3.connect(self.source_db)
        connection.execute(
            """
            CREATE TABLE source_snapshots (
              source_id TEXT NOT NULL,
              fetched_at TEXT NOT NULL,
              ok INTEGER NOT NULL,
              title TEXT NOT NULL,
              body_sample TEXT NOT NULL,
              content_hash TEXT NOT NULL
            )
            """
        )
        blueprints = json.loads((ROOT / "content" / "multigame-shadow-blueprints.json").read_text())
        source_ids = {source_id for item in blueprints["blueprints"] for source_id in item["evidenceSourceIds"]}
        for source_id in source_ids:
            connection.execute(
                "INSERT INTO source_snapshots VALUES (?, '2026-09-03T11:00:00+00:00', 1, ?, ?, ?)",
                (source_id, f"Publisher snapshot {source_id}", f"Current publisher evidence excerpt for {source_id}.", f"hash-{source_id}"),
            )
        connection.commit()
        connection.close()
        self.suite = prepare_suite(self.source_db, "2026-09-03T12:00:00+00:00")
        self.products = {
            item["id"]: item
            for item in json.loads((ROOT / "content" / "multigame-products.json").read_text())["products"]
        }
        self.policy = json.loads((ROOT / "content" / "answer-quality-policy.json").read_text())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def supported_case(self, game_id: str = "ark-survival-ascended") -> dict:
        return next(item for item in self.suite["cases"] if item["gameId"] == game_id and item["category"] == "supported")

    def test_suite_has_three_unique_cases_for_every_product(self) -> None:
        validate_suite(self.suite, self.products)
        self.assertEqual(self.suite["summary"], {
            "products": 11,
            "cases": 67,
            "supportedCases": 32,
            "noChargeCases": 35,
        })
        self.assertEqual(len({item["benchmarkKey"] for item in self.suite["cases"]}), 67)
        self.assertTrue(all(item["evidenceFingerprint"] for item in self.suite["cases"]))
        palworld_supported = [
            item for item in self.suite["cases"]
            if item["productId"] == "palworld-base-progression-review" and item["category"] == "supported"
        ]
        self.assertEqual(len({item["evidenceFingerprint"] for item in palworld_supported}), 1)
        self.assertTrue(all(item["evidenceFresh"] for item in self.suite["cases"] if item["category"] == "supported"))
        by_product = {
            product_id: [item for item in self.suite["cases"] if item["productId"] == product_id]
            for product_id in self.products
        }
        palworld = by_product["palworld-base-progression-review"]
        self.assertEqual(len(palworld), 15)
        self.assertEqual(sum(item["expectedDisposition"] == "answer_candidate" for item in palworld), 10)
        self.assertEqual(sum(item["expectedDisposition"] == "no_charge" for item in palworld), 5)
        self.assertTrue(all(sum(item["expectedDisposition"] == "answer_candidate" for item in cases) >= 2 for cases in by_product.values()))
        self.assertTrue(all(sum(item["expectedDisposition"] == "no_charge" for item in cases) >= 3 for cases in by_product.values()))

    def test_missing_and_policy_cases_match_production_no_charge_router(self) -> None:
        negatives = [item for item in self.suite["cases"] if item["expectedDisposition"] == "no_charge"]
        self.assertEqual(len(negatives), 35)
        for case in negatives:
            result = deterministic_route(case)
            self.assertEqual(result["reasonCode"], case["expectedReasonCode"])
            self.assertEqual(result["creditsCharged"], 0)
            self.assertFalse(result["purchaseAvailable"])

    def test_supported_case_has_closed_current_evidence(self) -> None:
        case = self.supported_case()
        self.assertEqual(validate_closed_evidence(case, self.policy), [])
        self.assertEqual({item["sourceType"] for item in case["evidence"]}, {
            "official", "customer_input", "deterministic_test"
        })

    def test_evidence_fingerprint_changes_only_when_source_content_changes(self) -> None:
        before = {
            item["productId"]: item
            for item in self.suite["cases"]
            if item["category"] == "supported"
        }
        connection = sqlite3.connect(self.source_db)
        connection.execute("UPDATE source_snapshots SET fetched_at = '2026-09-03T11:30:00+00:00'")
        connection.commit()
        connection.close()
        refreshed = prepare_suite(self.source_db, "2026-09-03T12:00:00+00:00")
        refreshed_by_product = {
            item["productId"]: item
            for item in refreshed["cases"]
            if item["category"] == "supported"
        }
        self.assertEqual(
            {key: item["evidenceFingerprint"] for key, item in before.items()},
            {key: item["evidenceFingerprint"] for key, item in refreshed_by_product.items()},
        )
        self.assertNotEqual(
            before["palworld-base-progression-review"]["evidenceOldestAt"],
            refreshed_by_product["palworld-base-progression-review"]["evidenceOldestAt"],
        )

        connection = sqlite3.connect(self.source_db)
        connection.execute(
            "UPDATE source_snapshots SET content_hash = 'changed-content' WHERE source_id = 'palworld-official-news'"
        )
        connection.commit()
        connection.close()
        changed = prepare_suite(self.source_db, "2026-09-03T12:00:00+00:00")
        changed_case = next(
            item for item in changed["cases"]
            if item["productId"] == "palworld-base-progression-review" and item["category"] == "supported"
        )
        self.assertNotEqual(
            refreshed_by_product["palworld-base-progression-review"]["evidenceFingerprint"],
            changed_case["evidenceFingerprint"],
        )

    def test_candidate_and_independent_review_contracts(self) -> None:
        case = self.supported_case()
        fixture = case["calculationFixture"]
        deterministic_id = next(item["evidenceId"] for item in case["evidence"] if item["sourceType"] == "deterministic_test")
        customer_id = next(item["evidenceId"] for item in case["evidence"] if item["sourceType"] == "customer_input")
        calculations = [
            {
                "calculationId": item["calculationId"],
                "formula": f"verified {item['path']}",
                "expected": item["expected"],
                "actual": item["expected"],
                "tolerance": item["tolerance"],
                "passed": True,
            }
            for item in fixture["assertions"]
        ]
        candidate = {
            "caseId": case["caseId"],
            "stage": "shadow_answer",
            "authorAgentId": "shadow-answer-author",
            "versionScope": case["gameVersion"],
            "disposition": "answer_candidate",
            "noChargeReason": "",
            "answerText": "The player-entered roster and reserve produce the tested material totals. Recheck the displayed blueprint before crafting.",
            "claims": [{
                "claimId": "claim_roster_total",
                "claimType": "numeric",
                "critical": True,
                "text": "The supplied values produce a twenty-saddle budget.",
                "status": "verified",
                "evidenceIds": [customer_id, deterministic_id],
                "calculationId": "saddles_budgeted",
                "assumptions": ["The entered blueprint values match the current server."],
                "conflictNotes": "",
            }],
            "calculations": calculations,
            "limitations": ["This does not establish boss readiness or official-rate material costs."],
            "confidence": "high",
        }
        self.assertEqual(validate_candidate(case, candidate, self.policy), [])
        review = {
            "caseId": case["caseId"],
            "stage": "shadow_answer_qa",
            "reviewerAgentId": "shadow-answer-independent-reviewer",
            "decision": "approve",
            "criticalClaimsVerified": True,
            "calculationTestsPassed": True,
            "versionChecked": True,
            "limitationsConfirmed": True,
            "productPromiseSatisfied": True,
            "claimReviews": [{
                "claimId": "claim_roster_total",
                "status": "supported",
                "evidenceIds": [customer_id, deterministic_id],
                "notes": "The claim matches the player input and deterministic assertion.",
            }],
            "blockers": [],
            "warnings": [],
            "reviewNotes": "Closed evidence and arithmetic reviewed independently.",
        }
        self.assertEqual(validate_review(case, candidate, review), [])
        peer_review = json.loads(json.dumps(review))
        peer_review["stage"] = "shadow_answer_peer_qa"
        peer_review["reviewerAgentId"] = "shadow-answer-peer-reviewer"
        self.assertEqual(
            validate_review(
                case,
                candidate,
                peer_review,
                expected_stage="shadow_answer_peer_qa",
                expected_reviewer="shadow-answer-peer-reviewer",
            ),
            [],
        )
        answer = reviewed_paid_answer(case, candidate, review, self.policy)
        self.assertEqual(answer["orderId"].split("_")[0], "shadow")
        self.assertEqual(answer["qa"]["decision"], "approve")
        self.assertNotEqual(answer["qa"]["authorAgentId"], answer["qa"]["reviewerAgentId"])

        no_charge_candidate = {
            **candidate,
            "disposition": "no_charge",
            "noChargeReason": "The complete product cannot be supported.",
            "answerText": "No charge. More inspectable evidence is required.",
            "claims": [],
            "calculations": [],
        }
        disputed_review = {
            **review,
            "decision": "block",
            "criticalClaimsVerified": False,
            "productPromiseSatisfied": False,
            "claimReviews": [],
            "blockers": ["The refusal is broader than the supplied evidence requires."],
        }
        self.assertEqual(validate_review(case, no_charge_candidate, disputed_review), [])

        unsafe = json.loads(json.dumps(candidate))
        unsafe["claims"][0]["evidenceIds"] = [customer_id]
        self.assertTrue(any("evidence" in error for error in validate_candidate(case, unsafe, self.policy)))

    def test_shadow_database_deduplicates_cases_and_enforces_zero_credits(self) -> None:
        database = self.temp / "shadow.db"
        report_path = self.temp / "readiness.json"
        connection = connect_database(database)
        try:
            connection.execute(
                "INSERT INTO shadow_runs (id,suite_id,mode,status,started_at) VALUES ('run_test','suite_test','validation_only','running','2026-09-03T12:00:00+00:00')"
            )
            case = next(item for item in self.suite["cases"] if item["category"] == "missing_context")
            result = {
                "actualDisposition": "no_charge",
                "actualReasonCode": "missing_context",
                "deterministicStatus": "pass",
                "criticalFailure": False,
            }
            store_result(connection, "run_test", case, result)
            store_result(connection, "run_test", case, result)
            row = connection.execute("SELECT COUNT(*) count,MAX(attempts) attempts,MAX(credits_charged) credits FROM shadow_benchmark_results").fetchone()
            self.assertEqual(dict(row), {"count": 1, "attempts": 2, "credits": 0})
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO shadow_benchmark_results (
                      benchmark_key,case_id,product_id,game_id,category,expected_disposition,
                      actual_disposition,deterministic_status,critical_failure,credits_charged,
                      attempts,latest_run_id,created_at,updated_at
                    ) VALUES ('bad','bad','bad','bad','bad','bad','bad','bad',0,1,1,'run_test','now','now')
                    """
                )
            report = evaluate_readiness(connection, report_path)
            self.assertEqual(report["summary"]["creditsCharged"], 0)
            self.assertEqual(report["summary"]["eligibleProducts"], 0)
            self.assertTrue(all(item["decision"] == "hold" for item in report["products"]))
        finally:
            connection.close()

    def test_complex_products_require_ten_dual_reviews(self) -> None:
        gates = json.loads((ROOT / "content" / "multigame-activation-gates.json").read_text())["products"]
        by_id = {item["productId"]: item for item in gates}
        for product_id in (
            "counter-strike-2-round-plan-review",
            "dota-2-match-decision-review",
            "pubg-battlegrounds-rotation-review",
        ):
            self.assertEqual(by_id[product_id]["minimumInterReviewerCases"], 10)
            self.assertEqual(by_id[product_id]["minimumInterReviewerAgreementRate"], 0.8)
        self.assertTrue(all(
            item["minimumInterReviewerCases"] == 0
            for product_id, item in by_id.items()
            if product_id not in {
                "counter-strike-2-round-plan-review",
                "dota-2-match-decision-review",
                "pubg-battlegrounds-rotation-review",
            }
        ))


if __name__ == "__main__":
    unittest.main()
