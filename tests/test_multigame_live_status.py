from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from backend.multigame_products import route_multigame_request
from backend.store import (
    connect,
    create_queued_question,
    get_or_create_demo_customer,
    grant_demo_order,
    hold_queued_question,
    init_database,
)
from scripts.export_multigame_live_status import execute


class MultiGameLiveStatusTests(unittest.TestCase):
    def test_report_exposes_counts_without_customer_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "commerce.db"
            queue = root / "jobs"
            for directory in ("inbox", "outbox", "archive", "rejected"):
                (queue / directory).mkdir(parents=True)
            init_database(
                database,
                ROOT / "local" / "raidbench-local-schema.sql",
                ROOT / "content" / "skus.json",
                ROOT / "content" / "multigame-products.json",
            )
            payload = {
                "productId": "palworld-base-progression-review",
                "gameId": "palworld",
                "questionText": "Which measured base handoff should I test before changing the full layout?",
                "inputs": {
                    "gameVersion": "1.0.3",
                    "serverType": "Single-player world",
                    "currentGoal": "Move one measured output batch",
                    "baseOrProgressionState": "The work area rises by eighty while the same destination remains unchanged.",
                    "observedProblem": "The destination does not change during the controlled observation.",
                },
            }
            routed = route_multigame_request(payload, implemented_handlers={payload["productId"]})
            with closing(connect(database)) as connection:
                customer = get_or_create_demo_customer(connection)
                grant_demo_order(connection, customer["id"], "credits-palworld-80", "status-order")
                question = create_queued_question(
                    connection,
                    customer["id"],
                    routed["productId"],
                    routed["questionText"],
                    routed["inputs"],
                    "status-question",
                    routed["game"],
                )
                hold_queued_question(connection, question["id"], "Independent QA held the answer without a charge.")
            report = execute(database, queue, ROOT)
            self.assertEqual(report["status"], "healthy")
            self.assertEqual(report["metrics"]["heldWithoutCharge"], 1)
            self.assertEqual(report["metrics"]["creditsCharged"], 0)
            serialized = str(report)
            self.assertNotIn(customer["email"], serialized)
            self.assertNotIn(payload["questionText"], serialized)


if __name__ == "__main__":
    unittest.main()
