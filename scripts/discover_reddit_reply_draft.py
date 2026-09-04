#!/usr/bin/env python3
"""Find one fresh multi-game Reddit question and save a private, link-free reply draft."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
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
GAME_REGISTRY_PATH = ROOT / "content" / "game-registry.json"
SOURCE_REGISTRY_PATH = ROOT / "content" / "source-registry.json"
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
REDDIT_THREAD_PATH = re.compile(
  r"^/r/(?P<community>[^/]+)/comments/(?P<thread_id>[a-z0-9]+)(?:/(?P<slug>[^/?#]+))?/?$",
  re.IGNORECASE,
)
LINK_PATTERN = re.compile(r"https?://|www\.|raidbench(?:\.com)?", re.IGNORECASE)
PROMOTION_PATTERN = re.compile(
  r"\b(?:subscribe|sign up|visit my|check out my|click here|dm me|message me)\b",
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


def load_game_profiles() -> list[dict[str, Any]]:
  game_registry = read_json(GAME_REGISTRY_PATH, {})
  source_registry = read_json(SOURCE_REGISTRY_PATH, {})
  games = game_registry.get("games", []) if isinstance(game_registry, dict) else []
  sources = source_registry.get("sources", []) if isinstance(source_registry, dict) else []
  demand_sources = {
    str(source.get("gameId") or ""): source
    for source in sources
    if isinstance(source, dict)
    and source.get("role") == "demand"
    and source.get("sourceType") == "community-web-search"
  }
  profiles: list[dict[str, Any]] = []
  for game in games:
    if not isinstance(game, dict):
      continue
    game_id = str(game.get("id") or "")
    source = demand_sources.get(game_id)
    communities = [
      str(value).strip()
      for value in (source or {}).get("redditCommunities", [])
      if str(value).strip()
    ]
    if not game_id or source is None or not communities:
      continue
    profiles.append({
      "id": game_id,
      "name": str(game.get("name") or game_id),
      "short_name": str(game.get("shortName") or game.get("name") or game_id),
      "hub_path": str(game.get("hubPath") or f"/games/{game_id}/"),
      "source_id": str(source.get("id") or f"{game_id}-community-demand"),
      "community_url": str(source.get("url") or f"https://www.reddit.com/r/{communities[0]}/"),
      "communities": communities,
      "topics": [str(value) for value in source.get("topics", []) if str(value).strip()],
      "query_terms": [str(value) for value in source.get("queryTerms", []) if str(value).strip()],
    })
  if len(profiles) != 12:
    raise DiscoveryError(f"Expected 12 Reddit game profiles, found {len(profiles)}")
  return profiles


def select_game_profile(
  state: dict[str, Any],
  profiles: list[dict[str, Any]],
  attempted_today: set[str],
  *,
  randomizer: random.Random | random.SystemRandom | None = None,
) -> tuple[dict[str, Any], list[str]] | None:
  by_id = {str(profile["id"]): profile for profile in profiles}
  queue = [
    str(game_id)
    for game_id in state.get("game_rotation_queue", [])
    if str(game_id) in by_id and str(game_id) not in attempted_today
  ]
  if not queue:
    queue = [game_id for game_id in by_id if game_id not in attempted_today]
    (randomizer or random.SystemRandom()).shuffle(queue)
  if not queue:
    return None
  selected_id = queue.pop(0)
  return by_id[selected_id], queue


def canonical_reddit_url(value: str, allowed_communities: list[str] | None = None) -> str:
  parsed = urlparse(value.strip())
  hostname = (parsed.hostname or "").lower()
  match = REDDIT_THREAD_PATH.match(parsed.path)
  if parsed.scheme != "https" or hostname not in {"reddit.com", "www.reddit.com", "old.reddit.com"} or not match:
    raise DiscoveryError("Candidate must use an exact HTTPS Reddit thread URL")
  community = match.group("community")
  if allowed_communities:
    allowed = {value.lower(): value for value in allowed_communities}
    if community.lower() not in allowed:
      raise DiscoveryError(f"Candidate subreddit r/{community} is outside the selected game profile")
    community = allowed[community.lower()]
  canonical_path = f"/r/{community}/comments/{match.group('thread_id').lower()}/"
  if match.group("slug"):
    canonical_path += f"{match.group('slug').lower()}/"
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


def count_daily_drafts(directories: list[Path], day: str) -> int:
  draft_ids: set[str] = set()
  for directory in directories:
    if not directory.is_dir():
      continue
    for path in directory.glob("*.json"):
      draft = read_json(path, {})
      if not isinstance(draft, dict) or str(draft.get("draft_type") or "reply") != "reply":
        continue
      created_at = str(draft.get("created_at") or "")
      try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if created.tzinfo is None:
          created = created.replace(tzinfo=timezone.utc)
      except ValueError:
        continue
      if created.astimezone(LOCAL_TIMEZONE).date().isoformat() == day:
        draft_ids.add(str(draft.get("draft_id") or path.name))
  return len(draft_ids)


def build_prompt(now: datetime, seen_thread_ids: set[str], profile: dict[str, Any]) -> str:
  exclusions = ", ".join(sorted(seen_thread_ids)[-100:]) or "none"
  search_after = (now - timedelta(days=7)).date().isoformat()
  communities = ", ".join(f"r/{value}" for value in profile["communities"])
  topics = ", ".join(str(value).replace("_", " ") for value in profile["topics"])
  query_terms = ", ".join(str(value) for value in profile["query_terms"])
  return f"""You are preparing one private community reply draft for the owner of RaidBench.

