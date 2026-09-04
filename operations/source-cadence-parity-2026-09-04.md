# RaidBench Source Cadence Parity

## Decision

All twelve games now use the same collection cadence by source role:

- Publisher-controlled factual sources: every hour.
- Community demand discovery: at most once per game per UTC day.

This matches the Rust operating model. It does not make Reddit or Steam community discussions an hourly bulk-crawl lane.

## Scope

- 25 official, publisher, and publisher-via-Steam sources use `cadence=1h`.
- 12 community demand profiles use `cadence=24h` and `fetchMode=search-only`.
- `raidbench-source-scout.timer` wakes hourly and fetches only due direct sources.
- The source-scout service allows up to 12 minutes for a complete 25-source cycle.
- `raidbench-multigame-demand.timer` rotates three games every six hours, while the state file prevents more than one attempt per game per UTC day.
- Reddit Data API use, bulk community scraping, and automatic external posting remain disabled.

## Verification

`tests/test-source-registry.mjs` fails if any factual source differs from the one-hour policy or any demand profile differs from the daily policy.
