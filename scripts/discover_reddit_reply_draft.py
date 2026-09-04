#!/usr/bin/env python3
"""Find one fresh Rust Reddit question and save a private, link-free reply draft."""

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
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "reddit-community-discovery.schema.json"
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
REDDIT_THREAD_PATH = re.compile(
  r"^/r/playrust/comments/(?P<thread_id>[a-z0-9]+)(?:/[^/?#]+)?/?$",
  re.IGNORECASE,
)
LINK_PATTERN = re.compile(r"https?://|www\.|raidbench(?:\.com)?", re.IGNORECASE)
PROMOTION_PATTERN = re.compile(
  r"\b(?:buy|subscribe|sign up|visit my|check out my|click here|dm me|message me)\b",
  re.IGNORECASE,
)
CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")


class DiscoveryError(RuntimeError):
  """Raised when discovery output is missing, stale, duplicated, or unsafe."""


def utc_now() -> datetime:
  return datetime.now(timezone.utc).replace(microsecond=0)


def local_day(now: datetime | None = None) -> str:
  return (now or utc_now()).astimezone(LOCAL_TIMEZONE).date().isoformat()


def isoformat(value: datetime) -> str:
  return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError:
    return default
  except json.JSONDecodeError as exc:
    raise DiscoveryError(f"Invalid JSON in {path}: {exc}") from exc


def write_json_atomic(path: Path, value: Any) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(f"{path.suffix}.tmp")
  temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temporary.replace(path)


def short_hash(value: str, length: int = 18) -> str:
  return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def canonical_reddit_url(value: str) -> str:
  parsed = urlparse(value.strip())
  hostname = (parsed.hostname or "").lower()
  match = REDDIT_THREAD_PATH.match(parsed.path)
  if parsed.scheme != "https" or hostname not in {"reddit.com", "www.reddit.com", "old.reddit.com"} or not match:
    raise DiscoveryError("Candidate must use an exact HTTPS r/playrust thread URL")
  path_parts = [part for part in parsed.path.split("/") if part]
  canonical_path = f"/r/playrust/comments/{match.group('thread_id').lower()}/"
  if len(path_parts) >= 5:
    canonical_path += f"{path_parts[4].lower()}/"
  return urlunparse(("https", "www.reddit.com", canonical_path, "", "", ""))


def reddit_thread_id(value: str) -> str:
  match = REDDIT_THREAD_PATH.match(urlparse(canonical_reddit_url(value)).path)
  if not match:
    raise DiscoveryError("Candidate Reddit URL does not contain a thread id")
  return match.group("thread_id").lower()


def parse_published_at(value: str) -> datetime:
  raw = value.strip()
  if not raw:
    raise DiscoveryError("Candidate requires a verified publication date")
  try:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
      parsed = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    else:
      parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
  except ValueError as exc:
    raise DiscoveryError("Candidate publication date is not ISO 8601") from exc
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
  return parsed.astimezone(timezone.utc)


def load_seen_thread_ids(directories: list[Path], state: dict[str, Any]) -> set[str]:
  seen: set[str] = set()
  for value in state.get("seen_reddit_urls", []):
    try:
      seen.add(reddit_thread_id(str(value)))
    except DiscoveryError:
      continue
  for directory in directories:
    if not directory.is_dir():
      continue
    for path in directory.glob("*.json"):
      draft = read_json(path, {})
      if not isinstance(draft, dict):
        continue
      target = str(draft.get("target_reddit_url") or draft.get("target_url") or "")
      if not target:
        continue
      try:
        seen.add(reddit_thread_id(target))
      except DiscoveryError:
        continue
  return seen


