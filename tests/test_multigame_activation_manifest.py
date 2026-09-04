from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from scripts.build_multigame_activation_manifest import ActivationManifestError, build_manifest


class MultiGameActivationManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = json.loads((ROOT / "content" / "multigame-products.json").read_text())
        self.product = self.catalog["products"][1]
        self.ready = {
            "generatedAt": "2026-09-04T00:00:00+00:00",
            "mode": "shadow_no_charge",
            "summary": {"creditsCharged": 0},
            "products": [{
                "productId": self.product["id"],
                "decision": "ready_live",
                "shadowCases": 15,
                "supportedQaPassRate": 0.9,
                "noChargeAccuracy": 1.0,
                "idempotencyPassed": True,
                "inAccountDeliveryPassed": True,
                "gateResults": [{"id": f"gate_{index}", "passed": True} for index in range(10)],
            }],
        }

    def test_ready_product_becomes_private_candidate_without_catalog_mutation(self) -> None:
        manifest = build_manifest(self.ready, self.catalog)
        self.assertEqual(manifest["summary"]["eligibleProducts"], 1)
        self.assertFalse(manifest["summary"]["publicCatalogMutationPerformed"])
        self.assertFalse(manifest["phase8Required"])
        self.assertEqual(manifest["candidates"][0]["activationStatus"], "live_monitored")
        self.assertEqual(self.product["status"], "ready_live")

    def test_failed_gate_blocks_manifest(self) -> None:
        self.ready["products"][0]["gateResults"][3]["passed"] = False
        with self.assertRaises(ActivationManifestError):
            build_manifest(self.ready, self.catalog)

    def test_nonzero_shadow_charge_blocks_manifest(self) -> None:
        self.ready["summary"]["creditsCharged"] = 1
        with self.assertRaises(ActivationManifestError):
            build_manifest(self.ready, self.catalog)


if __name__ == "__main__":
    unittest.main()
