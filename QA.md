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
