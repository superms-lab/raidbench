from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from backend.answer_engine import load_raid_data
from backend.digital_products import (
    STAGING_PACK_PRICE_USD,
    STAGING_PACK_SKU,
    build_staging_pack,
    staging_pack_product,
)


class DigitalProductTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_raid_data(ROOT / "content" / "rust-raid-data.json")
        self.data["verifiedAt"] = "2026-09-06"
        self.payload = {
            "serverType": "vanilla",
            "targets": [
                {"targetId": "sheet-door", "quantity": 2, "method": "satchels"},
                {"targetId": "stone-wall", "quantity": 1, "method": "rockets"},
            ],
            "bufferPercent": 15,
            "availableSulfur": 9000,
            "teamSize": 2,
            "routePreference": "lowest_sulfur",
            "ownedInventory": {"rockets": 2, "c4": 0, "satchels": 4, "explosiveAmmo": 0},
            "notes": "Use the west-side approach.",
        }

    def test_product_contract_is_accountless_one_time_purchase(self) -> None:
        product = staging_pack_product(available=True)
        self.assertEqual(product["id"], STAGING_PACK_SKU)
        self.assertEqual(product["price"], {"amount": STAGING_PACK_PRICE_USD, "currency": "USD"})
        self.assertEqual(product["purchaseType"], "one_time")
        self.assertFalse(product["accountRequired"])
        self.assertTrue(product["available"])

    def test_preview_reveals_decision_inputs_but_locks_full_report(self) -> None:
        preview, report = build_staging_pack(
            self.payload,
            self.data,
            now=datetime(2026, 9, 6, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(preview["selected"]["sulfur"], 9440)
        self.assertEqual(preview["selected"]["bufferedSulfur"], 10856)
        self.assertEqual(preview["primaryGap"]["amount"], 1856)
        self.assertEqual(preview["readiness"]["status"], "hold_for_resources")
        self.assertGreaterEqual(len(preview["lockedSections"]), 6)
        self.assertNotIn("routeReview", preview)
        self.assertNotIn("crafting", preview)

        self.assertEqual(report["productId"], STAGING_PACK_SKU)
        self.assertEqual(report["pricePaid"]["amount"], 4.99)
        self.assertEqual(report["qa"]["status"], "approved")
        self.assertEqual(len(report["plan"]["teamRoles"]), 2)
        self.assertEqual(report["inputs"]["notes"], "Use the west-side approach.")


if __name__ == "__main__":
    unittest.main()
