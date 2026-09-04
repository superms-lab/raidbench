# RaidBench Content Agent System

Last updated: 2026-09-04

## Production Status

The owned-site content loop is live on the VPS. It can select a recent official signal, run five
read-only Codex stages, reject unsupported output, generate a public guide, rebuild the allowlisted
Pages bundle, deploy it to Cloudflare Pages, verify the production URL, and submit the URL to IndexNow.

The first verified automatic publication is:

```text
https://raidbench.com/pages/palworld-100993-mod-stability-checklist
```

The first verified publication after enabling all twelve registered games and hourly scheduling is:

```text
https://raidbench.com/pages/once-human-september-2-update-workflow-check
```

No owner confirmation is required after the deterministic and Agent QA gates pass. External-platform
posting remains disabled until the platform grants the required commercial automation permission.

## What Runs Locally Now

RaidBench now has a local-first content and commerce data layer:

- Local database schema: `local/raidbench-local-schema.sql`
- Local runtime database: `local/raidbench.local.db` after initialization
- Agent roster: `content/agents.json`
- Draft SKU and credit rules: `content/skus.json`
- Source and signal runner: `scripts/run-content-agents.mjs`
- SEO expansion runner: `scripts/expand-seo-guides.mjs`
- Full public guide index generator: `scripts/generate-guide-index.mjs`
- GEO opportunity-map generator: `scripts/build-geo-operating-map.mjs`
- Fail-closed Codex Agent package: `scripts/run_raidbench_agent_pipeline.py`

The runtime database is intentionally ignored by Git. Commit the schema and scripts, not the local `.db` file.

## Agent Count

The production loop has one deterministic Scout and five isolated model stages:

1. Source Scout: fetches, hashes, dates, deduplicates, and scores permitted public sources.
2. Demand Analysis Agent.
3. Patch Sentinel Agent.
4. Guide Writing Agent.
5. Owner Localization Agent: creates a private Chinese review artifact only.
6. Publish QA Agent: independently checks evidence, localization, policy, and publish safety.

Only the five model stages consume Codex. A model draft cannot publish by itself.

The project-scoped Codex skills live in:

```text
.codex/skills/raidbench-demand-analysis/
.codex/skills/raidbench-patch-sentinel/
.codex/skills/raidbench-guide-writing/
.codex/skills/raidbench-owner-localization/
.codex/skills/raidbench-publish-qa/
.codex/skills/raidbench-shadow-answer/
.codex/skills/raidbench-shadow-answer-qa/
.codex/skills/raidbench-shadow-answer-peer-qa/
```

The pre-launch VPS handoff checklist lives in:

```text
operations/prelaunch-agent-server-checklist.md
```

## What Needs A Model

The local MVP can fetch, dedupe, hash, score keywords, and create queues without a model. A model becomes useful when:

- A Reddit or Steam thread needs semantic intent classification.
- A patch note must be mapped to affected guide pages.
- Several complaints should be clustered into one SEO topic.
- A draft guide needs professional English writing.
- Paid user intake needs a personalized answer.

Production-owned pages publish automatically only after schema validation, evidence validation, independent
QA, a complete site build, and a successful production check. Failed or blocked runs remain private.

## Source Cadence

Do not promise true real-time coverage. Use a disciplined staggered polling loop:

- Official patch/news and Steam publisher sources: every hour, with one fixed minute slot per source.
- Steam RSS items: only entries with a parseable publication date no older than 45 days are eligible.
- Community sources: excluded from the automatic content queue unless commercial platform permission is recorded.
- Emergency review: after major patches, balance notes, wipes, or visible traffic spikes.

Only use public pages and public JSON/RSS endpoints. Do not bypass login, CAPTCHA, robots controls, or community rules.

## VPS Source Scout

The deterministic Source Scout is deployed separately from the customer application at:

```text
/opt/raidbench-agent/app       -> versioned code release
/opt/raidbench-agent/data      -> durable Scout database
/opt/raidbench-agent/artifacts -> durable inbox and owner summary
```

`raidbench-source-scout.timer` wakes every minute at second 20. The 25 approved official and Steam
sources use a one-hour cadence and fixed UTC offsets `00, 02, 04, ... 48`; each invocation processes at most
two due sources. Missed slots are drained at no more than two per minute, while a failed source waits 15
minutes before retry. Reddit community demand remains a separate daily-per-game search-only lane.
It runs as the restricted `raidbench-agent` system user and writes only to its isolated Agent database,
inbox, and owner summary. It cannot access the PayPal environment or production customer database.
The timer is persistent across VPS restarts; a process-level failure retries after 15 minutes. The service
start limit permits minute-level healthy runs without allowing an endless restart loop.

The first verified VPS run on 2026-08-09 checked 11 sources, captured 37 signals, queued 11 high-value
signals, and recorded four inaccessible public sources without bypassing their controls. Empty cadence
runs preserve the latest non-empty review artifacts.

The 2026-08-10 source upgrade binds each signal to the snapshot from the same run, carries the dated source
excerpt into the closed Agent input, and rejects old or undated RSS items. Reddit sources are currently
reported as `platformRestrictedSources` and are not passed to Codex.

## VPS Automatic Publisher

