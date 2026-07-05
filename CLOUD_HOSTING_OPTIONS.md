# Cloud Hosting Options

Last updated: 2026-07-05

## Principle

Do not use the local Mac as a production server.

Local `localhost:4289` is only a development preview. Production traffic should stay on cloud
hosting.

## Current Production Hosting

Current site:

```text
https://raidbench.com/
```

Current hosting:

```text
GitHub Pages
```

This is acceptable for the static MVP because it costs nothing and does not depend on the local
computer.

## Recommended Next Cloud Path

### Option A: Cloudflare Pages + Workers + D1

Best for:

- static site
- lightweight API
- credit ledger
- payment webhook receiver
- low cost while validating

Recommended use:

```text
Frontend: Cloudflare Pages
Backend API: Cloudflare Workers
Database: Cloudflare D1
```

Why:

- no VPS maintenance
- global edge hosting
- can start cheaply
- good fit for small API and ledger workloads
- no need to keep a server process running

Tradeoff:

- Workers/D1 architecture is different from a normal Node server.
- Long-running jobs and complex background processing are not the best fit.

### Option B: Cheap VPS

Best for:

- full Node/Express or Next.js server
- background jobs
- custom database setup
- long-running queue workers

Possible providers to compare at purchase time:

- Hetzner Cloud
- DigitalOcean
- Vultr
- Linode/Akamai

Recommended first VPS shape:

```text
1 vCPU
1-2 GB RAM
25-50 GB SSD
Ubuntu LTS
```

Use a VPS only when:

- PayPal webhooks are active
- credits are actually being purchased or consumed
- a background job queue is needed
- Cloudflare Workers becomes too limiting

## Recommendation For This Project

Use this order:

1. Keep the current GitHub Pages site for static validation.
2. Move frontend to Cloudflare Pages when a custom domain is ready.
3. Add Cloudflare Workers + D1 for credits and PayPal webhook handling.
4. Consider a VPS only after repeated paid usage exists.

This keeps cost low and avoids managing a server too early.

## What Cloud Must Handle Later

- PayPal payment webhook verification.
- Order creation.
- Credit balance updates.
- Immutable credit ledger.
- Generated plan storage.
- Admin/export view for orders and disputes.
- Delivery evidence for digital goods.

## Current Blockers

- No purchased cloud account/server yet.
- No real PayPal Business payment link yet.
- No GA4 Measurement ID yet.
- No Search Console verification yet.

## Official Pricing References

- Cloudflare Workers pricing: https://developers.cloudflare.com/workers/platform/pricing/
- Cloudflare Pages pricing: https://developers.cloudflare.com/pages/platform/pricing/
- Cloudflare D1 pricing: https://developers.cloudflare.com/d1/platform/pricing/
- DigitalOcean Droplet pricing: https://www.digitalocean.com/pricing/droplets
- Vultr Cloud Compute pricing: https://www.vultr.com/pricing/
- Hetzner Cloud: https://www.hetzner.com/cloud/
