# RaidBench QA Log

Last updated: 2026-07-05

## Stage 1 Local QA

Status:

```text
Passed local smoke and browser interaction checks.
Not publicly deployed yet.
```

Local URL:

```text
http://localhost:4289/
```

Checks completed:

- JavaScript syntax check passed with `node --check`.
- HTML parser smoke check passed.
- Local server started on port `4289`.
- `/`, `/robots.txt`, and `/sitemap.xml` returned HTTP 200 via Python HTTP check.
- Browser title matched `RaidBench - Rust Raid Cost & Upkeep Calculator`.
- Page rendered meaningful content.
- Console warnings/errors were empty in browser check.
- First viewport was revised to be tool-first, not marketing-hero-first.
- Raid calculator default total rendered.
- Added `3 x Garage Door / Explosive Ammo`; totals updated.
- Removed the added row; totals returned to default.
- Changed upkeep fields; weekly totals updated.
- Mobile viewport `390x844` had no horizontal overflow.
- Mobile first viewport shows the calculator form directly.

Screenshots captured outside repo:

- `/tmp/raidbench-desktop-v3.png`
- `/tmp/raidbench-mobile-v2.png`

Known limitations:

- Public deployment has been completed in Stage 2.
- No real analytics yet.
- No real email capture yet.
- No payment, credits, or account system yet.

Next step:

```text
Stage 3: SEO content sprint.
```

## Stage 2 Public QA

Status:

```text
Passed public GitHub Pages deployment checks.
```

Public URL:

```text
https://supermszhanghao-eng.github.io/raidbench/
```

Checks completed:

- GitHub Pages status is `built`.
- GitHub Pages serves from `main` branch path `/`.
- HTTPS is enforced.
- `/`, `/robots.txt`, and `/sitemap.xml` returned HTTP 200.
- Public desktop Playwright check rendered the homepage and calculator.
- Public calculator interaction passed: adding `3 x Garage Door / Explosive Ammo` changed totals to `462` raid items and `20,690` sulfur.
- Public mobile viewport `390x844` had no horizontal overflow.

Screenshots captured outside repo:

- `/tmp/raidbench-live-desktop.png`
- `/tmp/raidbench-live-mobile.png`

Known limitations:

- Google Search Console still needs manual property verification.
- Analytics is not installed yet.

## Stage 3 SEO Page QA

Status:

```text
Passed local SEO page smoke checks.
```

Pages created:

- `/pages/rust-raid-cost-calculator.html`
- `/pages/rust-sheet-metal-door-raid-cost.html`
- `/pages/rust-garage-door-raid-cost.html`
- `/pages/rust-stone-wall-raid-cost.html`
- `/pages/rust-base-upkeep-calculator.html`
- `/pages/rust-beginner-raid-path.html`
- `/pages/rust-solo-raid-guide.html`
- `/pages/rust-sulfur-farming-route.html`
- `/pages/rust-tool-cupboard-upkeep-guide.html`
- `/pages/rust-explosive-ammo-vs-rockets.html`

Checks completed:

- Parsed `index.html` plus 10 guide pages with Python `HTMLParser`.
- Parsed `sitemap.xml`; it now lists 11 URLs.
- Local HTTP checks returned 200 for representative guide pages.
- Playwright confirmed the homepage exposes 10 real guide links.
- Playwright confirmed the representative garage-door guide page renders on desktop and mobile.
- Desktop and mobile guide checks had no horizontal overflow.
- Browser console logs were empty.

Screenshots captured outside repo:

- `/tmp/raidbench-guide-desktop.png`
- `/tmp/raidbench-guide-mobile.png`

## Stage 4 Traffic Instrumentation QA

Status:

```text
Passed local instrumentation QA. Google account setup is still manual.
```

Implemented:

- Added `config.js` for GA4 Measurement ID configuration.
- Added `analytics.js` for GA4 loading and event buffering.
- Added analytics scripts to homepage and all 10 guide pages.
- Added calculator events for ready, add target, remove target, reset, upkeep changes, and interest email submits.
- Added automatic click tracking for guide links and CTA links.
- Added `STAGE4_TRAFFIC_VALIDATION.md` with Search Console, GA4, event taxonomy, and weekly decision rules.

Checks completed:

- JavaScript syntax passed for `app.js`, `analytics.js`, and `config.js`.
- Parsed `index.html` plus 10 guide pages with Python `HTMLParser`.
- Confirmed all 11 HTML pages include `config.js` and `analytics.js`.
- Local HTTP checks passed on fixed port `4289`.
- Playwright confirmed homepage events: `calculator_ready`, `raid_add_target`, and `upkeep_input_change`.
- Playwright confirmed guide-page CTA event: `cta_click`.
- Mobile guide page had no horizontal overflow and analytics object loaded.

Known limitations:

- GA4 will not send live events until a real `G-...` Measurement ID is added to `config.js`.
- Search Console verification still requires the user's Google account and verification token or file.

## Stage 5 Monetization Test QA

Status:

```text
Passed local pre-checkout monetization QA. Real payment is intentionally disabled.
```

Implemented:

