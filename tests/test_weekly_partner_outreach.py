from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "discover_weekly_partner_outreach.py"
SPEC = importlib.util.spec_from_file_location("raidbench_weekly_partner_outreach", MODULE_PATH)
assert SPEC and SPEC.loader
partners = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = partners
SPEC.loader.exec_module(partners)


class WeeklyPartnerOutreachTests(unittest.TestCase):
  def test_decodes_cloudflare_email_protection(self) -> None:
    self.assertEqual(
      partners.decode_cfemail("52212722223d20261220272126303321373637213b353c217c313d3f"),
      "support@rustbasedesigns.com",
    )

  def test_week_key_uses_iso_week(self) -> None:
    self.assertEqual(partners.week_key(datetime(2026, 9, 3, tzinfo=timezone.utc)), "2026-W36")

  def test_visible_emails_includes_plain_and_protected(self) -> None:
    html = '<a href="mailto:partners@example.com">Mail</a><span data-cfemail="52212722223d20261220272126303321373637213b353c217c313d3f"></span>'
    self.assertEqual(partners.visible_emails(html), {"partners@example.com", "support@rustbasedesigns.com"})


if __name__ == "__main__":
  unittest.main()
