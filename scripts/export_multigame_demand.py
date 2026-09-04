#!/usr/bin/env python3
"""Export the private multi-game source and demand dashboard payload."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Export RaidBench multi-game demand status as JSON.")
  parser.add_argument("--database", type=Path, required=True)
  parser.add_argument("--limit", type=int, default=40)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  connection = sqlite3.connect(args.database)
  connection.row_factory = sqlite3.Row
  try:
    summary = dict(connection.execute(
      """
      SELECT
        (SELECT count(*) FROM game_catalog) AS games,
        (SELECT count(*) FROM content_source_profiles) AS registeredSources,
        (SELECT count(*) FROM content_sources WHERE active=1) AS activeDirectSources,
        (SELECT count(*) FROM demand_backlog) AS backlogTotal,
        (SELECT count(*) FROM demand_backlog WHERE status='new') AS newDemand,
        (SELECT count(*) FROM content_sources WHERE source_type='reddit-json' AND active=1) AS activeRedditApiSources
      """
    ).fetchone())
    per_game = [dict(row) for row in connection.execute(
      """
      SELECT game.id AS gameId,game.short_name AS game,game.status AS coverageStatus,
        count(DISTINCT profile.source_id) AS registeredSources,
        count(DISTINCT CASE WHEN profile.fetch_mode='direct' THEN profile.source_id END) AS directSources,
        count(DISTINCT backlog.id) AS backlogTotal,
        count(DISTINCT CASE WHEN backlog.status='new' THEN backlog.id END) AS newDemand,
        count(DISTINCT CASE WHEN backlog.status='source_trigger' THEN backlog.id END) AS sourceTriggers,
        max(backlog.opportunity_score) AS topScore,
        max(backlog.last_seen_at) AS lastSeenAt,
        max(CASE WHEN snapshot.ok=1 THEN snapshot.fetched_at ELSE '' END) AS lastSourceSuccess
      FROM game_catalog game
      LEFT JOIN content_source_profiles profile ON profile.game_id=game.id
      LEFT JOIN source_snapshots snapshot ON snapshot.source_id=profile.source_id
      LEFT JOIN demand_backlog backlog ON backlog.game_id=game.id
      GROUP BY game.id,game.short_name,game.status
      ORDER BY game.rowid
      """
    ).fetchall()]
    top_demand = [dict(row) for row in connection.execute(
      """
      SELECT backlog.id,game.short_name AS game,backlog.game_id AS gameId,
        backlog.source_title AS title,backlog.source_url AS url,backlog.topic,
        backlog.intent_zh AS intentZh,backlog.opportunity_score AS score,
        backlog.patch_sensitive AS patchSensitive,backlog.status,
        backlog.occurrence_count AS occurrences,backlog.last_seen_at AS lastSeenAt
      FROM demand_backlog backlog
      JOIN game_catalog game ON game.id=backlog.game_id
      ORDER BY backlog.opportunity_score DESC,backlog.last_seen_at DESC
      LIMIT ?
      """,
      (max(1, min(args.limit, 200)),),
    ).fetchall()]
    latest_run = connection.execute(
      "SELECT id,status,started_at,finished_at,summary_json FROM agent_runs WHERE run_type='content_sync' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
  finally:
    connection.close()
  payload = {
    "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "summary": summary,
    "perGame": per_game,
    "topDemand": top_demand,
    "latestSourceRun": ({**dict(latest_run), "summary": json.loads(latest_run["summary_json"] or "{}")} if latest_run else None),
  }
  if payload["latestSourceRun"]:
    payload["latestSourceRun"].pop("summary_json", None)
  print(json.dumps(payload, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
