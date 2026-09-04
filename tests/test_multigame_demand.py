from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "discover_multigame_demand.py"
SPEC = importlib.util.spec_from_file_location("raidbench_multigame_demand", MODULE_PATH)
assert SPEC and SPEC.loader
demand = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = demand
SPEC.loader.exec_module(demand)


class MultiGameDemandTests(unittest.TestCase):
  def setUp(self) -> None:
    self.games, self.profiles = demand.load_configuration()
    self.now = datetime.now(timezone.utc).replace(microsecond=0)

  def test_all_games_have_one_demand_profile(self) -> None:
    self.assertEqual(len(self.games), 12)
    self.assertEqual(set(self.games), set(self.profiles))

  def test_reddit_thread_is_canonicalized_without_query_data(self) -> None:
    url = demand.canonical_thread_url(
      "https://old.reddit.com/r/GlobalOffensive/comments/abc123/Help_Me/?utm_source=test",
      "reddit",
      self.profiles["counter-strike-2"],
    )
    self.assertEqual(url, "https://www.reddit.com/r/GlobalOffensive/comments/abc123/help_me/")

  def test_wrong_reddit_community_is_rejected(self) -> None:
    with self.assertRaises(demand.DemandError):
      demand.canonical_thread_url(
        "https://www.reddit.com/r/gaming/comments/abc123/help/",
        "reddit",
        self.profiles["counter-strike-2"],
      )

  def test_exact_steam_discussion_is_allowed(self) -> None:
    url = demand.canonical_thread_url(
      "https://steamcommunity.com/app/570/discussions/0/1234567890/?ctp=2",
      "steam",
      self.profiles["dota-2"],
    )
    self.assertEqual(url, "https://steamcommunity.com/app/570/discussions/0/1234567890/")

  def test_stale_candidate_is_rejected(self) -> None:
    value = {
      "status": "candidate",
      "game_id": "dota-2",
      "source_kind": "steam",
      "target_title": "Which item should I buy for this matchup?",
      "target_url": "https://steamcommunity.com/app/570/discussions/0/1234567890/",
      "published_at": demand.iso(self.now - timedelta(days=10)),
      "topic": "item_choice",
      "intent_zh": "玩家希望根据当前对局阵容选择更合适的装备。",
      "decision_cost": "medium",
      "patch_sensitive": True,
    }
    with self.assertRaises(demand.DemandError):
      demand.validate_result(value, self.games["dota-2"], self.profiles["dota-2"], self.now)

  def test_registration_deduplicates_similar_questions(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      database = Path(temporary) / "test.db"
      connection = sqlite3.connect(database)
      connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      game = self.games["dota-2"]
      source = self.profiles["dota-2"]
      connection.execute(
        "insert into game_catalog values (?,?,?,?,?,?,?,?,?)",
        (game["id"], game["name"], game["shortName"], game["genre"], game["status"], 0, "planned", "1.0.0", demand.iso(self.now)),
      )
      connection.execute(
        "insert into content_sources (id,game,source_type,url,cadence,active,notes) values (?,?,?,?,?,0,'test')",
        (source["id"], game["shortName"], "community-web-search", source["url"], "24h"),
      )
      connection.commit()
      connection.close()
      first = {
        "game_id": "dota-2", "source_id": source["id"], "source_kind": "steam",
        "target_title": "Which item should I buy for this difficult lane matchup?",
        "target_url": "https://steamcommunity.com/app/570/discussions/0/1234567890/",
        "published_at": demand.iso(self.now), "topic": "item_choice",
        "intent_zh": "玩家希望针对当前对线和敌方阵容选择装备。", "decision_cost": "medium", "patch_sensitive": True,
      }
      second = {**first, "target_title": "Which item should I buy for this difficult lane matchup now?", "target_url": "https://steamcommunity.com/app/570/discussions/0/1234567891/"}
      first_id, _ = demand.register_candidate(database, first, self.now)
      second_id, _ = demand.register_candidate(database, second, self.now)
      connection = sqlite3.connect(database)
      count, occurrences = connection.execute("select count(*),max(occurrence_count) from demand_backlog").fetchone()
      connection.close()
    self.assertEqual(first_id, second_id)
    self.assertEqual(count, 1)
    self.assertEqual(occurrences, 2)

  def test_existing_content_signal_removes_redundant_backlog_item(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      database = Path(temporary) / "test.db"
      connection = sqlite3.connect(database)
      connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      game = self.games["project-zomboid"]
      source = self.profiles["project-zomboid"]
      timestamp = demand.iso(self.now)
      url = "https://www.reddit.com/r/projectzomboid/comments/abc123/example/"
      connection.execute("insert into game_catalog values (?,?,?,?,?,?,?,?,?)", (game["id"], game["name"], game["shortName"], game["genre"], game["status"], 0, "planned", "1.0.0", timestamp))
      connection.execute("insert into content_sources (id,game,source_type,url,cadence,active,notes) values (?,?,?,?,?,0,'test')", (source["id"], game["shortName"], "community-web-search", source["url"], "24h"))
      connection.execute("insert into agent_runs (id,run_type,status,started_at,summary_json) values ('run','community','completed',?,'{}')", (timestamp,))
      connection.execute("insert into content_signals (id,run_id,source_id,game,topic,signal_title,signal_url,created_at) values ('signal','run',?,?,?,?,?,?)", (source["id"], game["shortName"], "patch", "Example question", url, timestamp))
      connection.execute("insert into demand_backlog (id,game_id,fingerprint,source_id,source_type,source_url,source_title,normalized_question,topic,first_seen_at,last_seen_at) values ('demand',?,?,?,?,?,?,?,?,?,?)", (game["id"], "fingerprint", source["id"], "community-web-search", url, "Example question", "example question", "patch", timestamp, timestamp))
      connection.commit()
      connection.close()
      removed = demand.reconcile_existing_signals(database)
      known = demand.known_urls_by_game(database)
      connection = sqlite3.connect(database)
      remaining = connection.execute("select count(*) from demand_backlog").fetchone()[0]
      connection.close()
    self.assertEqual(removed, 1)
    self.assertEqual(remaining, 0)
    self.assertIn(url, known[game["id"]])

  def test_historical_reddit_draft_is_included_in_global_dedup(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      draft_dir = Path(temporary)
      url = "https://www.reddit.com/r/playrust/comments/abc123/example/"
      (draft_dir / "reply.json").write_text(json.dumps({"game": "Rust", "target_reddit_url": url}), encoding="utf-8")
      urls = demand.draft_urls_by_game(draft_dir)
    self.assertEqual(urls, {"rust": {url}})


if __name__ == "__main__":
  unittest.main()
