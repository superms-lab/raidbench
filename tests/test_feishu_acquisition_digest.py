from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "send_feishu_acquisition_digest.py"
SPEC = importlib.util.spec_from_file_location("raidbench_acquisition_digest", MODULE_PATH)
assert SPEC and SPEC.loader
digest = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = digest
SPEC.loader.exec_module(digest)


class RaidBenchAcquisitionDigestTests(unittest.TestCase):
  def test_refreshes_traffic_from_the_protected_summary_endpoint(self) -> None:
    class FakeResponse:
      def __enter__(self):
        return self

      def __exit__(self, *_args):
        return False

      def read(self):
        return json.dumps({"metrics": {"today": 12}, "topPages": [], "funnel": {}}).encode()

    previous_key = os.environ.get("RAIDBENCH_EDGE_ORIGIN_KEY")
    original_urlopen = digest.urlopen
    os.environ["RAIDBENCH_EDGE_ORIGIN_KEY"] = "private-test-key"
    digest.urlopen = lambda request, timeout: FakeResponse()
    try:
      with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "traffic.json"
        digest.refresh_traffic_dashboard(path)
        self.assertEqual(json.loads(path.read_text())["metrics"]["today"], 12)
    finally:
      digest.urlopen = original_urlopen
      if previous_key is None:
        os.environ.pop("RAIDBENCH_EDGE_ORIGIN_KEY", None)
      else:
        os.environ["RAIDBENCH_EDGE_ORIGIN_KEY"] = previous_key

  def test_loads_pending_reply_and_builds_at_all_card(self) -> None:
    with tempfile.TemporaryDirectory() as temporary:
      directory = Path(temporary)
      (directory / "reply.json").write_text(json.dumps({
        "draft_id": "reply_test",
        "draft_type": "reply",
        "game": "Rust",
        "target_title": "How much sulfur?",
        "target_reddit_url": "https://www.reddit.com/r/playrust/comments/abc123/how_much_sulfur/",
        "intent_zh": "新玩家希望判断第一次突袭的资源量。",
        "draft_text": "Count the visible route first and keep a stop condition.",
        "status": "ready_for_reddit_reply",
        "created_at": "2026-08-23T00:00:00+00:00",
      }), encoding="utf-8")
      drafts = digest.load_pending_drafts([directory])
      payload = digest.build_digest_card(drafts, signed_at=1599360473, secret="secret")
      self.assertEqual(len(drafts), 1)
      self.assertEqual(payload["msg_type"], "interactive")
      self.assertEqual(payload["timestamp"], "1599360473")
      content = "\n".join(
        element.get("text", {}).get("content", "")
        for element in payload["card"]["elements"]
        if element.get("tag") == "div"
      )
      self.assertIn("<at id=all></at>", content)
      self.assertIn("Count the visible route", content)

  def test_terminal_drafts_are_not_repeated(self) -> None:
    with tempfile.TemporaryDirectory() as temporary:
      directory = Path(temporary)
      (directory / "done.json").write_text(json.dumps({
        "draft_id": "done",
        "draft_type": "reply",
        "target_reddit_url": "https://www.reddit.com/r/playrust/comments/abc123/done/",
        "status": "replied",
      }), encoding="utf-8")
      self.assertEqual(digest.load_pending_drafts([directory]), [])

  def test_duplicate_draft_keeps_newest_copy(self) -> None:
    with tempfile.TemporaryDirectory() as temporary:
      root = Path(temporary)
      old_directory = root / "old"
      new_directory = root / "new"
      old_directory.mkdir()
      new_directory.mkdir()
      base = {
        "draft_id": "profile_launch",
        "draft_type": "profile_post",
        "target_url": "https://www.reddit.com/submit?type=self",
        "status": "ready_for_owner_review",
      }
      (old_directory / "profile.json").write_text(json.dumps({
        **base,
        "post_title": "Old copy",
        "created_at": "2026-08-23T01:00:00+00:00",
        "updated_at": "2026-08-23T01:00:00+00:00",
      }), encoding="utf-8")
      (new_directory / "profile.json").write_text(json.dumps({
        **base,
        "post_title": "New copy",
        "created_at": "2026-08-28T01:00:00+00:00",
        "updated_at": "2026-08-28T01:00:00+00:00",
      }), encoding="utf-8")
      drafts = digest.load_pending_drafts([new_directory, old_directory])
      self.assertEqual(drafts[0]["post_title"], "New copy")

  def test_newest_unnotified_reply_is_selected(self) -> None:
    drafts = [{
      "draft_id": "reply_new",
      "draft_type": "reply",
      "created_at": "2026-08-24T12:00:00+00:00",
    }, {
      "draft_id": "reply_old",
      "draft_type": "reply",
      "created_at": "2026-08-23T12:00:00+00:00",
    }]
    original_local_day = digest.local_day
    digest.local_day = lambda: "2026-08-24"
    try:
      selected = digest.select_unnotified_draft(drafts, {"last_selected_draft": "reply_old"})
      self.assertEqual(selected["draft_id"], "reply_new")
    finally:
      digest.local_day = original_local_day

  def test_previously_notified_drafts_are_not_repeated(self) -> None:
    today = digest.utc_now()
    drafts = [
      {"draft_id": "reply_one", "created_at": today},
      {"draft_id": "reply_two", "created_at": today},
    ]
    selected = digest.select_unnotified_draft(
      drafts,
      {"notified_draft_ids": ["reply_one", "reply_two"]},
    )
    self.assertIsNone(selected)

  def test_selects_up_to_three_current_unnotified_drafts(self) -> None:
    drafts = [
      {"draft_id": f"reply_{index}", "created_at": f"2026-08-24T0{index}:00:00+00:00"}
      for index in range(1, 5)
    ]
    original_local_day = digest.local_day
    digest.local_day = lambda: "2026-08-24"
    try:
      selected = digest.select_unnotified_drafts(drafts, {"notified_draft_ids": ["reply_1"]}, limit=3)
    finally:
      digest.local_day = original_local_day
    self.assertEqual([draft["draft_id"] for draft in selected], ["reply_2", "reply_3", "reply_4"])

  def test_builds_three_draft_card_and_email(self) -> None:
    drafts = [{
      "draft_id": f"reply_{index}",
      "draft_type": "reply",
      "target_title": f"Question {index}",
      "target_reddit_url": f"https://www.reddit.com/r/playrust/comments/abc12{index}/question/",
      "intent_zh": "玩家希望获得具体建议。",
      "draft_text": f"Helpful answer {index}.",
    } for index in range(1, 4)]
    payload = digest.build_digest_card(drafts)
    self.assertIn("3 条待处理", payload["card"]["header"]["title"]["content"])
    self.assertEqual(sum(element.get("tag") == "action" for element in payload["card"]["elements"]), 3)
    subject, body = digest.build_digest_email(drafts)
    self.assertIn("3 条", subject)
    self.assertIn("Question 3", body)

  def test_daily_card_includes_game_labels_and_first_party_traffic(self) -> None:
    drafts = [{
      "draft_id": "reply_poe2_test",
      "draft_type": "reply",
      "game": "POE2",
      "target_title": "How should I fix this build?",
      "target_reddit_url": "https://www.reddit.com/r/PathOfExile2/comments/abc123/build_help/",
      "intent_zh": "玩家希望定位构筑问题。",
      "draft_text": "Check defenses before replacing every damage item.",
    }]
    traffic = {
      "metrics": {"today": 21, "last7Days": 80, "last30Days": 330},
      "daily": [],
      "topPages": [{"path": "/games/poe2/", "views": 18}],
      "funnel": {"accountEntries": 3, "checkoutStarts": 1, "paymentSuccesses": 0},
    }
    payload = digest.build_digest_card(drafts, traffic=traffic)
    content = "\n".join(
      element.get("text", {}).get("content", "")
      for element in payload["card"]["elements"]
      if element.get("tag") == "div"
    )
    self.assertIn("[POE2]", content)
    self.assertIn("今日 **21**", content)
    self.assertIn("发起结账 **1**", content)
    self.assertIn("`/games/poe2/` 18", content)

  def test_yesterdays_unnotified_draft_is_not_recycled(self) -> None:
    drafts = [{
      "draft_id": "reply_yesterday",
      "draft_type": "reply",
      "created_at": "2026-08-23T01:00:00+00:00",
    }]
    original_local_day = digest.local_day
    digest.local_day = lambda: "2026-08-24"
    try:
      self.assertIsNone(digest.select_unnotified_draft(drafts, {}))
    finally:
      digest.local_day = original_local_day

  def test_builds_plain_text_email_for_pending_reply(self) -> None:
    subject, body = digest.build_digest_email([{
      "draft_id": "reply_test",
      "draft_type": "reply",
      "target_title": "How much sulfur?",
      "target_reddit_url": "https://www.reddit.com/r/playrust/comments/abc123/how_much_sulfur/",
      "intent_zh": "确认第一次突袭需要多少资源。",
      "draft_text": "Count the visible route first.",
    }])
    self.assertIn("Reddit 内容待发布", subject)
    self.assertIn("https://www.reddit.com/r/playrust/comments/abc123/how_much_sulfur/", body)
    self.assertIn("Count the visible route first.", body)


if __name__ == "__main__":
  unittest.main()
