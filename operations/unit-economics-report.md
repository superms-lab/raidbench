# RaidBench Unit Economics

Generated: 2026-09-06T15:31:23.844Z
Model as of: 2026-09-06
Provider: PayPal China cross-border
Scenario: US and Canada organic launch

## Decision

The account-free Rust staging pack and the legacy North America credit products pass their modeled organic-launch cost floors. The staging pack is the primary public Rust conversion path. Paid acquisition remains a separate scenario and must not be scaled until measured acquisition cost fits inside contribution.

## Product Economics

| Product | Price | Variable cost before ads | CAC | Net per order after fixed allocation | Net margin | Decision |
|---|---:|---:|---:|---:|---:|---|
| Rust Full Raid Staging Pack | $4.99 | $1.90 | $0.00 | $0.48 | 9.6% | VIABLE |
| Verified Rust Answer Starter | $5.00 | $1.91 | $0.00 | $0.48 | 9.5% | VIABLE |
| Rust Raid Plan Standard | $19.00 | $9.21 | $0.00 | $7.17 | 37.7% | VIABLE |
| POE2 Build Audit Standard | $39.00 | $18.16 | $0.00 | $18.22 | 46.7% | VIABLE |
| Priority Complex Review | $69.00 | $31.35 | $0.00 | $35.04 | 50.8% | VIABLE |

Monthly fixed-cost planning reserve: $78.50. Monthly order assumption: 30.

## Credit Action Audit

Each ready credit action is tested against the least profitable positive-credit pack allocation, including allocated payment fees, withdrawal reserve, tax reserve, refund reserve, chargeback reserve, and its own delivery profile. The account-free staging product is modeled separately above. Blocked products are not treated as sellable revenue.

| Action | Credits | Conservative gross | Modeled variable cost | Contribution | Margin | Decision |
|---|---:|---:|---:|---:|---:|---|
| Verified Rust Raid Route Check | 10 | $1.58 | $0.50 | $1.09 | 68.7% | VIABLE |
| POE2 Item Value Decision | 3 | $0.00 | $0.00 | $0.00 | - | BLOCKED |
| POE2 Boss Prep | 6 | $0.00 | $0.00 | $0.00 | - | BLOCKED |
| POE2 Farming Route Score | 8 | $0.00 | $0.00 | $0.00 | - | BLOCKED |
| POE2 Build Audit | 10 | $0.00 | $0.00 | $0.00 | - | BLOCKED |
| Rust Raid Prep | 120 | $19.00 | $9.21 | $9.79 | 51.5% | VIABLE |

## Orders Needed For Monthly Net Target

| Product | $2,000 net | $5,000 net | $20,000 net |
|---|---:|---:|---:|
| Rust Full Raid Staging Pack | 672 | 1642 | 6491 |
| Verified Rust Answer Starter | 673 | 1643 | 6495 |
| Rust Raid Plan Standard | 213 | 519 | 2052 |
| POE2 Build Audit Standard | 100 | 244 | 964 |
| Priority Complex Review | 56 | 135 | 534 |

## Cost Sources And Limits

- Payment fee source: https://www.paypal.com/c2/business/paypal-business-fees?locale.x=en_C2
- Published Mainland China international commercial transaction rate: 4.40% plus the currency fixed fee. Currency conversion and withdrawal costs are separate.
- The launch model covers customers in the United States and Canada, with checkout denominated in USD. Europe is deferred and is not part of the launch-critical workflow.
- Tax reserve is a planning buffer, not a tax determination. Replace it after the seller model, buyer location rules, sales-tax or GST/HST obligations, and accountant advice are confirmed.
- AI costs are working budgets, not vendor quotes. Replace them with measured token and tool costs from real deliveries.
- Cloudflare is modeled at zero only while actual usage stays inside the applicable free-plan limits.
- The fixed-cost model reserves one 35 USD PayPal wire withdrawal per month. Replace this with the actual withdrawal path and frequency; eligible no-conversion Hong Kong bank withdrawals can differ.
- The 2.5% FX and withdrawal percentage is a planning reserve. Actual currency conversion can vary by transaction type and account path.
- No paid acquisition should be scaled until measured customer acquisition cost is below contribution before advertising.
- The 4.99 USD staging pack is intentionally modeled as a low-friction validation product with deterministic delivery. Reprice it from measured conversion, support, refund, and withdrawal costs rather than treating the launch price as permanent.
- The 5 USD legacy credit starter remains in the cost model for comparison but is no longer the primary public Rust conversion path.
