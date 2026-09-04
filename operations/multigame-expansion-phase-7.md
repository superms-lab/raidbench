# RaidBench Multi-Game Expansion - Phase 7

## Status

Phase 7 of 8 is complete locally and on the VPS. One product passed every machine-readable activation gate, but no non-Rust product was published or added to checkout.

Customer backend release: `/opt/raidbench/releases/20260903T231208Z-phase7-patch-gate-v8`

Cloudflare Pages deployment: `https://59f058be.raidbench.pages.dev`

Activation candidate: `palworld-base-progression-review`

Candidate state: `eligible_not_published`

## Delivered

- [x] Expand the shadow suite from 33 to 67 genuinely distinct case inputs.
- [x] Give every non-Rust product at least two supported cases and three no-charge cases.
- [x] Expand Palworld to its complete 15-case gate: ten supported cases and five no-charge cases.
- [x] Expand Project Zomboid and Once Human to six cases each and execute every new case.
- [x] Execute all 67 current cases rather than leaving a timer backlog.
- [x] Add a second blind reviewer for CS2, Dota 2, and PUBG complex-match products.
- [x] Require at least ten dual-reviewed cases and 80% agreement before a complex product can activate.
- [x] Add reviewer-disagreement and disputed-no-charge outcomes without treating them as delivered answers.
- [x] Verify in-account delivery and idempotent credit debit with the real production store functions inside isolated temporary commerce databases.
- [x] Bind delivery-gate validity to both the reviewed-answer fingerprint and delivery-code fingerprint.
- [x] Add delivery verification and private activation-manifest generation to the six-hour shadow service.
- [x] Generate an activation candidate only when every product gate is machine-verifiably green.
- [x] Keep the candidate manifest private and prohibit automatic public-catalog mutation.
- [x] Add a production paid-data status file so a newly detected Rust patch immediately hides Rust actions and new credit checkout until review passes.
- [x] Review Rust Breach and Clear changelist 4045, verify monitored counts and recipes, clear the blocked service, and publish the current Patch Watch brief.

## Current Results

| Product | Cases | Supported result | No-charge result | Dual review | Delivery gates | Decision |
|---|---:|---|---|---|---|---|
| Palworld | 15 / 15 | 9 passed, 1 review hold | 5 / 5 correct | Not required | Passed | Eligible, hidden |
| Project Zomboid | 6 / 15 | 3 passed | 3 / 3 correct | Not required | Passed | Hold |
| Once Human | 6 / 15 | 3 passed | 3 / 3 correct | Not required | Passed | Hold |
| POE2 | 5 / 20 | 2 held | 3 / 3 correct | Not required | Not available | Hold |
| Tarkov | 5 / 20 | 1 passed, 1 held | 3 / 3 correct | Not required | Passed | Hold |
| ARK | 5 / 20 | 1 passed, 1 review hold | 3 / 3 correct | Not required | Passed | Hold |
| Warframe | 5 / 20 | 1 passed, 1 held | 3 / 3 correct | Not required | Passed | Hold |
| CS2 | 5 / 25 | 2 held | 3 / 3 correct | 2 cases, 100% agreement | Not available | Hold |
| Dota 2 | 5 / 25 | 2 held | 3 / 3 correct | 2 cases, 100% agreement | Not available | Hold |
| PUBG | 5 / 20 | 2 held | 3 / 3 correct | 2 cases, 50% agreement | Not available | Hold |
| Rainbow Six Siege | 5 / 20 | 2 held | 3 / 3 correct | Not required | Not available | Hold |

Aggregate current results:

- Distinct cases: 67
- Approved complete answers: 18
- Supported requests proactively held without charge: 10
- Candidate answers held by QA: 4
- Correct missing-context or policy no-charge cases: 35
- Current contract failures: 0
- Current critical failures: 0
- Credits charged: 0

## Palworld Gate Result

Palworld is the first product to pass all ten gates:

1. 15 distinct shadow cases.
2. 10 supported cases.
3. 9 of 10 supported cases approved, exactly 90%.
4. 5 no-charge cases.
5. 100% no-charge accuracy.
6. At least ten cases with zero current critical failures.
7. No second-review requirement for this delivery class.
8. Current publisher evidence.
9. Idempotent debit verified.
10. In-account delivery verified.

The one held supported case was not hidden. The author considered the crafting-queue evidence too weak; the independent reviewer concluded a bounded observed-bottleneck diagnosis was possible and rejected the overly broad refusal. The answer was not delivered, and the resulting pass rate remains exactly the required 90%.

## Delivery Evidence

Six products with at least one approved answer passed the isolated delivery test: Palworld, Project Zomboid, Tarkov, ARK, Warframe, and Once Human.

For Palworld's 80-credit action, an isolated test account followed this sequence:

