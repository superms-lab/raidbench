from __future__ import annotations

import base64
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping


class PayPalError(RuntimeError):
    pass


class PayPalWebhookSignatureError(PayPalError):
    pass


class PayPalClient:
    def __init__(self) -> None:
        self.client_id = os.environ.get("PAYPAL_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "").strip()
        self.webhook_id = os.environ.get("PAYPAL_WEBHOOK_ID", "").strip()
        self.environment = os.environ.get("PAYPAL_ENV", "sandbox").strip().lower()
        self.base_url = (
            "https://api-m.paypal.com"
            if self.environment == "live"
            else "https://api-m.sandbox.paypal.com"
        )

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def webhook_configured(self) -> bool:
        return bool(self.webhook_id)

    def _access_token(self) -> str:
        if not self.configured:
            raise PayPalError("PayPal credentials are not configured.")
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        request = urllib.request.Request(
            f"{self.base_url}/v1/oauth2/token",
            data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "RaidBench/1.0",
            },
            method="POST",
        )
        payload = self._send(request)
        token = payload.get("access_token")
        if not token:
            raise PayPalError("PayPal did not return an access token.")
        return str(token)

    def _send(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body)
            except json.JSONDecodeError:
                detail = {"message": body[:500]}
            message = detail.get("message") or detail.get("error_description") or f"HTTP {error.code}"
            raise PayPalError(f"PayPal request failed: {message}") from error
        except urllib.error.URLError as error:
            raise PayPalError(f"PayPal network request failed: {error.reason}") from error

    def _json_request(self, path: str, *, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "PayPal-Request-Id": secrets.token_hex(16),
                "User-Agent": "RaidBench/1.0",
            },
            method=method,
        )
        return self._send(request)

    def create_order(
        self,
        *,
        sku: str,
        name: str,
        amount: float,
        return_url: str,
        cancel_url: str,
        local_order_id: str,
    ) -> dict[str, Any]:
        return self._json_request(
            "/v2/checkout/orders",
            method="POST",
            payload={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": sku,
                    "custom_id": local_order_id[:127],
                    "invoice_id": local_order_id[:127],
                    "description": name,
                    "amount": {"currency_code": "USD", "value": f"{amount:.2f}"},
                }],
                "application_context": {
                    "brand_name": "RaidBench",
                    "landing_page": "LOGIN",
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING",
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
            },
        )

    def capture_order(self, paypal_order_id: str) -> dict[str, Any]:
        if not paypal_order_id or len(paypal_order_id) > 64:
            raise PayPalError("Invalid PayPal order id.")
        return self._json_request(
            f"/v2/checkout/orders/{urllib.parse.quote(paypal_order_id)}/capture",
            method="POST",
            payload={},
        )

    def show_order(self, paypal_order_id: str) -> dict[str, Any]:
        if not paypal_order_id or len(paypal_order_id) > 64:
            raise PayPalError("Invalid PayPal order id.")
        return self._json_request(
            f"/v2/checkout/orders/{urllib.parse.quote(paypal_order_id)}",
            method="GET",
        )

    def list_webhooks(self) -> list[dict[str, Any]]:
        payload = self._json_request("/v1/notifications/webhooks", method="GET")
        return [item for item in payload.get("webhooks") or [] if isinstance(item, dict)]

    def create_webhook(self, url: str, event_names: list[str]) -> dict[str, Any]:
        if not url.startswith("https://"):
            raise PayPalError("PayPal webhook URL must use HTTPS.")
        if not event_names:
            raise PayPalError("At least one PayPal webhook event is required.")
        return self._json_request(
            "/v1/notifications/webhooks",
            method="POST",
            payload={
                "url": url,
                "event_types": [{"name": name} for name in event_names],
            },
        )

    def verify_webhook(self, headers: Mapping[str, str], event: Mapping[str, Any]) -> bool:
        if not self.webhook_configured:
            raise PayPalError("PayPal webhook id is not configured.")
        normalized = {str(key).lower(): str(value) for key, value in headers.items()}
        required = {
            "auth_algo": normalized.get("paypal-auth-algo", ""),
            "cert_url": normalized.get("paypal-cert-url", ""),
            "transmission_id": normalized.get("paypal-transmission-id", ""),
            "transmission_sig": normalized.get("paypal-transmission-sig", ""),
            "transmission_time": normalized.get("paypal-transmission-time", ""),
        }
        if not all(required.values()):
            raise PayPalWebhookSignatureError("PayPal webhook signature headers are incomplete.")
        result = self._json_request(
            "/v1/notifications/verify-webhook-signature",
            method="POST",
            payload={
                **required,
                "webhook_id": self.webhook_id,
                "webhook_event": dict(event),
            },
        )
        return str(result.get("verification_status") or "").upper() == "SUCCESS"


def approval_url(payload: dict[str, Any]) -> str:
    for link in payload.get("links") or []:
        if link.get("rel") == "approve" and link.get("href"):
            return str(link["href"])
    raise PayPalError("PayPal did not return an approval link.")
