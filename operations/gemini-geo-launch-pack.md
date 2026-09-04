# RaidBench Gemini / Google AI Launch Pack

Updated: 2026-08-09

## Executive conclusion

There is no separate Gemini submission button, special AI schema, or Google-required `llms.txt` file. RaidBench becomes eligible for Google's AI search experiences through the same foundation used for ordinary Google Search: crawlable pages, indexable text, useful answers, accurate structured data, clear source links, strong internal navigation, and good page experience.

The launch package therefore focuses on earning inclusion rather than manufacturing an “AI optimization” signal.

Official references:

- Google Search AI features: https://developers.google.com/search/docs/appearance/ai-features
- Google Article structured data: https://developers.google.com/search/docs/appearance/structured-data/article
- Google guidance for succeeding in AI search: https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search

## Ready on the local site

- 42 game-specific evergreen guides are exposed in the public guide library.
- 7 Patch Watch pages answer version-specific questions from official game sources.
- 58 public URLs pass the current indexability and Sitemap gate; 49 are guide or update pages.
- Every generated article exposes a short answer, review date, source list, refresh trigger, canonical URL, and Article JSON-LD.
- Generic mass-produced drafts remain `noindex` and are absent from the public guide library and Sitemap.
- `/guides`, `/updates`, and game hubs provide crawlable internal routes into the content.

## First URLs to request for indexing

1. https://raidbench.com/updates
2. https://raidbench.com/pages/rust-power-trip-raid-meta-guide
3. https://raidbench.com/pages/rust-fast-vs-efficient-raiding
4. https://raidbench.com/pages/rust-c4-vs-rockets
5. https://raidbench.com/pages/rust-raid-profit-calculator-outline

These URLs must not be submitted until the current local build has been deployed and each production URL returns its intended page.

## Launch procedure

1. Generate all article pages, the guide index, Patch Watch, and Sitemap.
2. Run `node scripts/validate-public-site.mjs`; do not deploy on a failure.
3. Deploy the public-file allowlist from `DEPLOY.md` to Cloudflare Pages.
4. Verify `robots.txt`, `sitemap.xml`, canonical URLs, and the five priority pages on production.
5. Add the domain property in Google Search Console and submit `https://raidbench.com/sitemap.xml`.
6. Use URL Inspection for the five priority pages after verifying that Google sees the rendered text.
7. Run `node scripts/submit-indexnow.mjs` after production deployment for Bing and other participating engines.
8. Record impressions, clicks, indexed pages, query variants, account entries, checkout starts, payments, and answer delivery.

## Patch-to-page operating loop

- Poll official update feeds every 15 minutes from the future Agent host.
- Create a source snapshot and content fingerprint when a page changes.
- Use a model to classify game, version, affected player decision, urgency, and impacted RaidBench URLs.
- Automatically publish only low-risk factual changes that preserve the official source URL and visible review date.
- Route ambiguous mechanics, exploit claims, economy advice, and conflicting sources to an editorial queue.
- Rebuild the Sitemap, validate the site, deploy, and ping the internal monitoring log after an approved change.

The current repository contains the content and validation foundation. The 15-minute scheduler still needs the future Agent host and production deployment credentials before it can run continuously.

## Answer format for future pages

Every new page should contain:

1. One player question in the title and H1.
2. A direct answer that stands on its own in two to four sentences.
3. The exact game version or a clear “version-independent” label.
4. A decision table or checklist that produces a next action.
5. At least one direct official source for patch-sensitive claims.
6. A visible reviewed date, known limitations, and refresh trigger.
7. Relevant internal links without circular or manufactured cross-linking.

## Measurement

Track these weekly after launch:

- Indexed priority URLs / submitted priority URLs.
- Search impressions and clicks by game and question cluster.
- Guide-to-tool click rate.
- Patch Watch return visits.
- Queries with impressions but no click, used as the next content queue.
- Corrections, stale-page alerts, and time from official update to refreshed page.

Do not report Gemini inclusion as guaranteed. Search eligibility can be engineered; selection remains Google's decision.
