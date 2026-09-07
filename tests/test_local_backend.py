from __future__ import annotations

import json
import hashlib
import tempfile
import threading
import time
import unittest
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]

from backend.answer_engine import UnsupportedScopeError, build_raid_answer, load_raid_data
from backend.digital_products import build_staging_pack
from backend.email_delivery import ResendEmailDelivery, Smtp2GoEmailDelivery
from backend.paypal import PayPalWebhookSignatureError
from backend.server import create_server
from backend.store import (
    account_summary,
    catalog,
    claim_owner_notification,
    complete_paypal_capture_event,
    complete_paypal_order,
    connect,
    create_demo_digital_delivery,
    create_deferred_question,
    create_pending_digital_delivery,
    create_pending_paypal_order,
    create_verified_question,
    digital_delivery_for_access,
    get_or_create_demo_customer,
    grant_demo_order,
    finish_owner_notification,
    init_database,
    list_questions,
    mark_payment_event,
    public_digital_delivery,
    record_payment_event,
    reverse_paypal_credits,
    sync_digital_delivery_status,
)


class StoreFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "raidbench-test.db"
        init_database(
            self.db_path,
            ROOT / "local" / "raidbench-local-schema.sql",
            ROOT / "content" / "skus.json",
        )
        self.data = load_raid_data(ROOT / "content" / "rust-raid-data.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_catalog_starts_with_low_friction_answer_pack(self) -> None:
        connection = connect(self.db_path)
        try:
            packs = catalog(connection, include_demo=False)["packs"]
        finally:
            connection.close()
        self.assertEqual(packs[0]["sku"], "credits-starter-20")
        self.assertEqual(packs[0]["credits"], 20)
        self.assertEqual(packs[0]["price_usd"], 5)

    def test_digital_report_is_private_until_payment_and_revoked_after_refund(self) -> None:
        self.data["verifiedAt"] = "2026-09-06"
        inputs = {
            "serverType": "vanilla",
            "targets": [{"targetId": "garage-door", "quantity": 1, "method": "rockets"}],
            "bufferPercent": 10,
            "availableSulfur": 5000,
            "teamSize": 1,
            "routePreference": "lowest_sulfur",
        }
        preview, report = build_staging_pack(
            inputs,
            self.data,
            now=datetime(2026, 9, 6, 12, tzinfo=timezone.utc),
        )
        access_token = "private_access_token_abcdefghijklmnopqrstuvwxyz123456"
        with closing(connect(self.db_path)) as connection:
            order = create_pending_digital_delivery(
                connection,
                sku="rust-staging-pack-v1",
                paypal_order_id="PAYPAL-DIGITAL-1",
                paypal_payload={"id": "PAYPAL-DIGITAL-1", "status": "CREATED"},
                local_order_id="ord_digital_1",
                access_token=access_token,
                inputs=report["inputs"],
                preview=preview,
                report=report,
                consent={
                    "termsVersion": "2026-09-06",
                    "refundPolicyVersion": "2026-09-06",
                    "consentedAt": "2026-09-06T12:00:00+00:00",
                },
            )
            stored = connection.execute(
                "SELECT access_token_hash, report_json FROM digital_deliveries WHERE order_id = ?",
                (order["id"],),
            ).fetchone()
            self.assertNotEqual(stored["access_token_hash"], access_token)
            self.assertNotIn(access_token, stored["report_json"])

            pending = digital_delivery_for_access(connection, access_token)
            public_pending = public_digital_delivery(pending, include_report=True)
            self.assertFalse(public_pending["ready"])
            self.assertNotIn("report", public_pending)

            result = complete_paypal_order(
                connection,
                order["customer_id"],
                "PAYPAL-DIGITAL-1",
                {
                    "status": "COMPLETED",
                    "purchase_units": [{
                        "payments": {"captures": [{
                            "id": "CAPTURE-DIGITAL-1",
                            "status": "COMPLETED",
                            "amount": {"currency_code": "USD", "value": "4.99"},
                        }]},
                    }],
                },
            )
            sync_digital_delivery_status(connection, result["order"])
            ready = digital_delivery_for_access(connection, access_token, record_access=True)
            public_ready = public_digital_delivery(ready, include_report=True)
            self.assertTrue(public_ready["ready"])
            self.assertEqual(public_ready["report"]["totals"]["sulfur"], 4200)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM credit_ledger WHERE order_id = ?",
                    (order["id"],),
                ).fetchone()["count"],
                0,
            )

            refunded = reverse_paypal_credits(
                connection,
                provider_event_id="WH-DIGITAL-REFUND-1",
                capture_id="CAPTURE-DIGITAL-1",
                amount=4.99,
                currency="USD",
                status="refunded",
                raw_event={"id": "WH-DIGITAL-REFUND-1"},
            )
            sync_digital_delivery_status(connection, refunded["order"])
            revoked = digital_delivery_for_access(connection, access_token)
            public_revoked = public_digital_delivery(revoked, include_report=True)
            self.assertEqual(public_revoked["deliveryStatus"], "revoked")
            self.assertFalse(public_revoked["ready"])
            self.assertNotIn("report", public_revoked)

    def test_partial_digital_refund_enters_payment_review(self) -> None:
        self.data["verifiedAt"] = "2026-09-06"
        inputs = {
            "targetId": "sheet-door",
            "quantity": 1,
            "method": "c4",
            "serverType": "vanilla",
            "bufferPercent": 0,
        }
        preview, report = build_staging_pack(
            inputs,
            self.data,
            now=datetime(2026, 9, 6, 12, tzinfo=timezone.utc),
        )
        access_token = "partial_refund_token_abcdefghijklmnopqrstuvwxyz12345"
        with closing(connect(self.db_path)) as connection:
            order = create_pending_digital_delivery(
                connection,
                sku="rust-staging-pack-v1",
                paypal_order_id="PAYPAL-PARTIAL-REFUND-1",
                paypal_payload={"id": "PAYPAL-PARTIAL-REFUND-1", "status": "CREATED"},
                local_order_id="ord_partial_refund_1",
                access_token=access_token,
                inputs=report["inputs"],
                preview=preview,
                report=report,
                consent={},
            )
            completed = complete_paypal_order(
                connection,
                order["customer_id"],
                "PAYPAL-PARTIAL-REFUND-1",
                {
                    "status": "COMPLETED",
                    "purchase_units": [{"payments": {"captures": [{
                        "id": "CAPTURE-PARTIAL-REFUND-1",
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "4.99"},
                    }]}}],
                },
            )
            sync_digital_delivery_status(connection, completed["order"])
            reviewed = reverse_paypal_credits(
                connection,
                provider_event_id="WH-PARTIAL-REFUND-1",
                capture_id="CAPTURE-PARTIAL-REFUND-1",
                amount=1.00,
                currency="USD",
                status="refunded",
                raw_event={"id": "WH-PARTIAL-REFUND-1"},
            )
            self.assertTrue(reviewed["manualReview"])
            sync_digital_delivery_status(connection, reviewed["order"])
            delivery = digital_delivery_for_access(connection, access_token)
            public = public_digital_delivery(delivery, include_report=True)
            self.assertEqual(public["paymentStatus"], "refund_review")
            self.assertEqual(public["deliveryStatus"], "payment_review")
            self.assertFalse(public["ready"])
            self.assertNotIn("report", public)

    def test_demo_digital_report_is_immediately_ready(self) -> None:
        self.data["verifiedAt"] = "2026-09-06"
        inputs = {
            "targetId": "sheet-door",
            "quantity": 1,
            "method": "c4",
            "serverType": "vanilla",
            "bufferPercent": 0,
        }
        preview, report = build_staging_pack(
            inputs,
            self.data,
            now=datetime(2026, 9, 6, 12, tzinfo=timezone.utc),
        )
        access_token = "demo_access_token_abcdefghijklmnopqrstuvwxyz123456789"
        with closing(connect(self.db_path)) as connection:
            create_demo_digital_delivery(
                connection,
                sku="rust-staging-pack-v1",
                access_token=access_token,
                inputs=report["inputs"],
                preview=preview,
                report=report,
            )
            delivery = digital_delivery_for_access(connection, access_token)
            self.assertTrue(public_digital_delivery(delivery, include_report=True)["ready"])

    def test_purchase_and_in_account_answer_are_persistent_and_idempotent(self) -> None:
        connection = connect(self.db_path)
        try:
            customer = get_or_create_demo_customer(connection)
            order = grant_demo_order(connection, customer["id"], "credits-scout-120", "demo-order-1")
            self.assertEqual(order["creditBalance"], 120)

            engine = build_raid_answer(
                {
                    "targetId": "sheet-door",
                    "quantity": 2,
                    "method": "satchels",
                    "serverType": "vanilla",
                },
                self.data,
                answer_type="instant",
                now=datetime(2026, 7, 20, 12, tzinfo=timezone.utc),
            )
            question = create_verified_question(
                connection,
                customer["id"],
                "rust-instant-raid-answer",
                "instant",
                "Two sheet metal doors with satchels",
                engine.answer["inputs"],
                engine.answer,
                "answer-request-1",
            )
            self.assertEqual(question["status"], "ready")
            self.assertEqual(question["answer"]["totals"]["sulfur"], 3840)
            self.assertEqual(question["answer"]["totals"]["gunpowder"], 1920)
            self.assertEqual(question["answer"]["totals"]["gunpowderCraftBatches"], 192)
            self.assertEqual(question["answer"]["totals"]["workbenchCharcoal"], 5760)
            self.assertEqual(question["answer"]["crafting"]["sulfurRequired"], 3840)
            review = question["answer"]["routeReview"]
            self.assertEqual(review["recommendationId"], "lowest_sulfur")
            self.assertEqual(review["selectedSulfurDelta"], 690)
            self.assertEqual({option["id"] for option in review["options"]}, {
                "selected", "lowest_sulfur", "fewest_items"
            })
            self.assertEqual(
                next(option for option in review["options"] if option["id"] == "lowest_sulfur")["sulfur"],
                3150,
            )
            self.assertEqual(account_summary(connection, customer["id"])["creditBalance"], 110)

            repeated = create_verified_question(
                connection,
                customer["id"],
                "rust-instant-raid-answer",
                "instant",
                "Two sheet metal doors with satchels",
                engine.answer["inputs"],
                engine.answer,
                "answer-request-1",
            )
            self.assertEqual(repeated["id"], question["id"])
            self.assertEqual(account_summary(connection, customer["id"])["creditBalance"], 110)
            self.assertEqual(len(list_questions(connection, customer["id"])), 1)
        finally:
            connection.close()

    def test_existing_database_can_add_compatibility_columns_before_indexes(self) -> None:
        connection = connect(self.db_path)
        try:
            connection.execute("DROP INDEX idx_orders_provider_capture")
            connection.execute("ALTER TABLE orders DROP COLUMN provider_capture_id")
            connection.execute("DROP TABLE password_reset_tokens")
            connection.execute("DROP TABLE password_reset_requests")
        finally:
            connection.close()

        init_database(
            self.db_path,
            ROOT / "local" / "raidbench-local-schema.sql",
            ROOT / "content" / "skus.json",
        )
        connection = connect(self.db_path)
        try:
            order_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(orders)").fetchall()
            }
            self.assertIn("provider_capture_id", order_columns)
            self.assertIsNotNone(connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_orders_provider_capture'"
            ).fetchone())
            self.assertIsNotNone(connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'password_reset_tokens'"
            ).fetchone())
        finally:
            connection.close()

    def test_multi_layer_plan_and_unsupported_server_hold(self) -> None:
        connection = connect(self.db_path)
        try:
            customer = get_or_create_demo_customer(connection)
            grant_demo_order(connection, customer["id"], "credits-strategist-250", "demo-order-2")
            engine = build_raid_answer(
                {
                    "serverType": "vanilla",
                    "targets": [
                        {"targetId": "sheet-door", "quantity": 2, "method": "satchels"},
                        {"targetId": "stone-wall", "quantity": 1, "method": "rockets"},
                    ],
                    "bufferPercent": 15,
                    "availableSulfur": 12000,
                    "teamSize": 2,
                    "routePreference": "fewest_items",
                    "notes": "Use the saved west-side route and preserve a separate seal kit.",
                },
                self.data,
                answer_type="raid_plan",
                now=datetime(2026, 7, 20, 12, tzinfo=timezone.utc),
            )
            question = create_verified_question(
                connection,
                customer["id"],
                "rust-raid-prep",
                "raid_plan",
                "Two-layer route",
                engine.answer["inputs"],
                engine.answer,
                "plan-request-1",
            )
            self.assertEqual(question["answer"]["totals"]["sulfur"], 9440)
            self.assertEqual(question["answer"]["totals"]["bufferedSulfur"], 10856)
            self.assertEqual(question["answer"]["totals"]["gunpowder"], 4520)
            self.assertEqual(question["answer"]["totals"]["workbenchCharcoal"], 13560)
            self.assertEqual(question["answer"]["plan"]["readiness"], "ready_to_stage")
            self.assertEqual(len(question["answer"]["plan"]["teamRoles"]), 2)
            self.assertEqual(len(question["answer"]["plan"]["checkpoints"]), 4)
            self.assertIn("west-side route", question["answer"]["plan"]["savedNotes"])
            self.assertEqual(question["answer"]["routeReview"]["recommendationId"], "fewest_items")
            self.assertEqual(account_summary(connection, customer["id"])["creditBalance"], 130)

            with self.assertRaises(UnsupportedScopeError) as context:
                build_raid_answer(
                    {"targetId": "sheet-door", "quantity": 1, "method": "c4", "serverType": "custom"},
                    self.data,
                    answer_type="instant",
                    now=datetime(2026, 7, 20, 12, tzinfo=timezone.utc),
                )
            held = create_deferred_question(
                connection,
                customer["id"],
                "instant",
                "Custom server request",
                {"serverType": "custom"},
                str(context.exception),
                "held-request-1",
            )
            self.assertEqual(held["creditsCharged"], 0)
            self.assertEqual(held["status"], "needs_review")
            self.assertEqual(account_summary(connection, customer["id"])["creditBalance"], 130)
        finally:
            connection.close()

    def test_paypal_webhook_credit_and_refund_are_idempotent(self) -> None:
        connection = connect(self.db_path)
        try:
            customer = get_or_create_demo_customer(connection)
            create_pending_paypal_order(
                connection,
                customer["id"],
                "credits-scout-120",
                "PAYPAL-ORDER-1",
                {"id": "PAYPAL-ORDER-1", "status": "CREATED"},
                "ord_webhook_test",
            )
            event = {
                "id": "WH-CAPTURE-1",
                "event_type": "PAYMENT.CAPTURE.COMPLETED",
                "resource": {
                    "id": "CAPTURE-1",
                    "status": "COMPLETED",
                    "amount": {"currency_code": "USD", "value": "19.00"},
                },
            }
            first = complete_paypal_capture_event(
                connection,
                "PAYPAL-ORDER-1",
                event["resource"],
                event,
            )
            repeated = complete_paypal_capture_event(
                connection,
                "PAYPAL-ORDER-1",
                event["resource"],
                event,
            )
            self.assertEqual(first["creditBalance"], 120)
            self.assertEqual(repeated["creditBalance"], 120)

            recorded = record_payment_event(
                connection,
                provider_event_id=event["id"],
                event_type=event["event_type"],
                payload=event,
                order_id=first["order"]["id"],
            )
            mark_payment_event(connection, event["id"], status="processed", order_id=first["order"]["id"])
            duplicate = record_payment_event(
                connection,
                provider_event_id=event["id"],
                event_type=event["event_type"],
                payload=event,
                order_id=first["order"]["id"],
            )
            self.assertEqual(recorded["processing_status"], "received")
            self.assertEqual(duplicate["processing_status"], "processed")

            refund = reverse_paypal_credits(
                connection,
                provider_event_id="WH-REFUND-1",
                capture_id="CAPTURE-1",
                amount=19.00,
                currency="USD",
                status="refunded",
                raw_event={"id": "WH-REFUND-1"},
            )
            repeated_refund = reverse_paypal_credits(
                connection,
                provider_event_id="WH-REFUND-1",
                capture_id="CAPTURE-1",
                amount=19.00,
                currency="USD",
                status="refunded",
                raw_event={"id": "WH-REFUND-1"},
            )
            self.assertEqual(refund["creditBalance"], 0)
            self.assertEqual(repeated_refund["creditBalance"], 0)
        finally:
            connection.close()

    def test_owner_payment_notification_claim_is_idempotent_and_retryable(self) -> None:
        connection = connect(self.db_path)
        try:
            customer = get_or_create_demo_customer(connection)
            order = create_pending_paypal_order(
                connection,
                customer["id"],
                "credits-scout-120",
                "PAYPAL-NOTIFICATION-ORDER-1",
                {"id": "PAYPAL-NOTIFICATION-ORDER-1", "status": "CREATED"},
            )
            key = claim_owner_notification(connection, order["id"], "payment_completed")
            self.assertIsNotNone(key)
            self.assertIsNone(claim_owner_notification(connection, order["id"], "payment_completed"))

            finish_owner_notification(connection, key, sent=False, error="temporary failure")
            self.assertEqual(
                claim_owner_notification(connection, order["id"], "payment_completed"),
                key,
            )
            finish_owner_notification(connection, key, sent=True)
            self.assertIsNone(claim_owner_notification(connection, order["id"], "payment_completed"))

            record = connection.execute(
                "SELECT status, attempts, sent_at FROM owner_notifications WHERE notification_key = ?",
                (key,),
            ).fetchone()
            self.assertEqual(record["status"], "sent")
            self.assertEqual(record["attempts"], 2)
            self.assertTrue(record["sent_at"])
        finally:
            connection.close()


