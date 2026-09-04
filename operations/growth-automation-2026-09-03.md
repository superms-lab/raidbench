# RaidBench Growth Automation

Updated: 2026-09-03
Timezone: Asia/Shanghai

## Weekly Targets And Implementation

| Target | Automation | Quality boundary | Current status |
| --- | --- | --- | --- |
| 9 high-intent Rust problem pages | Three daily Rust community searches feed demand signals; the content Agent publishes at most two total guides per day and stops Rust at nine per ISO week | Every page needs authoritative evidence and five-stage QA | Active; first new demand-backed Rust page published 2026-09-03 |
| POE2 in parallel | One daily POE2 demand search; POE2 stops at three guides per ISO week | Demand is context only; facts still require official or publisher evidence | Active |
| 3 calculator presets, comparisons, or downloads | Twelve reviewed Rust route presets are released in groups of three each Monday | Presets contain route inputs, not invented raid counts; live calculator applies the reviewed dataset | Active; first three are public |
| 3 patch-sensitive refreshes | Monday, Wednesday, and Friday rotate through the patch registry | A source change marks the page for revision; the system never changes a review date merely to look fresh | Active; first baseline completed |
| 3 link-free professional Reddit replies per day | Searches run around 08:25, 13:25, and 18:25 China time; the 20:00 Feishu digest can contain up to three distinct drafts | No Reddit API, bulk crawl, links, brand promotion, or automatic public posting | Active; owner still performs public posting |
| One disclosed UTM link on the Reddit profile | Prepared profile post points to the free planner/paid offer with `reddit_profile` UTM attribution | Standalone promotional posts require owner review | Prepared, not verified as published or pinned |
| 6 Rust partner contacts per week | Tuesday Agent finds only official public partnership/business contacts; strict validation, one contact per domain, no automatic follow-up | Gambling, skin trading, cheats, RMT, private contacts, and unverified addresses are rejected | Six contacts completed in the current rolling seven-day window |

## Timers

- `raidbench-community-scout.timer`: three windows per day.
- `raidbench-poe2-demand.timer`: once per day.
- `raidbench-content-agent.timer`: hourly selection and fail-closed publication.
- `raidbench-growth-assets.timer`: Monday release of three route assets.
- `raidbench-patch-refresh.timer`: Monday, Wednesday, and Friday source revalidation.
- `raidbench-partner-outreach.timer`: Tuesday bounded partner outreach.
- `raidbench-acquisition-digest.timer`: 20:00 China-time Feishu digest.

## Current Published Asset

- Route preset library: https://raidbench.com/rust-route-presets
- First demand-backed Rust page: https://raidbench.com/pages/rust-limited-playtime-session-plan

## Operating Truth

These values are targets and hard ceilings, not permission to publish filler. A week may finish below target if
current sources, duplicate checks, partner verification, or QA do not support the requested output. The owner
dashboard should report actual outputs separately from targets.
