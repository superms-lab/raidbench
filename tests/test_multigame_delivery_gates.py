from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from scripts.verify_multigame_delivery_gates import verify_product_delivery


class MultiGameDeliveryGateTests(unittest.TestCase):
    def test_hidden_product_uses_real_delivery_code_once(self) -> None:
        products = json.loads((ROOT / "content" / "multigame-products.json").read_text())["products"]
        product = next(item for item in products if item["id"] == "palworld-base-progression-review")
        answer = {
            "policyVersion": "raidbench-paid-answer-v2",
            "answerId": "answer_delivery_test",
            "orderId": "shadow_no_charge_delivery_test",
            "game": "Palworld",
            "gameVersion": "1.0 test scope",
            "generatedAt": "2026-09-04T00:00:00+00:00",
            "patchSensitive": True,
            "customerQuestion": "Which observed handoff should I test first?",
            "intake": {"status": "complete", "missingFields": [], "customerFacts": {"serverType": "test"}},
            "claims": [],
            "calculations": [],
            "answerText": "Test the observed handoff while holding other inputs constant.",
            "limitations": ["This is an isolated delivery test."],
            "qa": {
                "authorAgentId": "shadow-answer-author",
                "reviewerAgentId": "shadow-answer-independent-reviewer",
                "decision": "approve",
                "criticalClaimsVerified": True,
                "calculationTestsPassed": True,
                "versionChecked": True,
                "reviewedAt": "2026-09-04T00:00:00+00:00",
                "reviewNotes": "Delivery fixture only.",
            },
            "delivery": {"status": "ready", "correctionWindowDays": 14, "updatePolicy": "Retest after changes."},
        }
        result = verify_product_delivery(answer, product)
        self.assertTrue(result["idempotencyPassed"])
        self.assertTrue(result["inAccountDeliveryPassed"])
        self.assertEqual(result["firstBalance"], 450)
        self.assertEqual(result["balanceAfterFirst"], 370)
        self.assertEqual(result["balanceAfterReplay"], 370)
        self.assertEqual(result["questionCount"], 1)
        self.assertEqual(result["debitCount"], 1)
        self.assertEqual(result["deliveryCount"], 1)


if __name__ == "__main__":
    unittest.main()