Current UTC time: {isoformat(now)}
Selected game: {profile['name']}
Allowed Reddit communities: {communities}

Use live web search to find exactly one genuinely recent public thread in one of the allowed communities. The thread must:
- have been published within the last 7 days (search after {search_after});
- be an exact Reddit thread, not a search page, profile, listing, comment permalink, or deleted post;
- contain a clear {profile['name']} gameplay question that can receive a useful self-contained answer;
- preferably concern one of these lanes: {topics};
- not request cheats, exploits, bug abuse, account trading, harassment, or rule evasion;
- have a title and publication date you can verify from current search evidence.

Do not use the Reddit Data API, do not scrape in bulk, do not log in, and do not post anything. Use a focused `site:reddit.com/r/<community>/comments` query with terms such as {query_terms}. Use no more than four focused web-search/open operations. Exclude these previously seen Reddit thread IDs: {exclusions}.

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
  profile: dict[str, Any],
) -> dict[str, str] | None:
  if value.get("status") == "none":
    return None
  if value.get("status") != "candidate":
    raise DiscoveryError("Codex community search returned an unknown status")

  target_url = canonical_reddit_url(
    str(value.get("target_reddit_url") or ""),
    [str(community) for community in profile["communities"]],
  )
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
    "subreddit": REDDIT_THREAD_PATH.match(urlparse(target_url).path).group("community"),
  }


