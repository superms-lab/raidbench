from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run_automatic_content_pipeline.py"
SPEC = importlib.util.spec_from_file_location("raidbench_automatic_content", MODULE_PATH)
assert SPEC and SPEC.loader
automation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = automation
SPEC.loader.exec_module(automation)


class RaidBenchAutomaticContentTests(unittest.TestCase):
  def test_promotional_signal_is_not_sent_to_content_agents(self) -> None:
    self.assertFalse(automation.signal_is_actionable({
      "signal_title": "Watch the ExileCon Qualifier Tomorrow - New Twitch Drops",
    }))
    self.assertTrue(automation.signal_is_actionable({
      "signal_title": "Hotfix fixes a progression bug after the latest patch",
    }))

  def test_reddit_requires_recorded_commercial_permission(self) -> None:
    self.assertFalse(automation.source_is_eligible("reddit-json", False))
    self.assertTrue(automation.source_is_eligible("reddit-json", True))
    self.assertTrue(automation.source_is_eligible("official", False))

  def test_reddit_reply_and_standalone_post_have_distinct_review_rules(self) -> None:
    constraints = automation.content_constraints()
    policy = automation.external_publication_policy()
    self.assertFalse(constraints["owner_confirmation_required_for_exact_thread_link_free_replies"])
    self.assertTrue(constraints["owner_confirmation_required_for_external_posts"])
    self.assertTrue(constraints["automatic_reply_requires_approved_platform_posting_access"])
    self.assertTrue(constraints["no_sale_or_transfer_of_in_game_currency_or_items"])
    self.assertTrue(constraints["informational_in_game_economy_guidance_allowed"])
    self.assertFalse(policy["external_post_confirmation_required"])
    self.assertFalse(policy["exact_thread_link_free_reply_confirmation_required"])
    self.assertTrue(policy["standalone_external_post_confirmation_required"])
    self.assertTrue(policy["external_platform_permission_required"])

  def test_recent_steam_signal_is_fresh(self) -> None:
    published_at = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    row = {"source_type": "steam-rss", "evidence_json": json.dumps({"publishedAt": published_at})}
    self.assertTrue(automation.signal_is_fresh(row))

  def test_old_or_undated_steam_signal_is_not_fresh(self) -> None:
    published_at = (datetime.now(timezone.utc) - timedelta(days=46)).isoformat()
    old_row = {"source_type": "steam-rss", "evidence_json": json.dumps({"publishedAt": published_at})}
    undated_row = {"source_type": "steam-rss", "evidence_json": "{}"}
    self.assertFalse(automation.signal_is_fresh(old_row))
    self.assertFalse(automation.signal_is_fresh(undated_row))

  def test_preferred_game_receives_bounded_score_bonus(self) -> None:
    common = {
      "pain_score": 4,
      "commercial_score": 3,
      "patch_sensitive": 1,
      "evidence_json": json.dumps({"publishedAt": "2026-08-01T00:00:00+00:00"}),
      "created_at": "2026-08-02T00:00:00+00:00",
    }
    poe2 = {**common, "game": "POE2"}
    rust = {**common, "game": "Rust"}
    self.assertGreater(
      automation.candidate_rank(poe2, "POE2", 2),
      automation.candidate_rank(rust, "POE2", 2),
    )

  def test_failed_agent_item_retries_after_one_hour(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      database_path = Path(temporary) / "test.db"
      seed_connection = automation.sqlite3.connect(database_path)
      seed_connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      seed_connection.close()
      connection = automation.open_database(database_path)
      now = datetime.now(timezone.utc)
      connection.execute(
        "insert into content_sources (id,game,source_type,url,cadence) values ('source','POE2','official','https://example.com','1h')"
      )
      connection.execute(
        "insert into agent_runs (id,run_type,status,started_at,summary_json) values ('run','content_sync','completed',?,'{}')",
        ((now - timedelta(minutes=5)).isoformat(),),
      )
      connection.execute(
        """
        insert into source_snapshots (id,run_id,source_id,fetched_at,ok,status_code,title)
        values ('snapshot','run','source',?,1,200,'Patch notes')
        """,
        ((now - timedelta(minutes=5)).isoformat(),),
      )
      connection.execute(
        """
        insert into content_signals (
          id,run_id,source_id,game,topic,signal_title,signal_url,
          pain_score,commercial_score,patch_sensitive,evidence_json,created_at
        ) values ('signal','run','source','POE2','patch','Patch notes','https://example.com',5,5,1,'{}',?)
        """,
        ((now - timedelta(minutes=5)).isoformat(),),
      )
      connection.execute(
        """
        insert into content_automation_items (
          id,signal_id,source_type,status,attempts,created_at,updated_at
        ) values ('item','signal','official','agent_failed',1,?,?)
        """,
        ((now - timedelta(hours=2)).isoformat(), (now - timedelta(hours=2)).isoformat()),
      )
      connection.commit()
      try:
        eligible = automation.candidate_rows(connection, reddit_permission=False)
        connection.execute(
          "update content_automation_items set status='build_failed', updated_at=? where id='item'",
          ((now - timedelta(hours=2)).isoformat(),),
        )
        connection.commit()
        build_retry = automation.candidate_rows(connection, reddit_permission=False)
        connection.execute(
          "update content_automation_items set updated_at=? where id='item'",
          ((now - timedelta(minutes=30)).isoformat(),),
        )
        connection.commit()
        waiting = automation.candidate_rows(connection, reddit_permission=False)
      finally:
        connection.close()
    self.assertEqual([row["signal_id"] for row in eligible], ["signal"])
    self.assertEqual([row["signal_id"] for row in build_retry], ["signal"])
    self.assertEqual(waiting, [])

  def test_recovers_stale_agent_item_without_consuming_daily_limit(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      database_path = Path(temporary) / "test.db"
      database_path.touch()
      connection = automation.open_database(database_path)
      stale_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
      connection.execute(
        """
        INSERT INTO content_automation_items (
          id, signal_id, source_type, status, created_at, updated_at
        ) VALUES ('auto-stale', 'signal-stale', 'steam-rss', 'agent_running', ?, ?)
        """,
        (stale_at, stale_at),
      )
      connection.commit()
      previous_limit = os.environ.get("RAIDBENCH_MAX_NEW_GUIDES_PER_DAY")
      os.environ["RAIDBENCH_MAX_NEW_GUIDES_PER_DAY"] = "1"
      try:
        recovered = automation.recover_interrupted_items(connection)
        row = connection.execute(
          "SELECT status, last_error, updated_at FROM content_automation_items WHERE id = 'auto-stale'"
        ).fetchone()
        limit_reached = automation.daily_limit_reached(connection)
      finally:
        if previous_limit is None:
          os.environ.pop("RAIDBENCH_MAX_NEW_GUIDES_PER_DAY", None)
        else:
          os.environ["RAIDBENCH_MAX_NEW_GUIDES_PER_DAY"] = previous_limit
        connection.close()
    self.assertEqual(recovered, 1)
    self.assertEqual(row["status"], "agent_failed")
    self.assertIn("Recovered", row["last_error"])
    self.assertEqual(row["updated_at"], stale_at)
    self.assertFalse(limit_reached)

  def test_weekly_guide_limit_is_scoped_by_game(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      database_path = Path(temporary) / "test.db"
      connection = automation.sqlite3.connect(database_path)
      connection.row_factory = automation.sqlite3.Row
      connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      now = datetime.now(timezone.utc).isoformat()
      connection.executemany(
        "insert into content_sources (id,game,source_type,url,cadence) values (?,?,?,?,?)",
        [
          ("rust-source", "Rust", "official", "https://example.com/rust", "1h"),
          ("poe-source", "POE2", "official", "https://example.com/poe", "1h"),
        ],
      )
      connection.executemany(
        "insert into agent_runs (id,run_type,status,started_at,summary_json) values (?,?,?,?,?)",
        [("run-rust", "content_sync", "completed", now, "{}"), ("run-poe", "content_sync", "completed", now, "{}")],
      )
      connection.executemany(
        """insert into content_signals (
          id,run_id,source_id,game,topic,signal_title,pain_score,commercial_score,created_at
        ) values (?,?,?,?,?,?,5,5,?)""",
        [
          ("sig-rust", "run-rust", "rust-source", "Rust", "raid_cost", "Rust signal", now),
          ("sig-poe", "run-poe", "poe-source", "POE2", "build_help", "POE signal", now),
        ],
      )
      connection.execute(
        """insert into content_automation_items (
          id,signal_id,source_type,status,created_at,updated_at,published_at
        ) values ('item-rust','sig-rust','official','published',?,?,?)""",
        (now, now, now),
      )
      connection.commit()
      previous_rust = os.environ.get("RAIDBENCH_RUST_WEEKLY_GUIDE_LIMIT")
      previous_poe = os.environ.get("RAIDBENCH_POE2_WEEKLY_GUIDE_LIMIT")
      os.environ["RAIDBENCH_RUST_WEEKLY_GUIDE_LIMIT"] = "1"
      os.environ["RAIDBENCH_POE2_WEEKLY_GUIDE_LIMIT"] = "1"
      try:
        self.assertTrue(automation.weekly_guide_limit_reached(connection, "Rust"))
        self.assertFalse(automation.weekly_guide_limit_reached(connection, "POE2"))
      finally:
        if previous_rust is None:
          os.environ.pop("RAIDBENCH_RUST_WEEKLY_GUIDE_LIMIT", None)
        else:
          os.environ["RAIDBENCH_RUST_WEEKLY_GUIDE_LIMIT"] = previous_rust
        if previous_poe is None:
          os.environ.pop("RAIDBENCH_POE2_WEEKLY_GUIDE_LIMIT", None)
        else:
          os.environ["RAIDBENCH_POE2_WEEKLY_GUIDE_LIMIT"] = previous_poe
        connection.close()

  def test_daily_limit_counts_a_today_publish_created_yesterday(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      database_path = Path(temporary) / "test.db"
      connection = automation.sqlite3.connect(database_path)
      connection.row_factory = automation.sqlite3.Row
      connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      connection.execute(
        """insert into content_automation_items (
          id,signal_id,source_type,status,created_at,updated_at,published_at
        ) values ('item','signal','community-web-search','published',datetime('now','-1 day'),datetime('now'),datetime('now'))"""
      )
      connection.commit()
      previous = os.environ.get("RAIDBENCH_MAX_NEW_GUIDES_PER_DAY")
      os.environ["RAIDBENCH_MAX_NEW_GUIDES_PER_DAY"] = "1"
      try:
        self.assertTrue(automation.daily_limit_reached(connection))
      finally:
        if previous is None:
          os.environ.pop("RAIDBENCH_MAX_NEW_GUIDES_PER_DAY", None)
        else:
          os.environ["RAIDBENCH_MAX_NEW_GUIDES_PER_DAY"] = previous
        connection.close()

  def test_hourly_limit_counts_the_cycle_start_hour(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      database_path = Path(temporary) / "test.db"
      connection = automation.sqlite3.connect(database_path)
      connection.row_factory = automation.sqlite3.Row
      connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      now = datetime.now(timezone.utc)
      connection.execute(
        """insert into content_automation_items (
          id,signal_id,source_type,status,created_at,updated_at,published_at
        ) values ('item','signal','official','published',?,?,?)""",
        (now.isoformat(), now.isoformat(), now.isoformat()),
      )
      connection.commit()
      previous = os.environ.get("RAIDBENCH_MAX_NEW_GUIDES_PER_HOUR")
      os.environ["RAIDBENCH_MAX_NEW_GUIDES_PER_HOUR"] = "1"
      try:
        self.assertTrue(automation.hourly_limit_reached(connection))
        connection.execute(
          "update content_automation_items set created_at=?",
          ((now - timedelta(hours=1)).isoformat(),),
        )
        connection.commit()
        self.assertFalse(automation.hourly_limit_reached(connection))
      finally:
        if previous is None:
          os.environ.pop("RAIDBENCH_MAX_NEW_GUIDES_PER_HOUR", None)
        else:
          os.environ["RAIDBENCH_MAX_NEW_GUIDES_PER_HOUR"] = previous
        connection.close()

  def test_inventory_includes_relevant_public_copy_for_overlap_review(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      temporary_path = Path(temporary)
      pages = temporary_path / "pages"
      pages.mkdir()
      (pages / "poe2-boss-prep-checklist.html").write_text(
        "<html><body><h1>Boss prep</h1><p>Review voice cues and phase timing.</p>"
        "<script>privateNoise()</script></body></html>",
        encoding="utf-8",
      )
      (pages / "poe2-unpublished-note.html").write_text(
        '<html><head><meta name="robots" content="noindex,follow" /></head>'
        "<body><p>This draft must stay out of the review packet.</p></body></html>",
        encoding="utf-8",
      )
      connection = automation.sqlite3.connect(":memory:")
      connection.row_factory = automation.sqlite3.Row
      connection.execute(
        "create table guide_pages (slug text, game text, title text, status text, patch_sensitive integer)"
      )
      connection.executemany(
        "insert into guide_pages values (?, ?, ?, ?, ?)",
        [
          ("poe2-boss-prep-checklist", "POE2", "POE2 boss prep checklist", "published_or_draft", 1),
          ("poe2-unpublished-note", "POE2", "POE2 unpublished note", "draft", 1),
          ("rust-solo-raid-guide", "Rust", "Rust solo raid guide", "published", 1),
        ],
      )
      original_root = automation.ROOT
      automation.ROOT = temporary_path
      try:
        inventory = automation.guide_inventory(
          connection,
          game="POE2",
          context_text="boss voice cue timing and phase changes",
        )
      finally:
        automation.ROOT = original_root
        connection.close()
    by_slug = {item["slug"]: item for item in inventory}
    self.assertIn("Review voice cues and phase timing", by_slug["poe2-boss-prep-checklist"]["content_excerpt"])
    self.assertNotIn("privateNoise", by_slug["poe2-boss-prep-checklist"]["content_excerpt"])
    self.assertNotIn("poe2-unpublished-note", by_slug)
    self.assertNotIn("rust-solo-raid-guide", by_slug)

  def test_inventory_sync_registers_each_expanded_game_and_filters_cross_game_links(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      database_path = Path(temporary) / "test.db"
      connection = automation.sqlite3.connect(database_path)
      connection.row_factory = automation.sqlite3.Row
      connection.executescript((ROOT / "local" / "raidbench-local-schema.sql").read_text(encoding="utf-8"))
      try:
        synchronized = automation.sync_guide_inventory(connection)
        inventory = automation.guide_inventory(
          connection,
          game="Once Human",
          context_text="portable crafting search update",
        )
      finally:
        connection.close()
    self.assertGreaterEqual(synchronized, 100)
    self.assertGreaterEqual(len(inventory), 6)
    self.assertTrue(all(item["game"] == "Once Human" for item in inventory))
    self.assertIn("once-human-update-migration-checklist", {item["slug"] for item in inventory})

  def test_materialized_guide_requires_authoritative_evidence(self) -> None:
    case = self.case_fixture("reddit-json")
    with self.assertRaisesRegex(automation.AutomationError, "no authoritative evidence"):
      automation.materialize_guide(case, self.draft_fixture(), [])

  def test_materializes_source_checked_guide(self) -> None:
    case = self.case_fixture("official")
    guide = automation.materialize_guide(case, self.draft_fixture(), [])
    self.assertEqual(guide["slug"], "rust-automatic-test-guide")
    self.assertEqual(guide["game"], "Rust")
    self.assertEqual(guide["automation"]["qa"], "passed")
    self.assertEqual(guide["sources"][0]["url"], "https://rust.facepunch.com/news")

  def test_materializes_exact_reddit_target_metadata(self) -> None:
    case = self.case_fixture("reddit-json")
    case["signals"][0].update({
      "evidence_id": "E-01",
      "signal_title": "How should I plan this raid?",
      "signal_url": "https://www.reddit.com/r/playrust/comments/abc123/raid_help/",
    })
    case["evidence"].append({
      "evidence_id": "E-02",
      "source_type": "official",
      "source_url": "https://rust.facepunch.com/news",
      "scope_note": "test",
    })
    draft = self.draft_fixture()
    draft["evidence_ids"] = ["E-02"]
    guide = automation.materialize_guide(case, draft, [])
    self.assertEqual(guide["automation"]["communityTargetPlatform"], "reddit")
    self.assertEqual(guide["automation"]["communityTargetUrl"], case["signals"][0]["signal_url"])

  def test_backfill_skips_owned_site_guide_without_reddit_target(self) -> None:
    case = self.case_fixture("official")
    guide = automation.materialize_guide(case, self.draft_fixture(), [])
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      temporary_path = Path(temporary)
      guides_path = temporary_path / "agent-guides.json"
      guides_path.write_text(json.dumps([guide]), encoding="utf-8")
      database_path = temporary_path / "test.db"
      database_path.touch()
      connection = automation.open_database(database_path)
      original_path = automation.AGENT_GUIDES_PATH
      automation.AGENT_GUIDES_PATH = guides_path
      try:
        created = automation.backfill_agent_post_drafts(connection, temporary_path)
        queued = connection.execute("select count(*) from community_post_drafts").fetchone()[0]
      finally:
        automation.AGENT_GUIDES_PATH = original_path
        connection.close()
    self.assertEqual(created, 0)
    self.assertEqual(queued, 0)

  def test_writes_link_free_reddit_post_draft(self) -> None:
    case = self.case_fixture("official")
    guide = automation.materialize_guide(case, self.draft_fixture(), [])
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      path = automation.write_manual_post_draft(
        Path(temporary),
        guide,
        source_url="https://rust.facepunch.com/news",
        exact_target_url="https://www.reddit.com/r/playrust/comments/abc123/raid_help/",
        target_title="How should I plan this raid?",
      )
      draft = json.loads(path.read_text(encoding="utf-8"))
    self.assertEqual(draft["status"], "ready_for_reddit_owner_review")
    self.assertTrue(draft["manual_publish_required"])
    self.assertNotIn("http", draft["draft_text"].lower())
    self.assertEqual(draft["target_platform"], "reddit")
    self.assertEqual(draft["target_title"], "How should I plan this raid?")
    self.assertEqual(draft["target_reddit_url"], "https://www.reddit.com/r/playrust/comments/abc123/raid_help/")

  def test_rejects_reddit_search_page_as_post_target(self) -> None:
    case = self.case_fixture("official")
    guide = automation.materialize_guide(case, self.draft_fixture(), [])
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      with self.assertRaisesRegex(automation.AutomationError, "exact Reddit thread"):
        automation.write_manual_post_draft(
          Path(temporary),
          guide,
          source_url="https://rust.facepunch.com/news",
          exact_target_url="https://www.reddit.com/search/?q=rust+raid",
          target_title="Search results are not a target",
        )

  def test_preserves_review_link_when_draft_is_refreshed(self) -> None:
    case = self.case_fixture("official")
    guide = automation.materialize_guide(case, self.draft_fixture(), [])
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      state_dir = Path(temporary)
      first_path = automation.write_manual_post_draft(
        state_dir,
        guide,
        source_url="https://rust.facepunch.com/news",
        exact_target_url="https://www.reddit.com/r/playrust/comments/abc123/raid_help/",
        target_title="How should I plan this raid?",
      )
      first = json.loads(first_path.read_text(encoding="utf-8"))
      second_path = automation.write_manual_post_draft(
        state_dir,
        guide,
        source_url="https://rust.facepunch.com/news",
        exact_target_url="https://www.reddit.com/r/playrust/comments/abc123/raid_help/",
        target_title="How should I plan this raid?",
      )
      second = json.loads(second_path.read_text(encoding="utf-8"))
    self.assertEqual(first["created_at"], second["created_at"])
    self.assertEqual(first["target_reddit_url"], second["target_reddit_url"])

  def test_keeps_draft_queued_when_feishu_is_not_configured(self) -> None:
    case = self.case_fixture("official")
    guide = automation.materialize_guide(case, self.draft_fixture(), [])
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      temporary_path = Path(temporary)
      database_path = temporary_path / "test.db"
      database_path.touch()
      connection = automation.open_database(database_path)
      draft_path = automation.write_manual_post_draft(
        temporary_path,
        guide,
        source_url="https://rust.facepunch.com/news",
        exact_target_url="https://www.reddit.com/r/playrust/comments/abc123/raid_help/",
        target_title="How should I plan this raid?",
      )
      automation.register_manual_post_draft(connection, guide, draft_path)
      previous = os.environ.pop("RAIDBENCH_FEISHU_WEBHOOK_URL", None)
      try:
        result = automation.deliver_pending_draft_notifications(connection, temporary_path)
      finally:
        if previous is not None:
          os.environ["RAIDBENCH_FEISHU_WEBHOOK_URL"] = previous
      row = connection.execute(
        "select status, attempts, last_error from community_post_drafts where case_id = ?",
        (case["case_id"],),
      ).fetchone()
      connection.close()
    self.assertEqual(result[0]["status"], "awaiting_configuration")
    self.assertEqual(row["status"], "awaiting_configuration")
    self.assertEqual(row["attempts"], 0)
    self.assertIn("not configured", row["last_error"])

  def test_preserves_terminal_notification_failure_during_backfill(self) -> None:
    case = self.case_fixture("official")
    guide = automation.materialize_guide(case, self.draft_fixture(), [])
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
      temporary_path = Path(temporary)
      database_path = temporary_path / "test.db"
      database_path.touch()
      connection = automation.open_database(database_path)
      draft_path = automation.write_manual_post_draft(
        temporary_path,
        guide,
        source_url="https://rust.facepunch.com/news",
        exact_target_url="https://www.reddit.com/r/playrust/comments/abc123/raid_help/",
        target_title="How should I plan this raid?",
      )
      draft_id = automation.register_manual_post_draft(connection, guide, draft_path)
      connection.execute(
        "update community_post_drafts set status = 'notification_failed', attempts = 5, last_error = 'test failure' where id = ?",
        (draft_id,),
      )
      connection.commit()
      automation.register_manual_post_draft(connection, guide, draft_path)
      row = connection.execute(
        "select status, attempts, last_error from community_post_drafts where id = ?",
        (draft_id,),
      ).fetchone()
      connection.close()
    self.assertEqual(row["status"], "notification_failed")
    self.assertEqual(row["attempts"], 5)
    self.assertEqual(row["last_error"], "test failure")

  @staticmethod
  def case_fixture(source_type: str) -> dict:
    return {
      "case_id": "auto-test",
      "signals": [{"signal_id": "S-01", "game": "Rust"}],
      "evidence": [
        {
          "evidence_id": "E-01",
          "source_type": source_type,
          "source_url": "https://rust.facepunch.com/news",
          "scope_note": "test",
        }
      ],
      "guide_inventory": [
        {
          "slug": "rust-raid-cost-calculator",
          "game": "Rust",
          "title": "Rust raid cost calculator",
          "status": "published",
          "patch_sensitive": True,
        }
      ],
    }

  @staticmethod
  def draft_fixture() -> dict:
    return {
      "draft_id": "D-01",
      "evidence_ids": ["E-01"],
      "slug": "rust-automatic-test-guide",
      "title": "Rust automatic test guide",
      "meta_description": "A source-checked test description.",
      "hero_hook": "How should this decision be approached?",
      "short_answer": "Use the supplied evidence and keep the recommendation conditional.",
      "community_answer": "Use the supplied evidence and keep the recommendation conditional. Recheck the current patch before committing resources.",
      "outline": [
        {"heading": "Check context", "purpose": "Confirm scope.", "bullets": ["Check the current patch."]},
        {"heading": "Choose a test", "purpose": "Limit risk.", "bullets": ["Test one assumption first."]},
      ],
      "checklist": ["Check context", "Check cost", "Check risk"],
      "example": "A small test can invalidate a costly assumption.",
      "common_mistakes": ["Ignoring patch context", "Treating one result as universal"],
      "faqs": [
        {"question": "Is this universal?", "answer": "No. Recheck the current patch and server rules."},
        {"question": "What should I do first?", "answer": "Validate the most expensive assumption."},
      ],
      "related_slugs": ["rust-raid-cost-calculator"],
      "source_note": "Bounded to the supplied official source.",
      "patch_note": "Recheck after relevant changes.",
    }


if __name__ == "__main__":
  unittest.main()
