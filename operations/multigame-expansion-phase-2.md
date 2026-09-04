# RaidBench Multi-Game Expansion - Phase 2

## Status

Phase 2 of 8 is complete locally and on the production VPS. Phase 3 is documented in `operations/multigame-expansion-phase-3.md`.

## Delivered

- [x] Register publisher-controlled and Steam publisher-feed sources for all twelve games.
- [x] Register one bounded community-demand profile for every game.
- [x] Keep community material demand-only and outside the factual evidence boundary.
- [x] Disable every legacy Reddit JSON/API source.
- [x] Add normalized `game_catalog` and `content_source_profiles` database tables.
- [x] Add deduplicated `demand_backlog` and `demand_observations` tables.
- [x] Add deterministic pain, commercial, freshness, patch, and opportunity scores.
- [x] Add cross-source fuzzy title deduplication and exact URL deduplication.
- [x] Include historical Reddit reply drafts and existing content signals in global deduplication.
- [x] Add domain pacing, transient retry, and normalized content hashes for direct source monitoring.
- [x] Record initial HTML pages as baselines instead of false update events.
- [x] Rotate three games every six hours so all twelve demand lanes run once per day.
- [x] Replace the standalone POE2 demand timer with the shared multi-game timer.
- [x] Add a private Chinese demand dashboard at `http://127.0.0.1:4289/owner-demand-zh.html`.

## Production Inventory

- Registered games: 12
- Registered source profiles: 37
- Direct fact-monitoring sources: 25
- Community demand profiles: 12
- Active Reddit Data API sources: 0
- Initial private backlog after one complete rotation: 15
- High-scoring new community demand items: 9
- Official source-change triggers: 5
- Low-score observation items: 1

The first complete rotation found verified candidates for POE2, Palworld, Project Zomboid, Escape from Tarkov, ARK, Warframe, Once Human, Dota 2, and Rainbow Six Siege. PUBG produced a low-score observation. CS2 produced no verified candidate and was left empty rather than filled with a weak result. Rust's candidate matched a historical reply draft and was automatically removed by the global deduplication pass.

## Runtime

The direct source scout checks hourly but honors each source's configured one-to-twelve-hour cadence. It reads only entries marked `fetchMode=direct` and `role=fact`.

The community-demand timer runs at 00:40, 06:40, 12:40, and 18:40 UTC with up to ten minutes of randomized delay. Each run handles at most three games and finds at most one exact recent question per game. It does not log in, use the Reddit Data API, crawl listings in bulk, contact users, or publish externally.

## Source Boundary

- `content/game-registry.json` owns canonical game identity.
- `content/source-registry.json` owns source permissions, cadence, freshness, and authority.
- Official publisher pages and publisher Steam feeds may support factual claims.
- Reddit and Steam discussion threads may prove demand only.
- A backlog item is not an approved article, answer, or paid service.

## Resume Here

Phase 3 is the simultaneous baseline content pack. Promote reviewed high-value backlog items into source packets, create the first useful content cluster for each new game, add internal links and visible review metadata, keep paid answers closed, and make a game indexable only after its launch gate passes.