```text
Starting balance: 450
After first delivery: 370
After idempotent replay: 370
Questions created: 1
Answer-debit ledger rows: 1
In-account delivery rows: 1
```

The test creates no production order, writes no production customer, and charges no production credits. An unchanged reviewed answer and unchanged delivery code produce `unchanged_pass` instead of repeating the test.

## Complex Review Evidence

CS2, Dota 2, and PUBG now use an author, the existing independent reviewer, and a second blind peer reviewer. The peer reviewer reads the case and candidate but cannot read the first review.

CS2 and Dota 2 currently have two agreements from two dual-reviewed cases. PUBG has one agreement and one disagreement from two cases. None can pass the gate until at least ten dual-reviewed cases exist and agreement is at least 80%.

## Private Activation Manifest

```text
/opt/raidbench-agent/artifacts/shadow-benchmarks/latest-activation-candidates.json
```

The manifest contains one candidate, Palworld, and records `publicCatalogMutationPerformed=false`. It fails closed if readiness reports nonzero shadow credits, a missing product, a failed gate, or a catalog status other than `hidden_pending_qa`.

## Automated Cycle

`raidbench-shadow-qa.service` now runs four ordered steps:

1. Rebuild the closed suite from current Source Scout evidence.
2. Process at most two genuinely new or evidence-changed supported cases.
3. Recheck delivery when the reviewed answer or production delivery code changes.
4. Rebuild the private activation candidate manifest.

Repeated evidence and repeated benchmark inputs do not increase case counts or consume additional Agent calls.

## Public Boundary

- `content/multigame-products.json` still marks all eleven non-Rust products `hidden_pending_qa`.
- The public multi-game product API still returns zero products.
- The public checkout catalog still exposes only the two verified Rust actions.
- Phase 7 did not publish a non-Rust product and created no real order.
- A public Cloudflare deployment was required for the Rust 4045 data refresh and Breach and Clear Patch Watch page; it did not change the Palworld catalog status.

## Rust Patch Gate Incident

During final production checks, `raidbench-content-check.service` correctly detected Facepunch changelist 4045, Breach and Clear, and failed because production data still named changelist 4044. The public API remained operational, which exposed a design gap: a failed systemd verification did not immediately disable a recently dated paid dataset.

The permanent fix adds `/opt/raidbench/data/rust-paid-data-status.json`. Every hourly verification now writes `verified` or `blocked`, the accepted and latest changelist IDs, the data-file SHA-256, the check timestamp, and errors. The customer backend validates the status, changelist, file hash, and 72-hour freshness on every relevant request. A blocked or missing production status now:

- sets public `checkoutEnabled=false` when no other verified live answer exists;
- removes Rust actions and credit packs from `/api/catalog`;
- stores a submitted Rust request as held without charging credits;
- continues accepting capture and webhook reconciliation for already-approved PayPal orders.

The official Breach and Clear notes add group-scaled TC upkeep, monument blockers, grenade stack changes, and other balance changes. The post-update verifier found no mismatch in the six monitored door/wall counts, sulfur-per-item values, or official explosive recipe markers, so changelist 4045 was accepted with those new mechanics explicitly outside the six-target dataset. The new Patch Watch page is `/pages/rust-breach-and-clear-raid-upkeep-check`.

## Verification Evidence

- Local Python tests: 105 passed.
- Local Node test files: 12 passed.
- Public-site validation: 192 HTML files checked, 142 indexable pages, 109 guide/update pages, and 9 multi-game tools.
- All 67 suite cases are represented in the shadow database.
- All 18 currently approved answers pass the final paid-answer validator and contain no internal evidence IDs in customer text.
- Shadow SQLite integrity: `ok`.
- Current failed cases: 0.
- Current critical failures: 0.
- Current shadow credits charged: 0.
- Delivery tests: 6 tested, 6 passed.
- Activation manifest: 1 eligible, 0 public mutations, 0 production orders, 0 production credits.
- Four-step installed systemd service: success.
- Rust paid-data service: success against changelist 4045; no failed systemd units remain.
- Public API: `paidDataStatus=verified`, PayPal Live checkout enabled, and only the two Rust actions visible.
- Owner dashboard: 67 cases, 18 approved, 10 proactive holds, 4 QA holds, 35 correct no-charge cases, and Palworld visibly marked as machine-eligible but hidden.

## Safety Boundary

Machine eligibility is necessary but not sufficient for publication. The production backend still has no asynchronous Palworld answer worker or public Palworld intake. Publishing the catalog entry before those pieces exist would sell a product the live system cannot yet fulfill.

## Resume Here

Phase 8 is the controlled Palworld launch. Implement the production answer-job queue and isolated worker handoff, add the Palworld customer intake and status UI, activate only the 80-credit Palworld product after end-to-end production-mode tests, deploy without exposing other products, and monitor the first legitimate payment, debit, answer, correction, and refund path.
