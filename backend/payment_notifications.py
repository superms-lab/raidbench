from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class PaymentNotificationError(RuntimeError):
    pass


_STATUS_PRESENTATION = {
    "completed": ("payment_completed", "RaidBench 收款成功", "green"),
    "payment_pending": ("payment_pending", "RaidBench 付款待处理", "orange"),
    "payment_denied": ("payment_denied", "RaidBench 付款未完成", "red"),
    "refund_review": ("refund_review", "RaidBench 退款需要人工复核", "red"),
    "refunded": ("payment_refunded", "RaidBench 退款已完成", "orange"),
    "reversed": ("payment_reversed", "RaidBench 付款已撤销", "red"),
}


def validate_webhook_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in {"open.feishu.cn", "open.larksuite.com"}:
        raise PaymentNotificationError("Payment alert webhook must use an official Feishu or Lark HTTPS host.")
    if not parsed.path.startswith("/open-apis/bot/v2/hook/"):
        raise PaymentNotificationError("Payment alert webhook is not a v2 custom-bot hook.")
    return value


def generate_signature(timestamp: int, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def payment_notification_type(order: dict[str, Any]) -> str | None:
    presentation = _STATUS_PRESENTATION.get(str(order.get("status") or "").lower())
    return presentation[0] if presentation else None


def build_payment_card(
    order: dict[str, Any],
    event_type: str,
    *,
    timestamp: int | None = None,
    secret: str = "",
    configuration_test: bool = False,
) -> dict[str, Any]:
    status = str(order.get("status") or "unknown").lower()
    _, title, color = _STATUS_PRESENTATION.get(
        status,
        ("payment_status", "RaidBench 付款状态", "blue"),
    )
    if configuration_test:
        title = "RaidBench 收款提醒配置测试"
        color = "blue"

    amount = float(order.get("amount") or 0)
    currency = str(order.get("currency") or "USD").upper()
    credits = int(order.get("credits_granted") or 0)
    occurred_at = str(order.get("updated_at") or order.get("created_at") or "")
    if not occurred_at:
        occurred_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    rows = [
        f"订单号：{str(order.get('id') or 'configuration-test')}",
        f"SKU: {str(order.get('sku') or 'n/a')}",
        f"金额：{currency} {amount:.2f}",
        f"点数：{credits}",
        f"状态：{status}",
        f"PayPal 事件：{event_type}",
        f"时间：{occurred_at}",
    ]
    if configuration_test:
        rows.insert(0, "配置测试，不是实际收款。Configuration test only; no customer paid this order.")

    payload: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": color,
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {"tag": "div", "text": {"tag": "plain_text", "content": "\n".join(rows)}},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "请以 PayPal 商户后台为对账依据；退款与撤销需要在商户后台复核。",
                        }
                    ],
                },
            ],
        },
    }
    if secret:
        signed_at = int(timestamp if timestamp is not None else time.time())
        payload["timestamp"] = str(signed_at)
        payload["sign"] = generate_signature(signed_at, secret)
    return payload


@dataclass(frozen=True)
class FeishuPaymentNotifier:
    webhook_url: str = ""
    secret: str = ""
    timeout: int = 20

    @classmethod
    def from_environment(cls) -> "FeishuPaymentNotifier":
        return cls(
            webhook_url=os.environ.get("RAIDBENCH_PAYMENT_FEISHU_WEBHOOK_URL", "").strip(),
            secret=os.environ.get("RAIDBENCH_PAYMENT_FEISHU_WEBHOOK_SECRET", "").strip(),
        )

    @property
    def configured(self) -> bool:
        if not self.webhook_url:
            return False
        try:
            validate_webhook_url(self.webhook_url)
        except PaymentNotificationError:
            return False
        return True

    @staticmethod
    def notification_type(order: dict[str, Any]) -> str | None:
        return payment_notification_type(order)

    def send_payment_event(self, order: dict[str, Any], event_type: str) -> dict[str, Any]:
        return self._send(build_payment_card(order, event_type, secret=self.secret))

    def send_configuration_test(self) -> dict[str, Any]:
        return self._send(
            build_payment_card(
                {
                    "id": "configuration-test",
                    "sku": "credits-scout-120",
                    "amount": 0,
                    "currency": "USD",
                    "credits_granted": 0,
                    "status": "test",
                },
                "CONFIGURATION.TEST",
                secret=self.secret,
                configuration_test=True,
            )
        )

    def _send(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise PaymentNotificationError("Payment alert webhook is not configured.")
        request = urllib.request.Request(
            validate_webhook_url(self.webhook_url),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "RaidBench payment notifier/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise PaymentNotificationError(f"Feishu payment alert failed: {error}") from error
        try:
            result = json.loads(body)
        except json.JSONDecodeError as error:
            raise PaymentNotificationError("Feishu payment alert returned non-JSON data.") from error
        code = result.get("code", result.get("StatusCode"))
        if code != 0:
            message = result.get("msg", result.get("StatusMessage", "unknown error"))
            raise PaymentNotificationError(
                f"Feishu rejected the payment alert: code={code}, message={message}"
            )
        return result
