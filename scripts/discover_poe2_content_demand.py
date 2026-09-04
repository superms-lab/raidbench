#!/usr/bin/env python3
"""Discover one current POE2 player problem for the owned-site content queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "community-content-demand.schema.json"
THREAD_PATH = re.compile(r"^/r/pathofexile2/comments/(?P<id>[a-z0-9]+)(?:/[^/?#]+)?/?$", re.IGNORECASE)
TOPICS = {"build_help", "boss_help", "loot_value", "currency_route", "progression", "patch"}


class DemandError(RuntimeError):
  """Raised when a POE2 demand signal cannot be verified."""


def utc_now() -> datetime:
  return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime) -> str:
  return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError:
    return default
  except json.JSONDecodeError as exc:
    raise DemandError(f"Invalid JSON in {path}: {exc}") from exc


def write_json_atomic(path: Path, value: Any) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(f"{path.suffix}.tmp")
  temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temporary.replace(path)


def canonical_url(value: str) -> str:
  parsed = urlparse(value.strip())
  match = THREAD_PATH.match(parsed.path)
  if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"reddit.com", "www.reddit.com", "old.reddit.com"} or not match:
    raise DemandError("POE2 demand requires an exact r/PathOfExile2 thread URL")
  parts = [part for part in parsed.path.split("/") if part]
  path = f"/r/PathOfExile2/comments/{match.group('id').lower()}/"
  if len(parts) >= 5:
    path += f"{parts[4].lower()}/"
  return urlunparse(("https", "www.reddit.com", path, "", "", ""))


def thread_id(value: str) -> str:
  match = THREAD_PATH.match(urlparse(canonical_url(value)).path)
  if not match:
    raise DemandError("POE2 demand URL has no thread id")
  return match.group("id").lower()


def parse_date(value: str) -> datetime:
  try:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
  except ValueError as exc:
    raise DemandError("POE2 demand publication date is invalid") from exc
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
  return parsed.astimezone(timezone.utc)


def prompt(now: datetime, seen: set[str]) -> str:
  after = (now - timedelta(days=7)).date().isoformat()
  return f"""Use live web search to find exactly one public r/PathOfExile2 thread published after {after} where a player asks a clear current question about a build, boss, item value, currency route, progression, or patch impact. This is demand research for an owned website, not a Reddit reply.

Do not use the Reddit Data API, scrape listings in bulk, log in, contact anyone, or post. Verify the exact thread URL, title, and ISO publication date. Exclude these thread IDs: {', '.join(sorted(seen)[-150:]) or 'none'}.

