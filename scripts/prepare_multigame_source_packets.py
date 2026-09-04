#!/usr/bin/env python3
"""Build deterministic source packets for the Phase 3 baseline content packs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
  return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: Any) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(f"{path.suffix}.tmp")
  temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temporary.replace(path)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Prepare source packets for new RaidBench game sections.")
  parser.add_argument("--backlog", type=Path, default=ROOT / "private-data" / "content-automation" / "multigame-demand-backlog.json")
  parser.add_argument("--output", type=Path, default=ROOT / "content" / "inbox" / "multigame-source-packets-2026-09-03.json")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  games = read_json(ROOT / "content" / "game-registry.json")["games"]
  source_registry = read_json(ROOT / "content" / "source-registry.json")
  backlog = read_json(args.backlog)
  demand_by_game: dict[str, list[dict[str, Any]]] = {}
  for item in backlog.get("topDemand", []):
    if item.get("status") not in {"new", "observed"}:
      continue
    demand_by_game.setdefault(str(item["gameId"]), []).append(item)
  sources_by_game: dict[str, list[dict[str, Any]]] = {}
  for source in source_registry["sources"]:
    if source["role"] != "fact":
      continue
    sources_by_game.setdefault(str(source["gameId"]), []).append(source)
  packets = []
  for game in games:
    if game["id"] in {"rust", "poe2", "palworld"}:
      continue
    fact_sources = sources_by_game.get(game["id"], [])
    if len(fact_sources) < 2:
      raise RuntimeError(f"Missing factual sources for {game['id']}")
    candidates = sorted(demand_by_game.get(game["id"], []), key=lambda item: int(item.get("score") or 0), reverse=True)
    demand = candidates[0] if candidates else None
    packets.append({
      "gameId": game["id"],
      "game": game["name"],
      "preparedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
      "factSources": [
        {
          "id": source["id"],
          "url": source["url"],
          "authority": source["authority"],
          "freshnessHours": source["freshnessHours"],
          "notes": source["notes"],
        }
        for source in fact_sources
      ],
      "demandSignal": ({
        "title": demand["title"],
        "url": demand["url"],
        "topic": demand["topic"],
        "intentZh": demand.get("intentZh", ""),
        "score": demand["score"],
        "status": demand["status"],
        "demandOnly": True,
      } if demand else None),
      "evidenceBoundary": "Publisher-controlled sources may support factual claims. The community thread supports topic selection only. Unsupported mechanics, exact values, and outcomes must not be inferred.",
    })
  payload = {
    "schemaVersion": "1.0.0",
    "preparedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "backlogGeneratedAt": backlog.get("generatedAt", ""),
    "packets": packets,
  }
  write_json_atomic(args.output, payload)
  print(json.dumps({
    "status": "source_packets_ready",
    "games": len(packets),
    "withDemandSignal": sum(1 for packet in packets if packet["demandSignal"]),
    "withoutDemandSignal": [packet["gameId"] for packet in packets if not packet["demandSignal"]],
    "output": str(args.output),
  }))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
