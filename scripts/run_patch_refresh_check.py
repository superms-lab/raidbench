#!/usr/bin/env python3
"""Revalidate one rotating patch-sensitive page against its authoritative source."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RefreshError(RuntimeError):
  """Raised when a patch-sensitive refresh cannot be verified."""


def utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError:
    return default
  except json.JSONDecodeError as exc:
    raise RefreshError(f"Invalid JSON in {path}: {exc}") from exc


def write_json_atomic(path: Path, value: Any) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(f"{path.suffix}.tmp")
  temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temporary.replace(path)


def fetch_text(url: str) -> tuple[int, str]:
  request = urllib.request.Request(
    url,
    headers={"User-Agent": "RaidBench patch refresh checker; support@raidbench.com"},
  )
  try:
    with urllib.request.urlopen(request, timeout=20) as response:
      body = response.read(600_000).decode("utf-8", "replace")
      return int(response.status), body
  except (urllib.error.URLError, TimeoutError) as exc:
    raise RefreshError(f"Patch source request failed: {url}") from exc


def normalized_hash(html: str) -> str:
  text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
  text = re.sub(r"<[^>]+>", " ", text)
  text = re.sub(r"\s+", " ", text).strip()
  return hashlib.sha256(text.encode("utf-8")).hexdigest()


def choose_entry(entries: list[dict[str, str]], now: datetime) -> dict[str, str]:
  if not entries:
    raise RefreshError("Patch refresh registry is empty")
  iso_year, iso_week, iso_weekday = now.isocalendar()
  slot_by_weekday = {1: 0, 3: 1, 5: 2}
  slot = slot_by_weekday.get(iso_weekday, (iso_weekday - 1) % 3)
  index = ((iso_year * 53 + iso_week) * 3 + slot) % len(entries)
  return entries[index]


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Revalidate one RaidBench patch-sensitive page.")
  parser.add_argument("--registry", type=Path, required=True)
  parser.add_argument("--database", type=Path, required=True)
  parser.add_argument("--state", type=Path, required=True)
  parser.add_argument("--page-base", default="https://raidbench.com/pages/")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    now = datetime.now(timezone.utc)
    entries = read_json(args.registry, [])
    if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
      raise RefreshError("Patch refresh registry must be a JSON array")
    entry = choose_entry(entries, now)
    for field in ("game", "slug", "sourceUrl"):
      if not isinstance(entry.get(field), str) or not entry[field].strip():
        raise RefreshError(f"Patch refresh entry requires {field}")
    source_status, source_html = fetch_text(entry["sourceUrl"])
    page_url = f"{args.page_base.rstrip('/')}/{entry['slug']}"
    page_status, page_html = fetch_text(page_url)
    canonical = f'<link rel="canonical" href="{page_url}"'
    if source_status != 200 or page_status != 200 or canonical not in page_html:
      raise RefreshError("Patch source or public page did not pass the refresh gate")

    state = read_json(args.state, {})
    if not isinstance(state, dict):
      raise RefreshError("Patch refresh state must be a JSON object")
    records = state.get("records") if isinstance(state.get("records"), dict) else {}
    source_hash = normalized_hash(source_html)
    previous_hash = str(records.get(entry["slug"], {}).get("sourceHash") or "")
    status = "baseline_recorded" if not previous_hash else "revalidated_unchanged" if previous_hash == source_hash else "source_changed_review_required"
    checked_at = utc_now()
    records[entry["slug"]] = {
      "game": entry["game"],
      "sourceUrl": entry["sourceUrl"],
      "sourceHash": source_hash,
      "checkedAt": checked_at,
      "status": status,
    }
    history = state.get("history") if isinstance(state.get("history"), list) else []
    history.append({"slug": entry["slug"], "game": entry["game"], "checkedAt": checked_at, "status": status})
    state.update({"records": records, "history": history[-100:], "lastCheck": history[-1]})
    write_json_atomic(args.state, state)

    connection = sqlite3.connect(args.database)
    try:
      connection.execute(
        "UPDATE guide_pages SET last_checked_at = ?, status = CASE WHEN ? = 'source_changed_review_required' THEN 'refresh_required' ELSE status END WHERE slug = ?",
        (checked_at, status, entry["slug"]),
      )
      connection.commit()
    finally:
      connection.close()
    print(json.dumps({"status": status, "slug": entry["slug"], "game": entry["game"], "checkedAt": checked_at}))
    return 0
  except (RefreshError, OSError, sqlite3.Error) as exc:
    print(f"ERROR: {exc}")
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
