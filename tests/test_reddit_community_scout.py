from __future__ import annotations

import importlib.util
import json
import random
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "discover_reddit_reply_draft.py"
SPEC = importlib.util.spec_from_file_location("raidbench_reddit_community_scout", MODULE_PATH)
assert SPEC and SPEC.loader
scout = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scout
SPEC.loader.exec_module(scout)


class RaidBenchRedditCommunityScoutTests(unittest.TestCase):
  @classmethod
  def setUpClass(cls) -> None:
    cls.profiles = scout.load_game_profiles()
    cls.rust_profile = next(profile for profile in cls.profiles if profile["id"] == "rust")

  def candidate(self, now: datetime, profile: dict | None = None) -> dict[str, str]:
    selected = profile or self.rust_profile
    community = selected["communities"][0]
    return {
      "status": "candidate",
      "target_title": "What base should a casual trio build this wipe?",
      "target_reddit_url": f"https://www.reddit.com/r/{community}/comments/abc123/what_base/",
      "published_at": (now - timedelta(hours=10)).isoformat(),
      "intent_zh": "玩家希望为在线时间不一致的三人小队选择可维护的基地结构。",
      "draft_text": "Start with the base your most active player can maintain alone, then add team features only when the group is actually online. A compact two-by-one or two-by-two with an airlock, protected tool cupboard, and separated loot gives you a reliable reset point. Add a second exit and modest honeycomb before spending upkeep on a large shooting floor. Put kits and basic resources where the regular player can reach them without opening every door. When all three players are active, expand storage and flank options rather than replacing the entire core. The useful test is simple: if one person can farm a day of upkeep and recover after a loss, the base fits the group. If keeping it alive requires all three players every session, the design is already too large for the way you actually play.",
      "verification_note": "Search evidence showed an exact r/playrust thread and a current publication timestamp.",
    }

  def test_accepts_fresh_unseen_link_free_candidate(self) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    candidate = scout.validate_candidate(
      self.candidate(now), now=now, seen_thread_ids=set(), profile=self.rust_profile,
    )
    self.assertEqual(candidate["thread_id"], "abc123")

  def test_rejects_seen_thread(self) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    with self.assertRaises(scout.DiscoveryError):
      scout.validate_candidate(
        self.candidate(now), now=now, seen_thread_ids={"abc123"}, profile=self.rust_profile,
      )

  def test_rejects_stale_thread(self) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    value = self.candidate(now)
    value["published_at"] = (now - timedelta(days=9)).isoformat()
    with self.assertRaises(scout.DiscoveryError):
      scout.validate_candidate(value, now=now, seen_thread_ids=set(), profile=self.rust_profile)

  def test_rejects_a_thread_from_the_wrong_game_community(self) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    value = self.candidate(now)
    value["target_reddit_url"] = "https://www.reddit.com/r/DotA2/comments/abc123/what_base/"
    with self.assertRaises(scout.DiscoveryError):
      scout.validate_candidate(value, now=now, seen_thread_ids=set(), profile=self.rust_profile)

  def test_allows_in_game_buy_advice_but_rejects_real_promotion(self) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    value = self.candidate(now)
    value["draft_text"] = value["draft_text"].replace(
      "Start with the base",
      "Buy only the in-game equipment your current route can replace. Start with the base",
    )
    self.assertIsNotNone(
      scout.validate_candidate(value, now=now, seen_thread_ids=set(), profile=self.rust_profile),
    )
    value["draft_text"] += " Visit my website for more help."
    with self.assertRaises(scout.DiscoveryError):
      scout.validate_candidate(value, now=now, seen_thread_ids=set(), profile=self.rust_profile)

  def test_randomized_rotation_covers_all_games_without_same_day_duplicates(self) -> None:
    state: dict = {}
    randomizer = random.Random(42)
    first_day: list[str] = []
    attempted: set[str] = set()
    for _ in range(6):
      selected, queue = scout.select_game_profile(state, self.profiles, attempted, randomizer=randomizer)
      first_day.append(selected["id"])
      attempted.add(selected["id"])
      state["game_rotation_queue"] = queue
    second_day: list[str] = []
    attempted = set()
    for _ in range(6):
      selected, queue = scout.select_game_profile(state, self.profiles, attempted, randomizer=randomizer)
      second_day.append(selected["id"])
      attempted.add(selected["id"])
      state["game_rotation_queue"] = queue
    self.assertEqual(len(set(first_day)), 6)
    self.assertEqual(len(set(second_day)), 6)
    self.assertEqual(set(first_day + second_day), {profile["id"] for profile in self.profiles})

  def test_loads_seen_ids_from_state_and_drafts(self) -> None:
    with tempfile.TemporaryDirectory() as temporary:
      directory = Path(temporary)
      (directory / "draft.json").write_text(json.dumps({
        "target_reddit_url": "https://www.reddit.com/r/playrust/comments/fromdraft/question/",
      }), encoding="utf-8")
      seen = scout.load_seen_thread_ids([directory], {
        "seen_reddit_urls": ["https://www.reddit.com/r/playrust/comments/fromstate/question/"],
      })
      self.assertEqual(seen, {"fromdraft", "fromstate"})

  def test_registers_reddit_question_as_demand_only_signal(self) -> None:
    now = datetime(2026, 9, 3, 1, tzinfo=timezone.utc)
    value = self.candidate(now)
    candidate = scout.validate_candidate(
      value, now=now, seen_thread_ids=set(), profile=self.rust_profile,
    )
    with tempfile.TemporaryDirectory() as temporary:
      database = Path(temporary) / "raidbench.db"
      connection = scout.sqlite3.connect(database)
      connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      connection.close()
      signal_id = scout.register_community_demand(database, candidate, self.rust_profile, now=now)
      connection = scout.sqlite3.connect(database)
      row = connection.execute(
        "select content_sources.source_type, content_signals.game, content_signals.signal_url, content_signals.evidence_json from content_signals join content_sources on content_sources.id=content_signals.source_id where content_signals.id=?",
        (signal_id,),
      ).fetchone()
      connection.close()
    self.assertEqual(row[0], "community-web-search")
    self.assertEqual(row[1], "Rust")
    self.assertEqual(row[2], candidate["target_reddit_url"])
    self.assertTrue(json.loads(row[3])["demandOnly"])

  def test_timer_and_service_schedule_six_daily_multigame_attempts(self) -> None:
    timer = (ROOT / "deploy" / "raidbench-community-scout.timer").read_text(encoding="utf-8")
    service = (ROOT / "deploy" / "raidbench-community-scout.service").read_text(encoding="utf-8")
    self.assertIn("00,01,02,03,04,05,06,07,08,09:50:00 UTC", timer)
    self.assertIn("--daily-target 6", service)

  def test_counts_unique_reply_drafts_created_on_the_selected_day(self) -> None:
    with tempfile.TemporaryDirectory() as temporary:
      directory = Path(temporary)
      payload = {
        "draft_id": "reply_one",
        "draft_type": "reply",
        "created_at": "2026-09-04T01:00:00+00:00",
      }
      (directory / "one.json").write_text(json.dumps(payload), encoding="utf-8")
      (directory / "duplicate.json").write_text(json.dumps(payload), encoding="utf-8")
      (directory / "old.json").write_text(json.dumps({
        **payload,
        "draft_id": "reply_old",
        "created_at": "2026-09-02T01:00:00+00:00",
      }), encoding="utf-8")
      self.assertEqual(scout.count_daily_drafts([directory], "2026-09-04"), 1)


if __name__ == "__main__":
  unittest.main()
