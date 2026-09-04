from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.request
from contextlib import closing
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]

from backend.multigame_products import (
    ProductRoutingError,
    load_product_catalog,
    public_multigame_catalog,
    route_multigame_request,
)
from backend.server import create_server
from backend.store import (
    account_summary,
    catalog,
    connect,
    create_deferred_question,
    get_or_create_demo_customer,
    init_database,
)


def palworld_request() -> dict:
    return {
        "productId": "palworld-base-progression-review",
        "gameId": "palworld",
        "questionText": "Why does my ore base stop producing while I am away from the area?",
        "inputs": {
            "gameVersion": "1.0",
            "serverType": "dedicated server",
            "currentGoal": "Keep ore production stable",
            "baseOrProgressionState": "Second base with mining and transport Pals",
            "observedProblem": "Storage remains empty after an offline period",
        },
    }


class MultiGameCatalogTests(unittest.TestCase):
    def test_catalog_registers_only_palworld_as_controlled_live_product(self) -> None:
        catalog_data = load_product_catalog()
        products = catalog_data["products"]
        self.assertEqual(len(products), 11)
        self.assertEqual(len({item["id"] for item in products}), 11)
        self.assertEqual(len({item["gameId"] for item in products}), 11)
        self.assertNotIn("rust", {item["gameId"] for item in products})
        live = [item for item in products if item["status"] == "ready_live"]
        self.assertEqual([item["id"] for item in live], ["palworld-base-progression-review"])
        self.assertEqual(sum(item["status"] == "hidden_pending_qa" for item in products), 10)

        public = public_multigame_catalog()
        self.assertEqual([item["id"] for item in public["products"]], ["palworld-base-progression-review"])
        self.assertEqual(public["hiddenPendingQaCount"], 10)

    def test_supported_intake_requires_an_implemented_live_handler(self) -> None:
        result = route_multigame_request(palworld_request())
        self.assertEqual(result["reasonCode"], "answer_workflow_unavailable")
        self.assertEqual(result["status"], "held_without_charge")
        self.assertEqual(result["creditsQuoted"], 80)
        self.assertEqual(result["creditsCharged"], 0)
        self.assertFalse(result["purchaseAvailable"])
        self.assertEqual(result["missingInputs"], [])

        accepted = route_multigame_request(
            palworld_request(),
            implemented_handlers={"palworld-base-progression-review"},
        )
        self.assertEqual(accepted["status"], "queued_for_qa")
        self.assertEqual(accepted["reasonCode"], "")
        self.assertTrue(accepted["purchaseAvailable"])
        self.assertEqual(accepted["creditsCharged"], 0)

    def test_missing_context_and_disallowed_requests_are_no_charge(self) -> None:
        missing = palworld_request()
        missing["inputs"] = {"gameVersion": "1.0"}
        missing_result = route_multigame_request(missing)
        self.assertEqual(missing_result["reasonCode"], "missing_context")
        self.assertEqual(missing_result["creditsCharged"], 0)
        self.assertIn("serverType", missing_result["missingInputs"])

        blocked = palworld_request()
        blocked["questionText"] = "How can I use a duplication exploit to create unlimited materials?"
        blocked_result = route_multigame_request(blocked)
        self.assertEqual(blocked_result["reasonCode"], "policy_blocked")
        self.assertEqual(blocked_result["creditsCharged"], 0)

    def test_mismatched_game_is_rejected(self) -> None:
        payload = palworld_request()
        payload["gameId"] = "poe2"
        with self.assertRaises(ProductRoutingError):
            route_multigame_request(payload)


class MultiGameStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "multigame.db"
        init_database(
            self.db_path,
            ROOT / "local" / "raidbench-local-schema.sql",
            ROOT / "content" / "skus.json",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_only_palworld_joins_the_live_checkout_catalog(self) -> None:
        with closing(connect(self.db_path)) as connection:
            hidden_count = connection.execute(
                "SELECT COUNT(*) AS count FROM credit_actions WHERE status = 'hidden_pending_qa'"
            ).fetchone()["count"]
            public_actions = catalog(connection, include_demo=False)["actions"]
        self.assertEqual(hidden_count, 10)
        self.assertEqual({item["id"] for item in public_actions}, {
            "rust-instant-raid-answer",
            "rust-raid-prep",
            "palworld-base-progression-review",
        })

    def test_deferred_product_records_real_game_quote_and_zero_charge(self) -> None:
        routed = route_multigame_request(palworld_request())
        with closing(connect(self.db_path)) as connection:
            customer = get_or_create_demo_customer(connection)
            question = create_deferred_question(
                connection,
                customer["id"],
                routed["questionType"],
                routed["questionText"],
                routed["inputs"],
                routed["reason"],
                "multigame-store-1",
                game=routed["game"],
                credits_cost=routed["creditsQuoted"],
            )
            balance = account_summary(connection, customer["id"])["creditBalance"]
        self.assertEqual(question["game"], "Palworld")
        self.assertEqual(question["creditsCost"], 80)
        self.assertEqual(question["creditsCharged"], 0)
        self.assertEqual(question["status"], "needs_review")
        self.assertEqual(balance, 0)


class MultiGameHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "multigame-http.db"
        self.queue_path = Path(self.temp_dir.name) / "jobs"
        os.environ["RAIDBENCH_JOB_QUEUE_DIR"] = str(self.queue_path)
        os.environ["RAIDBENCH_JOB_SIGNING_SECRET"] = "test-multigame-signing-secret-32-bytes"
        self.server = create_server(host="127.0.0.1", port=0, root=ROOT, db_path=self.db_path, mode="demo")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        os.environ.pop("RAIDBENCH_JOB_QUEUE_DIR", None)
        os.environ.pop("RAIDBENCH_JOB_SIGNING_SECRET", None)
        self.temp_dir.cleanup()

    def request(self, path: str, *, method: str = "GET", body: dict | None = None, key: str | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if key:
            headers["Idempotency-Key"] = key
        request = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_http_intake_is_idempotent_reserves_credits_and_exports_private_job(self) -> None:
        status, product_catalog = self.request("/api/multigame/products")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in product_catalog["products"]], ["palworld-base-progression-review"])
        self.assertEqual(product_catalog["hiddenPendingQaCount"], 10)

        session_status, _ = self.request("/api/demo/session", method="POST")
        self.assertEqual(session_status, 200)
        order_status, order = self.request(
            "/api/demo/orders",
            method="POST",
            body={"sku": "credits-scout-120"},
            key="multigame-http-order",
        )
        self.assertEqual(order_status, 201)
        self.assertEqual(order["creditBalance"], 120)
        first_status, first = self.request(
            "/api/questions/multigame",
            method="POST",
            body=palworld_request(),
            key="multigame-http-1",
        )
        second_status, second = self.request(
            "/api/questions/multigame",
            method="POST",
            body=palworld_request(),
            key="multigame-http-1",
        )
        self.assertEqual(first_status, 202)
        self.assertEqual(second_status, 202)
        self.assertEqual(first["question"]["id"], second["question"]["id"])
        self.assertEqual(first["question"]["game"], "Palworld")
        self.assertEqual(first["question"]["status"], "queued")
        self.assertEqual(first["question"]["creditsCharged"], 0)
        self.assertEqual(first["customer"]["creditBalance"], 120)
        self.assertEqual(first["customer"]["reservedCredits"], 80)
        self.assertEqual(first["customer"]["availableCredits"], 40)
        self.assertTrue(first["intake"]["purchaseAvailable"])

        questions_status, questions = self.request("/api/questions")
        self.assertEqual(questions_status, 200)
        self.assertEqual(len(questions["questions"]), 1)
        jobs = list((self.queue_path / "inbox").glob("job_*.json"))
        self.assertEqual(len(jobs), 1)
        job_text = jobs[0].read_text()
        self.assertNotIn("@", job_text)
        self.assertNotIn("payment", job_text.lower())


if __name__ == "__main__":
    unittest.main()
