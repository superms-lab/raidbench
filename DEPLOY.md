# RaidBench Deployment Notes

## Current Production Shape

RaidBench uses a hybrid Cloudflare Pages + VPS deployment:

```text
Player
  -> raidbench.com on Cloudflare Pages (HTML, CSS, JavaScript, guides)
  -> /api/* through the Pages Worker
  -> signed private origin route
  -> RaidBench container on the VPS
  -> SQLite + PayPal API
```

Production URLs:

```text
https://raidbench.com/
https://raidbench.com/customer
```

Cloudflare Pages project:

```text
raidbench
```

Latest verified Pages deployment (2026-09-04):

```text
https://8acb441a.raidbench.pages.dev
```

The customer application and API are deployed with PayPal Live credentials and a verified Live webhook.
Checkout is enabled with the exact PayPal merchant identity and the recorded launch tax policy. A no-money
Live order probe passed at USD 19.00; the first legitimate paid order still requires close capture, webhook,
credit-ledger, delivery, and reconciliation monitoring.

The customer backend release is `/opt/raidbench/releases/20260904T013111Z-phase8-palworld-live-v11`.
It exposes the 80-credit Palworld base and progression review and keeps the other ten non-Rust products hidden.
It also enforces the Rust paid-data status, accepted changelist, file hash, and 72-hour freshness before exposing Rust actions or new credit checkout.

The production Rust paid-data bundle was independently verified against official `Breach and Clear`
changelist 4045 on 2026-09-03. The public health endpoint reports `paidDataStatus=verified` and
`paidDataVerifiedAt=2026-09-03`.

The isolated VPS Source Scout is enabled through `raidbench-source-scout.timer`. The independent
`raidbench-content-agent.timer` runs the five-stage Codex QA pipeline and can publish one approved owned-site
guide per UTC day. Neither service posts externally or accesses commerce data. Reddit sources remain excluded
until the required commercial platform permission is recorded.

## Public Package

Build the allowlisted Pages package:

```bash
node scripts/build-public-dist.mjs
```

The build copies only Sitemap-approved HTML, the customer application, and approved static assets.
It excludes owner dashboards, operations documents, source data, local databases, secrets, backups,
and editorial drafts that have not passed the index gate.

Deploy the generated package:

```bash
npx wrangler pages deploy /tmp/raidbench-pages --project-name raidbench --branch main
```

The Pages Worker has two responsibilities:

- Store privacy-minimized page-view aggregates in the `raidbench-analytics` D1 database.
- Forward `/api/*` to the private VPS origin using production-only Cloudflare secrets.

Required production bindings and secrets:

```text
ANALYTICS_DB
RAIDBENCH_ORIGIN_URL
RAIDBENCH_ORIGIN_KEY
```

Never put the origin key in Git, client JavaScript, screenshots, or operations reports.

## Content Build And Validation

Run before a public content deployment:

