#!/usr/bin/env python3
"""Create or locate the PayPal webhook used by RaidBench checkout."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.paypal import PayPalClient, PayPalError  # noqa: E402


EVENTS = [
    "CHECKOUT.ORDER.APPROVED",
    "CHECKOUT.PAYMENT-APPROVAL.REVERSED",
    "PAYMENT.CAPTURE.COMPLETED",
    "PAYMENT.CAPTURE.PENDING",
    "PAYMENT.CAPTURE.DENIED",
    "PAYMENT.CAPTURE.DECLINED",
    "PAYMENT.CAPTURE.REFUNDED",
    "PAYMENT.CAPTURE.REVERSED",
    "PAYMENT.REFUND.PENDING",
    "PAYMENT.REFUND.FAILED",
    "CUSTOMER.DISPUTE.CREATED",
    "CUSTOMER.DISPUTE.UPDATED",
    "CUSTOMER.DISPUTE.RESOLVED",
]


def main() -> int:
    base_url = os.environ.get("PUBLIC_BASE_URL", "https://raidbench.com").rstrip("/")
    webhook_url = f"{base_url}/api/payments/paypal/webhook"
    client = PayPalClient()
    if not client.configured:
        print("PayPal credentials are not configured.", file=sys.stderr)
        return 1

    try:
        existing = next(
            (item for item in client.list_webhooks() if str(item.get("url") or "") == webhook_url),
            None,
        )
        webhook = existing or client.create_webhook(webhook_url, EVENTS)
    except PayPalError as error:
        print(str(error), file=sys.stderr)
        return 1

    result = {
        "environment": client.environment,
        "created": existing is None,
        "webhookUrl": webhook_url,
        "webhookId": webhook.get("id"),
        "eventCount": len(webhook.get("event_types") or EVENTS),
    }
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["webhookId"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