def build_prompt(now: datetime, seen_thread_ids: set[str]) -> str:
  exclusions = ", ".join(sorted(seen_thread_ids)[-100:]) or "none"
  search_after = (now - timedelta(days=7)).date().isoformat()
  return f"""You are preparing one private community reply draft for the owner of RaidBench.

Current UTC time: {isoformat(now)}

Use live web search to find exactly one genuinely recent public thread in r/playrust. The thread must:
- have been published within the last 7 days (search after {search_after});
- be an exact Reddit thread, not a search page, profile, listing, comment permalink, or deleted post;
- contain a clear beginner, base design, upkeep, progression, or raiding question that can receive a useful self-contained answer;
- not request cheats, exploits, bug abuse, account trading, harassment, or rule evasion;
- have a title and publication date you can verify from current search evidence.

Do not use the Reddit Data API, do not scrape in bulk, do not log in, and do not post anything. You may use a focused `site:reddit.com/r/playrust/comments` query or open the public r/playrust new page through web search. Use no more than four focused web-search/open operations. Exclude these previously seen Reddit thread IDs: {exclusions}.

For the selected question, write an original English reply of 90-190 words. Answer the user's actual problem on Reddit. Keep patch-sensitive claims conditional, avoid unverified exact resource counts, and do not include a link, brand name, sales language, invitation to message, or promise of results. Write `intent_zh` as a concise professional Chinese summary for the owner. Put a short factual audit note in `verification_note`; it is private and will not be posted.

If any freshness, URL, title, or relevance requirement cannot be verified, return status `none` and empty strings for every other field. Otherwise return status `candidate`, the canonical exact Reddit URL, the exact title, and an ISO 8601 publication date. Return only data matching the supplied JSON schema."""


def run_codex(prompt: str, *, model: str, reasoning_effort: str, timeout_seconds: int) -> dict[str, Any]:
  if not SCHEMA_PATH.is_file():
    raise DiscoveryError(f"Missing output schema: {SCHEMA_PATH}")
  with tempfile.TemporaryDirectory(prefix="raidbench-community-scout-") as temporary:
    result_path = Path(temporary) / "result.json"
    command = [
      "codex",
      "--search",
      "exec",
      "--ephemeral",
      "--skip-git-repo-check",
      "--ignore-user-config",
      "-m",
      model,
      "-c",
      f'model_reasoning_effort="{reasoning_effort}"',
      "-s",
      "read-only",
      "-C",
      str(ROOT),
      "--output-schema",
      str(SCHEMA_PATH),
      "-o",
      str(result_path),
      prompt,
    ]
    try:
      result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
      )
    except subprocess.TimeoutExpired as exc:
      raise DiscoveryError("Codex community search timed out") from exc
    if result.returncode != 0:
      detail = (result.stderr or result.stdout).strip()[-1600:]
      raise DiscoveryError(f"Codex community search failed: {detail}")
    value = read_json(result_path, {})
    if not isinstance(value, dict):
      raise DiscoveryError("Codex community search did not return a JSON object")
    return value


def validate_candidate(
  value: dict[str, Any],
  *,
  now: datetime,
  seen_thread_ids: set[str],
) -> dict[str, str] | None:
  if value.get("status") == "none":
    return None
  if value.get("status") != "candidate":
    raise DiscoveryError("Codex community search returned an unknown status")

  target_url = canonical_reddit_url(str(value.get("target_reddit_url") or ""))
  thread_id = reddit_thread_id(target_url)
  if thread_id in seen_thread_ids:
    raise DiscoveryError(f"Codex selected an already-seen Reddit thread: {thread_id}")

  published_at = parse_published_at(str(value.get("published_at") or ""))
  if published_at > now + timedelta(hours=2):
    raise DiscoveryError("Candidate publication date is in the future")
  if now - published_at > timedelta(days=8):
    raise DiscoveryError("Candidate is too old for the daily community queue")

  title = str(value.get("target_title") or "").strip()
  intent_zh = str(value.get("intent_zh") or "").strip()
  draft_text = re.sub(r"\s+", " ", str(value.get("draft_text") or "")).strip()
  verification_note = str(value.get("verification_note") or "").strip()
  if not 8 <= len(title) <= 240:
    raise DiscoveryError("Candidate title length is invalid")
  if len(intent_zh) < 12 or not CJK_PATTERN.search(intent_zh):
    raise DiscoveryError("Candidate requires a useful Chinese owner summary")
  word_count = len(draft_text.split())
  if not 70 <= word_count <= 220:
    raise DiscoveryError(f"Candidate reply must contain 70-220 words, got {word_count}")
  if CJK_PATTERN.search(draft_text):
    raise DiscoveryError("Candidate Reddit reply must be English")
  if LINK_PATTERN.search(draft_text) or PROMOTION_PATTERN.search(draft_text):
    raise DiscoveryError("Candidate Reddit reply contains a link, brand, or promotional call to action")
  if len(verification_note) < 12:
    raise DiscoveryError("Candidate requires a private verification note")

  return {
    "thread_id": thread_id,
    "target_title": title,
    "target_reddit_url": target_url,
    "published_at": isoformat(published_at),
    "intent_zh": intent_zh,
    "draft_text": draft_text,
    "verification_note": verification_note,
  }


