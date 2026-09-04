# RaidBench Multi-Game Expansion - Phase 8

## Status

Phase 8 of 8 is operationally complete. Palworld is the only newly activated paid game product. The other ten non-Rust products remain hidden.

Production backend release: `/opt/raidbench/releases/20260904T013111Z-phase8-palworld-live-v11`

Production runtime image: `local/raidbench-runtime:2026-09-04-phase8-palworld-live-v11`

Content Agent image: `local/raidbench-content-agent:2026-09-04-phase8-live-answer-v1`

Cloudflare Pages deployment: `https://3d0a6b91.raidbench.pages.dev`

Live product: `palworld-base-progression-review`

Price: 80 credits; exact-match pack USD 13.00

Revenue status: technically sellable, but no legitimate Palworld sale has occurred yet. Deployment does not guarantee traffic, conversion, or revenue.

## Delivered

- [x] Activate only the Palworld 80-credit review after all ten machine gates passed.
- [x] Keep the other ten non-Rust products at `hidden_pending_qa`.
- [x] Add a public Palworld intake with version, server, goal, current state, observed problem, and question fields.
- [x] Reserve credits at submission without writing a debit.
- [x] Prevent queued reservations from being spent by a second answer request.
- [x] Export signed jobs without customer email, payment data, order IDs, or balance data.
- [x] Give the Agent read-only inbox access and no production database or PayPal-secret access.
- [x] Run a dedicated answer author and a different independent reviewer against a closed evidence packet.
- [x] Validate the answer again at production import before charging.
- [x] Debit exactly once and publish the answer inside the same account only after approval.
- [x] Release the reservation and charge zero for evidence gaps, QA blocks, invalid results, and 30-minute timeouts.
- [x] Poll queued answers in the customer page and render queued, ready, and held states.
- [x] Add the exact-match 80-credit / USD 13.00 pack to reduce first-order friction.
- [x] Add Palworld conversion paths to the game hub and every public Palworld guide.
- [x] Add privacy-minimized production counts to the private Chinese owner dashboard.
- [x] Install minute-level worker and importer timers on the VPS.
- [x] Re-run the 67-case shadow service after activation and preserve Palworld eligibility.

## Production Flow

```text
Player buys 80 credits through PayPal
  -> PayPal capture and signed webhook grant credits once
  -> player submits one Palworld review
  -> 80 credits are reserved, not debited
  -> production app writes an HMAC-signed, privacy-minimized inbox job
  -> isolated Codex author uses current publisher snapshots and player context
  -> different Codex reviewer independently approves, blocks, or agrees with no-charge
  -> Agent writes a fingerprinted result to outbox
  -> production importer verifies signature, exact request match, evidence freshness,
     source domains, QA identities, critical claims, limitations, and correction window
  -> approved: debit 80 once and publish in account
  -> blocked, invalid, stale, or timed out: release reservation and charge 0
```

## Isolation Boundary

The signed job contains only:

- opaque job and question identifiers;
- product and game identifiers;
- player question and submitted game context;
- quoted credits;
- submission and expiry timestamps;
- HMAC signature.

It does not contain customer email, display name, PayPal identifiers, payment payloads, order IDs, ledger entries, or account balance.

The Agent container mounts `/opt/raidbench/jobs/inbox` read-only and `/opt/raidbench/jobs/outbox` writable. It has no mount for `/opt/raidbench/data/raidbench.db` or `/opt/raidbench/secrets/runtime.env`.

## No-Money End-To-End Evidence

An actual Codex author and independent reviewer processed the same bounded Palworld ore-handoff case used in shadow QA. The first attempt safely refused too broadly; the reviewer identified that an observation-supported workflow boundary could be diagnosed without claiming a game mechanic. The author contract was clarified without weakening evidence or QA requirements.

The second isolated run passed:

```text
Starting ledger balance: 450
Reserved after submission: 80
Spendable after submission: 370
Agent result: approved
Imported question status: ready
Credits charged: 80
Final ledger balance: 370
Answer-debit rows: 1
In-account delivery rows: 1
Idempotent replay: 0 additional imports
Production orders created: 0
Production credits charged: 0
SQLite integrity: ok
```

Private evidence root:

```text
/opt/raidbench-agent/artifacts/phase8-smoke/phase8-live-smoke-20260904T002818Z
```

## Post-Activation QA

The complete shadow service was forced after Palworld moved to `ready_live`:

- 67 distinct cases remain recorded.
- 18 supported answers are approved.
- 35 missing-context or policy cases remain correctly no-charge.
- 11 supported requests were proactively held without charge.
- 3 candidate answers were blocked by QA.
- 0 contract failures and 0 charged shadow credits.
- Palworld remains 15 cases, 9 of 10 supported answers approved, 5 of 5 no-charge cases correct, 0 critical failures.
- All six available delivery gates passed.
- The private manifest records Palworld as `live_monitored` and `phase8Required=false`.

## Runtime Services

```text
raidbench-live-answer.timer     every minute; one pending job per run
raidbench-answer-import.timer   every minute; import or expire queued jobs
raidbench-shadow-qa.timer       every six hours; maintain activation evidence
raidbench-source-scout.timer    hourly; refresh publisher snapshots by source cadence
raidbench-content-check.timer   hourly; protect Rust paid data
```

The live-answer service initially hit a systemd start limit because successful minute-level runs counted against a two-hour burst limit. The unit now permits 20 starts per ten-minute window, the failed state was cleared, and subsequent empty-queue runs completed successfully.

## Public Boundary

- `GET /api/multigame/products` exposes exactly one product: Palworld at 80 credits.
- `GET /api/catalog` exposes three actions: two Rust actions and one Palworld action.
- `GET /api/catalog` includes `credits-palworld-80` at USD 13.00.
- The other ten multi-game products remain hidden.
- Owner pages, content source files, job files, databases, prompts, and Agent artifacts remain outside the Pages package.
- Public probes for owner, catalog-source, and job paths return 404.

## Verification

- Python tests: 112 passed.
- Node test files: 12 passed.
- Public validation: 192 HTML files checked, 142 indexable pages, 109 guide/update pages, and 9 multi-game tools.
- Pages allowlist: 143 public HTML files; no private owner, database, source, or job artifact.
- Browser QA: desktop and 390 px mobile, no horizontal overflow, no console errors, no failed resources.
- Interaction QA: Palworld selected, form submitted, 80-credit reservation shown, queued status shown, and approved answer rendered after polling.
- Production database remained at 4 customers, 1 order, 0 ledger rows, and 1 historical question through deployment.
- Production job inbox and outbox remained empty after deployment.
- PayPal Live checkout, webhook, password reset, and payment notification readiness remained enabled.

## Operating Truth

The technical earning loop is now open: a legitimate buyer can pay, receive credits, submit a Palworld problem, and receive a QA-approved answer inside the account. This does not mean the site has earned revenue yet. The next business milestone is the first unrelated paid customer and a monitored capture-to-answer outcome.

## Resume Here

The eight-stage expansion is complete. Continue with operation rather than another build phase: acquire qualified Palworld visitors, monitor the private live dashboard, inspect the first legitimate capture and answer without exposing customer content, and change pricing or acquisition only after real funnel evidence exists.
