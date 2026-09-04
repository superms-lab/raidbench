from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "send_feishu_draft_notification.py"
SPEC = importlib.util.spec_from_file_location("raidbench_feishu_notifier", MODULE_PATH)
assert SPEC and SPEC.loader
notifier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = notifier
SPEC.loader.exec_module(notifier)


class RaidBenchFeishuNotifierTests(unittest.TestCase):
  def test_builds_signed_interactive_card(self) -> None:
    draft = self.draft_fixture()
    payload = notifier.build_card(draft, timestamp=1599360473, secret="test-secret")
    self.assertEqual(payload["msg_type"], "interactive")
    self.assertEqual(payload["timestamp"], "1599360473")
    self.assertTrue(payload["sign"])
    actions = payload["card"]["elements"][-1]["actions"]
    self.assertEqual(len(actions), 1)
    self.assertEqual(actions[0]["url"], draft["target_reddit_url"])
    self.assertIn(draft["draft_text"], json.dumps(payload, ensure_ascii=False))

  def test_rejects_search_page_as_reddit_target(self) -> None:
    draft = self.draft_fixture()
    draft["target_reddit_url"] = "https://www.reddit.com/search/?q=palworld+mods"
    with tempfile.TemporaryDirectory() as temporary:
      path = Path(temporary) / "draft.json"
      path.write_text(json.dumps(draft), encoding="utf-8")
      with self.assertRaisesRegex(notifier.NotificationError, "exact Reddit thread"):
        notifier.read_draft(path)

  def test_rejects_non_feishu_webhook(self) -> None:
    with self.assertRaisesRegex(notifier.NotificationError, "official Feishu"):
      notifier.validate_webhook_url("https://example.com/open-apis/bot/v2/hook/test")

  def test_rejects_promotional_or_linked_draft_text(self) -> None:
    draft = self.draft_fixture()
    draft["draft_text"] = "Read the full answer at https://raidbench.com/example"
    with tempfile.TemporaryDirectory() as temporary:
      path = Path(temporary) / "draft.json"
      path.write_text(json.dumps(draft), encoding="utf-8")
      with self.assertRaisesRegex(notifier.NotificationError, "link-free"):
        notifier.read_draft(path)

  @staticmethod
  def draft_fixture() -> dict:
    return {
      "draft_id": "post_test",
      "game": "Palworld",
      "guide_title": "Palworld mod stability checklist",
      "guide_url": "https://raidbench.com/pages/palworld-test",
      "source_url": "https://store.steampowered.com/news/app/1623730/view/test",
      "target_title": "Mods stopped working after the latest update",
      "target_reddit_url": "https://www.reddit.com/r/Palworld/comments/abc123/mods_stopped_working/",
      "draft_text": "Record one repeatable symptom, update the PC build, and compare the same scenario before changing the mod stack.",
    }


if __name__ == "__main__":
  unittest.main()
