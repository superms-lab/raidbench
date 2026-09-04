#!/usr/bin/env python3
"""Recover a QA-passed RaidBench run whose build or deploy bookkeeping failed."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import run_automatic_content_pipeline as pipeline


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Recover one QA-passed content run.")
  parser.add_argument("--item-id", required=True)
  parser.add_argument("--run-dir", type=Path, required=True)
  parser.add_argument("--database", type=Path, required=True)
  parser.add_argument("--state-dir", type=Path, required=True)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    run_dir = args.run_dir if args.run_dir.is_absolute() else pipeline.ROOT / args.run_dir
    pipeline.relative_to_root(run_dir)
    state_dir = args.state_dir if args.state_dir.is_absolute() else pipeline.ROOT / args.state_dir
    pipeline.relative_to_root(state_dir)
    case = pipeline.read_json(run_dir / "input.json")
    manifest = pipeline.read_json(run_dir / "run-manifest.json")
    qa = pipeline.read_json(run_dir / "05-publish-qa.json")
    guide_output = pipeline.read_json(run_dir / "03-guide-writing.json")
    if manifest.get("publish_status") != "qa_passed" or qa.get("decision") != "pass" or qa.get("publish_safe") is not True:
      raise pipeline.AutomationError("Selected recovery run did not pass publication QA")

    connection = pipeline.open_database(args.database)
    row = connection.execute(
      "SELECT id, signal_id, status FROM content_automation_items WHERE id = ?",
      (args.item_id,),
    ).fetchone()
    if not row or row["status"] not in {"build_failed", "qa_blocked", "deployment_verification_failed"}:
      raise pipeline.AutomationError("Recovery item is missing or is not in a recoverable status")

    original_guides = pipeline.AGENT_GUIDES_PATH.read_bytes()
    existing_guides = pipeline.read_json(pipeline.AGENT_GUIDES_PATH)
    if not isinstance(existing_guides, list):
      raise pipeline.AutomationError("content/agent-guides.json must contain an array")
    guide = pipeline.materialize_guide(case, guide_output["drafts"][0], existing_guides)
    merged = [item for item in existing_guides if item.get("slug") != guide["slug"]]
    merged.append(guide)
    merged.sort(key=lambda item: (str(item.get("game", "")), str(item.get("slug", ""))))
    pipeline.write_json_atomic(pipeline.AGENT_GUIDES_PATH, merged)
    try:
      dist = pipeline.build_public_site(state_dir)
      deployment_url = pipeline.deploy_pages(dist, guide["slug"], state_dir)
      published_at = pipeline.utc_now()
      if pipeline.env_true("RAIDBENCH_AUTO_DEPLOY"):
        pipeline.verify_public_page(guide["slug"])
        pipeline.submit_indexnow(guide["slug"], state_dir)
        final_status = "published"
      else:
        final_status = "qa_passed_staged"
        published_at = ""
    except Exception:
      pipeline.restore_agent_guides(original_guides, state_dir)
      raise

    connection.execute(
      """
      INSERT INTO guide_pages (slug, game, title, status, last_checked_at, patch_sensitive, source_notes)
      VALUES (?, ?, ?, ?, ?, 1, ?)
      ON CONFLICT(slug) DO UPDATE SET
        title=excluded.title, status=excluded.status,
        last_checked_at=excluded.last_checked_at, source_notes=excluded.source_notes
      """,
      (guide["slug"], guide["game"], guide["title"], final_status, pipeline.utc_now(), guide["sourceNote"]),
    )
    connection.commit()
    pipeline.update_item(
      connection,
      args.item_id,
      final_status,
      run_dir=pipeline.relative_to_root(run_dir),
      output_slug=guide["slug"],
      published_at=published_at,
      last_error="",
    )
    connection.close()
    print({"status": final_status, "slug": guide["slug"], "deployment_url": deployment_url})
    return 0
  except (pipeline.AutomationError, OSError, KeyError, IndexError) as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