def materialize_draft(candidate: dict[str, str], *, now: datetime) -> dict[str, Any]:
  compact_day = local_day(now).replace("-", "")
  thread_id = candidate["thread_id"]
  return {
    "draft_id": f"reply_rust_{thread_id}_{compact_day}",
    "draft_type": "reply",
    "case_id": f"reddit_rust_{thread_id}_{compact_day}",
    "game": "Rust",
    "guide_slug": "rust-beginner-raid-path",
    "guide_title": "Best Early-Game Raid Paths",
    "guide_url": "https://raidbench.com/pages/rust-beginner-raid-path",
    "source_url": candidate["target_reddit_url"],
    "target_platform": "reddit",
    "target_title": candidate["target_title"],
    "target_reddit_url": candidate["target_reddit_url"],
    "published_at": candidate["published_at"],
    "intent_zh": candidate["intent_zh"],
    "draft_text": candidate["draft_text"],
    "verification_note": candidate["verification_note"],
    "discovery_source": "codex_live_web_search",
    "contains_link": False,
    "manual_publish_required": True,
    "status": "ready_for_reddit_reply",
    "created_at": isoformat(now),
    "updated_at": isoformat(now),
  }


def classify_demand_topic(candidate: dict[str, str]) -> tuple[str, int, int]:
  text = f"{candidate['target_title']} {candidate['intent_zh']}".lower()
  if re.search(r"raid|rocket|c4|satchel|sulfur|boom|breach", text):
    return "raid_cost", 5, 5
  if re.search(r"upkeep|decay|tool cupboard|\btc\b", text):
    return "upkeep", 5, 4
  if re.search(r"base|build|honeycomb|bunker|door|wall", text):
    return "base_design", 4, 4
  return "progression", 4, 3


