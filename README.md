# RaidBench

Patch-aware game guides, decision tools, verified Rust answers, customer credits, and in-account delivery.

## Current Product

- A shared directory for Rust, POE2, Palworld, Project Zomboid, Escape from Tarkov, ARK, Warframe, Once Human, CS2, Dota 2, PUBG, and Rainbow Six Siege.
- Public decision guides, Patch Watch content, and ten free calculators across all twelve game sections.
- Fifty-four source-bounded baseline guides for the nine newly expanded games, with all game hubs now indexable.
- A local Python service with SQLite accounts, sessions, orders, credit ledger, questions, evidence, QA, and in-account delivery.
- North America launch configuration for the United States and Canada with USD billing.
- PayPal Live checkout for verified Rust answers and one controlled Palworld review; the other ten non-Rust products remain hidden behind independent QA gates.
- A privacy-minimized Palworld job queue with credit reservation, two-stage Codex review, fail-closed import, 30-minute no-charge timeout, and in-account delivery.

## Files

- `index.html` - static app shell and SEO content
- `content/game-registry.json` - source of truth for all game names, routes, states, and content ownership
- `games.html` and `games/*/index.html` - generated game directory and per-game hubs
- `scripts/generate-game-directory.mjs` - multi-game page and homepage-selector generator
- `content/source-registry.json` - source authority, cadence, freshness, and demand-discovery policy for all games
- `scripts/sync-source-registry.mjs` - idempotent game/source database synchronization
- `scripts/discover_multigame_demand.py` - bounded daily community-demand rotation with no posting
- `styles.css` - visual system and responsive layout
- `app.js` - calculator logic
- `assets/survival-base.png` - generated original artwork, not official Rust art
- `assets/concept-ui.png` - generated concept reference

## Local Preview

Fixed local preview port:

```text
4289
```

Start the complete local customer application from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 backend/server.py --host 127.0.0.1 --port 4289 --mode demo
```

Open `http://127.0.0.1:4289/customer.html`. The local PayPal simulation writes real SQLite orders and ledger entries but cannot move real money. Production mode disables it.

## Deployment

The public content site currently deploys to Cloudflare Pages. The full account, payment, and answer service is packaged for a VPS with `Dockerfile`, `compose.yaml`, and `operations/vps-deployment.md`.

See `DEPLOY.md`.

## Traffic Validation

Stage 4 analytics and Search Console setup notes live in `STAGE4_TRAFFIC_VALIDATION.md`.
The current owner-facing setup guide lives in `operations/analytics-search-console-setup.md`.

First-party aggregate page-view analytics is live through the Cloudflare Pages Worker and D1. Open the private Chinese dashboard with fresh cloud data:

```bash
node scripts/serve-owner-dashboard.mjs
```

Then visit `http://127.0.0.1:4289/owner-traffic-zh.html`.

The 20:00 China-time Feishu growth brief refreshes the same Cloudflare D1 dataset and reports today's views,
seven- and thirty-day totals, top pages, and conversion counts alongside up to six new Reddit reply drafts.

The private product-admission dashboard is `http://127.0.0.1:4289/owner-products-zh.html`.

GA4 remains optional. Leave `ga4MeasurementId` blank in `config.js` until a real Measurement ID exists.

## Monetization Test

Public PayPal Live checkout is enabled. A USD 19.00 no-money Live order probe passed without granting credits. Palworld now has an exact-match 80-credit pack at USD 13.00; the first legitimate paid order still must be monitored through capture, signed webhook, one-time crediting, Agent QA, in-account answer delivery, and reconciliation. The complete local commerce runbook is `operations/local-commerce-runbook.md`; the current cost model is `operations/unit-economics-report.md`.

Rust paid actions are additionally gated by an hourly verification status bound to the accepted official changelist and the exact data-file hash. New or stale patch evidence hides new checkout and holds answers without charging credits until review passes.

## Cloud And Credits

Cloud hosting notes live in `CLOUD_HOSTING_OPTIONS.md`.

Stage 6 credits planning lives in `STAGE6_CREDITS_SYSTEM_PLAN.md`.

The public website and analytics collector run on Cloudflare, not the local Mac. Port `4289` is used only for development previews and the private owner dashboard.

## POE2 Route

Stage 7 notes live in `STAGE7_POE2_ROUTE_PLAN.md`.

The POE2 validation hub is `games/poe2/index.html`. It is intentionally lightweight and does not attempt to
replace a full Path of Building-style planner.

