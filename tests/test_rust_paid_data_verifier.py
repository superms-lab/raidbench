from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_rust_paid_data",
    ROOT / "scripts" / "verify_rust_paid_data.py",
)
assert SPEC and SPEC.loader
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class RustPaidDataVerifierTests(unittest.TestCase):
    def test_parses_latest_patch(self) -> None:
        source = """
        <div class="changes-container">
          <span class="subtitle">Patch Name</span>
          <a href="/news/common-ground" class="title">Common Ground</a>
          <a href="/changelist/4043">Thursday, July 2, 2026</a>
        </div>
        """
        self.assertEqual(
            VERIFIER.parse_latest_patch(source),
            {"id": "4043", "name": "Common Ground", "date": "2026-07-02"},
        )

    def test_parses_latest_patch_with_day_before_month(self) -> None:
        source = """
        <div class="changes-container">
          <span class="subtitle">Patch Name</span>
          <a href="/news/power-trip" class="title">Power Trip</a>
          <a href="/changelist/4044" class="date">Thursday, 06 August 2026</a>
        </div>
        """
        self.assertEqual(
            VERIFIER.parse_latest_patch(source),
            {"id": "4044", "name": "Power Trip", "date": "2026-08-06"},
        )

    def test_parses_monitored_counts(self) -> None:
        source = """
        const COUNTS = {
          c4: { 'sheet-door':1, 'armored-door':3 },
          rocket: { 'sheet-door':2, 'armored-door':5 },
          satchel: { 'sheet-door':4, 'armored-door':15 },
          'expl-556': { 'sheet-door':63, 'armored-door':250 }
        };
        """
        counts = VERIFIER.parse_count_table(source)
        self.assertEqual(counts["rocket"]["armored-door"], 5)
        self.assertEqual(counts["expl-556"]["sheet-door"], 63)

    def test_writes_fail_closed_status_bound_to_data_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_path = Path(temporary) / "rust-data.json"
            status_path = Path(temporary) / "status.json"
            data = {
                "verifiedAt": "2026-09-03",
                "verification": {"latestOfficialChangelistId": "4044"},
            }
            data_path.write_text(json.dumps(data))
            VERIFIER.write_verification_status(
                status_path,
                data_path=data_path,
                data=data,
                result={
                    "ok": False,
                    "checkedAt": "2026-09-04T00:00:00+00:00",
                    "latestOfficialPatch": {"id": "4045", "name": "Breach and Clear"},
                    "errors": ["New patch requires review."],
                },
            )
            status = json.loads(status_path.read_text())
            self.assertEqual(status["status"], "blocked")
            self.assertEqual(status["dataChangelistId"], "4044")
            self.assertEqual(status["latestOfficialChangelistId"], "4045")
            self.assertEqual(status["dataSha256"], VERIFIER.file_sha256(data_path))
            self.assertEqual(status["errors"], ["New patch requires review."])


if __name__ == "__main__":
    unittest.main()
