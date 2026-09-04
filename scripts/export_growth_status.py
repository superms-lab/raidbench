#!/usr/bin/env python3
"""Export private RaidBench growth minimum progress for the owner dashboard."""

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
  parser = argparse.ArgumentParser(description="Export RaidBench growth minimum progress.")
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
  day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
  hour_start = now.replace(minute=0, second=0, microsecond=0)
  quotas = read_json(args.quota, {})
  public_guide_targets = quotas.get("publicGuides", {})
  weekly_guides = public_guide_targets.get("weeklyMinimum", {})
  registry = read_json(Path(__file__).resolve().parents[1] / "content" / "game-registry.json", {})
  games = registry.get("games", []) if isinstance(registry, dict) else []
  aliases: dict[str, str] = {}
  game_pages: dict[str, dict[str, Any]] = {}
  for game in games:
    if not isinstance(game, dict):
      continue
    game_id = str(game.get("id") or "")
    name = str(game.get("name") or "")
    short_name = str(game.get("shortName") or name)
    if not game_id or not short_name:
      continue
    aliases[name] = game_id
    aliases[short_name] = game_id
    target = int(weekly_guides.get(name, weekly_guides.get(short_name, 0)))
    game_pages[game_id] = {
      "label": short_name,
      "actual": 0,
      "target": target,
      "deficit": target,
    }

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
  hourly_published = 0
  daily_published = 0
  for game, published_at in rows:
    published_value = str(published_at)
    if in_window(published_value, hour_start, hour_start + timedelta(hours=1)):
      hourly_published += 1
    if in_window(published_value, day_start, day_start + timedelta(days=1)):
      daily_published += 1
    game_id = aliases.get(str(game))
    if game_id and in_window(published_value, start, end):
      game_pages[game_id]["actual"] += 1

  for progress in game_pages.values():
    progress["deficit"] = max(0, int(progress["target"]) - int(progress["actual"]))

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
      "hourlyPages": {"actual": hourly_published, "target": int(public_guide_targets.get("hourlyMinimum", 1))},
      "dailyPages": {"actual": daily_published, "target": int(public_guide_targets.get("dailyMinimum", 24))},
      "weeklyAssets": {"actual": assets_this_week, "target": int(quotas.get("weeklyAssets", {}).get("calculatorPresetsComparisonsOrDownloads", 3))},
      "patchRefreshes": {"actual": patch_checks, "target": int(quotas.get("weeklyAssets", {}).get("patchSensitiveRefreshes", 3))},
      "partnerContacts": {"actual": partner_contacts, "target": int(quotas.get("partnerships", {}).get("contactsPerWeek", 6))},
      "repliesToday": {"actual": replies_today, "target": int(quotas.get("community", {}).get("linkFreeRepliesPerDay", 6))},
    },
    "gamePages": game_pages,
    "profilePostStatus": profile_status,
  }
  print(json.dumps(result, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
