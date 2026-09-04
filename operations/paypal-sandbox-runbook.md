# RaidBench PayPal Sandbox Runbook

Last updated: 2026-08-02

## Purpose

The PayPal Sandbox service proves the payment and credit-delivery loop without changing Live credentials
or moving real money. It uses its own container, loopback port, SQLite database, and secret file.

```text
Container: raidbench-sandbox
VPS listener: 127.0.0.1:8081
Local owner URL through SSH: http://localhost:18081/customer.html
Database: /opt/raidbench/sandbox-data/raidbench-sandbox.db
Secrets: /opt/raidbench/secrets/paypal-sandbox.env
```

The public Cloudflare site never routes to this service.

## Start And Inspect

```bash
docker compose --profile sandbox \
  -f /opt/raidbench/stacks/platform/compose.yaml \
  up -d --no-deps raidbench-sandbox

curl -fsS http://127.0.0.1:8081/api/health
curl -fsS http://127.0.0.1:8081/api/config
```

Expected configuration includes:

```text
checkoutEnabled=true
paypalEnvironment=sandbox
paypalWebhookReady=true
```

## Owner Tunnel

Run this on the owner Mac only while testing:

```bash
ssh -N -L 18081:127.0.0.1:8081 leadauditlab-vps
```

Then open `http://localhost:18081/customer.html`. The tunnel may be stopped after the test; it is not a
customer-facing server.

## Acceptance Sequence

1. Register a disposable account in the Sandbox customer page.
2. Accept the purchase disclosure and choose Scout Credits: USD 19.00 for 120 credits.
3. Approve the hosted order with a PayPal personal Sandbox buyer account.
4. Confirm PayPal returns to the local customer page and captures the order.
5. Confirm exactly 120 credits are added once.
6. Reload and repeat the capture callback; confirm no additional credits are added.
7. Purchase one verified 10-credit Rust answer and confirm 110 credits remain.
8. Issue a Sandbox refund and confirm the refund event is recorded without duplicate reversal.

Do not use Live PayPal credentials, a real buyer account, or a real card in this environment.

## Current Evidence

On 2026-08-02, the isolated service returned healthy configuration, authenticated successfully with the
Sandbox API, and created a USD 19.00 Scout Credits order. PayPal reported the order as `CREATED`; the
configured Sandbox webhook matched the expected RaidBench HTTPS endpoint and 13 subscribed event types.

Buyer approval, capture, refund, and the visible credit-balance checks remain pending.
