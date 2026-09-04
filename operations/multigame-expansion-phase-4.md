# RaidBench Multi-Game Expansion - Phase 4

## Status

Phase 4 of 8 is complete locally, synchronized to the VPS, and deployed to production.

Production deployment: `https://71394d06.raidbench.pages.dev`

## Delivered

- [x] Add one functional free tool for each of the nine new game sections.
- [x] Use deterministic formulas with player-entered values instead of unverified live prices or hidden game statistics.
- [x] Add a shared tool engine with risk, budget, weighted-comparison, and timing workflows.
- [x] Add immediate recalculation, visible breakdowns, copyable summaries, and shareable input URLs.
- [x] Generate one downloadable worksheet JSON for every tool.
- [x] Add a public `/tools` directory and tracked tool CTAs to every corresponding game hub.
- [x] Add Tools to the shared site navigation, Sitemap, public build, and `llms.txt` discovery surface.
- [x] Keep every new game tool free, accountless, and disconnected from paid-answer entry points.

## Tools

- Project Zomboid save-change risk planner
- Escape from Tarkov loadout replacement budget
- ARK: Survival Ascended roster material planner
- Warframe upgrade priority comparator
- Once Human scenario fit comparator
- CS2 team buy budget calculator
- Dota 2 item decision comparator
- PUBG rotation timing planner
- Rainbow Six Siege operator unlock comparator

The existing Rust raid calculator remains available as the tenth item in the shared tool directory.

## Verification Boundary

- Budget tools calculate only from values entered by the player.
- Weighted comparison tools expose every criterion and weight.
- The Project Zomboid score is an operational planning score, not a corruption probability.
- The PUBG result is a timing margin based on estimated distance, speed, and delays, not live map telemetry.
- Every worksheet retains assumptions and review date.
- No tool contains a paid CTA or unlock requirement.

## Resume Here

Phase 5 is complete and documented in `operations/multigame-expansion-phase-5.md`. Phase 6 builds the shadow-mode answer benchmark and independent QA layer without charging players.
