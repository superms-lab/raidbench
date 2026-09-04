# RaidBench Prelaunch Readiness

Audit date: 2026-07-17
Production deployment verified: 2026-07-18

## Decision

The free-content build is deployed and verified at `https://raidbench.com/`. Paid checkout must remain hidden until payment approval, seller disclosures, delivery evidence, and checkout-specific consumer consent are complete.

The production domain is file-identical to the generated public package for the homepage, guide library, Patch Watch, `app.js`, and `styles.css` as of the deployment above.

## Completed and deployed

- Professional public navigation, responsive layout, favicon, and customer-facing copy.
- Working Rust raid-cost and weekly-upkeep calculators.
- Searchable guide library with 37 editorially approved guides.
- Patch Watch with 6 current, official-source update pages.
- 43 indexable guide/update pages and 52 total public Sitemap URLs.
- Visible review dates, official source links, refresh triggers, canonical URLs, and Article JSON-LD.
- Privacy Policy, Terms of Service, Refund Policy, and editorial standards page.
- Paid routes and generic template drafts excluded from the public build package.
- Automatic HTML, link, metadata, JSON-LD, Sitemap, and hidden-route validation.
- Gemini / Google AI launch procedure and 20-query priority queue.
- Cloudflare Pages deployment with 52 public HTML files and no paid or owner-review files.
- Privacy-minimized first-party traffic analytics backed by Cloudflare D1, plus a local-only Chinese owner dashboard.
- Production verification of the homepage, guide library, Patch Watch, About page, Sitemap, redirects, and public assets.

## External owner inputs still required

### Required before accepting payment

- Legal seller name and any public trading name.
- Geographic business or service address suitable for legally required trader disclosures.
- Customer-service phone number if required for the seller's target markets and business structure.
- Business registration number, tax number, and VAT status where applicable.
- Final seller model: direct seller through PayPal/Stripe or Merchant of Record.
- Approved checkout URL, currencies, tax behavior, product price, delivery method, and order-confirmation evidence.
- Checkout wording for immediate digital delivery and any express consent/withdrawal acknowledgement required by the buyer's law.

### External search and optional behavior analytics

- GA4 Measurement ID in `config.js` if deeper event and conversion-path reporting is required.
- Google Search Console domain verification and Sitemap submission.

### Required before unattended Agent operation

- Agent host or VPS.
- Scheduler, production deploy credential, model credential, secret storage, alert destination, and rollback policy.
- A live end-to-end dry run from official source change through validation and Cloudflare deployment.

### Operational confirmation

- Send one real external test message to `support@raidbench.com` and confirm forwarding and reply handling.

## Production evidence

- Production domain: `https://raidbench.com/`
- Cloudflare Pages deployment: `https://043988bd.raidbench.pages.dev`
- Production page-view endpoint returns HTTP 204 and writes aggregate page views to the bound D1 database.
- Sitemap: 52 URLs, including `guides.html`, `updates.html`, and `about.html`; no paid-product URLs.
- Hidden offer routes return 302 redirects to free pages.
- Generic editorial drafts are absent from the deployment and resolve to the public homepage rather than draft content.

## Release commands

Run from the repository root:

```bash
node scripts/generate-guides.mjs
node scripts/generate-poe2-guides.mjs
node scripts/generate-palworld-guides.mjs
node scripts/generate-patch-watch.mjs
node scripts/upgrade-manual-guides.mjs
node scripts/generate-guide-index.mjs
node scripts/generate-sitemap.mjs
node scripts/validate-public-site.mjs
node scripts/build-public-dist.mjs
```

Deploy only the generated `/tmp/raidbench-pages` directory. Never deploy the repository root.
