# Rust Full Raid Staging Pack

Status: production live
Version: `rust-staging-pack-v1`
Effective: 2026-09-06

## Commercial Contract

- Price: USD 4.99, one-time purchase.
- Launch markets: United States and Canada.
- Fulfilment: deterministic generation immediately after PayPal capture.
- Account: not required before or after purchase.
- Owner involvement: none for a normally completed order.
- Unsupported scope: non-vanilla servers, stale evidence, invalid routes, and failed recalculation cannot enter checkout.
- Refund and payment exceptions: handled under the published refund policy and PayPal merchant process.

## Customer Input

- One to twelve route lines.
- Target, quantity, and selected breach method for each line.
- Route priority: lowest sulfur or fewest placements.
- Planning buffer: 0, 10, 15, or 20 percent.
- Optional available sulfur and explosive inventory.
- Team size from one to twenty.
- Optional private route note, capped at 1,000 characters.

## Free Preview

- Selected route item and sulfur totals.
- Buffered sulfur target.
- Readiness status and one actionable reason.
- Current data date and supported vanilla scope.
- A clear list of the report sections that remain locked.

The preview must be useful without disclosing the complete alternative-route and staging report.

## Paid Report

- Selected, lowest-sulfur, and fewest-placement route comparison.
- Target-by-target four-method comparison.
- Owned inventory, required inventory, and exact shortfalls.
- Gunpowder batches, sulfur component, and charcoal requirement.
- Planning buffer and available-sulfur decision.
- Team roles, staging checkpoints, and stop conditions.
- Evidence links, data date, independent recalculation status, and limitations.
- Browser-rendered report, JSON download, printable PDF workflow, and free-route share link.

## Security And Delivery

- The server stores only a SHA-256 hash of the 256-bit delivery token.
- The token is an unguessable bearer credential for one report. PayPal query parameters and private-link fragments are read before analytics loads and then removed from the browser URL.
- The customer can download JSON, print or save PDF, or copy a private fragment link for cross-device recovery. The free route link never contains the paid-report token.
- The full report is unavailable until the corresponding PayPal order is completed.
- Refunds and reversals revoke report access.
- PayPal capture and webhook processing remain idempotent.
- Analytics records funnel events but never records route notes, report tokens, PayPal identifiers, or report contents.

## Acceptance Gates

1. An anonymous visitor can generate a valid preview without an account.
2. An unsupported or stale request cannot create a PayPal order.
3. A completed capture activates exactly one report and grants zero credits.
4. Repeating capture or webhook calls cannot duplicate delivery or ledger entries.
5. A wrong token cannot reveal order or report existence.
6. A refunded or reversed order cannot retrieve the paid report.
7. The complete demo journey runs locally on port 4289.
8. Production exposes the product only when PayPal and paid Rust data are ready.

## Production Evidence

- Backend release: `/opt/raidbench/releases/20260906T235127Z-first-sale-v14`.
- Runtime image: `local/raidbench-runtime:2026-09-07-first-sale-v14`.
- Cloudflare Pages deployment: `https://68f0e231.raidbench.pages.dev`.
- Public product: `https://raidbench.com/rust-raid-staging-pack`.
- Production health: PayPal Live and webhook ready, paid Rust data verified at 2026-09-06, checkout ready.
- Production smoke test: anonymous preview passed; no PayPal test order or charge was created during deployment.
