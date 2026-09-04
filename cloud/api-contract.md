# Credits API Contract

Base URL later:

```text
https://api.raidbench.example
```

For Cloudflare Workers, the API can also live under:

```text
https://raidbench.example/api/*
```

## Authentication

MVP options:

1. Magic-link email login.
2. PayPal buyer email account lookup.
3. Admin-only manual fulfillment before user accounts.

Do not use client-only auth for credit balances.

## Endpoints

### GET /api/me

Returns the current user.

```json
{
  "userId": "usr_123",
  "email": "player@example.com"
}
```

### GET /api/credits/balance

Returns current computed balance.

```json
{
  "balance": 20,
  "currency": "credits"
}
```

### GET /api/products

Returns draft or active credit packs and action costs. Do not expose draft checkout URLs until a real payment provider is approved.

```json
{
  "checkoutEnabled": false,
  "packs": [
    {
      "sku": "credits-starter-100",
      "name": "Starter Credits",
      "credits": 100,
      "prices": {
        "USD": 4.99,
        "EUR": 4.99,
        "GBP": 4.49
      }
    }
  ],
  "actions": [
    {
      "id": "poe2-build-audit",
      "label": "POE2 Build Audit",
      "credits": 10
    }
  ]
}
```

### POST /api/credits/quote

Request:

```json
{
  "action": "custom_raid_route",
  "inputSize": "standard"
}
```

Response:

```json
{
  "action": "custom_raid_route",
  "cost": 3,
  "quoteId": "qt_123",
  "expiresAt": "2026-07-05T00:15:00Z"
}
```

### POST /api/credits/use

Request:

```json
{
  "quoteId": "qt_123",
  "idempotencyKey": "use_123"
}
```

Response:

```json
{
  "ledgerId": "led_123",
  "newBalance": 17,
  "planId": "plan_123"
}
```

### POST /api/paypal/webhook

Validates PayPal webhook signature, records order event, and credits the user if payment is complete.

Must be idempotent by PayPal event ID and transaction ID.

### GET /api/admin/ledger

Admin-only ledger export for dispute and reconciliation work.

### GET /api/admin/deliveries

Admin-only export of paid advice delivery records for customer support, refund review, and tax/accounting evidence.
