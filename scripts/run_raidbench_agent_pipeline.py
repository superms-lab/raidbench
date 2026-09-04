#!/usr/bin/env python3
"""Run the fail-closed RaidBench content Agent pipeline."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "templates" / "agent-guide-case.sample.json"
DEFAULT_RUN_ROOT = ROOT / "private-data" / "agent-runs"
DEFAULT_RUNTIME_CONFIG = ROOT / "config" / "codex_agent_runtime.json"
ALLOWED_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}


@dataclass(frozen=True)
class Stage:
  key: str
  skill: str
  schema: Path
  output_name: str
  inputs: tuple[str, ...]


STAGES = (
  Stage(
    key="demand_analysis",
    skill="raidbench-demand-analysis",
    schema=ROOT / "schemas" / "agents" / "demand-analysis.schema.json",
    output_name="01-demand-analysis.json",
    inputs=("input.json",),
  ),
  Stage(
    key="patch_sentinel",
    skill="raidbench-patch-sentinel",
    schema=ROOT / "schemas" / "agents" / "patch-sentinel.schema.json",
    output_name="02-patch-sentinel.json",
    inputs=("input.json", "01-demand-analysis.json"),
  ),
  Stage(
    key="guide_writing",
    skill="raidbench-guide-writing",
    schema=ROOT / "schemas" / "agents" / "guide-writing.schema.json",
    output_name="03-guide-writing.json",
    inputs=("input.json", "01-demand-analysis.json", "02-patch-sentinel.json"),
  ),
  Stage(
    key="owner_localization",
    skill="raidbench-owner-localization",
    schema=ROOT / "schemas" / "agents" / "owner-localization.schema.json",
    output_name="04-owner-localization.json",
    inputs=("input.json", "01-demand-analysis.json", "02-patch-sentinel.json", "03-guide-writing.json"),
  ),
  Stage(
    key="publish_qa",
    skill="raidbench-publish-qa",
    schema=ROOT / "schemas" / "agents" / "publish-qa.schema.json",
    output_name="05-publish-qa.json",
    inputs=(
      "input.json",
      "01-demand-analysis.json",
      "02-patch-sentinel.json",
      "03-guide-writing.json",
      "04-owner-localization.json",
    ),
  ),
)


class ContractError(ValueError):
  """Raised when deterministic contract validation fails."""


FORBIDDEN_PHRASES = (
  "guaranteed profit",
  "guaranteed currency",
  "guaranteed loot",
  "guaranteed boss kill",
  "guaranteed rank",
  "guaranteed revenue",
  "best build in the game",
  "always best",
  "unpatched exploit",
  "dupe glitch",
  "cheat",
  "hack",
  "botting",
  "account sale",
  "sell in-game currency",
  "real money trading",
  "rmt",
  "boosting service",
)

GUIDE_DRAFT_REQUIRED_KEYS = {
  "draft_id",
  "opportunity_ids",
  "refresh_ids",
  "evidence_ids",
  "slug",
  "title",
  "meta_description",
  "hero_hook",
  "short_answer",
  "community_answer",
  "outline",
  "checklist",
  "example",
  "common_mistakes",
  "faqs",
  "related_slugs",
  "cta_policy",
  "patch_note",
  "source_note",
  "publish_priority",
  "risk_flags",
}

COMMUNITY_LINK_PATTERN = re.compile(r"https?://|www\.|raidbench(?:\.com)?|\[[^\]]+\]\([^\)]+\)", re.IGNORECASE)
COMMUNITY_CTA_PATTERN = re.compile(
  r"\b(?:visit|click|subscribe|sign up|check out)\s+(?:our|my|the)\b|\b(?:buy|purchase)\s+our\b",
  re.IGNORECASE,
)


def utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
  try:
    value = json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError as exc:
    raise ContractError(f"Missing JSON artifact: {path}") from exc
  except json.JSONDecodeError as exc:
    raise ContractError(f"Invalid JSON in {path}: {exc}") from exc
  if not isinstance(value, dict):
    raise ContractError(f"Expected a JSON object in {path}")
  return value


def write_json(path: Path, value: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(path.suffix + ".tmp")
  temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  temporary.replace(path)


def resolve_runtime(model_override: str = "") -> dict[str, str]:
  value = read_json(DEFAULT_RUNTIME_CONFIG)
  model = (model_override or str(value.get("primary_model") or "")).strip()
  effort = str(value.get("reasoning_effort") or "").strip()
  allowed_models = {
    str(value.get("primary_model") or ""),
    *[str(item) for item in value.get("fallback_models", [])],
  }
  if not model:
    raise ContractError("Codex Agent runtime requires a model")
  if model_override and model not in allowed_models:
    raise ContractError(f"Model override is outside the approved runtime contract: {model}")
  if effort not in ALLOWED_REASONING_EFFORTS:
    raise ContractError(f"Unsupported reasoning effort: {effort}")
  return {"model": model, "reasoning_effort": effort, "runtime_id": str(value.get("runtime_id") or "")}


def require_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
  missing = sorted(keys.difference(value))
  if missing:
    raise ContractError(f"{label} is missing required keys: {', '.join(missing)}")


def unique_ids(items: Any, key: str, label: str) -> set[str]:
  if not isinstance(items, list):
    raise ContractError(f"{label} must be an array")
  values: list[str] = []
  for index, item in enumerate(items):
    if not isinstance(item, dict) or not isinstance(item.get(key), str) or not item[key]:
      raise ContractError(f"{label}[{index}] requires a non-empty {key}")
    values.append(item[key])
  if len(values) != len(set(values)):
    raise ContractError(f"{label} contains duplicate {key} values")
  return set(values)


def require_references(values: Any, valid: set[str], label: str, allow_empty: bool = False) -> None:
  if not isinstance(values, list) or (not values and not allow_empty):
    raise ContractError(f"{label} must contain at least one reference")
  unknown = sorted({value for value in values if value not in valid})
  if unknown:
    raise ContractError(f"{label} contains unknown references: {', '.join(unknown)}")


def collect_text_values(value: Any, path: str = "$") -> list[tuple[str, str]]:
  if isinstance(value, str):
    return [(path, value)]
  if isinstance(value, dict):
    texts: list[tuple[str, str]] = []
    for key, child in value.items():
      texts.extend(collect_text_values(child, f"{path}.{key}"))
    return texts
  if isinstance(value, list):
    texts = []
    for index, child in enumerate(value):
      texts.extend(collect_text_values(child, f"{path}[{index}]"))
    return texts
  return []


def validate_safe_content(label: str, artifact: dict[str, Any]) -> None:
  for path, text in collect_text_values(artifact):
    normalized = " ".join(text.lower().split())
    for phrase in FORBIDDEN_PHRASES:
      if phrase in normalized:
        raise ContractError(f"{label} contains forbidden wording at {path}: {phrase}")


def validate_case(case: dict[str, Any]) -> dict[str, set[str]]:
  require_keys(case, {"case_id", "site", "run_context", "evidence", "signals", "guide_inventory", "opportunity_scorecard", "constraints"}, "case")
  if not isinstance(case["case_id"], str) or not case["case_id"].strip():
    raise ContractError("case_id must be a non-empty string")
  evidence_ids = unique_ids(case["evidence"], "evidence_id", "evidence")
  signal_ids = unique_ids(case["signals"], "signal_id", "signals")
  guide_slugs = unique_ids(case["guide_inventory"], "slug", "guide_inventory")
  for evidence in case["evidence"]:
    evidence_path = evidence.get("evidence_path")
    if evidence_path and not (ROOT / evidence_path).is_file():
      raise ContractError(f"Evidence file does not exist: {evidence_path}")
  for signal in case["signals"]:
    if signal.get("evidence_id") not in evidence_ids:
      raise ContractError(f"Signal {signal['signal_id']} references unknown evidence {signal.get('evidence_id')}")
    for field in ("pain_score", "commercial_score"):
      value = signal.get(field)
      if not isinstance(value, int) or not 0 <= value <= 5:
        raise ContractError(f"Signal {signal['signal_id']} has invalid {field}")
  scorecard = case["opportunity_scorecard"]
  require_keys(scorecard, {"opportunity_score", "score_is_deterministic", "agent_may_modify_score"}, "opportunity_scorecard")
  if scorecard["score_is_deterministic"] is not True or scorecard["agent_may_modify_score"] is not False:
    raise ContractError("The opportunity score must be deterministic and immutable to Agents")
  constraints = case["constraints"]
  for key in ("public_sources_only", "no_guaranteed_outcomes", "no_cheats_or_exploits", "no_real_money_trading"):
    if constraints.get(key) is not True:
      raise ContractError(f"constraints.{key} must be true")
  return {"evidence": evidence_ids, "signals": signal_ids, "guides": guide_slugs}


def validate_demand(case: dict[str, Any], output: dict[str, Any], ids: dict[str, set[str]]) -> set[str]:
  require_keys(output, {"case_id", "stage", "score_acknowledgement", "opportunities", "analysis_limitations"}, "demand_analysis")
  validate_safe_content("demand_analysis", output)
  if output["case_id"] != case["case_id"] or output["stage"] != "demand_analysis":
    raise ContractError("Demand analysis case_id or stage does not match the input")
  acknowledgement = output["score_acknowledgement"]
  if acknowledgement.get("opportunity_score") != case["opportunity_scorecard"]["opportunity_score"]:
    raise ContractError("Demand analysis changed the deterministic opportunity score")
  if acknowledgement.get("score_was_modified") is not False:
    raise ContractError("Demand analysis must state that the score was not modified")
  opportunity_ids = unique_ids(output["opportunities"], "opportunity_id", "demand_analysis.opportunities")
  for opportunity in output["opportunities"]:
    require_references(opportunity.get("evidence_ids"), ids["evidence"], f"{opportunity['opportunity_id']}.evidence_ids")
    require_references(opportunity.get("signal_ids"), ids["signals"], f"{opportunity['opportunity_id']}.signal_ids")
  return opportunity_ids


def demand_rejects_content(output: dict[str, Any]) -> bool:
  opportunities = output.get("opportunities") or []
  return bool(opportunities) and all(
    opportunity.get("intent_type") == "discard"
    or opportunity.get("recommended_surface") == "hold"
    for opportunity in opportunities
  )


def validate_patch(output: dict[str, Any], case_id: str, opportunity_ids: set[str], ids: dict[str, set[str]]) -> set[str]:
  require_keys(output, {"case_id", "stage", "refresh_items", "global_patch_summary"}, "patch_sentinel")
  validate_safe_content("patch_sentinel", output)
  if output["case_id"] != case_id or output["stage"] != "patch_sentinel":
    raise ContractError("Patch sentinel case_id or stage does not match the input")
  refresh_ids = unique_ids(output["refresh_items"], "refresh_id", "patch_sentinel.refresh_items")
  for refresh in output["refresh_items"]:
    require_references(refresh.get("opportunity_ids"), opportunity_ids, f"{refresh['refresh_id']}.opportunity_ids")
    require_references(refresh.get("evidence_ids"), ids["evidence"], f"{refresh['refresh_id']}.evidence_ids")
    require_references(refresh.get("affected_slugs"), ids["guides"], f"{refresh['refresh_id']}.affected_slugs", allow_empty=True)
  return refresh_ids


def validate_guides(output: dict[str, Any], case: dict[str, Any], opportunity_ids: set[str], refresh_ids: set[str], ids: dict[str, set[str]]) -> set[str]:
  require_keys(output, {"case_id", "stage", "drafts", "content_positioning"}, "guide_writing")
  validate_safe_content("guide_writing", output)
  if output["case_id"] != case["case_id"] or output["stage"] != "guide_writing":
    raise ContractError("Guide writing case_id or stage does not match the input")
  draft_ids = unique_ids(output["drafts"], "draft_id", "guide_writing.drafts")
  payment_ready = bool(case["run_context"].get("payment_ready"))
  for draft in output["drafts"]:
    require_keys(draft, GUIDE_DRAFT_REQUIRED_KEYS, f"guide_writing draft {draft.get('draft_id', '<unknown>')}")
    require_references(draft.get("opportunity_ids"), opportunity_ids, f"{draft['draft_id']}.opportunity_ids")
    require_references(draft.get("refresh_ids"), refresh_ids, f"{draft['draft_id']}.refresh_ids", allow_empty=True)
    require_references(draft.get("evidence_ids"), ids["evidence"], f"{draft['draft_id']}.evidence_ids")
    require_references(draft.get("related_slugs"), ids["guides"], f"{draft['draft_id']}.related_slugs")
    if draft.get("slug") in ids["guides"]:
      raise ContractError(f"{draft['draft_id']}.slug must be new and must not replace a human-maintained guide")
    for field in ("checklist", "common_mistakes"):
      for index, item in enumerate(draft.get(field, [])):
        if re.search(r"[a-z)]\.(?=[A-Z])", str(item)):
          raise ContractError(f"{draft['draft_id']}.{field}[{index}] combines multiple list items")
    community_answer = str(draft.get("community_answer") or "")
    if COMMUNITY_LINK_PATTERN.search(community_answer):
      raise ContractError(f"{draft['draft_id']}.community_answer must not contain links or RaidBench promotion")
    if COMMUNITY_CTA_PATTERN.search(community_answer):
      raise ContractError(f"{draft['draft_id']}.community_answer must not contain a promotional call to action")
    if not payment_ready and draft.get("cta_policy") == "owner_review_required":
      raise ContractError(f"{draft['draft_id']} cannot require paid checkout while payment_ready=false")
  return draft_ids


def validate_localization(output: dict[str, Any], case_id: str, guide_output: dict[str, Any]) -> None:
  require_keys(output, {"case_id", "stage", "owner_summary_zh", "items", "global_risk_flags_zh"}, "owner_localization")
  if output["case_id"] != case_id or output["stage"] != "owner_localization":
    raise ContractError("Owner localization case_id or stage does not match the input")
  draft_by_id = {item["draft_id"]: item for item in guide_output["drafts"]}
  localized_ids = unique_ids(output["items"], "draft_id", "owner_localization.items")
  if localized_ids != set(draft_by_id):
    raise ContractError("Owner localization draft IDs do not exactly match guide drafts")
  for item in output["items"]:
    draft = draft_by_id[item["draft_id"]]
    for field in ("opportunity_ids", "refresh_ids", "publish_priority", "cta_policy"):
      if item.get(field) != draft.get(field):
        raise ContractError(f"Owner localization changed {field} for draft {item['draft_id']}")


def validate_qa(output: dict[str, Any], case_id: str, draft_ids: set[str], evidence_ids: set[str]) -> bool:
  require_keys(output, {"case_id", "stage", "decision", "publish_safe", "checked_claims", "localization_checks", "blockers", "warnings", "owner_decision_summary_zh"}, "publish_qa")
  if output["case_id"] != case_id or output["stage"] != "publish_qa":
    raise ContractError("Publish QA case_id or stage does not match the input")
  if output["decision"] not in {"pass", "block"}:
    raise ContractError("QA decision must be pass or block")
  blockers = output["blockers"]
  if not isinstance(blockers, list):
    raise ContractError("QA blockers must be an array")
  passed = output["decision"] == "pass"
  if passed and (blockers or output["publish_safe"] is not True):
    raise ContractError("QA cannot pass with blockers or publish_safe=false")
  if not passed and output["publish_safe"] is not False:
    raise ContractError("Blocked QA must set publish_safe=false")
  localization_checks = output["localization_checks"]
  if not isinstance(localization_checks, list):
    raise ContractError("QA localization_checks must be an array")
  checked_drafts = {item.get("draft_id") for item in localization_checks if isinstance(item, dict)}
  if checked_drafts != draft_ids:
    raise ContractError("QA must include exactly one localization check for every guide draft")
  if passed and any(item.get("status") != "aligned" for item in localization_checks):
    raise ContractError("QA cannot pass with a localization mismatch")
  checked_claims = output["checked_claims"]
  if not isinstance(checked_claims, list):
    raise ContractError("QA checked_claims must be an array")
  if passed and not checked_claims:
    raise ContractError("QA pass requires at least one evidence-checked claim")
  guide_claim_drafts: set[str] = set()
  for index, claim in enumerate(checked_claims):
    if not isinstance(claim, dict):
      raise ContractError(f"QA checked_claims[{index}] must be an object")
    require_references(
      claim.get("evidence_ids"),
      evidence_ids,
      f"checked_claims[{index}].evidence_ids",
      allow_empty=not passed,
    )
    if claim.get("source_artifact") == "guide_writing" and claim.get("item_id") in draft_ids:
      guide_claim_drafts.add(str(claim["item_id"]))
    if passed and claim.get("status") != "supported":
      raise ContractError("QA cannot pass with unsupported or revision-needed claims")
  if passed and guide_claim_drafts != draft_ids:
    raise ContractError("QA pass requires at least one checked guide claim for every draft")
  return passed


def relative_to_root(path: Path) -> str:
  try:
    return str(path.resolve().relative_to(ROOT))
  except ValueError as exc:
    raise ContractError(f"Artifact must be inside the project root: {path}") from exc


def stage_prompt(stage: Stage, run_dir: Path) -> str:
  input_lines = "\n".join(f"- `{relative_to_root(run_dir / name)}`" for name in stage.inputs)
  return f"""Use ${stage.skill} for this isolated RaidBench pipeline stage.

