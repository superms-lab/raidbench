from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "send_partner_outreach.py"
SPEC = importlib.util.spec_from_file_location("raidbench_partner_outreach", MODULE_PATH)
assert SPEC and SPEC.loader
outreach = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = outreach
SPEC.loader.exec_module(outreach)


class PartnerOutreachTests(unittest.TestCase):
  def test_validates_bounded_https_queue(self) -> None:
    queue = outreach.validate_queue({
      "campaign_id": "test",
      "messages": [{
        "message_id": "one",
        "recipient": "partner@example.com",
        "subject": "Useful free tool",
        "source_url": "https://example.com/contact",
        "text_body": "Hello from RaidBench.",
      }],
    })
    self.assertEqual(queue["messages"][0]["message_id"], "one")

  def test_rejects_duplicate_message_ids(self) -> None:
    message = {
      "message_id": "duplicate",
      "recipient": "partner@example.com",
      "subject": "Useful free tool",
      "source_url": "https://example.com/contact",
      "text_body": "Hello from RaidBench.",
    }
    with self.assertRaises(outreach.OutreachError):
      outreach.validate_queue({"campaign_id": "test", "messages": [message, dict(message)]})


if __name__ == "__main__":
  unittest.main()
