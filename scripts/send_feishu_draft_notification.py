#!/usr/bin/env python3
"""Send a signed Feishu card for one RaidBench manual-post draft."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ALLOWED_WEBHOOK_HOSTS = {"open.feishu.cn", "open.larksuite.com"}
LINK_PATTERN = re.compile(r"https?://|www\.|raidbench(?:\.com)?", re.IGNORECASE)


class NotificationError(RuntimeError):
  """Raised when a draft or Feishu response fails validation."""


def read_draft(path: Path) -> dict[str, Any]:
  try:
    value = json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError as exc:
    raise NotificationError(f"Draft does not exist: {path}") from exc
  except json.JSONDecodeError as exc:
    raise NotificationError(f"Draft is not valid JSON: {exc}") from exc
  if not isinstance(value, dict):
    raise NotificationError("Draft must be a JSON object")
  for key in ("draft_id", "game", "guide_title", "guide_url", "target_title", "target_reddit_url", "draft_text", "source_url"):
    if not isinstance(value.get(key), str) or not value[key].strip():
      raise NotificationError(f"Draft requires a non-empty {key}")
  if LINK_PATTERN.search(value["draft_text"]):
    raise NotificationError("Manual-post draft must remain link-free and must not promote RaidBench")
  for key in ("guide_url", "source_url"):
    url = urllib.parse.urlparse(value[key])
    if url.scheme != "https" or not url.hostname:
      raise NotificationError(f"Draft {key} must be an HTTPS URL")
  validate_reddit_thread_url(value["target_reddit_url"])
  return value


def validate_webhook_url(value: str) -> str:
  parsed = urllib.parse.urlparse(value)
  if parsed.scheme != "https" or parsed.hostname not in ALLOWED_WEBHOOK_HOSTS:
    raise NotificationError("Feishu webhook must use an official Feishu or Lark HTTPS host")
  if not parsed.path.startswith("/open-apis/bot/v2/hook/"):
    raise NotificationError("Feishu webhook path is not a v2 custom-bot hook")
  return value


def validate_reddit_thread_url(value: str) -> str:
  parsed = urllib.parse.urlparse(value)
  hostname = (parsed.hostname or "").lower()
  if (
    parsed.scheme != "https"
    or hostname not in {"reddit.com", "www.reddit.com", "old.reddit.com"}
    or re.match(r"^/r/[^/]+/comments/[a-z0-9]+(?:/|$)", parsed.path, re.IGNORECASE) is None
  ):
    raise NotificationError("Draft requires an exact Reddit thread URL")
  return value


def generate_signature(timestamp: int, secret: str) -> str:
  string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
  digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
  return base64.b64encode(digest).decode("utf-8")


def build_card(draft: dict[str, Any], *, timestamp: int | None = None, secret: str = "") -> dict[str, Any]:
  title = f"Reddit 回复待审核 · {draft['game']}"
  content = (
    f"草稿编号：{draft['draft_id']}\n"
    f"Reddit 原帖：{draft['target_title']}\n\n"
    "建议英文回复：\n"
    f"{draft['draft_text']}\n\n"
    "请先核对原帖语境和社区规则，再打开原帖、复制上述回复并由你手动点击发布。\n"
    "当前建议：每天最多 1 条，至少间隔 24 小时。"
  )
  actions = [
    {
      "tag": "button",
      "text": {"tag": "plain_text", "content": "打开 Reddit 原帖"},
      "type": "primary",
      "url": draft["target_reddit_url"],
    },
  ]
  payload: dict[str, Any] = {
    "msg_type": "interactive",
    "card": {
      "config": {"wide_screen_mode": True},
      "header": {
        "template": "blue",
        "title": {"tag": "plain_text", "content": title},
      },
      "elements": [
        {"tag": "div", "text": {"tag": "plain_text", "content": content}},
        {"tag": "hr"},
        {
          "tag": "note",
          "elements": [
            {
              "tag": "plain_text",
              "content": "RaidBench 网站内容仍全自动；这张卡片只用于 Reddit 人工审核，不会替你发布。",
            }
          ],
        },
        {"tag": "action", "actions": actions},
      ],
    },
  }
  if secret:
    signed_at = int(timestamp if timestamp is not None else time.time())
    payload["timestamp"] = str(signed_at)
    payload["sign"] = generate_signature(signed_at, secret)
  return payload


def send_card(webhook_url: str, payload: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
  request = urllib.request.Request(
    validate_webhook_url(webhook_url),
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "RaidBench draft notifier"},
    method="POST",
  )
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      body = response.read().decode("utf-8", "replace")
  except (urllib.error.URLError, TimeoutError) as exc:
    raise NotificationError(f"Feishu request failed: {exc}") from exc
  try:
    result = json.loads(body)
  except json.JSONDecodeError as exc:
    raise NotificationError("Feishu returned a non-JSON response") from exc
  code = result.get("code", result.get("StatusCode"))
  if code != 0:
    message = result.get("msg", result.get("StatusMessage", "unknown error"))
    raise NotificationError(f"Feishu rejected the notification: code={code}, message={message}")
  return result


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Send one RaidBench manual-post draft to Feishu.")
  parser.add_argument("--draft", type=Path, required=True)
  parser.add_argument("--dry-run", action="store_true")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    draft = read_draft(args.draft)
    secret = os.environ.get("RAIDBENCH_FEISHU_WEBHOOK_SECRET", "").strip()
    payload = build_card(draft, secret=secret)
    if args.dry_run:
      print(json.dumps({"status": "dry_run_passed", "draft_id": draft["draft_id"], "signed": bool(secret)}))
      return 0
    webhook_url = os.environ.get("RAIDBENCH_FEISHU_WEBHOOK_URL", "").strip()
    if not webhook_url:
      print(json.dumps({"status": "awaiting_configuration", "draft_id": draft["draft_id"]}))
      return 3
    send_card(webhook_url, payload)
    print(json.dumps({"status": "notified", "draft_id": draft["draft_id"]}))
    return 0
  except NotificationError as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
