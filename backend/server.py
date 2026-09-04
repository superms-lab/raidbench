from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from email.utils import formatdate
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.answer_engine import (  # noqa: E402
    AnswerEngineError,
    StaleEvidenceError,
    UnsupportedScopeError,
    build_raid_answer,
    load_raid_data,
)
from backend.email_delivery import EmailDeliveryError, email_delivery_from_environment  # noqa: E402
from backend.multigame_products import (  # noqa: E402
    ProductRoutingError,
    public_multigame_catalog,
    route_multigame_request,
)
from backend.multigame_jobs import (  # noqa: E402
    LIVE_PRODUCT_ID,
    MultiGameJobError,
    build_signed_job,
    export_signed_job,
)
from backend.paypal import (  # noqa: E402
    PayPalClient,
    PayPalError,
    PayPalWebhookSignatureError,
    approval_url,
)
from backend.payment_notifications import (  # noqa: E402
    FeishuPaymentNotifier,
    PaymentNotificationError,
)
from backend.store import (  # noqa: E402
    InsufficientCreditsError,
    StoreError,
    account_summary,
    catalog,
    claim_owner_notification,
    complete_paypal_capture_event,
    complete_paypal_order,
    completed_paypal_order_result,
    connect,
    consume_password_reset_token,
    create_customer,
    create_deferred_question,
    create_queued_question,
    create_pending_paypal_order,
    create_password_reset_token,
    create_session,
    create_verified_question,
    customer_for_session,
    delete_session,
    get_customer_auth,
    get_or_create_demo_customer,
    get_question,
    grant_demo_order,
    hold_queued_question,
    finish_owner_notification,
    init_database,
    invalidate_password_reset_token,
    list_orders,
    list_questions,
    mark_payment_event,
    new_id,
    paypal_order,
    paypal_order_by_capture,
    paypal_order_by_provider,
    password_reset_request_allowed,
    record_payment_event,
    reverse_paypal_credits,
    update_paypal_order_status,
)


SESSION_COOKIE = "rb_session"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
DENIED_STATIC_PARTS = {
    ".git",
    ".codex",
    "backend",
    "cloud",
    "content",
    "local",
    "operations",
    "schemas",
    "scripts",
    "templates",
    "tests",
}
ALLOWED_STATIC_SUFFIXES = {
    ".css",
    ".gif",
    ".html",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".png",
    ".svg",
    ".webmanifest",
    ".xml",
}
LEGAL_VERSION = "2026-08-01"


class ApiError(RuntimeError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def hash_password(password: str, *, iterations: int = 240_000) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iteration_text, salt_hex, expected_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iteration_text),
        )
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (TypeError, ValueError):
        return False


class RaidBenchHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        root: Path,
        db_path: Path,
        mode: str,
    ) -> None:
        self.root = root
        self.db_path = db_path
        self.mode = mode
        self.raid_data_path = Path(
            os.environ.get("RAIDBENCH_RAID_DATA_PATH", str(root / "content" / "rust-raid-data.json"))
        )
        self.raid_data = load_raid_data(self.raid_data_path)
        self.raid_data_mtime_ns = self.raid_data_path.stat().st_mtime_ns
        self.raid_data_lock = threading.Lock()
        self.raid_data_status_path = Path(
            os.environ.get(
                "RAIDBENCH_RAID_DATA_STATUS_PATH",
                str(self.raid_data_path.with_name("rust-paid-data-status.json")),
            )
        )
        self.sku_config = json.loads((root / "content" / "skus.json").read_text(encoding="utf-8"))
        self.paypal = PayPalClient()
        self.merchant_legal_name = os.environ.get("RAIDBENCH_MERCHANT_LEGAL_NAME", "").strip()
        self.merchant_country = os.environ.get("RAIDBENCH_MERCHANT_COUNTRY", "").strip()
        self.support_email = os.environ.get("RAIDBENCH_SUPPORT_EMAIL", "support@raidbench.com").strip()
        self.public_base_url = os.environ.get("PUBLIC_BASE_URL", "https://raidbench.com").rstrip("/")
        default_job_queue = "/jobs" if mode == "production" else f"/tmp/raidbench-answer-jobs-{os.getpid()}"
        self.multigame_job_queue = Path(os.environ.get("RAIDBENCH_JOB_QUEUE_DIR", default_job_queue))
        self.multigame_job_signing_secret = os.environ.get("RAIDBENCH_JOB_SIGNING_SECRET", "").strip()
        if mode == "demo" and not self.multigame_job_signing_secret:
            self.multigame_job_signing_secret = "raidbench-local-demo-answer-jobs-only"
        self.multigame_queue_ready = self._prepare_multigame_queue()
        self.implemented_multigame_handlers = {LIVE_PRODUCT_ID} if self.multigame_queue_ready else set()
        self.email_delivery = email_delivery_from_environment(
            public_base_url=self.public_base_url,
            support_email=self.support_email,
        )
        self.payment_notifier = FeishuPaymentNotifier.from_environment()
        self.background_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="raidbench-task")
        self.tax_policy_confirmed = os.environ.get("RAIDBENCH_TAX_POLICY_CONFIRMED", "0") == "1"
        self.merchant_ready = bool(self.merchant_legal_name and self.merchant_country)
        live_business_ready = bool(self.merchant_ready and self.tax_policy_confirmed)
        checkout_requested = bool(
            self.sku_config.get("publicCheckoutEnabled")
            or os.environ.get("RAIDBENCH_CHECKOUT_ENABLED", "0") == "1"
        )
        self.checkout_enabled = bool(
            checkout_requested
            and self.paypal.configured
            and self.paypal.webhook_configured
            and (self.paypal.environment == "sandbox" or live_business_ready)
        )
        super().__init__(server_address, handler_class)

    def _prepare_multigame_queue(self) -> bool:
        if len(self.multigame_job_signing_secret) < 32:
            return False
        try:
            for directory in ("inbox", "outbox", "archive", "rejected"):
                (self.multigame_job_queue / directory).mkdir(parents=True, exist_ok=True)
            probe = self.multigame_job_queue / "inbox" / f".write-probe-{os.getpid()}"
            probe.write_text("ready", encoding="ascii")
            probe.unlink()
        except OSError:
            return False
        return True

    def enqueue_multigame_job(self, question: dict[str, Any], routed: dict[str, Any]) -> Path:
        if not self.multigame_queue_ready:
            raise MultiGameJobError("The independent answer queue is unavailable.")
        job = build_signed_job(question, routed, self.multigame_job_signing_secret)
        return export_signed_job(self.multigame_job_queue, job)

    def enqueue_password_reset(self, email: str, token: str) -> None:
        self.background_executor.submit(self._deliver_password_reset, email, token)

    def _deliver_password_reset(self, email: str, token: str) -> None:
        try:
            self.email_delivery.send_password_reset(email, token)
        except EmailDeliveryError as error:
            with closing(connect(self.db_path)) as connection:
                invalidate_password_reset_token(connection, token)
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            print(f"[{timestamp}] Password reset email delivery failed: {error}")

    def enqueue_payment_notification(self, order: dict[str, Any] | None, event_type: str) -> None:
        if not order or not self.payment_notifier.configured:
            return
        notification_type = self.payment_notifier.notification_type(order)
        if not notification_type:
            return
        self.background_executor.submit(
            self._deliver_payment_notification,
            dict(order),
            event_type,
            notification_type,
        )

    def _deliver_payment_notification(
        self,
        order: dict[str, Any],
        event_type: str,
        notification_type: str,
    ) -> None:
        notification_key: str | None = None
        try:
            with closing(connect(self.db_path)) as connection:
                notification_key = claim_owner_notification(connection, order["id"], notification_type)
            if not notification_key:
                return

            last_error = ""
            for delay in (0, 1, 3):
                if delay:
                    time.sleep(delay)
                try:
                    self.payment_notifier.send_payment_event(order, event_type)
                except PaymentNotificationError as error:
                    last_error = str(error)
                    continue
                with closing(connect(self.db_path)) as connection:
                    finish_owner_notification(connection, notification_key, sent=True)
                return

            with closing(connect(self.db_path)) as connection:
                finish_owner_notification(connection, notification_key, sent=False, error=last_error)
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            print(f"[{timestamp}] Payment owner notification failed: {last_error}")
        except Exception as error:
            if notification_key:
                try:
                    with closing(connect(self.db_path)) as connection:
                        finish_owner_notification(connection, notification_key, sent=False, error=str(error))
                except Exception:
                    pass
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            print(f"[{timestamp}] Payment owner notification worker failed: {error}")

    def server_close(self) -> None:
        self.background_executor.shutdown(wait=True, cancel_futures=False)
        super().server_close()

    def _reload_raid_data_if_changed(self) -> None:
        current_mtime = self.raid_data_path.stat().st_mtime_ns
        if current_mtime == self.raid_data_mtime_ns:
            return
        with self.raid_data_lock:
            current_mtime = self.raid_data_path.stat().st_mtime_ns
            if current_mtime != self.raid_data_mtime_ns:
                self.raid_data = load_raid_data(self.raid_data_path)
                self.raid_data_mtime_ns = current_mtime

    def paid_data_status(self) -> dict[str, Any]:
        self._reload_raid_data_if_changed()
        if not self.raid_data_status_path.is_file():
            return {
                "status": "untracked",
                "ready": self.mode == "demo",
                "checkedAt": "",
                "errors": [] if self.mode == "demo" else ["Paid-data verification status is missing."],
            }
        try:
            status = json.loads(self.raid_data_status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return {"status": "blocked", "ready": False, "checkedAt": "", "errors": [f"Paid-data status is invalid: {error}"]}
        expected_id = str((self.raid_data.get("verification") or {}).get("latestOfficialChangelistId") or "")
        actual_hash = hashlib.sha256(self.raid_data_path.read_bytes()).hexdigest()
        errors = [str(item) for item in status.get("errors", [])]
        if status.get("status") != "verified":
            errors = errors or ["Paid Rust data is under patch review."]
        if str(status.get("dataChangelistId") or "") != expected_id:
            errors.append("Paid-data status does not match the loaded changelist.")
        latest_id = str(status.get("latestOfficialChangelistId") or "")
        if latest_id and latest_id != expected_id:
            errors.append("The latest official changelist has not been accepted into paid data.")
        if str(status.get("dataSha256") or "") != actual_hash:
            errors.append("Paid-data status does not match the loaded data file.")
        try:
            verified_at = datetime.strptime(str(self.raid_data.get("verifiedAt") or ""), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - verified_at).total_seconds() / 3600
            if age_hours < 0 or age_hours > 72:
                errors.append("Paid Rust data is outside the 72-hour freshness window.")
        except ValueError:
            errors.append("Paid Rust data has an invalid verification date.")
        return {
            "status": "verified" if not errors else "blocked",
            "ready": not errors,
            "checkedAt": str(status.get("checkedAt") or ""),
            "latestOfficialChangelistId": str(status.get("latestOfficialChangelistId") or ""),
            "errors": errors,
        }

    def checkout_available(self) -> bool:
        return self.checkout_enabled and (
            self.paid_data_status()["ready"] or self.live_multigame_available()
        )

    def live_multigame_available(self) -> bool:
        if not self.multigame_queue_ready:
            return False
        try:
            public = public_multigame_catalog(enabled_product_ids=self.implemented_multigame_handlers)
        except Exception:
            return False
        return bool(public["products"])

    def customer_catalog(self, connection, *, include_demo: bool) -> dict[str, Any]:
        result = catalog(connection, include_demo=include_demo)
        paid_status = self.paid_data_status()
        if not paid_status["ready"]:
            result["actions"] = [item for item in result["actions"] if not str(item["id"]).startswith("rust-")]
            if not result["actions"]:
                result["packs"] = []
        result["paidDataStatus"] = paid_status["status"]
        return result

    def current_raid_data(self, *, require_paid_ready: bool = False) -> dict[str, Any]:
        self._reload_raid_data_if_changed()
        if require_paid_ready and not self.paid_data_status()["ready"]:
            raise StaleEvidenceError("Rust paid-answer evidence is under patch review. No credits were charged.")
        return self.raid_data


class RaidBenchHandler(BaseHTTPRequestHandler):
    server: RaidBenchHTTPServer
    server_version = "RaidBench/1.0"

    def log_message(self, message_format: str, *args: Any) -> None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"[{timestamp}] {self.address_string()} {message_format % args}")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        if urlparse(self.path).path == "/embed/rust-raid-calculator.html":
            self.send_header("Content-Security-Policy", "frame-ancestors *")
        else:
            self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def _json(self, status: int, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _error(self, error: ApiError) -> None:
        self._json(error.status, {"error": {"code": error.code, "message": error.message}})

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ApiError(400, "invalid_length", "Invalid request length.") from error
        if length <= 0 or length > 65_536:
            raise ApiError(400, "invalid_body", "A JSON request body is required and must be under 64 KB.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ApiError(400, "invalid_json", "Request body must be valid JSON.") from error
        if not isinstance(payload, dict):
            raise ApiError(400, "invalid_json", "Request body must be a JSON object.")
        return payload

    def _connection(self):
        return connect(self.server.db_path)

    def _session_token(self) -> str:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def _customer(self, connection) -> dict[str, Any]:
        customer = customer_for_session(connection, self._session_token())
        if not customer:
            raise ApiError(401, "authentication_required", "Sign in to access this account.")
        return customer

    def _cookie_header(self, token: str, *, clear: bool = False) -> str:
        secure = "; Secure" if self.server.mode == "production" else ""
        max_age = 0 if clear else 14 * 24 * 60 * 60
        value = "" if clear else token
        return (
            f"{SESSION_COOKIE}={value}; Path=/; Max-Age={max_age}; HttpOnly; "
            f"SameSite=Lax{secure}"
        )

    def _idempotency_key(self) -> str:
        value = self.headers.get("Idempotency-Key", "").strip()
        if not value:
            return new_id("req")
        if len(value) > 120 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", value):
            raise ApiError(400, "invalid_idempotency_key", "Invalid idempotency key.")
        return value

    def _same_origin(self) -> None:
        origin = self.headers.get("Origin")
        if not origin:
            return
        parsed = urlparse(origin)
        if parsed.netloc != self.headers.get("Host") or parsed.scheme not in {"http", "https"}:
            raise ApiError(403, "origin_rejected", "Cross-origin requests are not accepted.")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/"):
                self._api_get(path)
            else:
                self._static(path)
        except ApiError as error:
            self._error(error)
        except StoreError as error:
            self._error(ApiError(404, "not_found", str(error)))
        except Exception as error:
            self.log_error("Unhandled GET error: %r", error)
            self._error(ApiError(500, "internal_error", "The local service could not complete this request."))

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            self._same_origin()
            self._api_post(path)
        except ApiError as error:
            self._error(error)
        except InsufficientCreditsError as error:
            self._error(ApiError(409, "insufficient_credits", str(error)))
        except (AnswerEngineError, StoreError) as error:
            self._error(ApiError(422, "request_rejected", str(error)))
        except PayPalError as error:
            self._error(ApiError(502, "paypal_error", str(error)))
        except Exception as error:
            self.log_error("Unhandled POST error: %r", error)
            self._error(ApiError(500, "internal_error", "The local service could not complete this request."))

    def _api_get(self, path: str) -> None:
        if path == "/api/health":
            raid_data = self.server.current_raid_data()
            paid_data_status = self.server.paid_data_status()
            with closing(self._connection()) as connection:
                connection.execute("SELECT 1").fetchone()
            self._json(200, {
                "status": "ok",
                "mode": self.server.mode,
                "database": "sqlite",
                "delivery": "in_account",
                "checkoutEnabled": self.server.checkout_available(),
                "paidDataVerifiedAt": raid_data["verifiedAt"],
                "paidDataStatus": paid_data_status["status"],
                "multigameQueueReady": self.server.multigame_queue_ready,
                "serverTime": datetime.now(timezone.utc).isoformat(),
            })
            return
        if path == "/api/config":
            paid_data_status = self.server.paid_data_status()
            self._json(200, {
                "mode": self.server.mode,
                "demoPaymentsEnabled": self.server.mode == "demo",
                "checkoutEnabled": self.server.checkout_available(),
                "passwordResetEnabled": self.server.email_delivery.configured,
                "paymentNotificationsEnabled": self.server.payment_notifier.configured,
                "paypalEnvironment": self.server.paypal.environment if self.server.paypal.configured else None,
                "paypalWebhookReady": self.server.paypal.webhook_configured,
                "legalVersion": LEGAL_VERSION,
                "merchant": {
                    "legalName": self.server.merchant_legal_name or (
                        "RaidBench PayPal sandbox merchant" if self.server.paypal.environment == "sandbox" else None
                    ),
                    "country": self.server.merchant_country or (
                        "Test environment" if self.server.paypal.environment == "sandbox" else None
                    ),
                    "supportEmail": self.server.support_email,
                    "identityReady": self.server.merchant_ready,
                },
                "liveReadiness": {
                    "merchantIdentityReady": self.server.merchant_ready,
                    "taxPolicyConfirmed": self.server.tax_policy_confirmed,
                    "paypalCredentialsReady": self.server.paypal.configured,
                    "paypalWebhookReady": self.server.paypal.webhook_configured,
                    "passwordResetEmailReady": self.server.email_delivery.configured,
                    "ownerPaymentNotificationsReady": self.server.payment_notifier.configured,
                    "rustPaidDataReady": paid_data_status["ready"],
                    "palworldAgentQueueReady": self.server.multigame_queue_ready,
                },
                "launchMarkets": ["US", "CA"],
                "billingCurrency": "USD",
                "deliveryTargets": {
                    "instantAnswerSeconds": 5,
                    "structuredPlanSeconds": 10,
                    "multigameReviewMinutes": 10,
                    "multigameHardStopMinutes": 30,
                    "unsupportedRequest": "held_without_charge",
                },
            })
            return
        if path == "/api/targets":
            data = self.server.current_raid_data()
            self._json(200, {
                "verifiedAt": data["verifiedAt"],
                "scope": data["scope"],
                "targets": data["targets"],
                "methods": [
                    {"id": "rockets", "label": "Rockets"},
                    {"id": "c4", "label": "Timed Explosive Charges"},
                    {"id": "satchels", "label": "Satchel Charges"},
                    {"id": "explosiveAmmo", "label": "Explosive Ammo"},
                ],
            })
            return

        if path == "/api/session":
            with closing(self._connection()) as connection:
                customer = customer_for_session(connection, self._session_token())
                if not customer:
                    self._json(200, {"authenticated": False})
                else:
                    self._json(200, {
                        "authenticated": True,
                        "customer": account_summary(connection, customer["id"]),
                    })
            return

        with closing(self._connection()) as connection:
            if path == "/api/catalog":
                self._json(200, self.server.customer_catalog(connection, include_demo=self.server.mode == "demo"))
                return
            if path == "/api/multigame/products":
                enabled = self.server.implemented_multigame_handlers if self.server.multigame_queue_ready else set()
                self._json(200, public_multigame_catalog(enabled_product_ids=enabled))
                return
            if path == "/api/me":
                customer = self._customer(connection)
                self._json(200, {"customer": account_summary(connection, customer["id"])})
                return
            if path == "/api/questions":
                customer = self._customer(connection)
                self._json(200, {"questions": list_questions(connection, customer["id"])})
                return
            if path == "/api/orders":
                customer = self._customer(connection)
                self._json(200, {"orders": list_orders(connection, customer["id"])})
                return
            match = re.fullmatch(r"/api/questions/([A-Za-z0-9_]+)", path)
            if match:
                customer = self._customer(connection)
                self._json(200, {"question": get_question(connection, customer["id"], match.group(1))})
                return
        raise ApiError(404, "not_found", "API route not found.")

    def _api_post(self, path: str) -> None:
        if path == "/api/payments/paypal/webhook":
            self._paypal_webhook()
            return

        if path == "/api/auth/register":
            payload = self._body()
            email = str(payload.get("email", "")).strip().lower()
            password = str(payload.get("password", ""))
            display_name = str(payload.get("displayName", "")).strip()
            region = str(payload.get("region", "US")).upper()
            if not EMAIL_PATTERN.fullmatch(email):
                raise ApiError(422, "invalid_email", "Enter a valid email address.")
            if len(password) < 10 or len(password) > 200:
                raise ApiError(422, "invalid_password", "Password must be between 10 and 200 characters.")
            if region not in {"US", "CA"}:
                raise ApiError(422, "invalid_region", "Launch accounts are currently available for the US and Canada.")
            with closing(self._connection()) as connection:
                customer = create_customer(connection, email, hash_password(password), display_name, region)
                token = create_session(connection, customer["id"])
                result = account_summary(connection, customer["id"])
            self._json(201, {"customer": result}, {"Set-Cookie": self._cookie_header(token)})
            return

        if path == "/api/auth/login":
            payload = self._body()
            email = str(payload.get("email", "")).strip().lower()
            password = str(payload.get("password", ""))
            with closing(self._connection()) as connection:
                record = get_customer_auth(connection, email)
                if not record or not record.get("password_hash") or not verify_password(password, record["password_hash"]):
                    raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
                token = create_session(connection, record["id"])
                customer = account_summary(connection, record["id"])
            self._json(200, {"customer": customer}, {"Set-Cookie": self._cookie_header(token)})
            return

        if path == "/api/auth/logout":
            with closing(self._connection()) as connection:
                delete_session(connection, self._session_token())
            self._json(200, {"ok": True}, {"Set-Cookie": self._cookie_header("", clear=True)})
            return

        if path == "/api/auth/password-reset/request":
            payload = self._body()
            email = str(payload.get("email", "")).strip().lower()
            if not EMAIL_PATTERN.fullmatch(email):
                raise ApiError(422, "invalid_email", "Enter a valid email address.")
            if not self.server.email_delivery.configured:
                raise ApiError(
                    503,
                    "password_reset_unavailable",
                    f"Automatic password reset is unavailable. Contact {self.server.support_email} for account help.",
                )

            reset_token = ""
            with closing(self._connection()) as connection:
                if password_reset_request_allowed(connection, email):
                    customer = get_customer_auth(connection, email)
                    if customer:
                        reset_token = create_password_reset_token(connection, customer["id"])
            if reset_token:
                self.server.enqueue_password_reset(email, reset_token)
            self._json(202, {
                "ok": True,
                "message": "If an account matches that email, a reset link will arrive shortly.",
            })
            return

        if path == "/api/auth/password-reset/confirm":
            payload = self._body()
            token = str(payload.get("token", ""))
            password = str(payload.get("password", ""))
            if len(password) < 10 or len(password) > 200:
                raise ApiError(422, "invalid_password", "Password must be between 10 and 200 characters.")
            if len(token) < 32 or len(token) > 200 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
                raise ApiError(422, "invalid_or_expired_reset", "This password reset link is invalid or has expired.")
            with closing(self._connection()) as connection:
                try:
                    consume_password_reset_token(connection, token, hash_password(password))
                except StoreError as error:
                    raise ApiError(422, "invalid_or_expired_reset", str(error)) from error
            self._json(
                200,
                {"ok": True, "message": "Password updated. Sign in with your new password."},
                {"Set-Cookie": self._cookie_header("", clear=True)},
            )
            return

        if path == "/api/demo/session":
            if self.server.mode != "demo":
                raise ApiError(404, "not_found", "API route not found.")
            with closing(self._connection()) as connection:
                customer = get_or_create_demo_customer(connection)
                token = create_session(connection, customer["id"])
                result = account_summary(connection, customer["id"])
            self._json(200, {"customer": result}, {"Set-Cookie": self._cookie_header(token)})
            return

        with closing(self._connection()) as connection:
            customer = self._customer(connection)
            if path == "/api/demo/orders":
                if self.server.mode != "demo":
                    raise ApiError(404, "not_found", "API route not found.")
                payload = self._body()
                result = grant_demo_order(
                    connection,
                    customer["id"],
                    str(payload.get("sku", "")),
                    self._idempotency_key(),
                )
                self._json(201, result)
                return
            if path in {"/api/answers/instant", "/api/questions/raid-plan"}:
                payload = self._body()
                answer_type = "instant" if path.endswith("instant") else "raid_plan"
                action_id = "rust-instant-raid-answer" if answer_type == "instant" else "rust-raid-prep"
                request_key = self._idempotency_key()
                try:
                    result = build_raid_answer(
                        payload,
                        self.server.current_raid_data(require_paid_ready=True),
                        answer_type=answer_type,
                    )
                except (UnsupportedScopeError, StaleEvidenceError) as error:
                    question = create_deferred_question(
                        connection,
                        customer["id"],
                        answer_type,
                        "Rust raid cost request",
                        payload,
                        str(error),
                        request_key,
                    )
                    self._json(202, {"question": question, "customer": account_summary(connection, customer["id"])})
                    return
                question = create_verified_question(
                    connection,
                    customer["id"],
                    action_id,
                    answer_type,
                    "Rust raid cost request",
                    payload,
                    result.answer,
                    request_key,
                )
                self._json(201, {"question": question, "customer": account_summary(connection, customer["id"])})
                return
            if path == "/api/questions/multigame":
                payload = self._body()
                try:
                    routed = route_multigame_request(
                        payload,
                        implemented_handlers=self.server.implemented_multigame_handlers,
                    )
                except ProductRoutingError as error:
                    raise ApiError(422, "invalid_multigame_request", str(error)) from error
                request_key = self._idempotency_key()
                if routed["purchaseAvailable"]:
                    question = create_queued_question(
                        connection,
                        customer["id"],
                        routed["productId"],
                        routed["questionText"],
                        routed["inputs"],
                        request_key,
                        routed["game"],
                    )
                    try:
                        self.server.enqueue_multigame_job(question, routed)
                    except MultiGameJobError:
                        question = hold_queued_question(
                            connection,
                            question["id"],
                            "The independent answer queue could not accept this request. No credits were charged.",
                        )
                        routed = {
                            **routed,
                            "status": "held_without_charge",
                            "reasonCode": "answer_queue_unavailable",
                            "reason": question["blockedReason"],
                            "purchaseAvailable": False,
                        }
                    self._json(202, {
                        "intake": {
                            "status": routed["status"],
                            "reasonCode": routed["reasonCode"],
                            "missingInputs": routed["missingInputs"],
                            "creditsQuoted": routed["creditsQuoted"],
                            "creditsCharged": 0,
                            "purchaseAvailable": routed["purchaseAvailable"],
                        },
                        "question": question,
                        "customer": account_summary(connection, customer["id"]),
                    })
                    return
                stored_inputs = {
                    **routed["inputs"],
                    "productId": routed["productId"],
                    "gameId": routed["gameId"],
                    "routingReasonCode": routed["reasonCode"],
                }
                question = create_deferred_question(
                    connection,
                    customer["id"],
                    routed["questionType"],
                    routed["questionText"],
                    stored_inputs,
                    routed["reason"],
                    request_key,
                    game=routed["game"],
                    credits_cost=routed["creditsQuoted"],
                )
                self._json(202, {
                    "intake": {
                        "status": routed["status"],
                        "reasonCode": routed["reasonCode"],
                        "missingInputs": routed["missingInputs"],
                        "creditsQuoted": routed["creditsQuoted"],
                        "creditsCharged": 0,
                        "purchaseAvailable": False,
                    },
                    "question": question,
                    "customer": account_summary(connection, customer["id"]),
                })
                return
            if path == "/api/payments/paypal/create":
                if not self.server.checkout_available():
                    raise ApiError(503, "checkout_unavailable", "PayPal checkout is not enabled yet.")
                payload = self._body()
                required_consent = (
                    payload.get("acceptedTerms") is True
                    and payload.get("acceptedRefundPolicy") is True
                    and payload.get("acknowledgedDigitalDelivery") is True
                    and str(payload.get("legalVersion") or "") == LEGAL_VERSION
                )
                if not required_consent:
                    raise ApiError(
                        422,
                        "checkout_consent_required",
                        "Review and accept the Terms, Refund Policy, and immediate account delivery before checkout.",
                    )
                sku = str(payload.get("sku", ""))
                available = {item["sku"]: item for item in self.server.customer_catalog(connection, include_demo=False)["packs"]}
                pack = available.get(sku)
                if not pack:
                    raise ApiError(422, "invalid_sku", "Credit pack is unavailable.")
                public_base = self.server.public_base_url
                local_order_id = new_id("ord")
                paypal_payload = self.server.paypal.create_order(
                    sku=pack["sku"],
                    name=pack["name"],
                    amount=float(pack["price_usd"]),
                    return_url=f"{public_base}/customer.html?paypal=return",
                    cancel_url=f"{public_base}/customer.html?paypal=cancel",
                    local_order_id=local_order_id,
                )
                create_pending_paypal_order(
                    connection,
                    customer["id"],
                    sku,
                    str(paypal_payload["id"]),
                    paypal_payload,
                    local_order_id,
                    {
                        "termsVersion": LEGAL_VERSION,
                        "refundPolicyVersion": LEGAL_VERSION,
                        "consentedAt": datetime.now(timezone.utc).isoformat(),
                    },
                )
                self._json(201, {
                    "paypalOrderId": paypal_payload["id"],
                    "approvalUrl": approval_url(paypal_payload),
                })
                return
            if path == "/api/payments/paypal/capture":
                if not self.server.checkout_enabled:
                    raise ApiError(503, "checkout_unavailable", "PayPal checkout is not enabled yet.")
                payload = self._body()
                paypal_order_id = str(payload.get("paypalOrderId", ""))
                existing = completed_paypal_order_result(connection, customer["id"], paypal_order_id)
                if existing:
                    self._json(200, existing)
                    return
                paypal_order(connection, customer["id"], paypal_order_id)
                capture = self._capture_or_reconcile(paypal_order_id)
                result = complete_paypal_order(connection, customer["id"], paypal_order_id, capture)
                self.server.enqueue_payment_notification(
                    result.get("order") if isinstance(result, dict) else None,
                    "PAYMENT.CAPTURE.COMPLETED",
                )
                self._json(200, result)
                return
        raise ApiError(404, "not_found", "API route not found.")

    def _capture_or_reconcile(self, paypal_order_id: str) -> dict[str, Any]:
        try:
            return self.server.paypal.capture_order(paypal_order_id)
        except PayPalError as capture_error:
            order = self.server.paypal.show_order(paypal_order_id)
            if order.get("status") != "COMPLETED":
                raise capture_error
            return order

    @staticmethod
    def _paypal_event_ids(event: dict[str, Any]) -> tuple[str, str]:
        event_type = str(event.get("event_type") or "").upper()
        resource = event.get("resource") or {}
        supplementary = resource.get("supplementary_data") or {}
        related = supplementary.get("related_ids") or {}
        provider_order_id = str(related.get("order_id") or "")
        capture_id = str(related.get("capture_id") or "")
        if event_type.startswith("CHECKOUT.ORDER.") or event_type == "CHECKOUT.PAYMENT-APPROVAL.REVERSED":
            provider_order_id = provider_order_id or str(resource.get("id") or "")
        if event_type in {
            "PAYMENT.CAPTURE.COMPLETED",
            "PAYMENT.CAPTURE.PENDING",
            "PAYMENT.CAPTURE.DENIED",
            "PAYMENT.CAPTURE.DECLINED",
            "PAYMENT.CAPTURE.REVERSED",
        }:
            capture_id = capture_id or str(resource.get("id") or "")
        return provider_order_id, capture_id

    def _paypal_webhook(self) -> None:
        if not self.server.checkout_enabled:
            raise ApiError(503, "webhook_unavailable", "PayPal webhook processing is not enabled.")
        event = self._body()
        provider_event_id = str(event.get("id") or "")
        event_type = str(event.get("event_type") or "").upper()
        resource = event.get("resource")
        if not provider_event_id or not event_type or not isinstance(resource, dict):
            raise ApiError(400, "invalid_webhook", "PayPal webhook payload is incomplete.")
        try:
            verified = self.server.paypal.verify_webhook(dict(self.headers.items()), event)
        except PayPalWebhookSignatureError as error:
            raise ApiError(400, "invalid_webhook_signature", str(error)) from error
        if not verified:
            raise ApiError(400, "invalid_webhook_signature", "PayPal webhook signature was rejected.")

        provider_order_id, capture_id = self._paypal_event_ids(event)
        processed_order: dict[str, Any] | None = None
        with closing(self._connection()) as connection:
            local_order: dict[str, Any] | None = None
            try:
                if provider_order_id:
                    local_order = paypal_order_by_provider(connection, provider_order_id)
                elif capture_id:
                    local_order = paypal_order_by_capture(connection, capture_id)
            except StoreError:
                local_order = None

            payment_event = record_payment_event(
                connection,
                provider_event_id=provider_event_id,
                event_type=event_type,
                payload=event,
                order_id=local_order["id"] if local_order else None,
            )
            if payment_event["processing_status"] == "processed":
                self._json(200, {"ok": True, "duplicate": True})
                return

            try:
                result: dict[str, Any] = {"ignored": True}
                if event_type == "CHECKOUT.ORDER.APPROVED":
                    if not provider_order_id or not local_order:
                        raise StoreError("Approved PayPal order is not linked to a RaidBench order.")
                    existing = completed_paypal_order_result(
                        connection,
                        local_order["customer_id"],
                        provider_order_id,
                    )
                    if existing:
                        result = existing
                    else:
                        capture = self._capture_or_reconcile(provider_order_id)
                        result = complete_paypal_order(
                            connection,
                            local_order["customer_id"],
                            provider_order_id,
                            capture,
                        )
                elif event_type == "PAYMENT.CAPTURE.COMPLETED":
                    if not provider_order_id:
                        raise StoreError("Completed PayPal capture has no related order id.")
                    result = complete_paypal_capture_event(
                        connection,
                        provider_order_id,
                        resource,
                        event,
                    )
                elif event_type in {
                    "PAYMENT.CAPTURE.PENDING",
                    "PAYMENT.CAPTURE.DENIED",
                    "PAYMENT.CAPTURE.DECLINED",
                    "CHECKOUT.PAYMENT-APPROVAL.REVERSED",
                }:
                    if not provider_order_id:
                        raise StoreError("PayPal capture status has no related order id.")
                    result = {
                        "order": update_paypal_order_status(
                            connection,
                            provider_order_id,
                            "payment_pending" if event_type.endswith("PENDING") else "payment_denied",
                            event,
                        )
                    }
                elif event_type in {"PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"}:
                    amount = resource.get("amount") or {}
                    if not capture_id:
                        raise StoreError("PayPal refund or reversal has no related capture id.")
                    result = reverse_paypal_credits(
                        connection,
                        provider_event_id=provider_event_id,
                        capture_id=capture_id,
                        amount=float(amount.get("value", 0)),
                        currency=str(amount.get("currency_code") or ""),
                        status="refunded" if event_type.endswith("REFUNDED") else "reversed",
                        raw_event=event,
                    )
                processed_order = result.get("order") if isinstance(result, dict) else None
                mark_payment_event(
                    connection,
                    provider_event_id,
                    status="processed",
                    order_id=processed_order.get("id") if isinstance(processed_order, dict) else None,
                )
            except Exception as error:
                mark_payment_event(
                    connection,
                    provider_event_id,
                    status="failed",
                    order_id=local_order["id"] if local_order else None,
                    error=str(error),
                )
                raise
        self.server.enqueue_payment_notification(processed_order, event_type)
        self._json(200, {"ok": True})

    def _static(self, raw_path: str) -> None:
        decoded = unquote(raw_path)
        relative_text = "index.html" if decoded in {"", "/"} else decoded.lstrip("/")
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts or any(part in DENIED_STATIC_PARTS for part in relative.parts):
            raise ApiError(404, "not_found", "File not found.")
        if relative.name.startswith("owner-") and self.server.mode != "demo":
            raise ApiError(404, "not_found", "File not found.")
        if relative.suffix.lower() not in ALLOWED_STATIC_SUFFIXES:
            raise ApiError(404, "not_found", "File not found.")
        path = (self.server.root / relative).resolve()
        if self.server.root not in path.parents or not path.is_file():
            raise ApiError(404, "not_found", "File not found.")
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Last-Modified", formatdate(path.stat().st_mtime, usegmt=True))
        self.send_header("Cache-Control", "no-store" if relative.name == "customer.html" else "public, max-age=300")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def create_server(*, host: str, port: int, root: Path, db_path: Path, mode: str) -> RaidBenchHTTPServer:
    init_database(
        db_path,
        root / "local" / "raidbench-local-schema.sql",
        root / "content" / "skus.json",
    )
    return RaidBenchHTTPServer((host, port), RaidBenchHandler, root=root, db_path=db_path, mode=mode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RaidBench local customer application.")
    parser.add_argument("--host", default=os.environ.get("RAIDBENCH_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("RAIDBENCH_PORT", "4289")))
    parser.add_argument("--mode", choices=("demo", "production"), default=os.environ.get("RAIDBENCH_MODE", "demo"))
    parser.add_argument("--db", default=os.environ.get("RAIDBENCH_DB_PATH", str(ROOT / "local" / "raidbench.local.db")))
    args = parser.parse_args()
    if args.mode == "demo" and args.host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("RAIDBENCH_ALLOW_REMOTE_DEMO") != "1":
        parser.error("Demo mode may only bind to localhost. Use production mode for a network listener.")
    server = create_server(host=args.host, port=args.port, root=ROOT, db_path=Path(args.db), mode=args.mode)
    print(f"RaidBench {args.mode} server: http://{args.host}:{server.server_address[1]}")
    print(f"SQLite database: {Path(args.db).resolve()}")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