class EmailDeliveryTests(unittest.TestCase):
    def test_resend_request_uses_fragment_link_and_safe_headers(self) -> None:
        captured = []

        class CaptureHandler(BaseHTTPRequestHandler):
            def log_message(self, message_format, *args):
                return

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                captured.append({
                    "path": self.path,
                    "headers": dict(self.headers.items()),
                    "payload": json.loads(body.decode("utf-8")),
                })
                response = json.dumps({"id": "email_test_1"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        provider = ThreadingHTTPServer(("127.0.0.1", 0), CaptureHandler)
        provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
        provider_thread.start()
        try:
            delivery = ResendEmailDelivery(
                api_key="test-key",
                sender="RaidBench <account@notify.raidbench.com>",
                public_base_url="https://raidbench.com",
                support_email="support@raidbench.com",
                api_url=f"http://127.0.0.1:{provider.server_address[1]}/emails",
            )
            token = "abcdefghijklmnopqrstuvwxyzABCDEFGH1234567890_-"
            self.assertEqual(delivery.send_password_reset("player@example.com", token), "email_test_1")
        finally:
            provider.shutdown()
            provider.server_close()
            provider_thread.join(timeout=2)

        self.assertEqual(len(captured), 1)
        request = captured[0]
        self.assertEqual(request["path"], "/emails")
        self.assertEqual(request["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(request["headers"]["User-Agent"], "RaidBench/1.0")
        self.assertNotIn(token, request["headers"]["Idempotency-Key"])
        self.assertEqual(request["payload"]["reply_to"], "support@raidbench.com")
        self.assertIn(f"customer.html#reset={token}", request["payload"]["html"])
        self.assertNotIn("customer.html?reset=", request["payload"]["html"])

    def test_smtp2go_request_uses_fragment_link_and_send_only_endpoint(self) -> None:
        captured = []

        class CaptureHandler(BaseHTTPRequestHandler):
            def log_message(self, message_format, *args):
                return

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                captured.append({
                    "path": self.path,
                    "headers": dict(self.headers.items()),
                    "payload": json.loads(body.decode("utf-8")),
                })
                response = json.dumps({
                    "request_id": "request_test_1",
                    "data": {"succeeded": 1, "failed": 0, "failures": [], "email_id": "smtp_test_1"},
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        provider = ThreadingHTTPServer(("127.0.0.1", 0), CaptureHandler)
        provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
        provider_thread.start()
        try:
            delivery = Smtp2GoEmailDelivery(
                api_key="api-test-key",
                sender="RaidBench <account@notify.raidbench.com>",
                public_base_url="https://raidbench.com",
                support_email="support@raidbench.com",
                api_url=f"http://127.0.0.1:{provider.server_address[1]}/v3/email/send",
            )
            token = "abcdefghijklmnopqrstuvwxyzABCDEFGH1234567890_-"
            self.assertEqual(delivery.send_password_reset("player@example.com", token), "smtp_test_1")
        finally:
            provider.shutdown()
            provider.server_close()
            provider_thread.join(timeout=2)

        self.assertEqual(len(captured), 1)
        request = captured[0]
        request_headers = {key.lower(): value for key, value in request["headers"].items()}
        self.assertEqual(request["path"], "/v3/email/send")
        self.assertEqual(request_headers["x-smtp2go-api-key"], "api-test-key")
        self.assertEqual(request_headers["user-agent"], "RaidBench/1.0")
        self.assertEqual(request["payload"]["sender"], "RaidBench <account@notify.raidbench.com>")
        self.assertEqual(request["payload"]["to"], ["player@example.com"])
        self.assertEqual(
            request["payload"]["custom_headers"][0],
            {"header": "Reply-To", "value": "support@raidbench.com"},
        )
        self.assertNotIn(token, json.dumps(request["payload"]["custom_headers"]))
        self.assertIn(f"customer.html#reset={token}", request["payload"]["html_body"])
        self.assertNotIn("customer.html?reset=", request["payload"]["html_body"])


class HttpFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "raidbench-http.db"
        self.server = create_server(host="127.0.0.1", port=0, root=ROOT, db_path=self.db_path, mode="demo")
        self.server.raid_data["verifiedAt"] = datetime.now(timezone.utc).date().isoformat()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def request(self, path: str, *, method: str = "GET", body: dict | None = None, key: str | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if key:
            headers["Idempotency-Key"] = key
        request = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            content_type = response.headers.get("Content-Type", "")
            payload = response.read()
            return response.status, json.loads(payload) if "application/json" in content_type else payload

    def test_http_customer_journey(self) -> None:
        status, health = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["database"], "sqlite")

        status, anonymous = self.request("/api/session")
        self.assertEqual(status, 200)
        self.assertFalse(anonymous["authenticated"])

        status, session = self.request("/api/demo/session", method="POST")
        self.assertEqual(status, 200)
        self.assertEqual(session["customer"]["creditBalance"], 0)

        status, authenticated = self.request("/api/session")
        self.assertTrue(authenticated["authenticated"])

        status, order = self.request(
            "/api/demo/orders",
            method="POST",
            body={"sku": "credits-scout-120"},
            key="http-demo-order-1",
        )
        self.assertEqual(status, 201)
        self.assertEqual(order["creditBalance"], 120)

        status, result = self.request(
            "/api/answers/instant",
            method="POST",
            body={
                "targetId": "garage-door",
                "quantity": 1,
                "method": "rockets",
                "serverType": "vanilla",
            },
            key="http-answer-1",
        )
        self.assertEqual(status, 201)
        self.assertEqual(result["question"]["answer"]["totals"]["sulfur"], 4200)
        self.assertEqual(result["customer"]["creditBalance"], 110)

        status, questions = self.request("/api/questions")
        self.assertEqual(status, 200)
        self.assertEqual(len(questions["questions"]), 1)

        status, customer_html = self.request("/customer.html")
        self.assertEqual(status, 200)
        self.assertIn(b"Player account", customer_html)

        clean_status, clean_html = self.request("/rust-raid-staging-pack")
        self.assertEqual(clean_status, 200)
        self.assertIn(b"Rust Full Raid Staging Pack", clean_html)

    def test_accountless_digital_report_demo_journey(self) -> None:
        product_status, product = self.request("/api/guest/raid-pack/product")
        self.assertEqual(product_status, 200)
        self.assertTrue(product["product"]["available"])
        self.assertFalse(product["product"]["accountRequired"])

        payload = {
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
        }
        preview_status, preview = self.request(
            "/api/guest/raid-pack/preview",
            method="POST",
            body=payload,
        )
        self.assertEqual(preview_status, 200)
        self.assertEqual(preview["preview"]["selected"]["sulfur"], 9440)
        self.assertNotIn("report", preview)

        complete_status, completed = self.request(
            "/api/guest/raid-pack/demo-complete",
            method="POST",
            body=payload,
        )
        self.assertEqual(complete_status, 201)
        self.assertTrue(completed["delivery"]["ready"])
        self.assertEqual(completed["delivery"]["report"]["qa"]["status"], "approved")

        access_status, accessed = self.request(
            "/api/guest/raid-pack/access",
            method="POST",
            body={"accessToken": completed["accessToken"]},
        )
        self.assertEqual(access_status, 200)
        self.assertEqual(accessed["delivery"]["reportSha256"], completed["delivery"]["reportSha256"])

        missing_status, missing = self.request(
            "/api/guest/raid-pack/access",
            method="POST",
            body={"accessToken": "wrong_access_token_abcdefghijklmnopqrstuvwxyz12345"},
        )
        self.assertEqual(missing_status, 404)
        self.assertEqual(missing["error"]["code"], "report_not_found")

        sample_status, sample = self.request("/api/guest/raid-pack/sample")
        self.assertEqual(sample_status, 200)
        self.assertEqual(sample["sample"]["report"]["reportKind"], "public_sample")
        self.assertEqual(sample["sample"]["report"]["totals"]["sulfur"], 15000)
        self.assertEqual(len(sample["sample"]["reportSha256"]), 64)

    def test_accountless_paypal_checkout_captures_once_and_delivers_report(self) -> None:
        class FakePayPal:
            configured = True
            webhook_configured = True
            environment = "live"

            def __init__(self):
                self.capture_calls = 0
                self.return_url = ""

            def create_order(self, **kwargs):
                self.return_url = kwargs["return_url"]
                self.asserted_amount = kwargs["amount"]
                return {
                    "id": "PAYPAL-GUEST-CHECKOUT-1",
                    "status": "CREATED",
                    "links": [{
                        "rel": "approve",
                        "href": "https://www.paypal.com/checkoutnow?token=PAYPAL-GUEST-CHECKOUT-1",
                    }],
                }

            def capture_order(self, paypal_order_id):
                self.capture_calls += 1
                return {
                    "id": paypal_order_id,
                    "status": "COMPLETED",
                    "purchase_units": [{
                        "payments": {"captures": [{
                            "id": "CAPTURE-GUEST-CHECKOUT-1",
                            "status": "COMPLETED",
                            "amount": {"currency_code": "USD", "value": "4.99"},
                        }]},
                    }],
                }

            @staticmethod
            def show_order(paypal_order_id):
                raise AssertionError(f"Unexpected reconciliation for {paypal_order_id}")

        fake_paypal = FakePayPal()
        self.server.mode = "production"
        self.server.paypal = fake_paypal
        self.server.checkout_enabled = True
        self.server.paid_data_status = lambda: {"ready": True, "status": "verified"}
        payload = {
            "serverType": "vanilla",
            "targets": [{"targetId": "garage-door", "quantity": 1, "method": "rockets"}],
            "bufferPercent": 10,
            "availableSulfur": 5000,
            "teamSize": 1,
            "routePreference": "lowest_sulfur",
            "ownedInventory": {"rockets": 3, "c4": 0, "satchels": 0, "explosiveAmmo": 0},
            "acceptedTerms": True,
            "acceptedRefundPolicy": True,
            "acknowledgedDigitalDelivery": True,
            "legalVersion": "2026-09-06",
        }
        checkout_status, checkout = self.request(
            "/api/guest/raid-pack/checkout",
            method="POST",
            body=payload,
        )
        self.assertEqual(checkout_status, 201)
        self.assertEqual(fake_paypal.asserted_amount, 4.99)
        self.assertIn("paypal=return", fake_paypal.return_url)
        self.assertIn("access=", fake_paypal.return_url)
        self.assertEqual(checkout["paypalOrderId"], "PAYPAL-GUEST-CHECKOUT-1")

        with closing(connect(self.db_path)) as connection:
            stored = connection.execute(
                "SELECT access_token_hash, status FROM digital_deliveries"
            ).fetchone()
            self.assertNotEqual(stored["access_token_hash"], checkout["accessToken"])
            self.assertEqual(stored["status"], "awaiting_payment")

        capture_body = {
            "accessToken": checkout["accessToken"],
            "paypalOrderId": checkout["paypalOrderId"],
        }
        capture_status, captured = self.request(
            "/api/guest/raid-pack/capture",
            method="POST",
            body=capture_body,
        )
        repeated_status, repeated = self.request(
            "/api/guest/raid-pack/capture",
            method="POST",
            body=capture_body,
        )
        self.assertEqual(capture_status, 200)
        self.assertEqual(repeated_status, 200)
        self.assertTrue(captured["delivery"]["ready"])
        self.assertEqual(captured["delivery"]["report"]["totals"]["sulfur"], 4200)
        self.assertEqual(repeated["delivery"]["reportSha256"], captured["delivery"]["reportSha256"])
        self.assertEqual(fake_paypal.capture_calls, 1)

        with closing(connect(self.db_path)) as connection:
            connection.execute(
                "UPDATE orders SET status = 'refund_review' WHERE provider_transaction_id = ?",
                (checkout["paypalOrderId"],),
            )
        review_status, review = self.request(
            "/api/guest/raid-pack/capture",
            method="POST",
            body=capture_body,
        )
        self.assertEqual(review_status, 200)
        self.assertEqual(review["delivery"]["deliveryStatus"], "payment_review")
        self.assertFalse(review["delivery"]["ready"])
        self.assertNotIn("report", review["delivery"])
        self.assertEqual(fake_paypal.capture_calls, 1)

    def test_blocked_paid_data_hides_rust_catalog_and_holds_answer_without_charge(self) -> None:
        status_path = Path(self.temp_dir.name) / "rust-paid-data-status.json"
        data_hash = hashlib.sha256(self.server.raid_data_path.read_bytes()).hexdigest()
        status_path.write_text(json.dumps({
            "status": "blocked",
            "checkedAt": "2026-09-04T00:00:00+00:00",
            "dataChangelistId": self.server.raid_data["verification"]["latestOfficialChangelistId"],
            "latestOfficialChangelistId": "new-patch",
            "dataSha256": data_hash,
            "errors": ["A new official patch requires review."],
        }))
        self.server.raid_data_status_path = status_path

        health_status, health = self.request("/api/health")
        self.assertEqual(health_status, 200)
        self.assertEqual(health["paidDataStatus"], "blocked")
        self.assertFalse(health["checkoutEnabled"])
        catalog_status, catalog_data = self.request("/api/catalog")
        self.assertEqual(catalog_status, 200)
        self.assertEqual(catalog_data["paidDataStatus"], "blocked")
        self.assertEqual(
            {item["id"] for item in catalog_data["actions"]},
            {"palworld-base-progression-review"},
        )
        self.assertTrue(catalog_data["packs"])

        self.request("/api/demo/session", method="POST")
        order_status, order = self.request(
            "/api/demo/orders",
            method="POST",
            body={"sku": "credits-scout-120"},
            key="blocked-data-order",
        )
        self.assertEqual(order_status, 201)
        self.assertEqual(order["creditBalance"], 120)
        answer_status, answer = self.request(
            "/api/answers/instant",
            method="POST",
            body={"targetId": "sheet-door", "quantity": 1, "method": "rockets", "serverType": "vanilla"},
            key="blocked-data-answer",
        )
        self.assertEqual(answer_status, 202)
        self.assertEqual(answer["question"]["creditsCharged"], 0)
        self.assertEqual(answer["customer"]["creditBalance"], 120)
        self.assertIn("patch review", answer["question"]["blockedReason"])

    def test_signed_paypal_webhook_is_idempotent_over_http(self) -> None:
        class VerifiedPayPal:
            @staticmethod
            def verify_webhook(headers, event):
                return True

        class FakePaymentNotifier:
            configured = True

            def __init__(self):
                self.sent = []
                self.sent_event = threading.Event()

            @staticmethod
            def notification_type(order):
                return "payment_completed" if order.get("status") == "completed" else None

            def send_payment_event(self, order, event_type):
                self.sent.append((order, event_type))
                self.sent_event.set()
                return {"code": 0}

        status, session = self.request("/api/demo/session", method="POST")
        self.assertEqual(status, 200)
        with closing(connect(self.db_path)) as connection:
            customer = get_or_create_demo_customer(connection)
            order = create_pending_paypal_order(
                connection,
                customer["id"],
                "credits-scout-120",
                "PAYPAL-HTTP-ORDER-1",
                {"id": "PAYPAL-HTTP-ORDER-1", "status": "CREATED"},
                "ord_http_webhook",
                {
                    "termsVersion": "2026-08-01",
                    "refundPolicyVersion": "2026-08-01",
                    "consentedAt": "2026-08-01T00:00:00+00:00",
                },
            )
            self.assertEqual(order["terms_version"], "2026-08-01")

        self.server.paypal = VerifiedPayPal()
        notifier = FakePaymentNotifier()
        self.server.payment_notifier = notifier
        self.server.checkout_enabled = True
        event = {
            "id": "WH-HTTP-CAPTURE-1",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "CAPTURE-HTTP-1",
                "status": "COMPLETED",
                "amount": {"currency_code": "USD", "value": "19.00"},
                "supplementary_data": {
                    "related_ids": {"order_id": "PAYPAL-HTTP-ORDER-1"},
                },
            },
        }
        first_status, first = self.request(
            "/api/payments/paypal/webhook",
            method="POST",
            body=event,
        )
        second_status, second = self.request(
            "/api/payments/paypal/webhook",
            method="POST",
            body=event,
        )
        self.assertEqual(first_status, 200)
        self.assertEqual(first, {"ok": True})
        self.assertEqual(second_status, 200)
        self.assertTrue(second["duplicate"])
        self.assertTrue(notifier.sent_event.wait(timeout=2))
        self.assertEqual(len(notifier.sent), 1)
        self.assertEqual(notifier.sent[0][1], "PAYMENT.CAPTURE.COMPLETED")
        notification = None
        deadline = time.time() + 2
        while time.time() < deadline:
            with closing(connect(self.db_path)) as connection:
                notification = connection.execute(
                    "SELECT status, attempts FROM owner_notifications WHERE order_id = ?",
                    ("ord_http_webhook",),
                ).fetchone()
            if notification and notification["status"] == "sent":
                break
            time.sleep(0.02)
        with closing(connect(self.db_path)) as connection:
            customer = get_or_create_demo_customer(connection)
            self.assertEqual(account_summary(connection, customer["id"])["creditBalance"], 120)
            self.assertEqual(notification["status"], "sent")
            self.assertEqual(notification["attempts"], 1)

    def test_unsigned_paypal_webhook_is_a_client_error(self) -> None:
        class MissingSignaturePayPal:
            @staticmethod
            def verify_webhook(headers, event):
                raise PayPalWebhookSignatureError("PayPal webhook signature headers are incomplete.")

        self.server.paypal = MissingSignaturePayPal()
        self.server.checkout_enabled = True
        status, result = self.request(
            "/api/payments/paypal/webhook",
            method="POST",
            body={
                "id": "WH-UNSIGNED-PROBE",
                "event_type": "PAYMENT.CAPTURE.COMPLETED",
                "resource": {},
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_webhook_signature")

    def test_password_reset_is_private_single_use_and_invalidates_sessions(self) -> None:
        class FakeEmailDelivery:
            configured = True

            def __init__(self):
                self.sent = []
                self.sent_event = threading.Event()

            def send_password_reset(self, recipient, token):
                self.sent.append((recipient, token))
                self.sent_event.set()
                return "email_test_1"

        delivery = FakeEmailDelivery()
        self.server.email_delivery = delivery

        register_status, registered = self.request(
            "/api/auth/register",
            method="POST",
            body={
                "email": "player@example.com",
                "password": "original-password-123",
                "displayName": "Player",
                "region": "US",
            },
        )
        self.assertEqual(register_status, 201)
        self.assertEqual(registered["customer"]["email"], "player@example.com")

        config_status, config = self.request("/api/config")
        self.assertEqual(config_status, 200)
        self.assertTrue(config["passwordResetEnabled"])

        reset_status, reset = self.request(
            "/api/auth/password-reset/request",
            method="POST",
            body={"email": "player@example.com"},
        )
        missing_status, missing = self.request(
            "/api/auth/password-reset/request",
            method="POST",
            body={"email": "missing@example.com"},
        )
        self.assertEqual(reset_status, 202)
        self.assertEqual(missing_status, 202)
        self.assertEqual(reset["message"], missing["message"])
        self.assertTrue(delivery.sent_event.wait(timeout=2))
        self.assertEqual(len(delivery.sent), 1)
        recipient, token = delivery.sent[0]
        self.assertEqual(recipient, "player@example.com")

        with closing(connect(self.db_path)) as connection:
            stored = connection.execute(
                "SELECT token_hash FROM password_reset_tokens WHERE customer_id = ?",
                (registered["customer"]["id"],),
            ).fetchone()
            self.assertIsNotNone(stored)
            self.assertNotEqual(stored["token_hash"], token)
            self.assertEqual(len(stored["token_hash"]), 64)

        confirm_status, confirmed = self.request(
            "/api/auth/password-reset/confirm",
            method="POST",
            body={"token": token, "password": "replacement-password-456"},
        )
        self.assertEqual(confirm_status, 200)
        self.assertTrue(confirmed["ok"])

        session_status, session = self.request("/api/session")
        self.assertEqual(session_status, 200)
        self.assertFalse(session["authenticated"])

        old_status, old_login = self.request(
            "/api/auth/login",
            method="POST",
            body={"email": "player@example.com", "password": "original-password-123"},
        )
        self.assertEqual(old_status, 401)
        self.assertEqual(old_login["error"]["code"], "invalid_credentials")

        new_status, new_login = self.request(
            "/api/auth/login",
            method="POST",
            body={"email": "player@example.com", "password": "replacement-password-456"},
        )
        self.assertEqual(new_status, 200)
        self.assertEqual(new_login["customer"]["email"], "player@example.com")

        reused_status, reused = self.request(
            "/api/auth/password-reset/confirm",
            method="POST",
            body={"token": token, "password": "another-password-789"},
        )
        self.assertEqual(reused_status, 422)
        self.assertEqual(reused["error"]["code"], "invalid_or_expired_reset")

    def test_password_reset_request_has_support_fallback_when_email_is_disabled(self) -> None:
        class DisabledEmailDelivery:
            configured = False

        self.server.email_delivery = DisabledEmailDelivery()
        status, payload = self.request(
            "/api/auth/password-reset/request",
            method="POST",
            body={"email": "player@example.com"},
        )
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"]["code"], "password_reset_unavailable")
        self.assertIn("support@raidbench.com", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