Classify the question as one of build_help, boss_help, loot_value, currency_route, progression, or patch. Write a concise professional Chinese intent summary. If any field cannot be verified, return status `none` and empty strings for all other fields. Return only JSON matching the supplied schema."""


def run_codex(value: str) -> dict[str, Any]:
  with tempfile.TemporaryDirectory(prefix="raidbench-poe2-demand-") as temporary:
    output = Path(temporary) / "result.json"
    command = [
      "codex", "--search", "exec", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
      "-m", os.environ.get("RAIDBENCH_POE2_DEMAND_MODEL", "gpt-5.6-sol"),
      "-c", f'model_reasoning_effort="{os.environ.get("RAIDBENCH_POE2_DEMAND_REASONING", "low")}"',
      "-s", "read-only", "-C", str(ROOT), "--output-schema", str(SCHEMA), "-o", str(output), value,
    ]
    try:
      result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=900, check=False)
    except subprocess.TimeoutExpired as exc:
      raise DemandError("POE2 demand search timed out") from exc
    if result.returncode != 0:
      raise DemandError(f"POE2 demand search failed: {(result.stderr or result.stdout)[-1200:]}")
    data = read_json(output, {})
    if not isinstance(data, dict):
      raise DemandError("POE2 demand search returned invalid output")
    return data


def validate(value: dict[str, Any], now: datetime, seen: set[str]) -> dict[str, str] | None:
  if value.get("status") == "none":
    return None
  if value.get("status") != "candidate":
    raise DemandError("POE2 demand returned an unknown status")
  url = canonical_url(str(value.get("target_url") or ""))
  identifier = thread_id(url)
  published = parse_date(str(value.get("published_at") or ""))
  topic = str(value.get("topic") or "")
  title = str(value.get("target_title") or "").strip()
  intent = str(value.get("intent_zh") or "").strip()
  if identifier in seen or now - published > timedelta(days=8) or published > now + timedelta(hours=2):
    raise DemandError("POE2 demand is duplicated or stale")
  if topic not in TOPICS or len(title) < 8 or len(intent) < 12 or not re.search(r"[\u3400-\u9fff]", intent):
    raise DemandError("POE2 demand fields are incomplete")
  return {"thread_id": identifier, "target_title": title, "target_url": url, "published_at": iso(published), "intent_zh": intent, "topic": topic}


def register(database: Path, candidate: dict[str, str], now: datetime) -> str:
  identifier = candidate["thread_id"]
  digest = hashlib.sha256(f"poe2:{identifier}".encode()).hexdigest()[:18]
  run_id = f"poe2_community_{identifier}_{now.strftime('%Y%m%dT%H%M%S')}"
  signal_id = f"sig_{digest}"
  source_id = "poe2-community-web-search"
  timestamp = iso(now)
  connection = sqlite3.connect(database)
  try:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("INSERT OR IGNORE INTO content_sources (id,game,source_type,url,cadence,active,notes) VALUES (?,'POE2','community-web-search','https://www.reddit.com/r/PathOfExile2/','24h',1,'Focused public demand search; no Reddit API or posting.')", (source_id,))
    connection.execute("INSERT OR IGNORE INTO agent_runs (id,run_type,status,started_at,finished_at,summary_json) VALUES (?,'community_demand','completed',?,?,'{\"signals\":1,\"game\":\"POE2\"}')", (run_id, timestamp, timestamp))
    connection.execute("INSERT OR IGNORE INTO source_snapshots (id,run_id,source_id,fetched_at,ok,status_code,title,body_sample,content_hash) VALUES (?,?,?, ?,1,200,?,?,?)", (f"snap_{digest}", run_id, source_id, timestamp, candidate["target_title"], candidate["intent_zh"], digest))
    evidence = json.dumps({"sourceType": "community-web-search", "publishedAt": candidate["published_at"], "excerpt": f"Player question: {candidate['target_title']}. Owner intent summary: {candidate['intent_zh']}", "demandOnly": True}, ensure_ascii=False)
    connection.execute("INSERT OR IGNORE INTO content_signals (id,run_id,source_id,game,topic,signal_title,signal_url,pain_score,commercial_score,patch_sensitive,evidence_json,created_at) VALUES (?,?,?,'POE2',?,?,?,4,4,1,?,?)", (signal_id, run_id, source_id, candidate["topic"], candidate["target_title"], candidate["target_url"], evidence, timestamp))
    connection.commit()
  finally:
    connection.close()
  return signal_id


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Discover one current POE2 content-demand signal.")
  parser.add_argument("--database", type=Path, required=True)
  parser.add_argument("--state", type=Path, required=True)
  parser.add_argument("--force", action="store_true")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    now = utc_now()
    day = now.date().isoformat()
    state = read_json(args.state, {})
    if not isinstance(state, dict):
      raise DemandError("POE2 demand state must be an object")
    if not args.force and state.get("lastAttemptDay") == day:
      print(json.dumps({"status": "already_attempted_today", "day": day}))
      return 0
    seen = {str(value) for value in state.get("seenThreadIds", []) if str(value)}
    candidate = validate(run_codex(prompt(now, seen)), now, seen)
    signal_id = ""
    status = "no_verified_candidate"
    if candidate:
      signal_id = register(args.database, candidate, now)
      seen.add(candidate["thread_id"])
      status = "signal_created"
    state.update({"lastAttemptDay": day, "lastAttemptAt": iso(now), "lastStatus": status, "lastSignalId": signal_id, "seenThreadIds": sorted(seen)[-200:]})
    write_json_atomic(args.state, state)
    print(json.dumps({"status": status, "signal_id": signal_id}))
    return 0
  except (DemandError, OSError, sqlite3.Error) as exc:
    print(f"ERROR: {exc}")
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
