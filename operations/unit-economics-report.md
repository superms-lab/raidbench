# RaidBench Unit Economics

Generated: 2026-09-04T00:32:16.810Z
Model as of: 2026-09-03
Provider: PayPal China cross-border
Scenario: US and Canada organic launch

## Decision

The North America credit packs pass the modeled cost floor for both launch-ready Rust actions. POE2 actions remain blocked until their evidence QA is complete. Paid acquisition remains a separate scenario and must not be scaled from this organic-launch result.

## Product Economics

| Product | Price | Variable cost before ads | CAC | Net per order after fixed allocation | Net margin | Decision |
|---|---:|---:|---:|---:|---:|---|
| Verified Rust Answer Starter | $5.00 | $1.91 | $0.00 | $0.48 | 9.5% | VIABLE |
| Rust Raid Plan Standard | $19.00 | $9.21 | $0.00 | $7.17 | 37.7% | VIABLE |
| POE2 Build Audit Standard | $39.00 | $18.16 | $0.00 | $18.22 | 46.7% | VIABLE |
| Priority Complex Review | $69.00 | $31.35 | $0.00 | $35.04 | 50.8% | VIABLE |

Monthly fixed-cost planning reserve: $78.50. Monthly order assumption: 30.

## Credit Action Audit

Each ready action is tested against the least profitable pack allocation, including allocated payment fees, withdrawal reserve, tax reserve, refund reserve, chargeback reserve, and its own delivery profile. Blocked products are not treated as sellable revenue.

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
- The 5 USD starter is intentionally modeled as a low-margin acquisition product. It should not become the dominant paid mix at low order volume.
