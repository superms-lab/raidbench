from __future__ import annotations

import importlib.util
import json
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
  def candidate(self, now: datetime) -> dict[str, str]:
    return {
      "status": "candidate",
      "target_title": "What base should a casual trio build this wipe?",
      "target_reddit_url": "https://www.reddit.com/r/playrust/comments/abc123/what_base/",
      "published_at": (now - timedelta(hours=10)).isoformat(),
      "intent_zh": "玩家希望为在线时间不一致的三人小队选择可维护的基地结构。",
      "draft_text": "Start with the base your most active player can maintain alone, then add team features only when the group is actually online. A compact two-by-one or two-by-two with an airlock, protected tool cupboard, and separated loot gives you a reliable reset point. Add a second exit and modest honeycomb before spending upkeep on a large shooting floor. Put kits and basic resources where the regular player can reach them without opening every door. When all three players are active, expand storage and flank options rather than replacing the entire core. The useful test is simple: if one person can farm a day of upkeep and recover after a loss, the base fits the group. If keeping it alive requires all three players every session, the design is already too large for the way you actually play.",
      "verification_note": "Search evidence showed an exact r/playrust thread and a current publication timestamp.",
    }

  def test_accepts_fresh_unseen_link_free_candidate(self) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    candidate = scout.validate_candidate(self.candidate(now), now=now, seen_thread_ids=set())
    self.assertEqual(candidate["thread_id"], "abc123")

  def test_rejects_seen_thread(self) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    with self.assertRaises(scout.DiscoveryError):
      scout.validate_candidate(self.candidate(now), now=now, seen_thread_ids={"abc123"})

  def test_rejects_stale_thread(self) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    value = self.candidate(now)
    value["published_at"] = (now - timedelta(days=9)).isoformat()
    with self.assertRaises(scout.DiscoveryError):
      scout.validate_candidate(value, now=now, seen_thread_ids=set())

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
    candidate = scout.validate_candidate(value, now=now, seen_thread_ids=set())
    with tempfile.TemporaryDirectory() as temporary:
      database = Path(temporary) / "raidbench.db"
      connection = scout.sqlite3.connect(database)
      connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      connection.close()
      signal_id = scout.register_community_demand(database, candidate, now=now)
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


if __name__ == "__main__":
  unittest.main()
