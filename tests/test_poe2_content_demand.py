from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "discover_poe2_content_demand.py"
SPEC = importlib.util.spec_from_file_location("raidbench_poe2_demand", MODULE_PATH)
assert SPEC and SPEC.loader
demand = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = demand
SPEC.loader.exec_module(demand)


class Poe2ContentDemandTests(unittest.TestCase):
  def test_validates_fresh_exact_thread(self) -> None:
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    result = demand.validate({
      "status": "candidate",
      "target_title": "How should I fix this POE2 build?",
      "target_url": "https://www.reddit.com/r/PathOfExile2/comments/abc123/build_help/",
      "published_at": (now - timedelta(hours=6)).isoformat(),
      "intent_zh": "玩家希望确认当前版本中应该优先修复哪些构筑问题。",
      "topic": "build_help",
    }, now, set())
    self.assertEqual(result["thread_id"], "abc123")

  def test_rejects_wrong_subreddit(self) -> None:
    with self.assertRaises(demand.DemandError):
      demand.canonical_url("https://www.reddit.com/r/playrust/comments/abc123/question/")


if __name__ == "__main__":
  unittest.main()
