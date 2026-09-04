#!/usr/bin/env python3
"""Send one daily RaidBench growth brief through Feishu, with optional legacy email delivery."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from send_feishu_draft_notification import (
  NotificationError,
  generate_signature,
  send_card,
  validate_reddit_thread_url,
)


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def local_day() -> str:
  return datetime.now(timezone.utc).astimezone(LOCAL_TIMEZONE).date().isoformat()


def read_json(path: Path, default: Any) -> Any:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError:
    return default
  except json.JSONDecodeError as exc:
    raise NotificationError(f"Invalid JSON in {path}: {exc}") from exc


def load_pending_drafts(directories: list[Path]) -> list[dict[str, Any]]:
  drafts: dict[str, dict[str, Any]] = {}
  for directory in directories:
    if not directory.is_dir():
      continue
    for path in sorted(directory.glob("*.json")):
      value = read_json(path, {})
      if not isinstance(value, dict):
        continue
      draft_id = str(value.get("draft_id") or "").strip()
      status = str(value.get("status") or "")
      if not draft_id or status in {"published", "replied", "cancelled", "rejected"}:
        continue
      draft_type = str(value.get("draft_type") or "reply")
      target_url = str(value.get("target_reddit_url") or value.get("target_url") or "")
      if draft_type == "reply":
        validate_reddit_thread_url(target_url)
      if not target_url.startswith("https://www.reddit.com/"):
        raise NotificationError(f"Draft {draft_id} requires an HTTPS Reddit destination")
      value["_path"] = str(path)
      existing = drafts.get(draft_id)
      if existing and str(existing.get("updated_at") or existing.get("created_at") or "") > str(
        value.get("updated_at") or value.get("created_at") or ""
      ):
        continue
      drafts[draft_id] = value
  newest_first = sorted(
    drafts.values(),
    key=lambda item: (str(item.get("created_at") or ""), str(item["draft_id"])),
    reverse=True,
  )
  return sorted(
    newest_first,
    key=lambda item: str(item.get("draft_type") or "reply") != "reply",
  )


def select_unnotified_drafts(
  drafts: list[dict[str, Any]],
  state: dict[str, Any],
  *,
  limit: int = 3,
) -> list[dict[str, Any]]:
  notified = {
    str(draft_id)
    for draft_id in state.get("notified_draft_ids", [])
    if str(draft_id).strip()
  }
  previous = str(state.get("last_selected_draft") or "").strip()
  if previous:
    notified.add(previous)
  today = local_day()
  selected: list[dict[str, Any]] = []
  for draft in drafts:
    if str(draft["draft_id"]) in notified:
      continue
    created_at = str(draft.get("created_at") or "").strip()
    try:
      created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
      if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    except ValueError:
      continue
    if created.astimezone(LOCAL_TIMEZONE).date().isoformat() == today:
      selected.append(draft)
      if len(selected) >= max(1, limit):
        break
  return selected


def select_unnotified_draft(drafts: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any] | None:
  selected = select_unnotified_drafts(drafts, state, limit=1)
  return selected[0] if selected else None


def refresh_traffic_dashboard(path: Path) -> None:
  key = (
    os.environ.get("RAIDBENCH_ANALYTICS_READ_KEY", "").strip()
    or os.environ.get("RAIDBENCH_EDGE_ORIGIN_KEY", "").strip()
  )
  if not key:
    raise NotificationError("Traffic summary key is not configured")
  endpoint = os.environ.get(
    "RAIDBENCH_ANALYTICS_SUMMARY_URL",
    "https://raidbench.com/api/analytics/summary",
  ).strip()
  parsed = urlparse(endpoint)
  if parsed.scheme != "https" or parsed.hostname not in {"raidbench.com", "www.raidbench.com"}:
    raise NotificationError("Traffic summary URL must use the RaidBench HTTPS origin")
  request = Request(
    endpoint,
    headers={
      "Accept": "application/json",
      "User-Agent": "RaidBench daily growth digest",
      "X-RaidBench-Analytics-Key": key,
    },
  )
  try:
    with urlopen(request, timeout=20) as response:
      value = json.loads(response.read().decode("utf-8"))
  except HTTPError as exc:
    raise NotificationError(f"Traffic summary endpoint rejected the request ({exc.code})") from exc
  except (URLError, TimeoutError, json.JSONDecodeError) as exc:
    raise NotificationError("Traffic summary endpoint did not return usable data") from exc
  if not isinstance(value, dict) or not isinstance(value.get("metrics"), dict):
    raise NotificationError("Traffic summary response is missing metrics")
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(path.suffix + ".tmp")
  temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temporary.replace(path)


def traffic_card_elements(traffic: dict[str, Any] | None, error: str = "") -> list[dict[str, Any]]:
  if not traffic:
    note = "今日流量暂时无法读取。" + (f" 原因：{error}" if error else "")
    return [
      {"tag": "hr"},
      {"tag": "div", "text": {"tag": "lark_md", "content": f"**网站流量**\n{note}"}},
    ]
  metrics = traffic.get("metrics") if isinstance(traffic.get("metrics"), dict) else {}
  funnel = traffic.get("funnel") if isinstance(traffic.get("funnel"), dict) else {}
  daily = traffic.get("daily") if isinstance(traffic.get("daily"), list) else []
  yesterday_day = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
  yesterday = int(metrics.get("yesterday") or next(
    (int(item.get("views") or 0) for item in daily if isinstance(item, dict) and item.get("day") == yesterday_day),
    0,
  ))
  top_pages = [item for item in traffic.get("topPages", []) if isinstance(item, dict)][:3]
  page_summary = " · ".join(f"`{item.get('path', '/')}` {int(item.get('views') or 0)}" for item in top_pages) or "暂无"
  content = (
    "**网站流量（Cloudflare 第一方统计）**\n"
    f"今日 **{int(metrics.get('today') or 0)}** · 昨日 **{yesterday}** · "
    f"近 7 日 **{int(metrics.get('last7Days') or 0)}** · 近 30 日 **{int(metrics.get('last30Days') or 0)}**\n"
    f"近 30 日转化：进入账户 **{int(funnel.get('accountEntries') or 0)}** · "
    f"发起结账 **{int(funnel.get('checkoutStarts') or 0)}** · 支付成功 **{int(funnel.get('paymentSuccesses') or 0)}**\n"
    f"热门页面：{page_summary}"
  )
  return [
    {"tag": "hr"},
    {"tag": "div", "text": {"tag": "lark_md", "content": content}},
  ]


def build_digest_card(
  drafts: list[dict[str, Any]],
  *,
  traffic: dict[str, Any] | None = None,
  traffic_error: str = "",
  signed_at: int | None = None,
  secret: str = "",
) -> dict[str, Any]:
  if drafts:
    title = f"RaidBench 每日增长简报 · {len(drafts)} 条待处理"
    color = "blue" if all(str(draft.get("draft_type") or "reply") == "reply" for draft in drafts) else "orange"
    elements = [{
      "tag": "div",
      "text": {"tag": "lark_md", "content": f"<at id=all></at> 今天准备了 **{len(drafts)} 条** Reddit 内容，逐条核对原帖后发布。"},
    }]
    for index, draft in enumerate(drafts, start=1):
      draft_type = str(draft.get("draft_type") or "reply")
      action_label = f"打开第 {index} 条原帖" if draft_type == "reply" else "打开 Reddit 发帖页"
      action_url = str(draft.get("target_reddit_url") or draft.get("target_url"))
      intent = str(draft.get("intent_zh") or "请先阅读原帖，确认英文内容与对方问题一致。")
      if draft_type == "reply":
        content = (
          f"**{index}. [{draft.get('game', '')}] {draft.get('target_title', '')}**\n"
          f"**用户意图：** {intent}\n\n"
          "**建议英文回复（无链接、无销售话术）：**\n"
          f"{draft.get('draft_text', '')}"
        )
      else:
        content = (
          f"**{index}. Reddit 个人主页引流帖：{draft.get('post_title', '')}**\n"
          f"**目的：** {intent}\n\n"
          "**正文：**\n"
          f"{draft.get('draft_text', '')}\n\n"
          "这类带站点链接的发布内容保留人工审核。"
        )
      elements.extend([
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md", "content": content}},
        {
          "tag": "action",
          "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": action_label},
            "type": "primary",
            "url": action_url,
          }],
        },
      ])
    elements.append({
      "tag": "note",
      "elements": [{
        "tag": "plain_text",
        "content": f"草稿 {', '.join(str(draft['draft_id']) for draft in drafts)} · 发布后请在站长获客箱标记为已回复。",
      }],
    })
  else:
    title = "RaidBench 每日增长简报 · 系统在线"
    color = "green"
    elements = [{
      "tag": "div",
      "text": {
        "tag": "lark_md",
        "content": "<at id=all></at> 今日没有可安全发布的 Reddit 草稿。系统仍在运行，没有为了凑数量而发送低质量或违规内容。",
      },
    }]

  elements[1:1] = traffic_card_elements(traffic, traffic_error)

  payload: dict[str, Any] = {
    "msg_type": "interactive",
    "card": {
      "config": {"wide_screen_mode": True},
      "header": {
        "template": color,
        "title": {"tag": "plain_text", "content": title},
      },
      "elements": elements,
    },
  }
  if secret:
    timestamp = int(signed_at if signed_at is not None else datetime.now().timestamp())
    payload["timestamp"] = str(timestamp)
    payload["sign"] = generate_signature(timestamp, secret)
  return payload


def build_digest_email(drafts: list[dict[str, Any]]) -> tuple[str, str]:
  if not drafts:
    return (
      "RaidBench daily acquisition brief: system online",
      "There is no safe community draft waiting today. The acquisition system is still running and did not create filler content.",
    )

  subject = f"RaidBench: {len(drafts)} 条 Reddit 内容待发布"
  sections: list[str] = []
  for index, draft in enumerate(drafts, start=1):
    draft_type = str(draft.get("draft_type") or "reply")
    target_url = str(draft.get("target_reddit_url") or draft.get("target_url") or "")
    intent = str(draft.get("intent_zh") or "请先阅读原帖，确认英文内容与对方问题一致。")
    label = "纯回答" if draft_type == "reply" else "个人主页引流帖"
    sections.append(
      f"{index}. {label}\n"
      f"标题：{draft.get('target_title') or draft.get('post_title', '')}\n"
      f"链接：{target_url}\n"
      f"用户意图：{intent}\n\n"
      f"建议英文内容：\n{draft.get('draft_text', '')}\n\n"
      f"草稿编号：{draft.get('draft_id', '')}"
    )
  body = "今天的 Reddit 待处理内容\n\n" + "\n\n--------------------\n\n".join(sections)
  body += "\n\n发布后请在 RaidBench 站长获客箱标记为已回复。"
  return subject, body


def send_email_digest(drafts: list[dict[str, Any]]) -> dict[str, str]:
  recipient = (
    os.environ.get("RAIDBENCH_ACQUISITION_EMAIL_TO", "").strip()
    or os.environ.get("RAIDBENCH_SUPPORT_EMAIL", "").strip()
  )
  sender = os.environ.get("RAIDBENCH_EMAIL_FROM", "").strip()
  provider = os.environ.get("RAIDBENCH_EMAIL_PROVIDER", "").strip().lower()
  if not recipient or not sender:
    return {"status": "not_configured"}

  subject, body = build_digest_email(drafts)
  if provider == "smtp2go":
    api_key = os.environ.get("SMTP2GO_API_KEY", "").strip()
    api_url = os.environ.get("SMTP2GO_API_URL", "https://api.smtp2go.com/v3/email/send").strip()
    if not api_key:
      return {"status": "not_configured"}
    payload = {
      "sender": sender,
      "to": [recipient],
      "subject": subject,
      "text_body": body,
      "custom_headers": [{"header": "Reply-To", "value": recipient}],
    }
    headers = {
      "X-Smtp2go-Api-Key": api_key,
      "Accept": "application/json",
      "Content-Type": "application/json",
      "User-Agent": "RaidBench/1.0",
    }
  elif provider in {"", "resend"}:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    api_url = os.environ.get("RESEND_API_URL", "https://api.resend.com/emails").strip()
    if not api_key:
      return {"status": "not_configured"}
    payload = {
      "from": sender,
      "to": [recipient],
      "reply_to": recipient,
      "subject": subject,
      "text": body,
    }
    headers = {
      "Authorization": f"Bearer {api_key}",
      "Content-Type": "application/json",
      "User-Agent": "RaidBench/1.0",
    }
  else:
    return {"status": "unsupported_provider", "provider": provider}

  request = Request(
    api_url,
    data=json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8"),
    headers=headers,
    method="POST",
  )
  try:
    with urlopen(request, timeout=10) as response:
      result = json.loads(response.read().decode("utf-8"))
  except HTTPError as exc:
    raise NotificationError(f"Acquisition email provider rejected the request ({exc.code})") from exc
  except (URLError, TimeoutError, json.JSONDecodeError) as exc:
    raise NotificationError("Acquisition email provider did not return a usable response") from exc

  if provider == "smtp2go":
    data = result.get("data") if isinstance(result, dict) else None
    message_id = str(data.get("email_id") or "") if isinstance(data, dict) else ""
  else:
    message_id = str(result.get("id") or "") if isinstance(result, dict) else ""
  if not message_id:
    raise NotificationError("Acquisition email provider response did not include a message id")
  return {"status": "provider_accepted_delivery_unverified", "message_id": message_id}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Send the daily RaidBench acquisition brief.")
  parser.add_argument("--draft-dir", type=Path, action="append", required=True)
  parser.add_argument("--state", type=Path, required=True)
  parser.add_argument("--traffic-dashboard", type=Path)
  parser.add_argument("--refresh-traffic", action="store_true")
  parser.add_argument("--limit", type=int, default=6)
  parser.add_argument("--feishu-only", action="store_true")
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument("--force", action="store_true")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    state = read_json(args.state, {})
    today = local_day()
    if not args.force and state.get("last_attempt_day") == today:
      print(json.dumps({"status": "already_attempted_today", "day": today}))
      return 0
    traffic: dict[str, Any] | None = None
    traffic_error = ""
    if args.traffic_dashboard:
      try:
        if args.refresh_traffic:
          refresh_traffic_dashboard(args.traffic_dashboard)
        value = read_json(args.traffic_dashboard, {})
        if isinstance(value, dict) and isinstance(value.get("metrics"), dict):
          traffic = value
        else:
          traffic_error = "流量文件缺少 metrics 数据"
      except (NotificationError, OSError) as exc:
        traffic_error = str(exc)
    drafts = load_pending_drafts(args.draft_dir)
    digest_drafts = select_unnotified_drafts(drafts, state, limit=max(1, min(12, args.limit)))
    secret = os.environ.get("RAIDBENCH_FEISHU_WEBHOOK_SECRET", "").strip()
    payload = build_digest_card(digest_drafts, traffic=traffic, traffic_error=traffic_error, secret=secret)
    selected_ids = [str(draft["draft_id"]) for draft in digest_drafts]
    selected = selected_ids[-1] if selected_ids else ""
    if args.dry_run:
      print(json.dumps({
        "status": "dry_run_passed",
        "selected": selected_ids,
        "pending": len(drafts),
        "signed": bool(secret),
        "traffic_today": int((traffic or {}).get("metrics", {}).get("today") or 0),
        "traffic_error": traffic_error,
      }))
      return 0

    webhook = os.environ.get("RAIDBENCH_FEISHU_WEBHOOK_URL", "").strip()
    webhook_result: dict[str, Any] = {"status": "not_configured"}
    webhook_error = ""
    if webhook:
      try:
        webhook_result = send_card(webhook, payload)
      except NotificationError as exc:
        webhook_error = str(exc)

    if args.feishu_only:
      email_result = {"status": "disabled"}
    else:
      try:
        email_result = send_email_digest(digest_drafts)
      except NotificationError as exc:
        email_result = {"status": "failed", "error": str(exc)}

    webhook_accepted = not webhook_error and webhook_result.get("status") != "not_configured"
    email_accepted = email_result.get("status") == "provider_accepted_delivery_unverified"
    if not webhook_accepted and not email_accepted:
      detail = webhook_error or str(email_result.get("error") or "No notification channel is configured")
      raise NotificationError(detail)

    delivery_status = (
      "webhook_and_email_accepted_delivery_unverified"
      if webhook_accepted and email_accepted
      else "webhook_accepted_delivery_unverified"
      if webhook_accepted
      else "email_accepted_delivery_unverified"
    )
    args.state.parent.mkdir(parents=True, exist_ok=True)
    notified_ids = [
      str(draft_id)
      for draft_id in state.get("notified_draft_ids", [])
      if str(draft_id).strip()
    ]
    for selected_id in selected_ids:
      if selected_id not in notified_ids:
        notified_ids.append(selected_id)
    state.update({
      "last_attempt_day": today,
      "last_attempt_at": utc_now(),
      "last_selected_draft": selected,
      "notified_draft_ids": notified_ids[-100:],
      "last_webhook_result": webhook_result,
      "last_webhook_error": webhook_error,
      "last_email_result": email_result,
      "last_traffic_generated_at": str((traffic or {}).get("generatedAt") or ""),
      "last_traffic_today": int((traffic or {}).get("metrics", {}).get("today") or 0),
      "last_traffic_error": traffic_error,
      "delivery_status": delivery_status,
    })
    args.state.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
      "status": delivery_status,
      "selected": selected_ids,
      "pending": len(drafts),
      "traffic_today": int((traffic or {}).get("metrics", {}).get("today") or 0),
      "traffic_error": traffic_error,
    }))
    return 0
  except NotificationError as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
