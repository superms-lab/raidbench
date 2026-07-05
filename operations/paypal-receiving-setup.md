# PayPal Receiving Setup

Last updated: 2026-07-05

## Recommended Account

Use a PayPal Business account for RaidBench payments.

Reason:

- The product is a paid digital guide pack.
- The site is selling for profit, even if the seller is an individual.
- PayPal China's account selection page says individual sellers and business sellers should use the business account option when selling for profit.

If you do not have a registered company yet, start with the individual seller route if PayPal offers it during China registration.

## What You Need

For an individual seller:

- Personal operator information.
- Personal identity document.
- A confirmed email address.
- A phone number you can verify.
- A bank/card setup for withdrawals if PayPal requests it.
- A customer support email for buyers.

For a registered company seller:

- Business owner information matching the legal representative on the business license.
- Business license scan.
- Legal representative identity document.
- Business display name.
- Customer support email.

## Product To Create

Create one Payment Link or Buy Button product:

```text
Product name: Rust Raid Prep Pack
Price: USD 9.00
Type: Digital product / no physical shipping
Delivery promise: Manual email delivery within 24 hours
Refund note: Refund available if the file was not delivered or is unusable
Support email: your support email
```

Use a PayPal-hosted Payment Link first. Do not build API checkout until the offer has real demand.

## Website Integration

After PayPal gives you a hosted checkout URL, paste it into `config.js`:

```js
window.RAIDBENCH_CONFIG = {
  premiumOffer: {
    offerId: "raid-prep-pack-9",
    paypalPaymentLink: "https://www.paypal.com/...",
    contactEmail: "support@example.com"
  }
};
```

The premium page will automatically switch from early-access mode to `Buy with PayPal`.

## Manual Delivery Flow

For the first 10-20 buyers, deliver manually:

1. Confirm PayPal payment status is paid.
2. Record the transaction in `operations/delivery-log-template.csv`.
3. Send `operations/paid-pack/RaidBench-Rust-Raid-Prep-Pack-v1.pdf` to the buyer email.
4. Record the delivery timestamp.
5. Reply quickly to refund/support requests.

## Do Not Enable Payment Until

- PayPal Business account is approved.
- Product link is created in USD.
- Support email works.
- Delivery PDF opens correctly.
- One test purchase or sandbox test has been completed.

## Official References

- PayPal China account selection: https://www.paypal.com/c2/webapps/mpp/account-selection
- PayPal Payment Links and Buttons: https://developer.paypal.com/studio/checkout/payment-links-and-buttons
- PayPal Business overview: https://www.paypal.com/us/business
