from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from backend.payment_notifications import (
    FeishuPaymentNotifier,
    PaymentNotificationError,
    build_payment_card,
    generate_signature,
    payment_notification_type,
    validate_webhook_url,
)


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    @staticmethod
    def read() -> bytes:
        return b'{"code":0,"msg":"success"}'


class PaymentNotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.order = {
            "id": "ord_alert_test",
            "customer_email": "private-player@example.com",
            "sku": "credits-scout-120",
            "amount": 19,
            "currency": "USD",
            "credits_granted": 120,
            "status": "completed",
            "updated_at": "2026-08-11T10:00:00+00:00",
        }

    def test_card_is_signed_and_excludes_customer_pii(self) -> None:
        card = build_payment_card(
            self.order,
            "PAYMENT.CAPTURE.COMPLETED",
            timestamp=1_700_000_000,
            secret="test-secret",
        )
        serialized = json.dumps(card, ensure_ascii=False)
        self.assertEqual(card["timestamp"], "1700000000")
        self.assertEqual(card["sign"], generate_signature(1_700_000_000, "test-secret"))
        self.assertIn("USD 19.00", serialized)
        self.assertIn("ord_alert_test", serialized)
        self.assertNotIn("private-player@example.com", serialized)
        self.assertEqual(payment_notification_type(self.order), "payment_completed")

    def test_rejects_non_feishu_webhook(self) -> None:
        with self.assertRaisesRegex(PaymentNotificationError, "official Feishu"):
            validate_webhook_url("https://example.com/open-apis/bot/v2/hook/test")

    def test_notifier_posts_one_interactive_card(self) -> None:
        captured = []

        def fake_urlopen(request, timeout):
            captured.append((request, timeout))
            return _FakeResponse()

        notifier = FeishuPaymentNotifier(
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-id",
            secret="test-secret",
        )
        with patch("backend.payment_notifications.urllib.request.urlopen", side_effect=fake_urlopen):
            result = notifier.send_payment_event(self.order, "PAYMENT.CAPTURE.COMPLETED")

        self.assertEqual(result["code"], 0)
        self.assertEqual(len(captured), 1)
        request, timeout = captured[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(timeout, 20)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(payload["msg_type"], "interactive")
        self.assertIn("sign", payload)

    def test_configuration_test_is_unmistakably_marked(self) -> None:
        card = build_payment_card(
            {"status": "test"},
            "CONFIGURATION.TEST",
            configuration_test=True,
        )
        serialized = json.dumps(card, ensure_ascii=False)
        self.assertIn("配置测试，不是实际收款", serialized)
        self.assertIn("no customer paid this order", serialized)


if __name__ == "__main__":
    unittest.main()