def materialize_draft(
  candidate: dict[str, str],
  profile: dict[str, Any],
  *,
  now: datetime,
) -> dict[str, Any]:
  compact_day = local_day(now).replace("-", "")
  thread_id = candidate["thread_id"]
  game_id = str(profile["id"])
  return {
    "draft_id": f"reply_{game_id}_{thread_id}_{compact_day}",
    "draft_type": "reply",
    "case_id": f"reddit_{game_id}_{thread_id}_{compact_day}",
    "game": str(profile["short_name"]),
    "game_id": game_id,
    "subreddit": candidate["subreddit"],
    "guide_slug": f"{game_id}-guide-library",
    "guide_title": f"{profile['name']} Guides and Decision Tools",
    "guide_url": f"https://raidbench.com{profile['hub_path']}",
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


def classify_demand_topic(candidate: dict[str, str], profile: dict[str, Any]) -> tuple[str, int, int]:
  text = f"{candidate['target_title']} {candidate['intent_zh']}".lower()
  topics = [str(value) for value in profile.get("topics", []) if str(value).strip()]
  for topic in topics:
    terms = [term for term in topic.replace("_", " ").split() if len(term) >= 4]
    if any(term in text for term in terms):
      return topic, 5, 4
  fallback = next((topic for topic in topics if topic != "patch"), "progression")
  return fallback, 4, 3


def register_community_demand(
  database: Path,
  candidate: dict[str, str],
  profile: dict[str, Any],
  *,
  now: datetime,
) -> str:
  if not database.is_file():
    raise DiscoveryError(f"Community demand database does not exist: {database}")
  thread_id = candidate["thread_id"]
  game_id = str(profile["id"])
  game_name = str(profile["short_name"])
  run_id = f"community_{game_id}_{thread_id}_{now.strftime('%Y%m%dT%H%M%S')}"
  source_id = str(profile["source_id"])
  snapshot_id = f"snap_{short_hash(run_id)}"
  signal_id = f"sig_{short_hash(f'community:{game_id}:{thread_id}')}"
  topic, pain_score, commercial_score = classify_demand_topic(candidate, profile)
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
      VALUES (?, ?, 'community-web-search', ?, '24h', 1,
        'Focused public web-search demand signals; no Reddit Data API, bulk collection, or automatic posting.')
      """,
      (source_id, game_name, str(profile["community_url"])),
    )
    connection.execute(
      """
      INSERT OR IGNORE INTO agent_runs (id, run_type, status, started_at, finished_at, summary_json)
      VALUES (?, 'community_demand', 'completed', ?, ?, ?)
      """,
      (run_id, timestamp, timestamp, json.dumps({"signals": 1, "game": game_name, "gameId": game_id})),
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
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
      """,
      (
        signal_id,
        run_id,
        source_id,
        game_name,
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
  parser = argparse.ArgumentParser(description="Discover one fresh multi-game Reddit question for owner review.")
  parser.add_argument("--draft-dir", type=Path, action="append", default=[])
  parser.add_argument("--output-dir", type=Path, required=True)
  parser.add_argument("--state", type=Path, required=True)
  parser.add_argument("--database", type=Path)
  parser.add_argument(
    "--daily-target",
    "--daily-limit",
    dest="daily_target",
    type=int,
    default=int(os.environ.get("RAIDBENCH_COMMUNITY_DRAFTS_PER_DAY", "6")),
  )
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
    profiles = load_game_profiles()
    draft_directories = [*args.draft_dir, args.output_dir]
    drafts_today = count_daily_drafts(draft_directories, today)
    attempts_by_day = state.get("attempts_by_day") if isinstance(state.get("attempts_by_day"), dict) else {}
    attempts_today = int(attempts_by_day.get(today, 0))
    daily_target = max(1, min(len(profiles), int(args.daily_target)))
    if not args.force and drafts_today >= daily_target:
      print(json.dumps({"status": "daily_target_reached", "day": today, "drafts": drafts_today}))
      return 0
    games_by_day = state.get("games_attempted_by_day") if isinstance(state.get("games_attempted_by_day"), dict) else {}
    attempted_today = {
      str(game_id)
      for game_id in games_by_day.get(today, [])
      if str(game_id).strip()
    }
    if attempts_today and not attempted_today:
      attempted_today.add("rust")
    selection = select_game_profile(state, profiles, set() if args.force else attempted_today)
    if selection is None:
      print(json.dumps({"status": "all_games_attempted_today", "day": today, "attempts": attempts_today}))
      return 0
    profile, remaining_rotation = selection

    seen_thread_ids = load_seen_thread_ids(draft_directories, state)
    model = os.environ.get("RAIDBENCH_COMMUNITY_SCOUT_MODEL", "gpt-5.6-sol").strip()
    reasoning_effort = os.environ.get("RAIDBENCH_COMMUNITY_SCOUT_REASONING", "low").strip()
    timeout_seconds = int(os.environ.get("RAIDBENCH_COMMUNITY_SCOUT_TIMEOUT_SECONDS", "900"))
    raw = run_codex(
      build_prompt(now, seen_thread_ids, profile),
      model=model,
      reasoning_effort=reasoning_effort,
      timeout_seconds=timeout_seconds,
    )
    candidate = validate_candidate(raw, now=now, seen_thread_ids=seen_thread_ids, profile=profile)

    result_status = "no_verified_candidate"
    draft_id = ""
    target_url = ""
    signal_id = ""
    if candidate:
      draft = materialize_draft(candidate, profile, now=now)
      draft_id = str(draft["draft_id"])
      target_url = str(draft["target_reddit_url"])
      if not args.dry_run:
        write_json_atomic(args.output_dir / f"{draft_id}.json", draft)
        if args.database:
          signal_id = register_community_demand(args.database, candidate, profile, now=now)
      result_status = "dry_run_candidate" if args.dry_run else "draft_created"

    seen_urls = [str(value) for value in state.get("seen_reddit_urls", []) if str(value).strip()]
    if target_url and target_url not in seen_urls:
      seen_urls.append(target_url)
    attempts_by_day[today] = attempts_today + 1
    recent_attempts = dict(sorted(attempts_by_day.items())[-14:])
    drafts_by_day = state.get("drafts_by_day") if isinstance(state.get("drafts_by_day"), dict) else {}
    drafts_by_day[today] = drafts_today + int(candidate is not None)
    recent_drafts = dict(sorted(drafts_by_day.items())[-14:])
    attempted_today.add(str(profile["id"]))
    games_by_day[today] = sorted(attempted_today)
    recent_games = dict(sorted(games_by_day.items())[-14:])
    state.update({
      "last_completed_day": today,
      "last_completed_at": isoformat(now),
      "last_status": result_status,
      "last_draft_id": draft_id,
      "last_target_url": target_url,
      "last_signal_id": signal_id,
      "last_game_id": str(profile["id"]),
      "last_game": str(profile["short_name"]),
      "attempts_by_day": recent_attempts,
      "drafts_by_day": recent_drafts,
      "games_attempted_by_day": recent_games,
      "game_rotation_queue": remaining_rotation,
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
      "game_id": str(profile["id"]),
      "game": str(profile["short_name"]),
      "attempts_today": attempts_today + 1,
      "drafts_today": drafts_today + int(candidate is not None),
      "daily_target": daily_target,
      "seen_threads": len(seen_thread_ids),
    }))
    return 0
  except (DiscoveryError, OSError, ValueError) as exc:
    print(f"ERROR: {exc}", file=os.sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