```bash
node scripts/generate-guides.mjs
node scripts/generate-poe2-guides.mjs
node scripts/generate-palworld-guides.mjs
node scripts/generate-agent-guides.mjs
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

Validate the deployed boundary:

```bash
curl -fsS https://raidbench.com/api/health
curl -fsS https://raidbench.com/api/config
curl -fsS https://raidbench.com/api/session
curl -I https://raidbench.com/customer
```

Current status after installing PayPal Live credentials:

- `/api/health` reports `status=ok`, `mode=production`, and `database=sqlite`.
- `/api/config` reports `paypalEnvironment=live`, `paypalWebhookReady=true`, and
  `checkoutEnabled=true`, with merchant identity and tax-policy readiness both true.
- `/api/config` reports `passwordResetEnabled=true`; SMTP2GO production delivery from
  `account@notify.raidbench.com` passed a real Gmail delivery and reset-page test on 2026-08-02.
- Anonymous `/api/session` reports `authenticated=false` rather than an error.
- Customer responses are private and not cached.
- The first automatic guide passed evidence QA, deployed to production, appeared in `guides.html` and
  `sitemap.xml`, and received an HTTP 200 response from IndexNow.

## Automatic Content Publisher

```bash
systemctl status raidbench-content-agent.timer
journalctl -u raidbench-content-agent.service -n 100 --no-pager
```

Runtime source and durable artifacts:

```text
/opt/raidbench-publisher/workspace
/opt/raidbench-agent/artifacts/content-automation
```

The publisher requires a recent dated signal, captured official excerpt, a new non-duplicate slug, all five
Codex stages, deterministic contract checks, and independent QA. POE2 receives a bounded selection bonus after
the initial cross-game validation. The Pages token is scoped to Pages Write and stored only in the VPS secret
file. Automatic deployment does not guarantee search indexing, traffic, conversion, or revenue.

## Multi-Game Demand Rotation

```bash
systemctl status raidbench-source-scout.timer
systemctl status raidbench-multigame-demand.timer
journalctl -u raidbench-multigame-demand.service -n 100 --no-pager
```

The source scout checks 25 direct publisher-controlled sources across all twelve games every hour, matching the Rust factual-source cadence. Each source has a fixed UTC minute offset from `00` through `48`, spaced two minutes apart; the timer wakes every minute and processes at most two due or catch-up sources. Community demand remains a separate daily-per-game lane: the multi-game service rotates three games every six hours and attempts each game at most once per UTC day. It stores at most one exact recent community question per game in the private backlog, does not use the Reddit Data API, bulk-crawl community listings, or publish externally. The legacy standalone POE2 demand timer is disabled after this shared rotation is installed.

The Reddit reply-draft scout has ten hourly opportunities between 08:50 and 17:50 China time and stops after six successful drafts. Searches without a verifiable candidate do not count toward the target. It draws without replacement from a randomized twelve-game queue, so a game is not repeated on the same day and a normal two-day cycle covers all twelve. It creates link-free private drafts only; the owner remains the public sender. The 20:00 Feishu growth brief includes up to six new drafts and a fresh Cloudflare D1 traffic summary. This operational brief is Feishu-only and does not send an email copy.

The owned-site publisher gets six attempts per hour at UTC minutes `05`, `15`, `25`, `35`, `45`, and `55`, offset from the even-minute source slots. One guide per hour, 24 per day, and 14 per game per week are minimum operating targets used to measure deficits and prioritize games. There is no guide-count ceiling. No qualifying new signal or any failed evidence, duplication, policy, build, or independent-QA check produces no public page for that attempt.

## Multi-Game Shadow Answer QA

```bash
systemctl status raidbench-shadow-qa.timer
journalctl -u raidbench-shadow-qa.service -n 100 --no-pager
```

The shadow runner uses a separate no-charge database and two different Codex Agent stages. It reopens a case only when the benchmark is new or official source content changes, processes at most two new supported cases per run, and never mounts customer orders, PayPal secrets, or the production credit ledger. A passed case does not activate a product; all structured product gates must pass first.

Complex match products add a second blind reviewer. After QA, the service verifies approved answers through an isolated temporary instance of the production SQLite delivery code and builds a private activation manifest. The current 67-case suite has one eligible product, Palworld, now recorded as `live_monitored`; the other ten products remain hidden.

## Palworld Customer Answer Queue

The production app writes signed, privacy-minimized jobs to `/opt/raidbench/jobs/inbox`. Jobs contain an opaque question ID, the selected game product, question text, player-supplied game context, quote, timestamps, and an HMAC signature. They contain no email, PayPal identifier, order identifier, or credit ledger.

`raidbench-live-answer.timer` checks every minute and sends at most one pending job through a Codex author and a different independent reviewer using current publisher snapshots. The Agent container mounts the inbox read-only, writes only to the outbox and private artifacts, and cannot access `/opt/raidbench/data/raidbench.db` or PayPal secrets.

`raidbench-answer-import.timer` checks every minute inside the production runtime. It verifies the original HMAC, exact database request match, answer fingerprint, source domains and freshness, QA identities, critical claims, limitations, and correction window. Only then does it debit once and publish the answer in the same account. Rejected, unsupported, stale, or 30-minute timed-out jobs close with zero credits charged.

```bash
systemctl status raidbench-live-answer.timer raidbench-answer-import.timer
journalctl -u raidbench-live-answer.service -u raidbench-answer-import.service -n 100 --no-pager
python3 /opt/raidbench-publisher/workspace/scripts/export_multigame_live_status.py
```

The private Chinese owner dashboard at `http://127.0.0.1:4289/owner-products-zh.html` displays queue, delivered, no-charge, charged-credit, debit, delivery, and anomaly counts without customer content.

## PayPal Live Gate

Real checkout must remain hidden until all of the following are true:

1. A PayPal Live REST app supplies a Live Client ID and Client Secret.
2. The Live app has a verified RaidBench webhook and its Webhook ID is stored on the VPS.
3. The exact merchant legal name and country are configured.
4. The North America tax treatment has been confirmed and recorded.
5. Automated tests cover amount checks, one-time crediting, answer delivery, reversals, and idempotency.
6. A no-money Live order probe confirms USD 19.00, the PayPal approval domain, and zero premature credits.
7. The public Account / Get Answer CTA may be enabled for legitimate buyers; the first paid order is monitored
   through Capture, signed Webhook, credit delivery, answer delivery, and reconciliation.

## Local Port

This project uses:

```text
PORT=4289
```

Do not use port `4173` for this project.

Open the private Chinese traffic dashboard with live D1 refresh:

```bash
node scripts/serve-owner-dashboard.mjs
```

Then visit:

```text
http://127.0.0.1:4289/owner-traffic-zh.html
```

This localhost dashboard is excluded from the public deployment package.

Repository:

```text
https://github.com/superms-lab/raidbench
```

See `operations/vps-deployment.md` for the VPS layout, automated verification, backup, and rollback procedures.
