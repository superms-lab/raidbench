from __future__ import annotations

import hashlib
import html
import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class EmailDeliveryError(RuntimeError):
    pass


def _password_reset_content(
    *, public_base_url: str, support_email: str, token: str
) -> tuple[str, str, str, str]:
    # The fragment keeps the secret token out of HTTP access logs and referrer headers.
    reset_url = f"{public_base_url}/customer.html#reset={quote(token, safe='')}"
    safe_url = html.escape(reset_url, quote=True)
    safe_support = html.escape(support_email)
    text_body = (
        "A password reset was requested for your RaidBench account.\n\n"
        f"Set a new password within 30 minutes:\n{reset_url}\n\n"
        "If you did not request this, no action is required. "
        f"For account help, contact {support_email}."
    )
    html_body = (
        '<div style="font-family:Arial,sans-serif;max-width:560px;color:#18201b;line-height:1.6">'
        '<p style="font-size:12px;font-weight:700;letter-spacing:0;color:#667168">RAIDBENCH ACCOUNT</p>'
        '<h1 style="font-size:24px;letter-spacing:0">Reset your password</h1>'
        '<p>A password reset was requested for your RaidBench account.</p>'
        f'<p><a href="{safe_url}" style="display:inline-block;padding:12px 18px;'
        'background:#c98222;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:700">'
        'Set a new password</a></p>'
        '<p>This link expires in 30 minutes and can be used once.</p>'
        '<p>If you did not request this, no action is required. '
        f'For account help, contact <a href="mailto:{safe_support}">{safe_support}</a>.</p>'
        '</div>'
    )
    entity_ref = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    return reset_url, text_body, html_body, entity_ref


@dataclass(frozen=True)
class ResendEmailDelivery:
    api_key: str
    sender: str
    public_base_url: str
    support_email: str
    api_url: str = "https://api.resend.com/emails"

    @classmethod
    def from_environment(cls, *, public_base_url: str, support_email: str) -> "ResendEmailDelivery":
        return cls(
            api_key=os.environ.get("RESEND_API_KEY", "").strip(),
            sender=os.environ.get("RAIDBENCH_EMAIL_FROM", "").strip(),
            public_base_url=public_base_url.rstrip("/"),
            support_email=support_email,
            api_url=os.environ.get("RESEND_API_URL", "https://api.resend.com/emails").strip(),
        )

    @property
    def configured(self) -> bool:
        return bool(
            self.api_key
            and self.sender
            and self.public_base_url
            and self.public_base_url.startswith(("https://", "http://localhost", "http://127.0.0.1"))
        )

    def password_reset_url(self, token: str) -> str:
        return f"{self.public_base_url}/customer.html#reset={quote(token, safe='')}"

    def send_password_reset(self, recipient: str, token: str) -> str:
        if not self.configured:
            raise EmailDeliveryError("Password reset email delivery is not configured.")

        _, text_body, html_body, entity_ref = _password_reset_content(
            public_base_url=self.public_base_url,
            support_email=self.support_email,
            token=token,
        )
        payload = {
            "from": self.sender,
            "to": [recipient],
            "reply_to": self.support_email,
            "subject": "Reset your RaidBench password",
            "text": text_body,
            "html": html_body,
            "headers": {"X-Entity-Ref-ID": entity_ref},
        }
        request = Request(
            self.api_url,
            data=json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": f"password-reset-{hashlib.sha256(token.encode('utf-8')).hexdigest()}",
                "User-Agent": "RaidBench/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise EmailDeliveryError(f"Email provider rejected the request ({error.code}).") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise EmailDeliveryError("Email provider did not return a usable response.") from error

        message_id = str(result.get("id") or "")
        if not message_id:
            raise EmailDeliveryError("Email provider response did not include a message id.")
        return message_id


@dataclass(frozen=True)
class Smtp2GoEmailDelivery:
    api_key: str
    sender: str
    public_base_url: str
    support_email: str
    api_url: str = "https://api.smtp2go.com/v3/email/send"

    @classmethod
    def from_environment(cls, *, public_base_url: str, support_email: str) -> "Smtp2GoEmailDelivery":
        return cls(
            api_key=os.environ.get("SMTP2GO_API_KEY", "").strip(),
            sender=os.environ.get("RAIDBENCH_EMAIL_FROM", "").strip(),
            public_base_url=public_base_url.rstrip("/"),
            support_email=support_email,
            api_url=os.environ.get(
                "SMTP2GO_API_URL", "https://api.smtp2go.com/v3/email/send"
            ).strip(),
        )

    @property
    def configured(self) -> bool:
        return bool(
            self.api_key
            and self.sender
            and self.public_base_url
            and self.public_base_url.startswith(("https://", "http://localhost", "http://127.0.0.1"))
        )

    def password_reset_url(self, token: str) -> str:
        return f"{self.public_base_url}/customer.html#reset={quote(token, safe='')}"

    def send_password_reset(self, recipient: str, token: str) -> str:
        if not self.configured:
            raise EmailDeliveryError("Password reset email delivery is not configured.")

        _, text_body, html_body, entity_ref = _password_reset_content(
            public_base_url=self.public_base_url,
            support_email=self.support_email,
            token=token,
        )
        payload = {
            "sender": self.sender,
            "to": [recipient],
            "subject": "Reset your RaidBench password",
            "text_body": text_body,
            "html_body": html_body,
            "custom_headers": [
                {"header": "Reply-To", "value": self.support_email},
                {"header": "X-Entity-Ref-ID", "value": entity_ref},
            ],
        }
        request = Request(
            self.api_url,
            data=json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
            headers={
                "X-Smtp2go-Api-Key": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "RaidBench/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise EmailDeliveryError(f"Email provider rejected the request ({error.code}).") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise EmailDeliveryError("Email provider did not return a usable response.") from error

        response_data = result.get("data") if isinstance(result, dict) else None
        message_id = str(response_data.get("email_id") or "") if isinstance(response_data, dict) else ""
        if not message_id:
            raise EmailDeliveryError("Email provider response did not include a message id.")
        return message_id


def email_delivery_from_environment(*, public_base_url: str, support_email: str):
    provider = os.environ.get("RAIDBENCH_EMAIL_PROVIDER", "").strip().lower()
    if provider == "smtp2go" or (not provider and os.environ.get("SMTP2GO_API_KEY", "").strip()):
        return Smtp2GoEmailDelivery.from_environment(
            public_base_url=public_base_url,
            support_email=support_email,
        )
    if provider in {"", "resend"}:
        return ResendEmailDelivery.from_environment(
            public_base_url=public_base_url,
            support_email=support_email,
        )
    raise ValueError(f"Unsupported RAIDBENCH_EMAIL_PROVIDER: {provider}")
