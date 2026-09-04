# RaidBench Content Cadence And Traffic Plan

Updated: 2026-09-03

## Verified Current Cadence

- Public-source Scout: once per hour, normally 24 completed collection runs per UTC day.
- Content Agent: once per hour, but it starts a guide only when a recent, eligible, source-backed signal exists.
- Public guide limit: at most one new guide per UTC day.
- Reddit community scout: once per day, normally one private reply draft. This does not update the public website.
- Public content is fail-closed: no eligible signal or a QA block means zero new public pages that day.

## Recent Actual Output

- Indexable public pages: 62 before the next accepted guide publication.
- Successful Agent-published guides in the automation database: 3 total.
- Most recent successful automated publication before this audit: 2026-08-12.
- From 2026-08-28 through 2026-09-02, the community scout created about one Reddit reply draft per day.
- Two recent POE2 guide attempts passed factual drafting stages but did not publish because of build permissions,
  non-indexable related-page selection, and over-broad localization/commerce policy checks.

## Repairs Applied

- Added write ownership for generated JSON, CSV, feed, sitemap, and Wrangler temporary files.
- Allowed previously `build_failed` items to retry after the normal backoff.
- Restricted related-guide inventory to same-game, indexable public pages.
- Separated exact-thread link-free reply rules from standalone promotional-post approval rules.
- Clarified that legitimate in-game economy guidance is allowed while real-money trading and item sales remain blocked.
- Prevented Chinese owner localization from inventing platform-specific external-action policies.

## Traffic Growth Operating Target

Do not force filler pages merely to claim a daily update. Use this weekly target:

- 3 high-intent Rust problem pages tied to repeated player questions and the live paid product.
- 1 calculator preset, comparison, or downloadable data asset that earns links and repeat use.
- 1 patch-sensitive refresh when an official change affects a published answer.
- 7 link-free community answers, with one disclosed, UTM-tagged link retained on the owner's Reddit profile.
- 2 personalized partner or publisher approaches offering the free widget or reviewed data.

## Measurement

- Page views now record UTM source, medium, and campaign in `acquisition_page_views`.
- The private Chinese dashboard shows traffic sources separately from conversion actions.
- Historical visits cannot be retroactively attributed to Reddit.
- The next decision gate is 100 attributable visits: compare Reddit/profile, organic search, and partner traffic by
  account entry, checkout start, and payment rather than by page views alone.
