# RaidBench Multi-Game Expansion

## Current Position

Phase 1 of 8 is complete locally and in production. Phase 2 is documented in `operations/multigame-expansion-phase-2.md`.

The single source of truth is `content/game-registry.json`. It defines twelve games, canonical hub routes, display names, genre filters, editorial state, indexing state, paid-answer state, decision areas, and initial question lanes.

## Phase 1 Deliverables

- [x] Register all twelve games in one versioned data model.
- [x] Generate `/games` and `/games/<game>/` routes from the registry.
- [x] Add an interactive twelve-game selector to the homepage.
- [x] Add genre filters to the shared game directory.
- [x] Assign existing Rust, POE2, and Palworld guides to their canonical hubs.
- [x] Generate the guide-library filters from the same registry.
- [x] Apply one shared Games / Guides / Patch Watch / About navigation to public content.
- [x] Preserve the existing shared account, credits, orders, analytics, and Rust payment stack.
- [x] Keep paid answers enabled only for the already verified Rust product.
- [x] Keep nine new game hubs `noindex,follow` until useful source-checked coverage exists.
- [x] Redirect the legacy `/poe2` and `/palworld` hub routes to the canonical game directories.
- [x] Include game hubs in public build validation, trailing-slash sitemap handling, and static packaging.

## Canonical Routes

- `/games/rust/`
- `/games/poe2/`
- `/games/palworld/`
- `/games/project-zomboid/`
- `/games/escape-from-tarkov/`
- `/games/ark-survival-ascended/`
- `/games/warframe/`
- `/games/once-human/`
- `/games/counter-strike-2/`
- `/games/dota-2/`
- `/games/pubg-battlegrounds/`
- `/games/rainbow-six-siege/`

## Safety Boundary

The new hubs are architecture, not a claim that RaidBench can already answer every game question. A game becomes indexable only after its initial content set has current primary sources, a defined patch scope, editorial QA, and working internal links. A game becomes eligible for paid answers only after its answer type has deterministic checks or a documented evidence-and-review gate.

## Resume Here

Phase 2 is the twelve-game demand and source pipeline. Add publisher-controlled patch sources, bounded community-demand discovery, normalized game identifiers, deduplication, source freshness rules, and a scored private backlog without publishing new answers yet.
