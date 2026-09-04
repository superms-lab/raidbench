# RaidBench Source Cadence Parity

## Decision

All twelve games now use the same collection cadence by source role:

- Publisher-controlled factual sources: every hour.
- Community demand discovery: at most once per game per UTC day.
- Owned-site publication: one QA-approved guide per hour at most.

This matches the Rust operating model. It does not make Reddit or Steam community discussions an hourly bulk-crawl lane.

## Scope

- 25 official, publisher, and publisher-via-Steam sources use `cadence=1h` and fixed UTC minute offsets `00, 02, 04, ... 48`.
- 12 community demand profiles use `cadence=24h` and `fetchMode=search-only`.
- `raidbench-source-scout.timer` wakes every minute and processes at most two due or catch-up sources.
- A failed source waits 15 minutes before another attempt.
- Minutes without a due source exit without creating an empty database run row.
- `raidbench-multigame-demand.timer` rotates three games every six hours, while the state file prevents more than one attempt per game per UTC day.
- `raidbench-content-agent.timer` runs at UTC minute `55:30` and can publish at most one guide per hour, 24 per day, and 14 per game per week.
- All twelve games have two publisher-controlled sources eligible for content QA; the Rust commit stream is collection-only.
- Reddit Data API use, bulk community scraping, and automatic external posting remain disabled.

## UTC Minute Slots

| Game | Collection minute(s) each hour |
|---|---|
| Rust | `00`, `02`, `04` |
| POE2 | `06`, `08` |
| Palworld | `10`, `12` |
| Project Zomboid | `14`, `16` |
| Escape from Tarkov | `18`, `20` |
| ARK: Survival Ascended | `22`, `24` |
| Warframe | `26`, `28` |
| Once Human | `30`, `32` |
| Counter-Strike 2 | `34`, `36` |
| Dota 2 | `38`, `40` |
| PUBG: BATTLEGROUNDS | `42`, `44` |
| Rainbow Six Siege | `46`, `48` |
| Content QA and publication | `55:30` |

## Verification

`tests/test-source-registry.mjs`, `tests/test-source-schedule.mjs`, and `tests/test-hourly-content-schedule.mjs` fail if cadence, minute slots, per-run limits, publication timing, or publication ceilings drift.

The first production staggered window showed one source at each even-minute slot and zero sources at the intervening odd minutes, with no failed source. The first cross-game publication attempt exposed and safely blocked two legacy three-game assumptions: missing same-game inventory records and a hard-coded generator allowlist. Both were replaced with synchronized public inventory and the twelve-game registry.

The repaired production cycle published:

```text
https://raidbench.com/pages/once-human-september-2-update-workflow-check
```

Cloudflare deployment `https://8acb441a.raidbench.pages.dev` completed, production returned HTTP 200, and IndexNow accepted the URL. The regular `05:55:30 UTC` timer then detected that one guide had already started in that UTC hour and correctly skipped a second publication.