def register_community_demand(database: Path, candidate: dict[str, str], *, now: datetime) -> str:
  if not database.is_file():
    raise DiscoveryError(f"Community demand database does not exist: {database}")
  thread_id = candidate["thread_id"]
  run_id = f"community_{thread_id}_{now.strftime('%Y%m%dT%H%M%S')}"
  source_id = "rust-community-web-search"
  snapshot_id = f"snap_{short_hash(run_id)}"
  signal_id = f"sig_{short_hash(f'community:{thread_id}')}"
  topic, pain_score, commercial_score = classify_demand_topic(candidate)
  timestamp = isoformat(now)
  evidence = json.dumps({
    "sourceType": "community-web-search",
    "publishedAt": candidate["published_at"],
    "excerpt": f"Player question: {candidate['target_title']}. Owner intent summary: {candidate['intent_zh']}",
    "demandOnly": True,
  }, ensure_ascii=False)
  connection = sqlite3.connect(database)
  try:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
      """
      INSERT OR IGNORE INTO content_sources (id, game, source_type, url, cadence, active, notes)
      VALUES (?, 'Rust', 'community-web-search', 'https://www.reddit.com/r/playrust/', '8h', 1,
        'Focused public web-search demand signals; no Reddit Data API or bulk collection.')
      """,
      (source_id,),
    )
    connection.execute(
      """
      INSERT OR IGNORE INTO agent_runs (id, run_type, status, started_at, finished_at, summary_json)
      VALUES (?, 'community_demand', 'completed', ?, ?, ?)
      """,
      (run_id, timestamp, timestamp, json.dumps({"signals": 1, "game": "Rust"})),
    )
    connection.execute(
      """
      INSERT OR IGNORE INTO source_snapshots (
        id, run_id, source_id, fetched_at, ok, status_code, title, body_sample, error, content_hash
      ) VALUES (?, ?, ?, ?, 1, 200, ?, ?, '', ?)
      """,
      (
        snapshot_id,
        run_id,
        source_id,
        timestamp,
        candidate["target_title"],
        candidate["intent_zh"],
        short_hash(candidate["target_reddit_url"], 40),
      ),
    )
    connection.execute(
      """
      INSERT OR IGNORE INTO content_signals (
        id, run_id, source_id, game, topic, signal_title, signal_url,
        pain_score, commercial_score, patch_sensitive, evidence_json, created_at
      ) VALUES (?, ?, ?, 'Rust', ?, ?, ?, ?, ?, 1, ?, ?)
      """,
      (
        signal_id,
        run_id,
        source_id,
        topic,
        candidate["target_title"],
        candidate["target_reddit_url"],
        pain_score,
        commercial_score,
        evidence,
        timestamp,
      ),
    )
    connection.commit()
  finally:
    connection.close()
  return signal_id


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Discover one fresh r/playrust question for owner review.")
  parser.add_argument("--draft-dir", type=Path, action="append", default=[])
  parser.add_argument("--output-dir", type=Path, required=True)
  parser.add_argument("--state", type=Path, required=True)
  parser.add_argument("--database", type=Path)
  parser.add_argument("--daily-limit", type=int, default=int(os.environ.get("RAIDBENCH_COMMUNITY_DRAFTS_PER_DAY", "3")))
  parser.add_argument("--force", action="store_true")
  parser.add_argument("--dry-run", action="store_true")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    now = utc_now()
    today = local_day(now)
    state = read_json(args.state, {})
    if not isinstance(state, dict):
      raise DiscoveryError("Community discovery state must be a JSON object")
    attempts_by_day = state.get("attempts_by_day") if isinstance(state.get("attempts_by_day"), dict) else {}
    attempts_today = int(attempts_by_day.get(today, 0))
    daily_limit = max(1, min(3, int(args.daily_limit)))
    if not args.force and attempts_today >= daily_limit:
      print(json.dumps({"status": "daily_limit_reached", "day": today, "attempts": attempts_today}))
      return 0

    draft_directories = [*args.draft_dir, args.output_dir]
    seen_thread_ids = load_seen_thread_ids(draft_directories, state)
    model = os.environ.get("RAIDBENCH_COMMUNITY_SCOUT_MODEL", "gpt-5.6-sol").strip()
    reasoning_effort = os.environ.get("RAIDBENCH_COMMUNITY_SCOUT_REASONING", "low").strip()
    timeout_seconds = int(os.environ.get("RAIDBENCH_COMMUNITY_SCOUT_TIMEOUT_SECONDS", "900"))
    raw = run_codex(
      build_prompt(now, seen_thread_ids),
      model=model,
      reasoning_effort=reasoning_effort,
      timeout_seconds=timeout_seconds,
    )
    candidate = validate_candidate(raw, now=now, seen_thread_ids=seen_thread_ids)

    result_status = "no_verified_candidate"
    draft_id = ""
    target_url = ""
    signal_id = ""
    if candidate:
      draft = materialize_draft(candidate, now=now)
      draft_id = str(draft["draft_id"])
      target_url = str(draft["target_reddit_url"])
      if not args.dry_run:
        write_json_atomic(args.output_dir / f"{draft_id}.json", draft)
        if args.database:
          signal_id = register_community_demand(args.database, candidate, now=now)
      result_status = "dry_run_candidate" if args.dry_run else "draft_created"

    seen_urls = [str(value) for value in state.get("seen_reddit_urls", []) if str(value).strip()]
    if target_url and target_url not in seen_urls:
      seen_urls.append(target_url)
    attempts_by_day[today] = attempts_today + 1
    recent_attempts = dict(sorted(attempts_by_day.items())[-14:])
    state.update({
      "last_completed_day": today,
      "last_completed_at": isoformat(now),
      "last_status": result_status,
      "last_draft_id": draft_id,
      "last_target_url": target_url,
      "last_signal_id": signal_id,
      "attempts_by_day": recent_attempts,
      "seen_reddit_urls": seen_urls[-200:],
      "model": model,
      "reasoning_effort": reasoning_effort,
    })
    if not args.dry_run:
      write_json_atomic(args.state, state)
    print(json.dumps({
      "status": result_status,
      "draft_id": draft_id,
      "target_url": target_url,
      "signal_id": signal_id,
      "attempts_today": attempts_today + 1,
      "daily_limit": daily_limit,
      "seen_threads": len(seen_thread_ids),
    }))
    return 0
  except (DiscoveryError, OSError, ValueError) as exc:
    print(f"ERROR: {exc}", file=os.sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
