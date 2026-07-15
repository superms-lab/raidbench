# POE2 Content Run - 2026-07-15

## Objective

Build the first real POE2 content base for RaidBench without copying third-party guides.

The content strategy is:

1. Collect player pain points from official updates, Steam, Reddit, guide comments, and search demand.
2. Convert repeated problems into original checklists, scorecards, and audit flows.
3. Keep patch-sensitive claims out of static pages.
4. Sell lightweight RaidBench website credits for personalized audits, not in-game currency or game services.

## Current Source Snapshot

Automated source snapshot:

- `content/inbox/source-snapshot-2026-07-15.json`
- `content/inbox/poe2-demand-2026-07-15.json`

Successful automated sources:

- Path of Exile 2 official site: `https://pathofexile2.com/`
- Path of Exile official news: `https://www.pathofexile.com/news`
- Rust official sources for the existing Rust track

Current automated limitation:

- Reddit JSON endpoints timed out from the current local network during this run. The script records the failures and still saves the official-source results.

Manual review sources to keep in the weekly loop:

- Steam store and discussions for Path of Exile 2: `https://store.steampowered.com/app/2694490/Path_of_Exile_2/`
- Path of Exile 2 subreddit: `https://www.reddit.com/r/PathOfExile2/`
- Official forums and patch notes from Grinding Gear Games
- YouTube guide comments on starter builds, boss clears, loot filters, and farming routes

## Content Added

Machine-readable source file:

- `content/poe2-problem-guides.json`

Generated guide script:

- `scripts/generate-poe2-guides.mjs`

Generated pages:

- `pages/poe2-outdated-build-guide-checklist.html`
- `pages/poe2-endgame-defense-checklist.html`
- `pages/poe2-boss-prep-checklist.html`
- `pages/poe2-loot-filter-setup-checklist.html`
- `pages/poe2-currency-farming-checklist.html`
- `pages/poe2-item-value-triage.html`
- `pages/poe2-endgame-route-scorecard.html`
- `pages/poe2-build-audit-product.html`

Site updates:

- `poe2.html` now links to 12 POE2 pages.
- `premium.html` now includes POE2 audit credits with USD, EUR, and GBP pricing.
- `sitemap.xml` now includes the generated POE2 pages.

## 50-Problem Backlog

### Build Selection

1. How do I know if a POE2 build guide is outdated?
2. What makes a build a real starter build?
3. Why does my build work in campaign but fail in endgame?
4. Which parts of a build guide are mandatory and which are optional?
5. How do I choose a build if I only play a few hours per week?
6. How do I compare two builds without understanding every formula?
7. What does a cheap fallback version of a build look like?
8. How do I avoid bait showcase builds?
9. Should I change skills or fix gear first?
10. How do I know when to abandon a build?

### Defense And Bossing

11. Why am I getting one-shot in endgame?
12. What defenses should I check before maps or harder content?
13. Why do bosses feel impossible even when my damage is high?
14. How do I prepare for a boss attempt?
15. How do I review why a boss attempt failed?
16. Which gear swaps help boss attempts most often?
17. How do I balance damage and survivability?
18. What should I practice before spending more attempts?
19. Why does standing still kill my build?
20. How do I make a squishy build safer without rebuilding everything?

### Loot And Items

21. How strict should my loot filter be?
22. What items should a new player keep?
23. How do I know if an item is worth selling?
24. How do I avoid keeping too many maybe items?
25. Which item bases matter for my build?
26. How do I price-check without wasting the whole session?
27. When should I craft-test an item instead of selling it?
28. What should I do with stash tabs full of uncertain items?
29. How do I identify affixes that work together?
30. What is the difference between listed price and real demand?

### Farming And Economy

31. What currency farming route should my build run?
32. How many runs should I test before judging profit?
33. How do I count entry cost and failed runs?
34. How do I know if a farming video applies to my build?
35. What is a low-risk farming route for weak builds?
36. How do I track profit without fooling myself?
37. When is bossing worse than mapping for my build?
38. How do I choose between speed, safety, and profit?
39. How do I reduce trade friction in a farming plan?
40. What should I upgrade first to improve farming?

### Progression And Paid Audit Products

41. What should I do next after finishing campaign?
42. How do I turn a build problem into a short checklist?
43. What information should I submit for a build audit?
44. What information should I submit for a boss prep review?
45. What information should I submit for an item value decision?
46. What should a personalized progression plan include?
47. How should RaidBench spend credits for different audit types?
48. How should RaidBench avoid promising exact profit or best-in-slot results?
49. How should RaidBench handle refund evidence for digital advice?
50. How should RaidBench refresh advice after each major patch?

## Paid Product Draft

Credits are only for RaidBench website outputs:

| Action | Credits | Output |
| --- | ---: | --- |
| Item Value Decision | 3 | Keep, sell, vendor, craft-test, or personal-use note |
| Boss Prep | 6 | Attempt checklist and one defensive/mobility adjustment list |
| Farming Route Score | 8 | Route fit, risk, entry cost, and tracking sheet |
| Build Audit | 10 | Patch-sensitivity, defenses, gear blockers, next three fixes |
| Progression Plan | 15 | Short roadmap for campaign, early endgame, or upgrades |

Starter prices for checkout testing:

| Pack | USD | EUR | GBP | Credits |
| --- | ---: | ---: | ---: | ---: |
| Starter | $4.99 | €4.99 | £4.49 | 100 |
| Pro | $9.99 | €9.99 | £8.99 | 300 |
| Season | $19.99 | €19.99 | £17.99 | 800 |

## Legal/Platform Guardrails

- Do not sell in-game currency, items, accounts, boosting, gambling, or game top-up.
- Do not copy guide text, screenshots, tables, or paid builds from other creators.
- Use community sources to identify demand, not as final truth.
- Keep all POE2 pages marked unofficial.
- State that advice is patch-sensitive.
- Keep delivery evidence for paid digital outputs.

## Next Operating Loop

Run weekly:

1. Refresh official source snapshot.
2. Run `node scripts/collect-poe2-demand.mjs`.
3. Manually review top Reddit/Steam/YouTube questions when the automatic Reddit fetch fails.
4. Add 5 new problems or update 5 existing problems in `content/poe2-problem-guides.json`.
5. Run `node scripts/generate-poe2-guides.mjs`.
6. Check links and sitemap.
7. Publish updated files.
8. Share one useful answer in a community without spam.
