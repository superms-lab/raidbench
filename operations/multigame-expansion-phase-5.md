# RaidBench Multi-Game Expansion - Phase 5

## Status

Phase 5 of 8 is complete locally, synchronized to the VPS publisher workspace, and deployed to the production customer backend.

Production backend release: `/opt/raidbench/releases/20260903T135435Z-phase5-product-gates-v7`

## Delivered

- [x] Define one draft paid-answer product for each of the eleven non-Rust games.
- [x] Set credit prices from 80 to 180 credits according to delivery complexity.
- [x] Record required player inputs, factual evidence, independent QA, activation gates, and no-charge reasons for every product.
- [x] Model PayPal fees, withdrawal and conversion reserve, AI work, independent review, support, and fixed operating costs.
- [x] Keep every new product at `hidden_pending_qa`, regardless of positive modeled margin.
- [x] Load hidden products into the production `credit_actions` table without returning them from the public checkout catalog.
- [x] Add a shared multi-game request router with game/product validation, missing-context detection, policy screening, and idempotent intake.
- [x] Store the correct game name and quoted credit cost while keeping `credits_charged=0` for every held request.
- [x] Add a public-safe product endpoint that exposes only `ready_live` products and reports the hidden count without leaking draft offers.
- [x] Add a private Chinese product-admission dashboard with desktop and mobile QA.

## Product Inventory

| Game lane | Products | Credit range | Checkout state |
|---|---:|---:|---|
| POE2 and Palworld | 2 | 80-120 | Hidden pending QA |
| Nine newly expanded games | 9 | 80-180 | Hidden pending QA |
| Total non-Rust | 11 | 80-180 | 0 public |

The production database now contains seventeen credit actions: two Rust actions are `ready_live`, four legacy POE2 actions remain blocked, and eleven Phase 5 products are `hidden_pending_qa`.

## Unit Economics

All eleven draft products clear their delivery-class contribution-margin target under the current conservative model. Modeled contribution margins range from 40.9% to 48.1%; zero products require a price hold.

This is not an answer-quality approval. The model uses the official PayPal Mainland China international commercial-receipt rate of 4.40% plus the USD 0.30 fixed fee, a 2.5% conversion and withdrawal reserve, and one USD 35 monthly bank-wire withdrawal reserve. Tax remains a planning reserve rather than a tax determination.

## Runtime Contract

- `GET /api/multigame/products` returns only `ready_live` products. Its Phase 5 production result contains zero products and `hiddenPendingQaCount=11`.
- `POST /api/questions/multigame` requires an authenticated customer and an idempotency key.
- Missing context, prohibited scope, pending QA, or an unavailable verified handler produces `held_without_charge`.
- A held request records the game, product, inputs, reason, and quoted credits, but always records zero charged credits.
- The shared router never performs a debit. A future live handler must deliver through the separately verified answer service.

## Verification Evidence

- Local Python suite: 92 tests passed.
- Local Node suite: all 11 test files passed.
- Release-specific VPS suite: 20 Python tests and the multi-game economics test passed before activation.
- Production SQLite integrity: `ok`.
- Production container: running and healthy.
- PayPal environment: Live; checkout remains enabled for existing verified products.
- Production database comparison: customer, order, ledger, and question row counts were unchanged from the pre-release backup.
- Public checkout catalog after deployment: four credit packs and two Rust actions only.
- Private dashboard QA: 11 rendered rows, no console warnings or errors, no body overflow at 390 px, and internal horizontal scrolling for the wide product table.

## Safety Boundary

Positive margin cannot override answer QA. No non-Rust product may become public merely because its content pages, tools, or pricing exist. Activation requires the product-specific shadow-case count, supported-case QA rate, source freshness, factual-drift limit, no-charge behavior, idempotency, and in-account delivery checks to pass.

## Resume Here

Phase 6 is complete and documented in `operations/multigame-expansion-phase-6.md`. Phase 7 expands distinct activation evidence and validates real in-account delivery without bypassing any product gate.
