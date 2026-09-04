from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run_patch_refresh_check.py"
SPEC = importlib.util.spec_from_file_location("raidbench_patch_refresh", MODULE_PATH)
assert SPEC and SPEC.loader
refresh = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = refresh
SPEC.loader.exec_module(refresh)


class PatchRefreshCheckTests(unittest.TestCase):
  def test_normalized_hash_ignores_script_and_whitespace(self) -> None:
    first = refresh.normalized_hash("<main>Hello   world</main><script>one()</script>")
    second = refresh.normalized_hash("<main>Hello world</main><script>two()</script>")
    self.assertEqual(first, second)

  def test_rotation_is_deterministic_for_each_weekday_slot(self) -> None:
    entries = [{"slug": str(index)} for index in range(6)]
    monday = refresh.choose_entry(entries, datetime(2026, 9, 7, tzinfo=timezone.utc))
    wednesday = refresh.choose_entry(entries, datetime(2026, 9, 9, tzinfo=timezone.utc))
    friday = refresh.choose_entry(entries, datetime(2026, 9, 11, tzinfo=timezone.utc))
    self.assertEqual(len({monday["slug"], wednesday["slug"], friday["slug"]}), 3)


if __name__ == "__main__":
  unittest.main()
