# RaidBench MVP

Fast static MVP for validating the Rust game-guide/tool website route.

## What It Tests

- Whether a tool-first Rust guide site feels useful.
- Whether raid cost and upkeep searches can become SEO pages.
- Whether a simple calculator can justify later paid packs or credits.

## Files

- `index.html` - static app shell and SEO content
- `styles.css` - visual system and responsive layout
- `app.js` - calculator logic
- `assets/survival-base.png` - generated original artwork, not official Rust art
- `assets/concept-ui.png` - generated concept reference

## Local Preview

Open `index.html` directly in a browser, or serve the directory with any static server.

Fixed local preview port:

```text
4289
```

Start command from the repository root:

```bash
PORT=$(awk -F= '/^PORT=/{print $2}' .env)
python3 -m http.server "$PORT" --directory .
```

## Deployment

This can deploy as-is to Cloudflare Pages, GitHub Pages, Netlify, or Vercel static hosting.

See `DEPLOY.md`.

## Traffic Validation

Stage 4 analytics and Search Console setup notes live in `STAGE4_TRAFFIC_VALIDATION.md`.

GA4 is configured in `config.js`. Leave `ga4MeasurementId` blank until the real Measurement ID exists.

## Monetization Test

Stage 5 notes live in `STAGE5_MONETIZATION_TEST.md`.

The first offer page is `premium.html`. PayPal checkout remains disabled until `premiumOffer.paypalPaymentLink` is configured in `config.js`.

## Cloud And Credits

Cloud hosting notes live in `CLOUD_HOSTING_OPTIONS.md`.

Stage 6 credits planning lives in `STAGE6_CREDITS_SYSTEM_PLAN.md`.

Production should not run from the local Mac. The local `4289` server is development preview only.

## POE2 Route

Stage 7 notes live in `STAGE7_POE2_ROUTE_PLAN.md`.

The POE2 validation hub is `poe2.html`. It is intentionally lightweight and does not attempt to
replace a full Path of Building-style planner.

## Content Production

The operating playbook lives in `operations/content-production-playbook.md`.

The first 30-day content calendar lives in `operations/30-day-content-calendar.csv`.

The first paid deliverable draft lives in `operations/raid-prep-pack-v1.md`.

## Legal Note

RaidBench is an unofficial fan-made planning tool and is not affiliated with or endorsed by Facepunch Studios. All trademarks and game names belong to their respective owners.
