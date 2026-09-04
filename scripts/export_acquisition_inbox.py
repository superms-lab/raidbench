#!/usr/bin/env python3
"""Export or update private RaidBench community acquisition drafts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"published", "replied", "cancelled", "rejected"}


def utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
  value = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(value, dict):
    raise ValueError(f"Draft must be an object: {path}")
  return value


def draft_files(directories: list[Path]) -> dict[str, Path]:
  files: dict[str, Path] = {}
  for directory in directories:
    if not directory.is_dir():
      continue
    for path in sorted(directory.glob("*.json")):
      draft = read_json(path)
      draft_id = str(draft.get("draft_id") or "")
      if draft_id:
        files[draft_id] = path
  return files


def export(directories: list[Path], digest_state: Path | None) -> dict[str, Any]:
  rows = []
  for draft_id, path in draft_files(directories).items():
    draft = read_json(path)
    rows.append({
      "draftId": draft_id,
      "draftType": str(draft.get("draft_type") or "reply"),
      "game": str(draft.get("game") or ""),
      "targetTitle": str(draft.get("target_title") or draft.get("post_title") or ""),
      "targetUrl": str(draft.get("target_reddit_url") or draft.get("target_url") or ""),
      "intentZh": str(draft.get("intent_zh") or ""),
      "draftText": str(draft.get("draft_text") or ""),
      "status": str(draft.get("status") or "draft"),
      "createdAt": str(draft.get("created_at") or ""),
      "updatedAt": str(draft.get("updated_at") or ""),
      "actionRequired": str(draft.get("status") or "") not in TERMINAL_STATUSES,
    })
  rows.sort(key=lambda row: (
    not row["actionRequired"],
    row["draftType"] != "reply",
    row["createdAt"],
    row["draftId"],
  ))
  digest = {}
  if digest_state and digest_state.is_file():
    digest = read_json(digest_state)
  return {"generatedAt": utc_now(), "digest": digest, "drafts": rows}


def mark(directories: list[Path], draft_id: str, status: str) -> dict[str, Any]:
  files = draft_files(directories)
  path = files.get(draft_id)
  if path is None:
    raise ValueError(f"Unknown draft: {draft_id}")
  draft = read_json(path)
  draft["status"] = status
  draft["updated_at"] = utc_now()
  draft[f"{status}_at"] = draft["updated_at"]
  temporary = path.with_suffix(".json.tmp")
  temporary.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temporary.replace(path)
  return {"ok": True, "draftId": draft_id, "status": status}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser()
  parser.add_argument("--draft-dir", type=Path, action="append", required=True)
  parser.add_argument("--digest-state", type=Path)
  parser.add_argument("--mark", metavar="DRAFT_ID")
  parser.add_argument("--status", choices=sorted(TERMINAL_STATUSES), default="replied")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    result = mark(args.draft_dir, args.mark, args.status) if args.mark else export(args.draft_dir, args.digest_state)
    print(json.dumps(result, ensure_ascii=False))
    return 0
  except (OSError, ValueError, json.JSONDecodeError) as exc:
    print(json.dumps({"error": str(exc)}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
