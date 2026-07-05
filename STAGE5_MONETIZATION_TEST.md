# Stage 5 Monetization Test

Last updated: 2026-07-05

## Goal

Test whether RaidBench visitors have purchase intent before building user accounts, credits, or a
custom checkout backend.

## Offer

```text
Rust Raid Prep Pack
Price: USD 9
Format: downloadable checklist and worksheet pack
Delivery: manual first, automated later
```

## Why This Offer

- It is small enough for an impulse purchase.
- It matches the calculator use case.
- It does not require a credits ledger.
- It can be delivered manually at first.
- It can validate paid intent before a full product build.

## Current Implementation

Public offer page:

```text
https://raidbench.com/premium.html
```

Current mode:

```text
Early access / purchase intent only. Real checkout is disabled until PayPal is configured.
```

Files:

- `premium.html` - offer page.
- `premium.js` - checkout/interest behavior and events.
- `config.js` - PayPal payment link configuration.
- `operations/delivery-log-template.csv` - manual fulfillment record template.
- `operations/raid-prep-pack-outline.md` - first product outline.

## PayPal Setup

Fastest route:

1. Create or confirm a PayPal Business account. If you are in mainland China and selling for profit as an individual seller, PayPal's China account selection page says to choose the business account route rather than the personal account route.
2. Create a PayPal Payment Link or Buy Button for `Rust Raid Prep Pack`.
3. Price it at `9.00 USD`.
4. Set a clear product description and delivery expectation.
5. Paste the hosted PayPal URL into `config.js`:

```js
window.RAIDBENCH_CONFIG = {
  ga4MeasurementId: "G-XXXXXXXXXX",
  analyticsDebug: false,
  premiumOffer: {
    offerId: "raid-prep-pack-9",
    paypalPaymentLink: "https://www.paypal.com/...",
    contactEmail: "support@example.com",
  },
};
```

Do not enable payment until delivery records are ready.

Detailed setup checklist:

```text
operations/paypal-receiving-setup.md
```

## Delivery Records

For digital goods, keep a basic order log:

| Field | Why it matters |
| --- | --- |
| PayPal transaction ID | Payment lookup and dispute handling |
| Buyer email | Delivery evidence |
| Product name | Confirms what was purchased |
| Sent timestamp | Proof of fulfillment |
| Delivery method | Email, file link, or account access |
| Access/download timestamp | Useful if available |
| Refund/dispute status | Follow-up tracking |

## Events

The premium flow records these events through `analytics.js`:

- `premium_offer_view`
- `premium_interest_click`
- `premium_interest_submit`
- `premium_checkout_click`

Recommended GA4 custom dimensions:

- `offer_id`
- `price_usd`
- `checkout_provider`
- `email_domain`
- `player_type`

## Decision Rules

Continue to real checkout if:

- At least 3-5 non-test visitors click the premium CTA, or
- At least 1 real visitor submits interest, or
- Search Console shows repeated traffic to raid planning pages.

Do not build credits yet if:

- No one clicks the premium CTA.
- Users use only one-off calculators.
- There is no repeat intent signal.

Move toward credits later if:

- Users ask for custom plans.
- Users repeatedly create or share raid plans.
- A paid pack gets purchases or serious interest.

## Official References

- PayPal China account selection: https://www.paypal.com/c2/webapps/mpp/account-selection
- PayPal Payment Links and Buttons: https://developer.paypal.com/studio/checkout/payment-links-and-buttons
- PayPal Standard Checkout: https://developer.paypal.com/studio/checkout/standard
- PayPal Seller Protection: https://www.paypal.com/us/legalhub/paypal/seller-protection
