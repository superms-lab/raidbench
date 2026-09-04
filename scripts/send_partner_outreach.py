#!/usr/bin/env python3
"""Send an explicitly approved, idempotent RaidBench partner-outreach queue."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OutreachError(RuntimeError):
  """Raised when an outreach queue or provider response is unsafe."""


def utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError:
    return default
  except json.JSONDecodeError as exc:
    raise OutreachError(f"Invalid JSON in {path}: {exc}") from exc


def write_json_atomic(path: Path, value: Any) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(f"{path.suffix}.tmp")
  temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temporary.replace(path)


def validate_queue(value: Any) -> dict[str, Any]:
  if not isinstance(value, dict) or not str(value.get("campaign_id") or "").strip():
    raise OutreachError("Outreach queue requires a campaign_id")
  messages = value.get("messages")
  if not isinstance(messages, list) or not messages or len(messages) > 5:
    raise OutreachError("Outreach queue requires 1-5 messages")
  seen_ids: set[str] = set()
  for message in messages:
    if not isinstance(message, dict):
      raise OutreachError("Each outreach message must be an object")
    for key in ("message_id", "recipient", "subject", "source_url", "text_body"):
      if not isinstance(message.get(key), str) or not message[key].strip():
        raise OutreachError(f"Outreach message requires {key}")
    message_id = message["message_id"].strip()
    if message_id in seen_ids:
      raise OutreachError(f"Duplicate outreach message id: {message_id}")
    seen_ids.add(message_id)
    recipient = message["recipient"].strip()
    if "@" not in recipient or any(character in recipient for character in "\r\n,;"):
      raise OutreachError(f"Unsafe outreach recipient: {recipient}")
    source = urlparse(message["source_url"])
    if source.scheme != "https" or not source.hostname:
      raise OutreachError("Outreach source must be an HTTPS URL")
    if len(message["subject"]) > 180 or len(message["text_body"]) > 12000:
      raise OutreachError(f"Outreach message is too large: {message_id}")
  return value


def send_smtp2go(message: dict[str, str], *, sender: str, reply_to: str, api_key: str) -> str:
  api_url = os.environ.get("SMTP2GO_API_URL", "https://api.smtp2go.com/v3/email/send").strip()
  payload = {
    "sender": sender,
    "to": [message["recipient"]],
    "subject": message["subject"],
    "text_body": message["text_body"],
    "custom_headers": [
      {"header": "Reply-To", "value": reply_to},
      {"header": "X-RaidBench-Outreach-ID", "value": message["message_id"]},
    ],
  }
  request = Request(
    api_url,
    data=json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
    headers={
      "X-Smtp2go-Api-Key": api_key,
      "Accept": "application/json",
      "Content-Type": "application/json",
      "User-Agent": "RaidBench partner outreach/1.0",
    },
    method="POST",
  )
  try:
    with urlopen(request, timeout=15) as response:
      result = json.loads(response.read().decode("utf-8"))
  except HTTPError as exc:
    raise OutreachError(f"SMTP2GO rejected outreach ({exc.code})") from exc
  except (URLError, TimeoutError, json.JSONDecodeError) as exc:
    raise OutreachError("SMTP2GO did not return a usable outreach response") from exc
  data = result.get("data") if isinstance(result, dict) else None
  provider_id = str(data.get("email_id") or "") if isinstance(data, dict) else ""
  if not provider_id:
    raise OutreachError("SMTP2GO outreach response did not include an email id")
  return provider_id


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Send one approved RaidBench partner-outreach queue.")
  parser.add_argument("--queue", type=Path, required=True)
  parser.add_argument("--state", type=Path, required=True)
  parser.add_argument("--send", action="store_true")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    queue = validate_queue(read_json(args.queue, {}))
    state = read_json(args.state, {})
    if not isinstance(state, dict):
      raise OutreachError("Outreach state must be a JSON object")
    sent = state.get("sent") if isinstance(state.get("sent"), dict) else {}
    pending = [message for message in queue["messages"] if message["message_id"] not in sent]
    if not args.send:
      print(json.dumps({
        "status": "dry_run_passed",
        "campaign_id": queue["campaign_id"],
        "pending": [message["message_id"] for message in pending],
      }))
      return 0

    provider = os.environ.get("RAIDBENCH_EMAIL_PROVIDER", "").strip().lower()
    sender = os.environ.get("RAIDBENCH_EMAIL_FROM", "").strip()
    reply_to = str(queue.get("reply_to") or os.environ.get("RAIDBENCH_SUPPORT_EMAIL", "")).strip()
    api_key = os.environ.get("SMTP2GO_API_KEY", "").strip()
    if provider != "smtp2go" or not sender or not reply_to or not api_key:
      raise OutreachError("Approved outreach requires the configured SMTP2GO sender and reply-to address")

    results: list[dict[str, str]] = []
    for message in pending:
      provider_id = send_smtp2go(message, sender=sender, reply_to=reply_to, api_key=api_key)
      sent[message["message_id"]] = {
        "recipient": message["recipient"],
        "subject": message["subject"],
        "provider_message_id": provider_id,
        "sent_at": utc_now(),
        "delivery_status": "provider_accepted_delivery_unverified",
      }
      state.update({"campaign_id": queue["campaign_id"], "sent": sent, "updated_at": utc_now()})
      write_json_atomic(args.state, state)
      results.append({
        "message_id": message["message_id"],
        "provider_message_id": provider_id,
        "status": "provider_accepted_delivery_unverified",
      })
    print(json.dumps({"status": "completed", "campaign_id": queue["campaign_id"], "results": results}))
    return 0
  except (OutreachError, OSError) as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
