#!/usr/bin/env python3
"""Export private RaidBench growth quota progress for the owner dashboard."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
TERMINAL_DRAFT_STATUSES = {"published", "replied", "cancelled", "rejected"}


def read_json(path: Path, default: Any) -> Any:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except (FileNotFoundError, json.JSONDecodeError):
    return default


def parse_datetime(value: str) -> datetime | None:
  try:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
  except (AttributeError, ValueError):
    return None
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
  return parsed.astimezone(LOCAL_TIMEZONE)


def current_week_bounds(now: datetime) -> tuple[datetime, datetime]:
  start_date = (now - timedelta(days=now.weekday())).date()
  start = datetime.combine(start_date, time.min, tzinfo=LOCAL_TIMEZONE)
  return start, start + timedelta(days=7)


def in_window(value: str, start: datetime, end: datetime) -> bool:
  parsed = parse_datetime(value)
  return bool(parsed and start <= parsed < end)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Export RaidBench growth quota progress.")
  parser.add_argument("--database", type=Path, required=True)
  parser.add_argument("--quota", type=Path, required=True)
  parser.add_argument("--draft-dir", type=Path, required=True)
  parser.add_argument("--partner-state", type=Path, required=True)
  parser.add_argument("--asset-source", type=Path, required=True)
  parser.add_argument("--patch-state", type=Path, required=True)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  now = datetime.now(LOCAL_TIMEZONE)
  start, end = current_week_bounds(now)
  quotas = read_json(args.quota, {})
  weekly_guides = quotas.get("publicGuides", {}).get("weekly", {})

  connection = sqlite3.connect(args.database)
  rows = connection.execute(
    """
    SELECT signal.game, item.published_at
    FROM content_automation_items item
    JOIN content_signals signal ON signal.id = item.signal_id
    WHERE item.status = 'published'
    """
  ).fetchall()
  connection.close()
  published = {"Rust": 0, "POE2": 0}
  for game, published_at in rows:
    if game in published and in_window(str(published_at), start, end):
      published[game] += 1

  replies_today = 0
  profile_status = "missing"
  if args.draft_dir.is_dir():
    for path in args.draft_dir.glob("*.json"):
      draft = read_json(path, {})
      if not isinstance(draft, dict):
        continue
      draft_type = str(draft.get("draft_type") or "reply")
      status = str(draft.get("status") or "")
      if draft_type == "reply" and status not in TERMINAL_DRAFT_STATUSES:
        created = parse_datetime(str(draft.get("created_at") or ""))
        if created and created.date() == now.date():
          replies_today += 1
      if draft_type == "profile_post":
        profile_status = status or "unknown"

  presets = read_json(args.asset_source, [])
  assets_this_week = sum(
    1 for item in presets
    if isinstance(item, dict)
    and start.date().isoformat() <= str(item.get("availableFrom") or "") < end.date().isoformat()
    and str(item.get("availableFrom") or "") <= now.date().isoformat()
  )

  patch_state = read_json(args.patch_state, {})
  patch_checks = sum(
    1 for item in patch_state.get("history", [])
    if isinstance(item, dict) and in_window(str(item.get("checkedAt") or ""), start, end)
  )
  iso_year, iso_week, _ = now.isocalendar()
  current_week = f"{iso_year}-W{iso_week:02d}"
  partner_state = read_json(args.partner_state, {})
  partner_contacts = int(partner_state.get("weekly", {}).get(current_week, 0))

  result = {
    "generatedAt": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
    "week": current_week,
    "weekStart": start.date().isoformat(),
    "metrics": {
      "rustPages": {"actual": published["Rust"], "target": int(weekly_guides.get("Rust", 9))},
      "poe2Pages": {"actual": published["POE2"], "target": int(weekly_guides.get("POE2", 3))},
      "weeklyAssets": {"actual": assets_this_week, "target": int(quotas.get("weeklyAssets", {}).get("calculatorPresetsComparisonsOrDownloads", 3))},
      "patchRefreshes": {"actual": patch_checks, "target": int(quotas.get("weeklyAssets", {}).get("patchSensitiveRefreshes", 3))},
      "partnerContacts": {"actual": partner_contacts, "target": int(quotas.get("partnerships", {}).get("contactsPerWeek", 6))},
      "repliesToday": {"actual": replies_today, "target": int(quotas.get("community", {}).get("linkFreeRepliesPerDay", 3))},
    },
    "profilePostStatus": profile_status,
  }
  print(json.dumps(result, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
