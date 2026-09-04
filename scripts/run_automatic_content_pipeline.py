#!/usr/bin/env python3
"""Run the fail-closed RaidBench Scout -> Codex -> Pages publishing loop."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("RAIDBENCH_LOCAL_DB_PATH", ROOT / "local" / "raidbench.local.db"))
DEFAULT_STATE = Path(os.environ.get("RAIDBENCH_AUTOMATION_STATE_DIR", ROOT / "private-data" / "content-automation"))
AGENT_GUIDES_PATH = ROOT / "content" / "agent-guides.json"
GAME_REGISTRY_PATH = ROOT / "content" / "game-registry.json"
GAME_REGISTRY = json.loads(GAME_REGISTRY_PATH.read_text(encoding="utf-8"))["games"]
GROWTH_QUOTAS = json.loads((ROOT / "config" / "growth-quotas.json").read_text(encoding="utf-8"))
GAME_BY_NAME = {
  alias: game
  for game in GAME_REGISTRY
  for alias in {str(game["name"]), str(game["shortName"])}
}
ALLOWED_GAMES = set(GAME_BY_NAME)
AUTHORITATIVE_SOURCE_TYPES = {"official", "steam-rss"}
HIDDEN_SLUG_PATTERN = re.compile(r"paid|product|credit|premium|audit-product", re.IGNORECASE)
INVENTORY_EXCERPT_LIMIT = 12
INVENTORY_EXCERPT_CHARS = 3500
INVENTORY_STOP_WORDS = {
  "about", "after", "before", "check", "checklist", "guide", "how", "page", "palworld",
  "path", "poe2", "rust", "status", "the", "this", "update", "with",
}


class AutomationError(RuntimeError):
  """Raised when a publishing guard fails."""


class VisibleTextExtractor(HTMLParser):
  def __init__(self) -> None:
    super().__init__(convert_charrefs=True)
    self.hidden_depth = 0
    self.parts: list[str] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    if tag.lower() in {"script", "style", "noscript"}:
      self.hidden_depth += 1

  def handle_endtag(self, tag: str) -> None:
    if tag.lower() in {"script", "style", "noscript"} and self.hidden_depth:
      self.hidden_depth -= 1

  def handle_data(self, data: str) -> None:
    if not self.hidden_depth and data.strip():
      self.parts.append(data)


def utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_day() -> str:
  return datetime.now(timezone.utc).date().isoformat()


def env_true(name: str, default: bool = False) -> bool:
  value = os.environ.get(name)
  if value is None:
    return default
  return value.strip().lower() in {"1", "true", "yes", "on"}


def is_reddit_thread_url(value: str) -> bool:
  try:
    parsed = urllib.parse.urlparse(value)
  except ValueError:
    return False
  hostname = (parsed.hostname or "").lower()
  return (
    parsed.scheme == "https"
    and hostname in {"reddit.com", "www.reddit.com", "old.reddit.com"}
    and re.match(r"^/r/[^/]+/comments/[a-z0-9]+(?:/|$)", parsed.path, re.IGNORECASE) is not None
  )


def short_hash(value: str, length: int = 16) -> str:
  return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def read_json(path: Path) -> Any:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError as exc:
    raise AutomationError(f"Missing JSON file: {path}") from exc
  except json.JSONDecodeError as exc:
    raise AutomationError(f"Invalid JSON in {path}: {exc}") from exc


def write_json_atomic(path: Path, value: Any) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(path.suffix + ".tmp")
  temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temporary.replace(path)


def relative_to_root(path: Path) -> str:
  try:
    return str(path.resolve().relative_to(ROOT))
  except ValueError as exc:
    raise AutomationError(f"Automation artifact must stay inside the project root: {path}") from exc


def open_database(path: Path) -> sqlite3.Connection:
  if not path.is_file():
    raise AutomationError(f"Scout database does not exist: {path}")
  connection = sqlite3.connect(path)
  connection.row_factory = sqlite3.Row
  connection.execute("PRAGMA foreign_keys = ON")
  connection.executescript(
    """
    CREATE TABLE IF NOT EXISTS content_automation_items (
      id TEXT PRIMARY KEY,
      signal_id TEXT NOT NULL UNIQUE,
      source_type TEXT NOT NULL,
      status TEXT NOT NULL,
      case_id TEXT NOT NULL DEFAULT '',
      case_path TEXT NOT NULL DEFAULT '',
      run_dir TEXT NOT NULL DEFAULT '',
      output_slug TEXT NOT NULL DEFAULT '',
      attempts INTEGER NOT NULL DEFAULT 0,
      last_error TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      published_at TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_content_automation_status
      ON content_automation_items(status, updated_at);
    CREATE TABLE IF NOT EXISTS community_post_drafts (
      id TEXT PRIMARY KEY,
      case_id TEXT NOT NULL UNIQUE,
      game TEXT NOT NULL,
      guide_slug TEXT NOT NULL,
      artifact_path TEXT NOT NULL,
      status TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0,
      last_error TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      notified_at TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_community_post_drafts_status
      ON community_post_drafts(status, updated_at);
    """
  )
  connection.commit()
  return connection


def source_is_eligible(source_type: str, reddit_permission: bool) -> bool:
  if source_type == "reddit-json":
    return reddit_permission
  return source_type in {"official", "steam-rss", "community-web-search"}


def signal_is_fresh(row: sqlite3.Row) -> bool:
  if str(row["source_type"]) != "steam-rss":
    return True
  try:
    evidence = json.loads(str(row["evidence_json"] or "{}"))
    published_at = datetime.fromisoformat(str(evidence.get("publishedAt") or "").replace("Z", "+00:00"))
  except (json.JSONDecodeError, TypeError, ValueError):
    return False
  age_seconds = (datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)).total_seconds()
  return -86400 <= age_seconds <= 45 * 24 * 60 * 60


def signal_is_actionable(row: sqlite3.Row | dict[str, Any]) -> bool:
  title = str(row["signal_title"] or "").lower()
  promotional = (
    "twitch drop",
    "watch the",
    "livestream",
    "qualifier",
    "fan art",
    "microtransaction",
    "now available in store",
    "sale",
  )
  player_problem = ("patch", "hotfix", "fix", "bug", "balance", "crash", "save data", "progression")
  return not (any(term in title for term in promotional) and not any(term in title for term in player_problem))


def candidate_rank(row: sqlite3.Row, preferred_game: str, preference_bonus: int) -> tuple[int, int, str, str]:
  base_score = int(row["pain_score"]) + int(row["commercial_score"])
  weighted_score = base_score + (preference_bonus if str(row["game"]).lower() == preferred_game.lower() else 0)
  try:
    evidence = json.loads(str(row["evidence_json"] or "{}"))
    published_at = str(evidence.get("publishedAt") or "")
  except (json.JSONDecodeError, TypeError):
    published_at = ""
  return weighted_score, int(row["patch_sensitive"]), published_at, str(row["created_at"])


def candidate_rows(connection: sqlite3.Connection, reddit_permission: bool) -> list[sqlite3.Row]:
  rows = connection.execute(
    """
    SELECT
      signal.id AS signal_id,
      signal.game,
      signal.topic,
      signal.signal_title,
      signal.signal_url,
      signal.pain_score,
      signal.commercial_score,
      signal.patch_sensitive,
      signal.evidence_json,
      signal.created_at,
      source.id AS source_id,
      source.source_type,
      source.url AS source_url,
      snapshot.fetched_at,
      snapshot.title AS snapshot_title,
      snapshot.body_sample,
      existing.status AS existing_status,
      COALESCE(existing.attempts, 0) AS attempts,
      COALESCE(existing.updated_at, '') AS existing_updated_at
    FROM content_signals signal
    JOIN content_sources source ON source.id = signal.source_id
    LEFT JOIN content_source_profiles profile ON profile.source_id = source.id
    LEFT JOIN content_automation_items existing ON existing.signal_id = signal.id
    LEFT JOIN source_snapshots snapshot ON snapshot.id = (
      SELECT matching.id
      FROM source_snapshots matching
      WHERE matching.source_id = source.id
        AND matching.run_id = signal.run_id
        AND matching.ok = 1
      ORDER BY matching.fetched_at DESC
      LIMIT 1
    )
    WHERE (signal.pain_score + signal.commercial_score) >= ?
      AND signal.created_at >= datetime('now', '-21 days')
      AND snapshot.id IS NOT NULL
      AND (
        source.source_type = 'community-web-search'
        OR COALESCE(profile.generation_eligible, 1) = 1
      )
      AND (
        existing.signal_id IS NULL
        OR (
          existing.status IN ('agent_failed', 'build_failed')
          AND existing.attempts < 3
          AND datetime(existing.updated_at) <= datetime('now', '-1 hour')
        )
      )
    ORDER BY
      (signal.pain_score + signal.commercial_score) DESC,
      signal.patch_sensitive DESC,
      COALESCE(json_extract(signal.evidence_json, '$.publishedAt'), '') DESC,
      signal.created_at DESC
    LIMIT 50
    """,
    (int(os.environ.get("RAIDBENCH_AUTOMATION_MIN_SIGNAL_SCORE", "8")),),
  ).fetchall()
  eligible = [
    row
    for row in rows
    if source_is_eligible(str(row["source_type"]), reddit_permission)
    and signal_is_fresh(row)
    and signal_is_actionable(row)
  ]
  preferred_game = os.environ.get("RAIDBENCH_PREFERRED_GAME", "").strip()
  preference_bonus = max(0, int(os.environ.get("RAIDBENCH_PREFERRED_GAME_SCORE_BONUS", "2")))
  if preferred_game:
    eligible.sort(key=lambda row: candidate_rank(row, preferred_game, preference_bonus), reverse=True)
  return eligible


def daily_limit_reached(connection: sqlite3.Connection) -> bool:
  default = int(GROWTH_QUOTAS.get("publicGuides", {}).get("dailyMaximum", 24))
  configured = int(os.environ.get("RAIDBENCH_MAX_NEW_GUIDES_PER_DAY", str(default)))
  used = connection.execute(
    """
    SELECT count(*)
    FROM content_automation_items
    WHERE datetime(COALESCE(NULLIF(published_at, ''), created_at)) >= datetime('now', 'start of day')
      AND status NOT IN ('agent_failed', 'qa_blocked', 'build_failed')
    """
  ).fetchone()[0]
  return int(used) >= configured


def hourly_limit_reached(connection: sqlite3.Connection) -> bool:
  default = int(GROWTH_QUOTAS.get("publicGuides", {}).get("hourlyMaximum", 1))
  configured = int(os.environ.get("RAIDBENCH_MAX_NEW_GUIDES_PER_HOUR", str(default)))
  used = connection.execute(
    """
    SELECT count(*)
    FROM content_automation_items
    WHERE datetime(created_at) >= datetime(strftime('%Y-%m-%d %H:00:00', 'now'))
      AND status NOT IN ('agent_failed', 'qa_blocked', 'build_failed')
    """
  ).fetchone()[0]
  return int(used) >= configured


def utc_week_start() -> str:
  now = datetime.now(timezone.utc)
  return (now - timedelta(days=now.weekday())).date().isoformat()


def weekly_guide_limit(game: str) -> int:
  registry_game = GAME_BY_NAME.get(game)
  if registry_game is None:
    return 0
  weekly_defaults = GROWTH_QUOTAS.get("publicGuides", {}).get("weekly", {})
  default = weekly_defaults.get(
    str(registry_game["name"]),
    weekly_defaults.get(str(registry_game["shortName"]), 0),
  )
  env_key = re.sub(r"[^A-Z0-9]+", "_", str(registry_game["id"]).upper()).strip("_")
  env_name = f"RAIDBENCH_{env_key}_WEEKLY_GUIDE_LIMIT"
  return max(0, int(os.environ.get(env_name, str(default))))


def weekly_guide_limit_reached(connection: sqlite3.Connection, game: str) -> bool:
  limit = weekly_guide_limit(game)
  if limit == 0:
    return True
  used = connection.execute(
    """
    SELECT count(*)
    FROM content_automation_items item
    JOIN content_signals signal ON signal.id = item.signal_id
    WHERE signal.game = ?
      AND item.status IN ('published', 'qa_passed_staged')
      AND COALESCE(NULLIF(item.published_at, ''), item.updated_at) >= ?
    """,
    (game, utc_week_start()),
  ).fetchone()[0]
  return int(used) >= limit


def recover_interrupted_items(connection: sqlite3.Connection) -> int:
  result = connection.execute(
    """
    UPDATE content_automation_items
    SET status = 'agent_failed',
        last_error = CASE
          WHEN last_error = '' THEN 'Recovered after the previous automation process ended before a final status'
          ELSE last_error
        END
    WHERE status IN ('case_ready', 'agent_running')
      AND datetime(updated_at) <= datetime('now', '-30 minutes')
    """
  )
  connection.commit()
  return int(result.rowcount)


def latest_authoritative_snapshots(connection: sqlite3.Connection, game: str, limit: int = 3) -> list[sqlite3.Row]:
  return connection.execute(
    """
    SELECT
      source.id AS source_id,
      source.source_type,
      source.url AS source_url,
      snapshot.fetched_at,
      snapshot.title AS snapshot_title,
      snapshot.body_sample
    FROM content_sources source
    JOIN source_snapshots snapshot ON snapshot.id = (
      SELECT latest.id
      FROM source_snapshots latest
      WHERE latest.source_id = source.id AND latest.ok = 1
      ORDER BY latest.fetched_at DESC
      LIMIT 1
    )
    WHERE source.game = ? AND source.source_type IN ('official', 'steam-rss')
    ORDER BY snapshot.fetched_at DESC
    LIMIT ?
    """,
    (game, limit),
  ).fetchall()


def inventory_terms(value: str) -> set[str]:
  return {
    term
    for term in re.findall(r"[a-z0-9]{3,}", value.lower())
    if term not in INVENTORY_STOP_WORDS
  }


def published_guide_excerpt(slug: str) -> str:
  if re.fullmatch(r"[a-z0-9-]+", slug) is None:
    return ""
  path = ROOT / "pages" / f"{slug}.html"
  if not path.is_file():
    return ""
  parser = VisibleTextExtractor()
  parser.feed(path.read_text(encoding="utf-8"))
  return " ".join(" ".join(parser.parts).split())[:INVENTORY_EXCERPT_CHARS]


def public_page_is_indexable(slug: str) -> bool:
  if re.fullmatch(r"[a-z0-9-]+", slug) is None:
    return False
  path = ROOT / "pages" / f"{slug}.html"
  if not path.is_file():
    return False
  html = path.read_text(encoding="utf-8")
  return re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex', html, re.IGNORECASE) is None


def sync_guide_inventory(connection: sqlite3.Connection) -> int:
  game_by_id = {str(item["id"]): str(item["shortName"]) for item in GAME_REGISTRY}
  records: dict[str, dict[str, Any]] = {}

  def register(guide: dict[str, Any], game: str, status: str, checked_at: str, source_notes: str) -> None:
    slug = str(guide.get("slug") or "")
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) is None:
      return
    if not (ROOT / "pages" / f"{slug}.html").is_file():
      return
    records[slug] = {
      "slug": slug,
      "game": game,
      "title": str(guide.get("title") or slug.replace("-", " ").title()),
      "status": status,
      "checked_at": checked_at,
      "patch_sensitive": int(bool(guide.get("patchSensitive", True))),
      "source_notes": source_notes,
    }

  for filename, game in (
    ("rust-problem-guides.json", "Rust"),
    ("poe2-problem-guides.json", "POE2"),
    ("palworld-problem-guides.json", "Palworld"),
  ):
    for guide in read_json(ROOT / "content" / filename):
      register(guide, game, "published_or_draft", utc_now(), "; ".join(str(item) for item in guide.get("sources", [])))

  for guide in read_json(ROOT / "content" / "manual-guides.json"):
    register(guide, str(guide.get("game") or ""), "published", utc_now(), "Manually reviewed RaidBench guide")

  baseline = read_json(ROOT / "content" / "multigame-baseline-guides.json")
  for pack in baseline.get("packs", []):
    game = game_by_id.get(str(pack.get("gameId") or ""), str(pack.get("gameId") or ""))
    for guide in pack.get("guides", []):
      register(
        guide,
        game,
        "published",
        str(baseline.get("reviewedAt") or utc_now()),
        "Phase 3 source packet; publisher facts plus demand-only community context",
      )

  for guide in read_json(AGENT_GUIDES_PATH):
    register(
      guide,
      str(guide.get("game") or ""),
      "published",
      str(guide.get("reviewedAt") or utc_now()),
      str(guide.get("sourceNote") or "Source-checked Agent guide"),
    )

  for item in records.values():
    connection.execute(
      """
      INSERT INTO guide_pages (slug, game, title, status, last_checked_at, patch_sensitive, source_notes)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(slug) DO UPDATE SET
        game=excluded.game,
        title=excluded.title,
        status=excluded.status,
        last_checked_at=excluded.last_checked_at,
        patch_sensitive=excluded.patch_sensitive,
        source_notes=excluded.source_notes
      """,
      (
        item["slug"], item["game"], item["title"], item["status"], item["checked_at"],
        item["patch_sensitive"], item["source_notes"],
      ),
    )
  connection.commit()
  return len(records)


def guide_inventory(
  connection: sqlite3.Connection,
  *,
  game: str = "",
  context_text: str = "",
) -> list[dict[str, Any]]:
  rows = connection.execute(
    """
    SELECT slug, game, title, status, patch_sensitive
    FROM guide_pages
    ORDER BY game, slug
    """
  ).fetchall()
  if not rows:
    raise AutomationError("Guide inventory is empty")
  inventory = [
    {
      "slug": row["slug"],
      "game": row["game"],
      "title": row["title"],
      "status": row["status"],
      "patch_sensitive": bool(row["patch_sensitive"]),
    }
    for row in rows
    if row["status"] in {"published", "published_or_draft"}
    and (not game or row["game"] == game)
    and public_page_is_indexable(str(row["slug"]))
  ]
  if not inventory:
    raise AutomationError("Guide inventory has no indexable public pages")
  context_terms = inventory_terms(context_text)
  excerpt_candidates = [
    item
    for item in inventory
    if item["game"] == game
  ]
  excerpt_candidates.sort(
    key=lambda item: (
      len(inventory_terms(f"{item['slug']} {item['title']}").intersection(context_terms)),
      int(item["patch_sensitive"]),
      item["slug"],
    ),
    reverse=True,
  )
  excerpt_slugs = {item["slug"] for item in excerpt_candidates[:INVENTORY_EXCERPT_LIMIT]}
  for item in inventory:
    if item["slug"] not in excerpt_slugs:
      continue
    excerpt = published_guide_excerpt(str(item["slug"]))
    if excerpt:
      item["content_path"] = f"pages/{item['slug']}.html"
      item["content_excerpt"] = excerpt
      item["content_excerpt_scope"] = (
        "Existing public RaidBench copy for overlap and conflict review only; not authority for current game facts."
      )
  return inventory


def deterministic_score(candidate: sqlite3.Row, source_type: str) -> dict[str, Any]:
  components = [
    {"component": "player_pain", "score": int(candidate["pain_score"]) * 20, "weight": 35},
    {"component": "seo_fit", "score": int(candidate["commercial_score"]) * 20, "weight": 25},
    {"component": "paid_audit_fit", "score": int(candidate["commercial_score"]) * 20, "weight": 25},
    {"component": "compliance_safety", "score": 90 if source_type in AUTHORITATIVE_SOURCE_TYPES else 70, "weight": 15},
  ]
  score = round(sum(item["score"] * item["weight"] for item in components) / 100)
  return {
    "method_version": "raidbench-opportunity-v2",
    "opportunity_score": score,
    "components": components,
    "score_is_deterministic": True,
    "agent_may_modify_score": False,
  }


def external_publication_policy() -> dict[str, bool]:
  return {
    "external_post_confirmation_required": False,
    "exact_thread_link_free_reply_confirmation_required": False,
    "standalone_external_post_confirmation_required": True,
    "external_platform_permission_required": True,
  }


def content_constraints() -> dict[str, bool]:
  policy = external_publication_policy()
  return {
    "public_sources_only": True,
    "no_guaranteed_outcomes": True,
    "no_cheats_or_exploits": True,
    "no_real_money_trading": True,
    "no_sale_or_transfer_of_in_game_currency_or_items": True,
    "informational_in_game_economy_guidance_allowed": True,
    "owned_site_auto_publish_after_qa": True,
    "external_post_requires_platform_permission": True,
    "owner_confirmation_required_for_external_posts": policy["standalone_external_post_confirmation_required"],
    "owner_confirmation_required_for_exact_thread_link_free_replies": policy["exact_thread_link_free_reply_confirmation_required"],
    "automatic_reply_requires_approved_platform_posting_access": True,
  }


def build_case(connection: sqlite3.Connection, candidate: sqlite3.Row, state_dir: Path) -> tuple[dict[str, Any], Path]:
  game = str(candidate["game"])
  if game not in ALLOWED_GAMES:
    raise AutomationError(f"Unsupported candidate game: {game}")
  case_id = f"auto-{game.lower()}-{utc_day()}-{short_hash(str(candidate['signal_id']), 10)}"
  evidence_rows: list[dict[str, Any]] = []
  seen_sources: set[str] = set()

  def add_evidence(row: sqlite3.Row, demand_only: bool) -> None:
    source_id = str(row["source_id"])
    if source_id in seen_sources:
      return
    seen_sources.add(source_id)
    signal_evidence: dict[str, Any] = {}
    if "evidence_json" in row.keys():
      try:
        parsed = json.loads(str(row["evidence_json"] or "{}"))
        if isinstance(parsed, dict):
          signal_evidence = parsed
      except json.JSONDecodeError:
        signal_evidence = {}
    source_url = str(row["source_url"])
    source_title = str(row["snapshot_title"] or "")
    if "signal_url" in row.keys() and str(row["signal_url"] or "").startswith("https://"):
      source_url = str(row["signal_url"])
    if "signal_title" in row.keys() and str(row["signal_title"] or "").strip():
      source_title = str(row["signal_title"])
    evidence_rows.append({
      "source_id": source_id,
      "source_type": str(row["source_type"]),
      "source_url": source_url,
      "captured_at": str(row["fetched_at"]),
      "title": source_title,
      "body_sample": str(signal_evidence.get("excerpt") or row["body_sample"] or "")[:8000],
      "published_at": str(signal_evidence.get("publishedAt") or ""),
      "demand_only": demand_only,
    })

  add_evidence(candidate, str(candidate["source_type"]) not in AUTHORITATIVE_SOURCE_TYPES)
  for row in latest_authoritative_snapshots(connection, game):
    add_evidence(row, False)
  if not any(item["source_type"] in AUTHORITATIVE_SOURCE_TYPES for item in evidence_rows):
    raise AutomationError("No authoritative game evidence is available for this candidate")

  evidence_file = state_dir / "evidence" / f"{case_id}.json"
  write_json_atomic(
    evidence_file,
    {
      "case_id": case_id,
      "captured_at": utc_now(),
      "candidate": {key: candidate[key] for key in candidate.keys() if key not in {"body_sample"}},
      "sources": evidence_rows,
      "evidence_boundary": "Community titles are demand context only. Factual claims require an official or publisher-controlled source in this file.",
    },
  )

  evidence = []
  source_to_evidence: dict[str, str] = {}
  for index, item in enumerate(evidence_rows, start=1):
    evidence_id = f"E-{index:02d}"
    source_to_evidence[item["source_id"]] = evidence_id
    evidence.append({
      "evidence_id": evidence_id,
      "source_type": item["source_type"],
      "source_url": item["source_url"],
      "source_title": item["title"],
      "evidence_path": relative_to_root(evidence_file),
      "captured_at": item["captured_at"],
      "published_at": item["published_at"],
      "captured_excerpt": item["body_sample"],
      "scope_note": "Demand context only; do not use as factual authority." if item["demand_only"] else "Primary patch, product, or publisher evidence; stay within the captured text.",
    })

  inventory_context = " ".join([
    str(candidate["signal_title"]),
    str(candidate["topic"]),
    *[str(item["body_sample"]) for item in evidence_rows],
  ])
  case = {
    "case_id": case_id,
    "case_type": "automatic_owned_content",
    "site": {
      "site_name": "RaidBench",
      "domain": "raidbench.com",
      "public_language": "en",
      "owner_language": "zh-CN",
    },
    "run_context": {
      "game_focus": [game],
      "objective": "Create one source-bounded guide and one link-free community answer for the selected player problem.",
      "payment_ready": True,
      "publish_mode": "automatic_owned_site_only",
      **external_publication_policy(),
    },
    "evidence": evidence,
    "signals": [{
      "signal_id": str(candidate["signal_id"]),
      "evidence_id": source_to_evidence[str(candidate["source_id"])],
      "game": game,
      "topic": str(candidate["topic"]),
      "signal_title": str(candidate["signal_title"]),
      "signal_url": str(candidate["signal_url"]),
      "pain_score": int(candidate["pain_score"]),
      "commercial_score": int(candidate["commercial_score"]),
      "patch_sensitive": bool(candidate["patch_sensitive"]),
    }],
    "guide_inventory": guide_inventory(connection, game=game, context_text=inventory_context),
    "opportunity_scorecard": deterministic_score(candidate, str(candidate["source_type"])),
    "constraints": content_constraints(),
  }
  case_path = state_dir / "cases" / f"{case_id}.json"
  write_json_atomic(case_path, case)
  return case, case_path


def register_case(connection: sqlite3.Connection, candidate: sqlite3.Row, case: dict[str, Any], case_path: Path) -> str:
  item_id = f"auto_{short_hash(str(candidate['signal_id']))}"
  now = utc_now()
  connection.execute(
    """
    INSERT INTO content_automation_items (
      id, signal_id, source_type, status, case_id, case_path, attempts, created_at, updated_at
    ) VALUES (?, ?, ?, 'case_ready', ?, ?, 0, ?, ?)
    ON CONFLICT(signal_id) DO UPDATE SET
      status = 'case_ready',
      case_id = excluded.case_id,
      case_path = excluded.case_path,
      last_error = '',
      updated_at = excluded.updated_at
    """,
    (
      item_id,
      str(candidate["signal_id"]),
      str(candidate["source_type"]),
      str(case["case_id"]),
      relative_to_root(case_path),
      now,
      now,
    ),
  )
  connection.commit()
  return item_id


def update_item(connection: sqlite3.Connection, item_id: str, status: str, **fields: str | int) -> None:
  allowed = {"run_dir", "output_slug", "last_error", "published_at", "attempts"}
  unknown = set(fields).difference(allowed)
  if unknown:
    raise AutomationError(f"Unsupported automation item fields: {', '.join(sorted(unknown))}")
  assignments = ["status = ?", "updated_at = ?"]
  values: list[Any] = [status, utc_now()]
  for key, value in fields.items():
    assignments.append(f"{key} = ?")
    values.append(value)
  values.append(item_id)
  connection.execute(f"UPDATE content_automation_items SET {', '.join(assignments)} WHERE id = ?", values)
  connection.commit()


def run_command(command: list[str], *, timeout: int, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
  result = subprocess.run(
    command,
    cwd=ROOT,
    env=env,
    text=True,
    capture_output=True,
    timeout=timeout,
    check=False,
  )
  if result.returncode != 0:
    detail = (result.stderr or result.stdout).strip()[-2000:]
    raise AutomationError(f"Command failed ({' '.join(command)}): {detail}")
  return result


def existing_public_slugs() -> set[str]:
  slugs: set[str] = set()
  for filename in ["rust-problem-guides.json", "poe2-problem-guides.json", "palworld-problem-guides.json", "manual-guides.json"]:
    value = read_json(ROOT / "content" / filename)
    for guide in value:
      if isinstance(guide, dict) and isinstance(guide.get("slug"), str):
        slugs.add(guide["slug"])
  return slugs


def materialize_guide(case: dict[str, Any], draft: dict[str, Any], existing_agent_guides: list[dict[str, Any]]) -> dict[str, Any]:
  slug = str(draft.get("slug") or "")
  if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
    raise AutomationError(f"Agent produced an unsafe slug: {slug}")
  if HIDDEN_SLUG_PATTERN.search(slug):
    raise AutomationError(f"Agent slug crosses a hidden monetization boundary: {slug}")
  agent_by_slug = {guide["slug"]: guide for guide in existing_agent_guides}
  if slug in existing_public_slugs() and slug not in agent_by_slug:
    raise AutomationError(f"Agent attempted to overwrite a human-maintained guide: {slug}")

  evidence_by_id = {item["evidence_id"]: item for item in case["evidence"]}
  draft_evidence = [evidence_by_id[item] for item in draft["evidence_ids"] if item in evidence_by_id]
  authoritative = [item for item in draft_evidence if item["source_type"] in AUTHORITATIVE_SOURCE_TYPES]
  if not authoritative:
    raise AutomationError("Publishable guide has no authoritative evidence reference")

  related = [str(item) for item in draft.get("related_slugs", [])]
  related_inventory = {
    guide["slug"]
    for guide in case["guide_inventory"]
    if str(guide.get("game") or "") == str(case["signals"][0]["game"])
  }
  if not related or any(item not in related_inventory for item in related):
    raise AutomationError("Agent guide contains an invalid related guide reference")

  sources = []
  for item in authoritative:
    url = str(item["source_url"])
    if not url.startswith("https://"):
      raise AutomationError(f"Source URL must use HTTPS: {url}")
    sources.append({
      "label": str(item.get("source_title") or f"{case['signals'][0]['game']} official or publisher source"),
      "url": url,
      "note": str(item["scope_note"]),
    })

  today = utc_day()
  existing = agent_by_slug.get(slug, {})
  signal = case["signals"][0]
  signal_evidence = evidence_by_id.get(str(signal.get("evidence_id") or ""), {})
  community_target_url = str(signal.get("signal_url") or "")
  automation_metadata = {
    "caseId": str(case["case_id"]),
    "draftId": str(draft["draft_id"]),
    "signalId": str(signal["signal_id"]),
    "qa": "passed",
    "generatedAt": utc_now(),
  }
  if signal_evidence.get("source_type") == "reddit-json" and is_reddit_thread_url(community_target_url):
    automation_metadata.update({
      "communityTargetPlatform": "reddit",
      "communityTargetUrl": community_target_url,
      "communityTargetTitle": str(signal.get("signal_title") or ""),
    })
  return {
    "slug": slug,
    "game": str(case["signals"][0]["game"]),
    "title": str(draft["title"]),
    "description": str(draft["meta_description"]),
    "problem": str(draft["hero_hook"]),
    "shortAnswer": str(draft["short_answer"]),
    "publishedAt": str(existing.get("publishedAt") or today),
    "reviewedAt": today,
    "status": f"Evidence-bounded {case['signals'][0]['game']} guide; recheck after relevant patch changes",
    "sections": [
      {
        "title": str(section["heading"]),
        "purpose": str(section["purpose"]),
        "bullets": [str(item) for item in section["bullets"]],
      }
      for section in draft["outline"]
    ],
    "checklist": [str(item) for item in draft["checklist"]],
    "example": str(draft["example"]),
    "mistakes": [str(item) for item in draft["common_mistakes"]],
    "faqs": [
      {"question": str(item["question"]), "answer": str(item["answer"])}
      for item in draft["faqs"]
    ],
    "related": related,
    "sources": sources,
    "sourceNote": str(draft["source_note"]),
    "patchNote": str(draft["patch_note"]),
    "communityAnswer": str(draft["community_answer"]),
    "automation": automation_metadata,
  }


def write_community_artifact(state_dir: Path, case: dict[str, Any], guide: dict[str, Any], source_type: str) -> None:
  if source_type != "reddit-json":
    return
  answer = str(guide["communityAnswer"])
  if re.search(r"https?://|www\.|raidbench", answer, re.IGNORECASE):
    raise AutomationError("Community answer link-free guard failed")
  platform_permission = env_true("RAIDBENCH_REDDIT_COMMERCIAL_PERMISSION_CONFIRMED")
  status = "ready_for_owner_review" if platform_permission else "platform_permission_required"
  write_json_atomic(
    state_dir / "community-replies" / f"{case['case_id']}.json",
    {
      "case_id": case["case_id"],
      "platform": "reddit",
      "target_url": case["signals"][0]["signal_url"],
      "answer": answer,
      "contains_link": False,
      "owner_confirmation_required": True,
      "platform_permission_confirmed": platform_permission,
      "status": status,
      "created_at": utc_now(),
    },
  )


def write_manual_post_draft(
  state_dir: Path,
  guide: dict[str, Any],
  *,
  source_url: str,
  exact_target_url: str,
  target_title: str,
) -> Path:
  answer = str(guide.get("communityAnswer") or "").strip()
  if not answer or re.search(r"https?://|www\.|raidbench", answer, re.IGNORECASE):
    raise AutomationError("Manual-post draft must be a non-empty, link-free answer")
  if not source_url.startswith("https://"):
    raise AutomationError("Manual-post draft requires an HTTPS source URL")
  if not is_reddit_thread_url(exact_target_url):
    raise AutomationError("Manual-post draft requires an exact Reddit thread URL")
  if not target_title.strip():
    raise AutomationError("Manual-post draft requires the Reddit thread title")
  guide_url = f"https://raidbench.com/pages/{guide['slug']}"
  case_id = str(guide["automation"]["caseId"])
  path = state_dir / "community-drafts" / f"{case_id}.json"
  created_at = utc_now()
  if path.is_file():
    try:
      existing = read_json(path)
      created_at = str(existing.get("created_at") or created_at)
    except AutomationError:
      pass
  updated_at = utc_now()
  stored = {
    "draft_id": f"post_{short_hash(case_id)}",
    "case_id": case_id,
    "game": str(guide["game"]),
    "guide_slug": str(guide["slug"]),
    "guide_title": str(guide["title"]),
    "guide_url": guide_url,
    "source_url": source_url,
    "target_platform": "reddit",
    "target_title": target_title.strip(),
    "target_reddit_url": exact_target_url,
    "draft_text": answer,
    "contains_link": False,
    "manual_publish_required": True,
    "status": "ready_for_reddit_owner_review",
    "posting_notes_zh": [
      "先确认草稿与当前帖子的问题完全匹配；不匹配就不要发布。",
      "默认保持无链接、无品牌推广；同一段内容不要重复发布到多个帖子。",
      "如社区规则允许且你决定加入 RaidBench 链接，必须披露你与网站的关系。",
    ],
    "created_at": created_at,
    "updated_at": updated_at,
  }
  write_json_atomic(path, stored)
  return path


def register_manual_post_draft(
  connection: sqlite3.Connection,
  guide: dict[str, Any],
  draft_path: Path,
) -> str:
  draft = read_json(draft_path)
  draft_id = str(draft["draft_id"])
  now = utc_now()
  connection.execute(
    """
    INSERT INTO community_post_drafts (
      id, case_id, game, guide_slug, artifact_path, status, attempts, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, 'pending_notification', 0, ?, ?)
    ON CONFLICT(case_id) DO UPDATE SET
      game = excluded.game,
      guide_slug = excluded.guide_slug,
      artifact_path = excluded.artifact_path,
      status = CASE
        WHEN community_post_drafts.status = 'notified' THEN community_post_drafts.status
        WHEN community_post_drafts.attempts >= 5 THEN 'notification_failed'
        ELSE 'pending_notification'
      END,
      last_error = CASE
        WHEN community_post_drafts.status = 'notified' THEN community_post_drafts.last_error
        WHEN community_post_drafts.attempts >= 5 THEN community_post_drafts.last_error
        ELSE ''
      END,
      updated_at = excluded.updated_at
    """,
    (
      draft_id,
      str(draft["case_id"]),
      str(draft["game"]),
      str(draft["guide_slug"]),
      relative_to_root(draft_path),
      str(draft["created_at"]),
      now,
    ),
  )
  connection.commit()
  return draft_id


def backfill_agent_post_drafts(connection: sqlite3.Connection, state_dir: Path) -> int:
  guides = read_json(AGENT_GUIDES_PATH)
  if not isinstance(guides, list):
    raise AutomationError("content/agent-guides.json must contain an array")
  created = 0
  for guide in guides:
    if not isinstance(guide, dict) or not isinstance(guide.get("automation"), dict):
      continue
    automation = guide["automation"]
    target_url = str(automation.get("communityTargetUrl") or "")
    target_title = str(automation.get("communityTargetTitle") or "")
    if automation.get("communityTargetPlatform") != "reddit" or not is_reddit_thread_url(target_url):
      continue
    sources = guide.get("sources")
    if not isinstance(sources, list) or not sources or not isinstance(sources[0], dict):
      continue
    source_url = str(sources[0].get("url") or "")
    if not source_url.startswith("https://") or not guide.get("communityAnswer") or not target_title.strip():
      continue
    path = write_manual_post_draft(
      state_dir,
      guide,
      source_url=source_url,
      exact_target_url=target_url,
      target_title=target_title,
    )
    register_manual_post_draft(connection, guide, path)
    created += 1
  return created


def deliver_pending_draft_notifications(
  connection: sqlite3.Connection,
  state_dir: Path,
  limit: int = 5,
) -> list[dict[str, str]]:
  rows = connection.execute(
    """
    SELECT id, artifact_path, attempts
    FROM community_post_drafts
    WHERE status IN ('pending_notification', 'awaiting_configuration', 'notification_failed')
      AND attempts < 5
    ORDER BY created_at ASC
    LIMIT ?
    """,
    (limit,),
  ).fetchall()
  results: list[dict[str, str]] = []
  for row in rows:
    draft_id = str(row["id"])
    draft_path = ROOT / str(row["artifact_path"])
    command = [sys.executable, "scripts/send_feishu_draft_notification.py", "--draft", relative_to_root(draft_path)]
    try:
      result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
      )
      if result.returncode == 0:
        status = "notified"
        attempts = int(row["attempts"]) + 1
        notified_at = utc_now()
        error = ""
      elif result.returncode == 3:
        status = "awaiting_configuration"
        attempts = int(row["attempts"])
        notified_at = ""
        error = "Feishu webhook is not configured"
      else:
        status = "notification_failed"
        attempts = int(row["attempts"]) + 1
        notified_at = ""
        error = (result.stderr or result.stdout).strip()[-1000:]
    except subprocess.TimeoutExpired:
      status = "notification_failed"
      attempts = int(row["attempts"]) + 1
      notified_at = ""
      error = "Feishu notification timed out"
    connection.execute(
      """
      UPDATE community_post_drafts
      SET status = ?, attempts = ?, last_error = ?, notified_at = ?, updated_at = ?
      WHERE id = ?
      """,
      (status, attempts, error, notified_at, utc_now(), draft_id),
    )
    connection.commit()
    log_path = state_dir / "logs" / f"feishu-{draft_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"status={status}\nerror={error}\n", encoding="utf-8")
    results.append({"draft_id": draft_id, "status": status})
  return results


def build_public_site(state_dir: Path) -> Path:
  commands = [
    ["node", "scripts/generate-guides.mjs"],
    ["node", "scripts/generate-poe2-guides.mjs"],
    ["node", "scripts/generate-palworld-guides.mjs"],
    ["node", "scripts/generate-agent-guides.mjs"],
    ["node", "scripts/generate-patch-watch.mjs"],
    ["node", "scripts/upgrade-manual-guides.mjs"],
    ["node", "scripts/generate-multigame-baseline-guides.mjs"],
    ["node", "scripts/validate-multigame-launch-gates.mjs"],
    ["node", "scripts/generate-multigame-tools.mjs"],
    ["node", "scripts/generate-game-directory.mjs"],
    ["node", "scripts/generate-guide-index.mjs"],
    ["node", "scripts/apply-site-navigation.mjs"],
    ["node", "scripts/generate-sitemap.mjs"],
    ["node", "scripts/generate-public-raid-data.mjs"],
    ["node", "scripts/generate-rust-route-presets.mjs"],
    ["node", "scripts/generate-discovery-feeds.mjs"],
    ["node", "scripts/validate-public-site.mjs"],
  ]
  for command in commands:
    run_command(command, timeout=180)
  dist = state_dir / "dist"
  env = dict(os.environ)
  env["RAIDBENCH_DIST_DIR"] = str(dist)
  run_command(["node", "scripts/build-public-dist.mjs"], timeout=180, env=env)
  return dist


def deploy_pages(dist: Path, slug: str, state_dir: Path) -> str:
  if not env_true("RAIDBENCH_AUTO_DEPLOY"):
    return ""
  for variable in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
    if not os.environ.get(variable):
      raise AutomationError(f"Automatic deployment is enabled but {variable} is missing")
  wrangler = os.environ.get("RAIDBENCH_WRANGLER_BIN", "wrangler")
  result = run_command(
    [
      wrangler,
      "pages",
      "deploy",
      str(dist),
      "--project-name",
      "raidbench",
      "--branch",
      "main",
      "--commit-message",
      f"RaidBench Agent publish: {slug}",
    ],
    timeout=900,
  )
  log_path = state_dir / "logs" / f"deploy-{utc_day()}-{slug}.log"
  log_path.parent.mkdir(parents=True, exist_ok=True)
  log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
  match = re.search(r"https://[a-z0-9-]+\.raidbench\.pages\.dev", result.stdout + result.stderr, re.IGNORECASE)
  return match.group(0) if match else ""


def verify_public_page(slug: str) -> None:
  url = f"https://raidbench.com/pages/{slug}"
  expected_canonical = f'<link rel="canonical" href="{url}"'
  last_error = ""
  for _ in range(8):
    try:
      request = urllib.request.Request(url, headers={"User-Agent": "RaidBench deployment verifier"})
      with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8", "replace")
        if response.status == 200 and expected_canonical in body and "RaidBench" in body:
          return
        last_error = f"unexpected response status/content: {response.status}"
    except (urllib.error.URLError, TimeoutError) as exc:
      last_error = str(exc)
    time.sleep(8)
  raise AutomationError(f"Production verification failed for {url}: {last_error}")


def submit_indexnow(slug: str, state_dir: Path) -> str:
  url = f"https://raidbench.com/pages/{slug}"
  try:
    result = run_command(["node", "scripts/submit-indexnow.mjs", url], timeout=90)
    return result.stdout.strip()
  except AutomationError as exc:
    warning_path = state_dir / "logs" / f"indexnow-{utc_day()}-{slug}.log"
    warning_path.parent.mkdir(parents=True, exist_ok=True)
    warning_path.write_text(str(exc) + "\n", encoding="utf-8")
    return f"WARNING: {exc}"


def restore_agent_guides(original: bytes, state_dir: Path) -> None:
  AGENT_GUIDES_PATH.write_bytes(original)
  try:
    build_public_site(state_dir)
  except Exception:
    pass


def execute(args: argparse.Namespace) -> int:
  state_dir = args.state_dir.resolve()
  relative_to_root(state_dir)
  state_dir.mkdir(parents=True, exist_ok=True)
  lock_path = state_dir / "automation.lock"
  with lock_path.open("a+", encoding="utf-8") as lock:
    try:
      fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
      print("Another RaidBench content automation run is active; exiting without overlap.")
      return 0

    connection = open_database(args.database)
    item_id = ""
    original_guides: bytes | None = None
    try:
      recovered = recover_interrupted_items(connection)
      if recovered:
        print(f"Recovered {recovered} interrupted content automation item(s).")
      synced_guides = sync_guide_inventory(connection)
      print(f"Synchronized {synced_guides} public guides into the Agent inventory.")
      backfill_agent_post_drafts(connection, state_dir)
      notification_results = deliver_pending_draft_notifications(connection, state_dir)
      reddit_permission = env_true("RAIDBENCH_REDDIT_COMMERCIAL_PERMISSION_CONFIRMED")
      candidates = [
        candidate
        for candidate in candidate_rows(connection, reddit_permission)
        if not weekly_guide_limit_reached(connection, str(candidate["game"]))
      ]
      if not candidates:
        print("No eligible unprocessed content signal is available.")
        if notification_results:
          print(json.dumps({"draft_notifications": notification_results}, indent=2))
        return 0
      candidate = candidates[0]
      if args.dry_run:
        print(json.dumps({
          "signal_id": candidate["signal_id"],
          "game": candidate["game"],
          "topic": candidate["topic"],
          "source_type": candidate["source_type"],
          "score": int(candidate["pain_score"]) + int(candidate["commercial_score"]),
          "reddit_permission_confirmed": reddit_permission,
        }, indent=2))
        return 0
      if hourly_limit_reached(connection):
        print("Hourly automatic guide limit reached; no Codex run started.")
        if notification_results:
          print(json.dumps({"draft_notifications": notification_results}, indent=2))
        return 0
      if daily_limit_reached(connection):
        print("Daily automatic guide limit reached; no Codex run started.")
        if notification_results:
          print(json.dumps({"draft_notifications": notification_results}, indent=2))
        return 0

      case, case_path = build_case(connection, candidate, state_dir)
      item_id = register_case(connection, candidate, case, case_path)
      run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
      run_dir = state_dir / "runs" / str(case["case_id"]) / run_stamp
      update_item(
        connection,
        item_id,
        "agent_running",
        run_dir=relative_to_root(run_dir),
        attempts=int(candidate["attempts"]) + 1,
      )

      command = [
        sys.executable,
        "scripts/run_raidbench_agent_pipeline.py",
        "--input",
        relative_to_root(case_path),
        "--output-dir",
        relative_to_root(run_dir),
        "--execute",
        "--timeout",
        str(args.stage_timeout),
      ]
      result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=args.pipeline_timeout,
        check=False,
      )
      log_path = state_dir / "logs" / f"agent-{case['case_id']}.log"
      log_path.parent.mkdir(parents=True, exist_ok=True)
      log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
      if result.returncode == 2:
        manifest_path = run_dir / "run-manifest.json"
        manifest = read_json(manifest_path) if manifest_path.exists() else {}
        if manifest.get("publish_status") == "demand_discarded":
          reason = "Demand analysis discarded a non-actionable signal"
          print(f"Demand rejected {case['case_id']}; no further Agent stages ran.")
        else:
          reason = "Publish QA blocked this case"
          print(f"QA blocked {case['case_id']}; nothing was published.")
        update_item(connection, item_id, "qa_blocked", last_error=reason)
        return 0
      if result.returncode != 0:
        error = (result.stderr or result.stdout)[-1500:]
        update_item(connection, item_id, "agent_failed", last_error=error)
        print(f"Codex pipeline failed for {case['case_id']}; recorded for an hourly retry.")
        return 0

      manifest = read_json(run_dir / "run-manifest.json")
      qa = read_json(run_dir / "05-publish-qa.json")
      guide_output = read_json(run_dir / "03-guide-writing.json")
      if manifest.get("publish_status") != "qa_passed" or qa.get("decision") != "pass" or qa.get("publish_safe") is not True:
        update_item(connection, item_id, "qa_blocked", last_error="QA artifacts did not satisfy the publish gate")
        raise AutomationError("Fail-closed publish gate rejected the Agent artifacts")

      original_guides = AGENT_GUIDES_PATH.read_bytes()
      existing_guides = read_json(AGENT_GUIDES_PATH)
      if not isinstance(existing_guides, list):
        raise AutomationError("content/agent-guides.json must contain an array")
      draft = guide_output["drafts"][0]
      guide = materialize_guide(case, draft, existing_guides)
      merged = [item for item in existing_guides if item.get("slug") != guide["slug"]]
      merged.append(guide)
      merged.sort(key=lambda item: (str(item.get("game", "")), str(item.get("slug", ""))))
      write_json_atomic(AGENT_GUIDES_PATH, merged)
      write_community_artifact(state_dir, case, guide, str(candidate["source_type"]))
      manual_draft_path: Path | None = None
      if str(candidate["source_type"]) == "reddit-json":
        manual_draft_path = write_manual_post_draft(
          state_dir,
          guide,
          source_url=str(guide["sources"][0]["url"]),
          exact_target_url=str(case["signals"][0]["signal_url"]),
          target_title=str(case["signals"][0]["signal_title"]),
        )

      try:
        dist = build_public_site(state_dir)
        deployment_url = deploy_pages(dist, guide["slug"], state_dir)
      except Exception as exc:
        restore_agent_guides(original_guides, state_dir)
        update_item(connection, item_id, "build_failed", last_error=str(exc)[-1500:])
        raise

      if env_true("RAIDBENCH_AUTO_DEPLOY"):
        published_at = utc_now()
        try:
          verify_public_page(guide["slug"])
        except Exception as exc:
          update_item(
            connection,
            item_id,
            "deployment_verification_failed",
            output_slug=guide["slug"],
            published_at=published_at,
            last_error=str(exc)[-1500:],
          )
          raise
        indexnow_result = submit_indexnow(guide["slug"], state_dir)
        final_status = "published"
      else:
        indexnow_result = "not submitted; automatic deployment disabled"
        final_status = "qa_passed_staged"
        published_at = ""

      connection.execute(
        """
        INSERT INTO guide_pages (slug, game, title, status, last_checked_at, patch_sensitive, source_notes)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(slug) DO UPDATE SET
          title = excluded.title,
          status = excluded.status,
          last_checked_at = excluded.last_checked_at,
          source_notes = excluded.source_notes
        """,
        (guide["slug"], guide["game"], guide["title"], final_status, utc_now(), guide["sourceNote"]),
      )
      connection.commit()
      update_item(
        connection,
        item_id,
        final_status,
        output_slug=guide["slug"],
        published_at=published_at,
        last_error="",
      )
      draft_id = ""
      if final_status == "published" and manual_draft_path is not None:
        draft_id = register_manual_post_draft(connection, guide, manual_draft_path)
        notification_results.extend(deliver_pending_draft_notifications(connection, state_dir))
      print(json.dumps({
        "case_id": case["case_id"],
        "status": final_status,
        "slug": guide["slug"],
        "deployment_url": deployment_url,
        "indexnow": indexnow_result,
        "manual_post_draft_id": draft_id,
        "draft_notifications": notification_results,
      }, indent=2))
      return 0
    except Exception as exc:
      if item_id:
        current = connection.execute(
          "SELECT status FROM content_automation_items WHERE id = ?",
          (item_id,),
        ).fetchone()
        if current and current["status"] in {"case_ready", "agent_running"}:
          if original_guides is not None:
            try:
              restore_agent_guides(original_guides, state_dir)
            except Exception:
              pass
          try:
            update_item(connection, item_id, "agent_failed", last_error=str(exc)[-1500:])
          except sqlite3.Error:
            pass
      raise
    finally:
      connection.close()


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run one fail-closed RaidBench automatic content cycle.")
  parser.add_argument("--database", type=Path, default=DEFAULT_DB)
  parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
  parser.add_argument("--dry-run", action="store_true", help="Select and report a candidate without running Codex or changing state.")
  parser.add_argument("--stage-timeout", type=int, default=900)
  parser.add_argument("--pipeline-timeout", type=int, default=5400)
  return parser.parse_args()


def main() -> int:
  try:
    return execute(parse_args())
  except (AutomationError, subprocess.TimeoutExpired, sqlite3.Error, OSError) as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
