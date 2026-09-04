# Traffic Analytics, GA4, And Search Console Setup

## Current Analytics Stack

Use two private dashboards rather than a public page-view counter:

- RaidBench first-party analytics for immediate traffic feedback: page views, popular pages, referrer domains, and countries.
- Google Analytics 4 as an optional later enhancement for deeper product behavior: calculator use, guide clicks, conversion paths, and checkout events.
- Cloudflare Web Analytics as an optional second dashboard for visits, devices, and Core Web Vitals.

A public counter is intentionally excluded. It is easy to inflate with bots, reveals commercial data, and can make an early-stage site look less established. The owner dashboard is the source of truth.

## First-Party Analytics

Current status on July 18, 2026: live and production-verified.

- `analytics.js` sends one page-view request from the production domains only.
- The Cloudflare Pages Worker writes anonymous aggregate rows to the EU-jurisdiction `raidbench-analytics` D1 database.
- Stored dimensions are UTC date, page path, referrer hostname, Cloudflare country code, and aggregate view count.
- IP addresses, cookies, user-agent strings, email addresses, account IDs, and full referrer URLs are not stored.
- Do Not Track and Global Privacy Control are respected.
- Rows older than 400 days are removed automatically.
- Preview deployments and local development do not write production traffic.

Open the private Chinese owner dashboard:

```text
http://127.0.0.1:4289/owner-traffic-zh.html
```

Start it from the repository root:

```bash
node scripts/serve-owner-dashboard.mjs
```

Opening the dashboard or choosing **Sync data** queries D1 immediately. The server listens only on `127.0.0.1`; the owner dashboard and its cloud query route are excluded from the public Pages package.

For a JSON-only snapshot, run:

```bash
node scripts/fetch-traffic-dashboard.mjs
```

The snapshot is written to ignored local file `local/traffic-dashboard.json`.

## Daily Feishu Traffic Brief

At 20:00 China time, `raidbench-acquisition-digest.timer` sends the owner one Feishu-only growth brief containing
the current day's page views, yesterday's views, rolling 7-day and 30-day totals, top pages, account entries,
checkout starts, payment successes, and up to six new Reddit reply drafts.

The Pages Worker serves aggregate data from `GET /api/analytics/summary` only when the request carries the existing
RaidBench edge-origin key. Requests without the correct key return `404`. The endpoint never returns IP addresses,
cookies, account data, full referrer URLs, or individual visit records. The VPS reuses the existing key from the
protected Caddy environment; no broader Cloudflare API token or paid analytics service is required.

## Cloudflare Web Analytics

Optional enhancement status on July 18, 2026:

- `raidbench.com` is live on Cloudflare Pages.
- First-party D1 analytics is already collecting production page views, so this is not a launch blocker.
- The production HTML does not contain the Cloudflare Web Analytics beacon.
- Wrangler is logged into the correct Cloudflare account, but its OAuth token has account read access rather than the account-settings write access required to enable Web Analytics through the API.

Enable it in Cloudflare:

1. Open **Workers & Pages**.
2. Open the **raidbench** Pages project.
3. Open **Metrics**.
4. Under **Web Analytics**, choose **Enable**.
5. Deploy the Pages project once more so Cloudflare can add the beacon.

Data collection starts after activation; it does not reconstruct historical visits. Review these numbers first:

- Page views: total page loads.
- Visits: browsing sessions, which is more useful than raw page views for estimating real demand.
- Top pages: which guides and calculators attract attention.
- Referrers: Google, Reddit, forums, direct visits, and other acquisition sources.
- Countries and devices: where the paying audience may be and how they browse.

Use it as a secondary dashboard after activation. RaidBench's private D1 dashboard remains the immediate source for content-demand validation.

## What GA4 Is

GA4 means Google Analytics 4. For RaidBench, it answers:

- Which pages players visit.
- Which guide links they click.
- Whether they use the Rust calculator.
- Which game tracks attract attention: Rust, POE2, or Palworld.
- Whether Patch Watch and game-specific guides lead players into a useful tool or another answer.

GA4 is not a payment system and does not make the site rank on Google by itself.

## What Search Console Is

Google Search Console answers:

- Whether Google can index `raidbench.com`.
- Which search keywords show impressions and clicks.
- Whether sitemap URLs are discovered.
- Whether pages have crawl or indexing errors.

Use Search Console for SEO health. Use GA4 for visitor behavior.

## Current Site Readiness

Already present:

- First-party aggregate analytics is live on the production domain.
- A private Chinese owner dashboard reads fresh D1 data without exposing business metrics publicly.
- `analytics.js` loads GA4 only when a valid `G-...` Measurement ID is set.
- `config.js` has `ga4MeasurementId: ""` as the safe placeholder.
- Calculator, guide clicks, CTA clicks, and email-interest events are instrumented.
- `sitemap.xml` exists and includes 52 indexable public URLs, including 43 guide and Patch Watch pages.
- `robots.txt` points to `https://raidbench.com/sitemap.xml`.

Optional or external-account steps still available:

- Optionally enable Cloudflare Web Analytics in the Pages project Metrics screen.
- Create a GA4 web property for `https://raidbench.com`.
- Put the `G-...` Measurement ID into `config.js`.
- Add `raidbench.com` to Search Console.
- Prefer DNS TXT verification in Cloudflare DNS.
- Submit `https://raidbench.com/sitemap.xml` in Search Console.

## Recommended Events

Keep these event names:

- `calculator_ready`
- `raid_add_target`
- `raid_remove_target`
- `raid_reset`
- `upkeep_input_change`
- `guide_link_click`
- `cta_click`
- `guide_filter_change`
- `button_click`

Later, after payment is active, add:

- `checkout_click`
- `checkout_complete`
- `credit_quote`
- `credit_use`
- `paid_delivery_created`

## Weekly Review

Each week, check:

- Top 20 pages by visits.
- Top guide clicks by game.
- Search Console queries with impressions but low CTR.
- Pages with traffic but no calculator or CTA interaction.
- Topics that deserve another guide, checklist, or calculator.
