# RaidBench Multi-Game Expansion - Phase 6

## Status

Phase 6 of 8 is complete locally, synchronized to the VPS, and operating in production shadow mode. No new paid product was activated.

Cloudflare Pages deployment: `https://a5132d9c.raidbench.pages.dev`

Shadow Agent image: `local/raidbench-content-agent:2026-09-04-shadow-qa-v2`

## Delivered

- [x] Define machine-readable activation gates for all eleven non-Rust products.
- [x] Require 15-25 distinct cases, at least 90% supported-case QA, exact no-charge behavior, zero critical drift, current evidence, idempotency, and in-account delivery before activation.
- [x] Add one supported, one missing-context, and one policy-blocked benchmark for every product.
- [x] Build 33 unique benchmark keys without counting repeat runs as new cases.
- [x] Capture current publisher evidence from the isolated Source Scout database into a closed Agent input.
- [x] Add a no-charge answer-author Agent and a different independent-review Agent.
- [x] Add deterministic calculation checks for nine products: 28 assertions in total.
- [x] Require the complete paid product promise, not merely a safe partial answer.
- [x] Block internal evidence IDs from customer-facing answer text.
- [x] Store runs, attempts, current results, and product readiness in a separate SQLite database with a database-level `credits_charged=0` constraint.
- [x] Fingerprint official source content so unchanged fetches do not rerun Agents, while changed evidence reopens the case.
- [x] Add a six-hour VPS timer that processes at most two genuinely new or changed supported cases per run.
- [x] Add live shadow-case results to the private Chinese product-admission dashboard.

## First Benchmark Result

| Result | Count | Meaning |
|---|---:|---|
| Complete answer passed | 6 | One bounded case passed authoring, independent review, calculations, and final answer validation. |
| Complete request safely held | 5 | Available evidence could not fulfill the complete paid product promise, so the answer was not delivered. |
| Missing-context or policy request correctly rejected | 22 | Every expected no-charge case matched the required reason. |
| Contract or critical failures in the current result set | 0 | Earlier development failures were corrected and remain only in attempt history. |
| Credits charged | 0 | Shadow mode cannot access or debit the commerce ledger. |
| Products eligible for checkout | 0 | Three cases per product is below every activation threshold. |

Passed supported cases: Palworld, Project Zomboid, Escape from Tarkov, ARK: Survival Ascended, Warframe, and Once Human.

Safely held supported cases: POE2, Counter-Strike 2, Dota 2, PUBG, and Rainbow Six Siege. These cases contained enough information for a narrow checklist or calculation, but not enough to deliver the full paid product described in the catalog.

## Quality Findings

The first POE2 draft was factually cautious but did not deliver the promised verified bottleneck and prioritized repairs. Adding the product-promise gate changed the correct result to independently confirmed no charge.

The first CS2, Dota 2, PUBG, and Rainbow Six Siege drafts tried to elevate free calculator output into a complete match or site review. The strengthened author contract now refuses those requests before a partial answer reaches delivery.

The ARK benchmark exposed a floating-point ceiling error where mathematically integral totals could be rounded one unit too high. The shared tool engine now applies stable ceiling correction, and the production tool returns 7,700 hide, 3,960 fiber, and 1,320 metal for the benchmark inputs.

## Runtime Boundary

```text
/opt/raidbench-agent/data/raidbench.shadow.db
/opt/raidbench-agent/artifacts/shadow-benchmarks/
/opt/raidbench-publisher/workspace/scripts/run_shadow_answer_benchmarks.py
raidbench-shadow-qa.timer
```

The shadow container mounts the public-content workspace, Source Scout database, private artifact directory, and Codex login. It does not mount `/opt/raidbench/data/raidbench.db`, PayPal secrets, customer sessions, orders, or the production credit ledger.

The timer runs at 02:50, 08:50, 14:50, and 20:50 UTC with up to five minutes of randomized delay. It refreshes source evidence first, then processes at most two new or content-changed supported cases. Identical evidence and identical benchmark inputs are skipped.

## Public Release

- The corrected multi-game tool engine is live and its production hash matches the tested local file.
- Public Rust static data now carries the production-verified date `2026-09-03`.
- A top-level `404.html` disables Cloudflare Pages' soft-404 fallback. Private owner paths, benchmark paths, and unknown routes now return HTTP 404 rather than the homepage with HTTP 200.
- The public paid-action catalog still contains only `rust-instant-raid-answer` and `rust-raid-prep`.

## Verification Evidence

- Python tests: 98 passed.
- Node test files: 12 passed.
- Shadow calculation assertions: 28 passed across nine products.
- Public HTML files checked: 191.
- Indexable public pages: 141.
- Indexable guide and update pages: 108.
- Interactive multi-game tools: 9, plus the existing Rust calculator.
- Public build: 142 approved HTML routes plus the custom 404 page.
- Shadow SQLite integrity: `ok`.
- Installed shadow service result: success; an unchanged suite skipped all 33 cases.
- Owner dashboard: 11 product rows, zero console errors, and zero page overflow at 390 px.

## Safety Boundary

A passed benchmark proves only that one specific closed case can be handled. It does not approve the whole product. Repeating the same case does not increase readiness. A product remains hidden until every structured activation gate passes against distinct current cases and the real in-account delivery path is tested.

## Resume Here

Phase 7 is complete and documented in `operations/multigame-expansion-phase-7.md`. Phase 8 is the controlled Palworld production launch; no other non-Rust product is eligible.