## Content Production

The operating playbook lives in `operations/content-production-playbook.md`.

The first 30-day content calendar lives in `operations/30-day-content-calendar.csv`.

Generate the current public guide set, Patch Watch pages, guide index, and sitemap in this order:

```bash
node scripts/generate-guides.mjs
node scripts/generate-poe2-guides.mjs
node scripts/generate-palworld-guides.mjs
node scripts/generate-patch-watch.mjs
node scripts/upgrade-manual-guides.mjs
node scripts/generate-multigame-baseline-guides.mjs
node scripts/validate-multigame-launch-gates.mjs
node scripts/generate-multigame-tools.mjs
node scripts/generate-game-directory.mjs
node scripts/generate-guide-index.mjs
node scripts/apply-site-navigation.mjs
node scripts/generate-sitemap.mjs
node scripts/validate-public-site.mjs
node scripts/build-public-dist.mjs
```

Guide blueprints that still use the generic decision table are generated as `noindex` drafts and are omitted from the public guide library until they pass editorial review.

The production Source Scout wakes every minute but processes only the source slots due at that minute. Twenty-five factual sources are distributed across UTC minute offsets `00` through `48` at two-minute intervals. The content publisher gets six non-overlapping attempts each hour at UTC minutes `05`, `15`, `25`, `35`, `45`, and `55`. One guide can pass through each attempt. One guide per hour, 24 per day, and 14 per game per week are minimum operating targets, never publication ceilings. A qualifying signal must still pass the complete evidence and independent-QA pipeline; failed checks do not produce filler pages.

The first paid deliverable draft lives in `operations/raid-prep-pack-v1.md`.

The buyer-facing paid pack files live in `operations/paid-pack/`.

Generated guide data lives in `content/rust-problem-guides.json`.
Agent, SKU, and local database notes live in `operations/agent-content-system.md`.
The Codex/VPS Agent handoff checklist lives in `operations/prelaunch-agent-server-checklist.md`.

## Multi-Game Demand Pipeline

Phase 1 architecture is recorded in `operations/multigame-expansion-phase-1.md`.
Phase 2 source and demand automation is recorded in `operations/multigame-expansion-phase-2.md`.
Phase 3 baseline content and launch-gate evidence is recorded in `operations/multigame-expansion-phase-3.md`.
Phase 4 free calculators and downloadable worksheets are recorded in `operations/multigame-expansion-phase-4.md`.
Phase 5 product pricing, no-charge routing, and checkout-admission gates are recorded in `operations/multigame-expansion-phase-5.md`.
Phase 6 shadow answers, independent QA, evidence fingerprints, and product-readiness results are recorded in `operations/multigame-expansion-phase-6.md`.
Phase 7 expanded activation evidence, complex double review, isolated delivery gates, and the first private activation candidate are recorded in `operations/multigame-expansion-phase-7.md`.
Phase 8 activated only Palworld with a signed production job queue, independent per-order QA, exact-match credit pack, fail-closed delivery, public conversion paths, and private live monitoring. See `operations/multigame-expansion-phase-8.md`.

Synchronize the registry and run a due-only source check:

```bash
node scripts/sync-source-registry.mjs
node scripts/run-content-agents.mjs
```

Run one bounded three-game demand batch:

```bash
python3 scripts/discover_multigame_demand.py \
  --database local/raidbench.local.db \
  --state private-data/content-automation/multigame-demand-state.json \
  --limit 3
```

Community results are stored only in `demand_backlog`; they do not become public pages until a later evidence and editorial gate promotes them.

Run:

```bash
node scripts/init-local-db.mjs
node scripts/run-content-agents.mjs
python3 scripts/run_raidbench_agent_pipeline.py
node scripts/build-geo-operating-map.mjs
node scripts/expand-seo-guides.mjs
node scripts/generate-guides.mjs
node scripts/generate-poe2-guides.mjs
node scripts/generate-palworld-guides.mjs
node scripts/generate-multigame-baseline-guides.mjs
node scripts/validate-multigame-launch-gates.mjs
node scripts/generate-multigame-tools.mjs
node scripts/generate-game-directory.mjs
node scripts/generate-guide-index.mjs
node scripts/apply-site-navigation.mjs
```

## Legal Note

RaidBench is an unofficial fan-made planning tool and is not affiliated with or endorsed by Facepunch Studios. All trademarks and game names belong to their respective owners.
