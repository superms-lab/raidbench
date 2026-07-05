# Stage 4 Traffic Validation

Last updated: 2026-07-05

## Goal

Decide whether RaidBench deserves monetization work before adding accounts, PayPal, credits, or
PoE2 expansion.

## Public URLs

Site:

```text
https://raidbench.com/
```

Sitemap:

```text
https://raidbench.com/sitemap.xml
```

## Google Search Console Setup

Use URL-prefix verification for the fastest path:

```text
https://raidbench.com/
```

Recommended verification options:

1. HTML tag: paste the verification meta tag into `index.html` inside `<head>`.
2. HTML file: download the verification file from Search Console and place it in the repository root.

After verification:

1. Submit the sitemap URL.
2. Use URL Inspection for the homepage.
3. Request indexing for the homepage and the first 3 guide pages.
4. Recheck impressions after 3-7 days.

Priority URLs to inspect first:

- `https://raidbench.com/`
- `https://raidbench.com/pages/rust-raid-cost-calculator.html`
- `https://raidbench.com/pages/rust-garage-door-raid-cost.html`
- `https://raidbench.com/pages/rust-explosive-ammo-vs-rockets.html`

## GA4 Setup

Create a GA4 web data stream for:

```text
https://raidbench.com/
```

Then paste the Measurement ID into `config.js`:

```js
window.RAIDBENCH_CONFIG = {
  ga4MeasurementId: "G-XXXXXXXXXX",
  analyticsDebug: false,
};
```

Do not commit a fake ID. Leave it blank until the real ID exists.

## Event Taxonomy

The site now emits these events when GA4 is configured:

- `calculator_ready` - homepage calculator loaded.
- `raid_add_target` - user adds a target to the raid calculator.
- `raid_remove_target` - user removes a target.
- `raid_reset` - user resets the raid plan.
- `upkeep_input_change` - user changes one upkeep value.
- `email_interest_submit` - user submits interest email; only the email domain is tracked.
- `guide_link_click` - user clicks a guide link or guide page link.
- `cta_click` - user clicks a primary CTA.
- `button_click` - user clicks a non-submit button not covered above.

Recommended GA4 custom dimensions:

- `target_id`
- `target_label`
- `method`
- `quantity`
- `rows`
- `resource`
- `daily_value`
- `link_text`
- `link_url`
- `email_domain`

## Weekly Validation Scorecard

Track once per week:

| Metric | Tool | Good early signal |
| --- | --- | --- |
| Search impressions | Search Console | Any repeated impressions on raid/upkeep keywords |
| Search clicks | Search Console | 5+ organic clicks/week |
| Calculator usage | GA4 events | 20+ `raid_add_target` events/week |
| Guide engagement | GA4/Search Console | Guide pages get clicks or CTA clicks |
| Email interest | GA4/event count | 1+ real submit from non-test visitors |
| Referrals | GA4 | Any Reddit/Steam/forum/Discord traffic |

## Decision Rules

Continue Rust:

- Search Console shows growing impressions for at least one Rust keyword cluster.
- Calculator events happen from organic or referral visitors.
- At least one guide page gets repeated traffic or CTA clicks.

Improve content before monetization:

- Pages get impressions but low clicks.
- Users land on guides but rarely click the calculator.
- Search Console shows keywords that need more focused pages.

Pause Rust and consider PoE2:

- No impressions after indexing and a reasonable wait.
- No calculator use from real visitors.
- No sign that Rust raid/upkeep pages can compete.

## Next Build Items

Only after analytics is live:

1. Add a small "copy plan" button to the calculator and track `raid_copy_plan`.
2. Add shareable URL state and track `raid_share_plan`.
3. Expand the top 3 Search Console queries into deeper pages.
4. Test one simple paid PDF or spreadsheet offer.