```text
/opt/raidbench-publisher/workspace     writable publishing source tree
/opt/raidbench-publisher/compose.yaml  isolated one-shot container definition
/opt/raidbench-agent/codex             RaidBench-only Codex login state
/opt/raidbench-agent/runtime-home      non-secret CLI cache
/opt/raidbench-agent/secrets           600-permission environment files
/opt/raidbench-agent/artifacts         cases, stage outputs, logs, builds, and audit history
```

`raidbench-content-agent.timer` runs at UTC minute `55:30` of every hour, after the last source slot.
The ceiling is one newly published guide per hour, 24 per day, and 14 per game per week. Infrastructure failures retry after 15 minutes and systemd
limits repeated starts. A validly recorded Agent-output failure waits for the next hourly cycle instead of
creating a restart loop. Codex runs with a read-only Landlock sandbox inside a non-root, read-only container.

Selection currently uses a minimum signal score of 7 without a preferred-game bonus. Every game has two
publisher-controlled sources eligible to enter content QA; the Rust commit stream remains awareness-only.

The Cloudflare API token is account-scoped to Pages Write. It is stored only on the VPS and must never be
printed, copied into Git, or exposed to browser JavaScript.

## Shadow Paid-Answer QA

The no-charge paid-answer benchmark runs separately from article publication. It combines a current closed
publisher-evidence packet with one curated customer-style case, runs a shadow answer author, then runs a
different independent reviewer. Deterministic validators recheck evidence IDs, calculation assertions,
product-promise fulfillment, version scope, prohibited wording, and customer-facing copy.

The current isolated Agent image is `local/raidbench-content-agent:2026-09-04-shadow-qa-v2`, with Codex CLI
0.153.0. Results live in `/opt/raidbench-agent/data/raidbench.shadow.db`; artifacts live under
`/opt/raidbench-agent/artifacts/shadow-benchmarks`. Neither location is part of the customer database.

`raidbench-shadow-qa.timer` checks every six hours. Unchanged source content does not repeat a passed or safely
held case, and repeated execution never increases the distinct-case count. New source content changes the
evidence fingerprint and reopens the relevant case. No run can charge credits.

The Phase 7 service adds a second blind review for complex match products, verifies reviewed answers through
the real store and ledger functions in an ephemeral commerce database, then writes a private activation
manifest. A delivery check is reused only while both the reviewed-answer fingerprint and delivery-code
fingerprint remain unchanged. The current suite has 67 cases and one unpublished activation candidate:
`palworld-base-progression-review`.

## Reddit Replies, Standalone Posts, And Feishu

Owned-site guides continue through automatic QA and publication without owner review. A separate community
draft is created only when the selected demand signal is an exact Reddit thread URL and the Reddit data-use
permission gate is enabled. The private draft is stored at:

```text
/opt/raidbench-agent/artifacts/content-automation/community-drafts/<case-id>.json
```

The pipeline records notification state in `community_post_drafts` and sends an interactive Feishu card with
the exact Reddit thread title, the complete link-free reply, the operating cadence, and a button that opens
that Reddit thread. No community draft or review page is published on RaidBench. A delivered notification is
marked `notified`; a transient delivery failure is retried up to five times. If the Feishu bot is not
configured, the draft remains `awaiting_configuration` with zero attempts consumed.

The requested operating policy distinguishes replies from publication: an exact-thread, link-free Reddit
reply may run without owner review only after Reddit has granted the commercial use case and approved OAuth
credentials are configured. Standalone posts, link-bearing comments, direct messages, and promotional copy
always require owner review. The current production permission switch remains off, so automated Reddit
collection and replies remain inactive rather than bypassing platform controls. Do not reuse one answer
across threads.

One-time private VPS configuration:

```text
RAIDBENCH_FEISHU_WEBHOOK_URL=<Feishu custom-bot webhook>
RAIDBENCH_FEISHU_WEBHOOK_SECRET=<signature secret, recommended>
```

Both values belong only in `/opt/raidbench-agent/secrets/content-agent.env` with mode `600`. They must not be
committed, printed in logs, or exposed to the public site.

## GA4 In Plain English

GA4 means Google Analytics 4. It tells us what players actually do on the site:

- Which pages get visits.
- Which guide links people click.
- Whether players use the calculator.
- Which games and topics attract attention.
- Whether visitors return after updates.

It does not collect money. It does not replace Search Console. Search Console tells us how Google search sees the site; GA4 tells us how visitors behave after they arrive.

## Local Commands

```bash
node scripts/init-local-db.mjs
node scripts/run-content-agents.mjs
python3 scripts/run_raidbench_agent_pipeline.py
python3 scripts/run_automatic_content_pipeline.py --dry-run
python3 scripts/run_automatic_content_pipeline.py
node scripts/build-geo-operating-map.mjs
node scripts/expand-seo-guides.mjs
node scripts/generate-guides.mjs
node scripts/generate-poe2-guides.mjs
node scripts/generate-palworld-guides.mjs
node scripts/generate-guide-index.mjs
```

## Product Data Migration

The same schema style can move to Cloudflare D1. The future cloud version should add:

- PayPal or Stripe webhook verification.
- Server-side idempotency for orders.
- Credit ledger writes only on verified payment events.
- Admin delivery records for refund evidence.
- A scheduled Worker for source polling.