- Added `premium.html` for the $9 Rust Raid Prep Pack offer.
- Added `premium.js` for checkout state, early-access form behavior, and premium events.
- Added `premiumOffer` configuration in `config.js`.
- Added premium links to the homepage navigation, database CTA, and monetization band.
- Added `premium.html` to `sitemap.xml`.
- Added `STAGE5_MONETIZATION_TEST.md` with PayPal setup, delivery record, and decision rules.

Checks completed:

- JavaScript syntax passed for `premium.js`.
- Parsed `index.html`, `premium.html`, and 10 guide pages with Python `HTMLParser`.
- Parsed `sitemap.xml`; it now lists 12 URLs and includes `premium.html`.
- Local HTTP checks returned 200 for `/`, `/premium.html`, `/premium.js`, and `/sitemap.xml`.
- Playwright confirmed homepage has a Premium navigation link and premium CTA.
- Playwright confirmed premium page defaults to early-access mode when no PayPal link is configured.
- Playwright confirmed premium events: `premium_offer_view`, `premium_interest_click`, `cta_click`, and `premium_interest_submit`.
- Desktop and mobile premium page checks had no horizontal overflow.
- Browser page errors were empty after fixing the PayPal URL check.

Known limitations:

- No real checkout is active until a PayPal Payment Link or Buy Button URL is added.
- Early-access form stores no backend data; it only emits local/GA events for validation.
- Real delivery automation is not built yet.

## Stage 6 Credits And Cloud Readiness QA

Status:

```text
Planning and schema preflight complete. No real credits or cloud backend are enabled yet.
```

Implemented:

- Added `CLOUD_HOSTING_OPTIONS.md` to document cheap cloud paths and the no-local-production rule.
- Added `STAGE6_CREDITS_SYSTEM_PLAN.md` for credit package, ledger, API, and launch-gate rules.
- Added `cloud/api-contract.md` for future API endpoints.
- Added `cloud/credits-schema.sql` for a server-side credit ledger schema.
- Added `cloud/wrangler.example.toml` as a Cloudflare Workers/D1 deployment template.

Known limitations:

- No cloud provider account is connected yet.
- No D1/Postgres database is provisioned yet.
- No PayPal webhook endpoint is deployed yet.
- Credits must not be sold until cloud webhook and ledger idempotency are tested.

## Stage 7 POE2 Route QA

Status:

```text
Passed local POE2 lightweight route QA. No full planner is built.
```

Implemented:

- Added `poe2.html` as the POE2 Lab hub.
- Added four POE2 validation pages under `/pages/`.
- Added homepage POE2 Lab entry.
- Added POE2 URLs to `sitemap.xml`.
- Added `STAGE7_POE2_ROUTE_PLAN.md`.

Checks completed:

- JavaScript syntax check passed.
- Parsed `index.html`, `premium.html`, `poe2.html`, and 14 guide pages with Python `HTMLParser`.
- Parsed `sitemap.xml`; it now lists 17 URLs, including 5 POE2 URLs.
- Playwright confirmed homepage has a POE2 Lab entry.
- Playwright confirmed `poe2.html` renders 4 validation links and loads analytics.
- Playwright confirmed `poe2-build-planner-roadmap.html` renders the roadmap table.
- Playwright confirmed POE2 guide clicks emit `guide_link_click`.
- Desktop and mobile POE2 checks had no horizontal overflow.
- Browser console and page errors were empty.

Known limitations:

- POE2 content is intentionally generic because Early Access balance changes frequently.
- No passive tree renderer, item database, DPS simulator, or economy tracker is built.
- Content should be refreshed against official POE2 sources before serious SEO expansion.

## Content Automation QA

Status:

```text
Passed local content automation QA.
```

Implemented:

- Added `content/rust-problem-guides.json` as the first structured guide dataset.
- Added `scripts/generate-guides.mjs` to generate guide pages and append sitemap URLs.
- Added `scripts/collect-content-sources.mjs` to collect lightweight official-source snapshots.
- Added `operations/review-checklist.md` for human review before publishing generated pages.
- Generated 10 Rust problem guide pages from structured data.
- Added generated guide links to the homepage.
- Added buyer-facing files under `operations/paid-pack/` for the $9 Rust Raid Prep Pack.

Checks completed:

- Ran `node scripts/generate-guides.mjs`; it generated 10 Rust problem guide pages.
- Re-ran the generator without creating duplicate sitemap URLs.
- Ran `node scripts/collect-content-sources.mjs`; it wrote `content/inbox/source-snapshot-2026-07-05.json`.
- JavaScript syntax passed for `scripts/generate-guides.mjs` and `scripts/collect-content-sources.mjs`.
- Parsed 27 HTML pages with `HTMLParser`.
- Parsed `sitemap.xml`; it now lists 27 unique URLs, including 10 generated Rust problem guide URLs.
- Local HTTP checks returned 200 for `/`, a representative generated guide page, and `/sitemap.xml`.
- Playwright confirmed the homepage exposes 10 generated problem guide links.
- Playwright confirmed a generated guide page renders 7 content cards, 4 comparison rows, and analytics.
- Desktop and mobile generated-guide checks had no horizontal overflow.
- Confirmed the paid pack folder contains 8 buyer-facing files.

Known limitations:

- Source collection records metadata and status only; it does not replace manual/in-game verification.
- Generated pages still require review after major game patches.