Read only these input artifacts:
{input_lines}

The source set is closed. Do not browse the web, edit files, send messages, deploy, modify accounts, or perform external actions.
Return only the final JSON object required by the supplied output schema. Do not wrap JSON in Markdown.
"""


def run_stage(stage: Stage, run_dir: Path, codex_bin: str, runtime: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
  output_path = run_dir / stage.output_name
  event_path = run_dir / f"{stage.key}.events.jsonl"
  command = [
    codex_bin,
    "exec",
    "--enable",
    "use_legacy_landlock",
    "--ephemeral",
    "--sandbox",
    "read-only",
    "--cd",
    str(ROOT),
    "--skip-git-repo-check",
    "--output-schema",
    str(stage.schema),
    "--output-last-message",
    str(output_path),
    "--json",
    "--color",
    "never",
  ]
  command.extend([
    "--model",
    runtime["model"],
    "--config",
    f'model_reasoning_effort="{runtime["reasoning_effort"]}"',
  ])
  command.append("-")
  result = subprocess.run(
    command,
    input=stage_prompt(stage, run_dir),
    text=True,
    capture_output=True,
    timeout=timeout_seconds,
    check=False,
  )
  event_path.write_text(result.stdout, encoding="utf-8")
  if result.stderr:
    (run_dir / f"{stage.key}.stderr.log").write_text(result.stderr, encoding="utf-8")
  if result.returncode != 0:
    raise RuntimeError(f"Codex stage {stage.key} failed with exit code {result.returncode}")
  return read_json(output_path)


def build_run_dir(case_id: str, requested: Path | None) -> Path:
  if requested:
    run_dir = requested if requested.is_absolute() else ROOT / requested
  else:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = DEFAULT_RUN_ROOT / case_id / stamp
  relative_to_root(run_dir)
  run_dir.mkdir(parents=True, exist_ok=False)
  return run_dir


def dry_run_summary(case: dict[str, Any]) -> None:
  print(f"Case: {case['case_id']}")
  print("Mode: validation only; no Codex usage and no external actions")
  for number, stage in enumerate(STAGES, start=1):
    print(f"{number}. ${stage.skill} -> {stage.output_name}")
  print("PASS: input contract and all local evidence paths are valid.")


def execute(args: argparse.Namespace) -> int:
  input_path = args.input if args.input.is_absolute() else ROOT / args.input
  relative_to_root(input_path)
  case = read_json(input_path)
  ids = validate_case(case)

  if not args.execute:
    dry_run_summary(case)
    return 0

  codex_bin = shutil.which(args.codex_bin)
  if not codex_bin:
    raise RuntimeError(f"Codex executable not found: {args.codex_bin}")
  login = subprocess.run([codex_bin, "login", "status"], text=True, capture_output=True, check=False)
  if login.returncode != 0:
    raise RuntimeError("Codex is not logged in on this machine")
  runtime = resolve_runtime(args.model)

  run_dir = build_run_dir(case["case_id"], args.output_dir)
  shutil.copy2(input_path, run_dir / "input.json")
  manifest: dict[str, Any] = {
    "case_id": case["case_id"],
    "started_at": utc_now(),
    "completed_at": "",
    "mode": "codex",
    "runtime_id": runtime["runtime_id"],
    "model": runtime["model"],
    "reasoning_effort": runtime["reasoning_effort"],
    "publish_status": "blocked_until_qa_passes",
    "stages": [],
  }
  manifest_path = run_dir / "run-manifest.json"
  write_json(manifest_path, manifest)

  outputs: dict[str, dict[str, Any]] = {}
  opportunity_ids: set[str] = set()
  refresh_ids: set[str] = set()
  draft_ids: set[str] = set()
  try:
    for stage in STAGES:
      stage_record = {"stage": stage.key, "skill": stage.skill, "status": "running", "started_at": utc_now()}
      manifest["stages"].append(stage_record)
      write_json(manifest_path, manifest)
      output = run_stage(stage, run_dir, codex_bin, runtime, args.timeout)
      outputs[stage.key] = output

      if stage.key == "demand_analysis":
        opportunity_ids = validate_demand(case, output, ids)
      elif stage.key == "patch_sentinel":
        refresh_ids = validate_patch(output, case["case_id"], opportunity_ids, ids)
      elif stage.key == "guide_writing":
        draft_ids = validate_guides(output, case, opportunity_ids, refresh_ids, ids)
      elif stage.key == "owner_localization":
        validate_localization(output, case["case_id"], outputs["guide_writing"])
      elif stage.key == "publish_qa":
        passed = validate_qa(output, case["case_id"], draft_ids, ids["evidence"])
        manifest["publish_status"] = "qa_passed" if passed else "qa_blocked"

      stage_record["status"] = "completed"
      stage_record["completed_at"] = utc_now()
      stage_record["output"] = relative_to_root(run_dir / stage.output_name)
      write_json(manifest_path, manifest)

      if stage.key == "demand_analysis" and demand_rejects_content(output):
        manifest["publish_status"] = "demand_discarded"
        manifest["completed_at"] = utc_now()
        write_json(manifest_path, manifest)
        print(f"Run directory: {run_dir}")
        print("Demand analysis rejected this signal; no additional Agent stages were started.")
        return 2

    manifest["completed_at"] = utc_now()
    write_json(manifest_path, manifest)
    qa = outputs["publish_qa"]
    print(f"Run directory: {run_dir}")
    print(f"QA decision: {qa['decision']}")
    print(qa["owner_decision_summary_zh"])
    return 0 if qa["decision"] == "pass" else 2
  except Exception as exc:
    if manifest["stages"]:
      manifest["stages"][-1]["status"] = "failed"
      manifest["stages"][-1]["completed_at"] = utc_now()
      manifest["stages"][-1]["error"] = str(exc)
    manifest["completed_at"] = utc_now()
    manifest["publish_status"] = "pipeline_failed"
    write_json(manifest_path, manifest)
    raise


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Validate or execute the five-stage RaidBench content Agent pipeline.")
  parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Structured guide case JSON inside the project.")
  parser.add_argument("--execute", action="store_true", help="Run Codex stages. Without this flag, perform validation only.")
  parser.add_argument("--output-dir", type=Path, help="New output directory inside the project. Defaults to private-data/agent-runs.")
  parser.add_argument("--model", default="", help="Optional approved Codex model override. Uses config/codex_agent_runtime.json when omitted.")
  parser.add_argument("--codex-bin", default="codex", help="Codex executable name or path.")
  parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds for each Agent stage.")
  return parser.parse_args()


def main() -> int:
  try:
    return execute(parse_args())
  except (ContractError, RuntimeError, subprocess.TimeoutExpired) as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
