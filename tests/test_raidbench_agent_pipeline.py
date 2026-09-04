from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run_raidbench_agent_pipeline.py"
SPEC = importlib.util.spec_from_file_location("raidbench_agent_pipeline", MODULE_PATH)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pipeline
SPEC.loader.exec_module(pipeline)


class RaidBenchAgentPipelineContractTests(unittest.TestCase):
  @classmethod
  def setUpClass(cls) -> None:
    cls.case = json.loads((ROOT / "templates" / "agent-guide-case.sample.json").read_text(encoding="utf-8"))

  def test_sample_case_is_valid(self) -> None:
    ids = pipeline.validate_case(copy.deepcopy(self.case))
    self.assertEqual(ids["evidence"], {"E-01", "E-02"})
    self.assertEqual(ids["signals"], {"S-01", "S-02", "S-03"})
    self.assertIn("poe2-outdated-build-guide-checklist", ids["guides"])

  def test_signal_unknown_evidence_is_rejected(self) -> None:
    case = copy.deepcopy(self.case)
    case["signals"][0]["evidence_id"] = "E-NOPE"
    with self.assertRaisesRegex(pipeline.ContractError, "unknown evidence"):
      pipeline.validate_case(case)

  def test_demand_cannot_change_deterministic_score(self) -> None:
    ids = pipeline.validate_case(copy.deepcopy(self.case))
    output = {
      "case_id": self.case["case_id"],
      "stage": "demand_analysis",
      "score_acknowledgement": {"opportunity_score": 99, "score_was_modified": False},
      "opportunities": [
        {
          "opportunity_id": "OP-01",
          "game": "POE2",
          "topic": "build_help",
          "player_problem": "test",
          "intent_type": "seo",
          "priority": "high",
          "evidence_ids": ["E-01"],
          "signal_ids": ["S-01"],
          "recommended_surface": "guide_page",
          "free_content_angle": "test",
          "paid_angle": "test",
          "confidence": 90,
          "risk_flags": [],
        }
      ],
      "analysis_limitations": [],
    }
    with self.assertRaisesRegex(pipeline.ContractError, "changed the deterministic opportunity score"):
      pipeline.validate_demand(self.case, output, ids)

  def test_demand_discard_stops_later_agent_stages(self) -> None:
    output = {
      "opportunities": [
        {"intent_type": "discard", "recommended_surface": "hold"},
        {"intent_type": "discard", "recommended_surface": "hold"},
      ]
    }
    self.assertTrue(pipeline.demand_rejects_content(output))
    output["opportunities"][1] = {"intent_type": "seo", "recommended_surface": "guide_page"}
    self.assertFalse(pipeline.demand_rejects_content(output))

  def test_patch_unknown_guide_slug_is_rejected(self) -> None:
    ids = pipeline.validate_case(copy.deepcopy(self.case))
    output = {
      "case_id": self.case["case_id"],
      "stage": "patch_sentinel",
      "refresh_items": [
        {
          "refresh_id": "RF-01",
          "opportunity_ids": ["OP-01"],
          "affected_slugs": ["missing-guide"],
          "evidence_ids": ["E-01"],
          "refresh_priority": "normal",
          "reason": "test",
          "claim_sensitivity": "medium",
          "recommended_action": "review",
        }
      ],
      "global_patch_summary": "test",
    }
    with self.assertRaisesRegex(pipeline.ContractError, "unknown references"):
      pipeline.validate_patch(output, self.case["case_id"], {"OP-01"}, ids)

  def test_guide_forbidden_wording_is_rejected(self) -> None:
    ids = pipeline.validate_case(copy.deepcopy(self.case))
    output = {
      "case_id": self.case["case_id"],
      "stage": "guide_writing",
      "drafts": [
        {
          "draft_id": "D-01",
          "opportunity_ids": ["OP-01"],
          "refresh_ids": ["RF-01"],
          "evidence_ids": ["E-01"],
          "slug": "poe2-test",
          "title": "Guaranteed profit guide",
          "meta_description": "test",
          "hero_hook": "test",
          "short_answer": "test",
          "community_answer": "This is a self-contained answer that explains the decision using only the supplied evidence and does not promote a website or promise a result.",
          "outline": [{"heading": "test", "purpose": "test", "bullets": ["test"]}],
          "checklist": ["one", "two", "three"],
          "example": "test",
          "common_mistakes": ["one", "two"],
          "faqs": [
            {"question": "one", "answer": "one"},
            {"question": "two", "answer": "two"},
          ],
          "related_slugs": ["poe2-outdated-build-guide-checklist"],
          "cta_policy": "free_only",
          "patch_note": "test",
          "source_note": "test",
          "publish_priority": "high",
          "risk_flags": [],
        }
      ],
      "content_positioning": "test",
    }
    with self.assertRaisesRegex(pipeline.ContractError, "forbidden wording"):
      pipeline.validate_guides(output, self.case, {"OP-01"}, {"RF-01"}, ids)

  def test_localization_must_preserve_draft_metadata(self) -> None:
    guide_output = {
      "drafts": [
        {
          "draft_id": "D-01",
          "opportunity_ids": ["OP-01"],
          "refresh_ids": ["RF-01"],
          "publish_priority": "high",
          "cta_policy": "free_only",
        }
      ]
    }
    output = {
      "case_id": self.case["case_id"],
      "stage": "owner_localization",
      "owner_summary_zh": "测试",
      "items": [
        {
          "draft_id": "D-01",
          "opportunity_ids": ["OP-01"],
          "refresh_ids": ["RF-01"],
          "publish_priority": "medium",
          "cta_policy": "free_only",
          "customer_english_summary": "test",
          "owner_chinese_summary": "测试",
          "risk_flags_zh": [],
          "recommended_owner_action_zh": "测试",
        }
      ],
      "global_risk_flags_zh": [],
    }
    with self.assertRaisesRegex(pipeline.ContractError, "changed publish_priority"):
      pipeline.validate_localization(output, self.case["case_id"], guide_output)

  def test_qa_pass_cannot_contain_blockers(self) -> None:
    output = {
      "case_id": self.case["case_id"],
      "stage": "publish_qa",
      "decision": "pass",
      "publish_safe": True,
      "checked_claims": [],
      "localization_checks": [{"draft_id": "D-01", "status": "aligned", "note": "ok"}],
      "blockers": [
        {
          "code": "UNSUPPORTED",
          "artifact": "guide_writing",
          "item_id": "D-01",
          "message": "unsupported",
          "required_action": "remove",
        }
      ],
      "warnings": [],
      "owner_decision_summary_zh": "阻止",
    }
    with self.assertRaisesRegex(pipeline.ContractError, "cannot pass with blockers"):
      pipeline.validate_qa(output, self.case["case_id"], {"D-01"}, {"E-01"})

  def test_community_answer_cannot_promote_raidbench(self) -> None:
    ids = pipeline.validate_case(copy.deepcopy(self.case))
    output = {
      "case_id": self.case["case_id"],
      "stage": "guide_writing",
      "drafts": [
        {
          "draft_id": "D-01",
          "opportunity_ids": ["OP-01"],
          "refresh_ids": [],
          "evidence_ids": ["E-01"],
          "slug": "poe2-test",
          "title": "POE2 test guide",
          "meta_description": "test",
          "hero_hook": "test",
          "short_answer": "test",
          "community_answer": "Visit RaidBench for the complete answer and the rest of this intentionally promotional test message.",
          "outline": [
            {"heading": "one", "purpose": "one", "bullets": ["one"]},
            {"heading": "two", "purpose": "two", "bullets": ["two"]},
          ],
          "checklist": ["one", "two", "three"],
          "example": "test",
          "common_mistakes": ["one", "two"],
          "faqs": [
            {"question": "one", "answer": "one"},
            {"question": "two", "answer": "two"},
          ],
          "related_slugs": ["poe2-outdated-build-guide-checklist"],
          "cta_policy": "free_only",
          "patch_note": "test",
          "source_note": "test",
          "publish_priority": "high",
          "risk_flags": [],
        }
      ],
      "content_positioning": "test",
    }
    with self.assertRaisesRegex(pipeline.ContractError, "must not contain links or RaidBench promotion"):
      pipeline.validate_guides(output, self.case, {"OP-01"}, set(), ids)

  def test_qa_pass_requires_supported_guide_claim(self) -> None:
    output = {
      "case_id": self.case["case_id"],
      "stage": "publish_qa",
      "decision": "pass",
      "publish_safe": True,
      "checked_claims": [
        {
          "claim_id": "C-01",
          "source_artifact": "guide_writing",
          "item_id": "D-01",
          "claim_text": "test",
          "evidence_ids": ["E-01"],
          "status": "unsupported",
          "reason": "test",
          "corrected_text": "",
        }
      ],
      "localization_checks": [{"draft_id": "D-01", "status": "aligned", "note": "ok"}],
      "blockers": [],
      "warnings": [],
      "owner_decision_summary_zh": "测试",
    }
    with self.assertRaisesRegex(pipeline.ContractError, "cannot pass with unsupported"):
      pipeline.validate_qa(output, self.case["case_id"], {"D-01"}, {"E-01"})


if __name__ == "__main__":
  unittest.main()
