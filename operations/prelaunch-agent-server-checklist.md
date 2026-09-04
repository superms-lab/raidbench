# RaidBench Pre-Launch Agent Server Checklist

Last updated: 2026-08-09

## Deployment Decision

Use Cloudflare for the public product runtime:

- Cloudflare Pages: public website
- Cloudflare Workers: API, payment webhooks, lightweight scheduled jobs
- Cloudflare D1: orders, credits, content queue, delivery records

Use a VPS for private Agent work:

- Codex CLI
- Python/Node orchestration
- browser-based or long-running collection jobs
- source snapshots and private owner review artifacts
- Git commits/pushes that trigger Cloudflare deployment

Cloudflare is the production platform. The VPS is the Agent workstation.

## Agent Package Ready Before VPS Purchase

The five model-assisted RaidBench stages are now versioned in this repository:

```text
.codex/skills/raidbench-demand-analysis/
.codex/skills/raidbench-patch-sentinel/
.codex/skills/raidbench-guide-writing/
.codex/skills/raidbench-owner-localization/
.codex/skills/raidbench-publish-qa/
```

The deterministic runner and contracts are:

```text
scripts/run_raidbench_agent_pipeline.py
schemas/agents/
templates/agent-guide-case.sample.json
tests/test_raidbench_agent_pipeline.py
```

The runner defaults to validation-only mode. It does not call Codex unless `--execute` is supplied.

```bash
python3 scripts/run_raidbench_agent_pipeline.py
```

After Codex is logged in on the VPS:

```bash
codex login --device-auth
python3 scripts/run_raidbench_agent_pipeline.py --execute
```

Generated run artifacts are private and stored under:

```text
private-data/agent-runs/{case_id}/{timestamp}/
```

They are excluded from Git.

The deterministic public-source scanner is now deployed on the VPS independently of Codex. Its systemd
timer, low-privilege account, source cadence, and first successful run are documented in
`operations/agent-content-system.md`. Model-assisted drafting still requires a separate Codex device login.

## Server Preparation

After buying the VPS:

- Create a non-root Linux user named `raidbench`.
- Disable password SSH after key-based login works.
- Install Python 3, Node.js LTS, Git, Codex CLI, Chromium, and required fonts.
- Clone the RaidBench repository.
- Run Codex login as `raidbench`, not root.
- Keep OpenAI, Cloudflare, GitHub, payment, and email credentials outside Git.
- Keep `~/.codex` owner-only.
- Create encrypted or restricted private storage for `private-data/`.
- Configure daily backup for local database, source captures, and Agent run artifacts.
- Add disk, memory, failed-job, and API-usage alerts.

## Runtime Safety Rules

- Run model stages with `--sandbox read-only`.
- Use `--ephemeral` so stages do not share hidden conversation state.
- Keep deterministic source collection and scoring in scripts.
- Keep the source/evidence set closed for each Agent run.
- Stop when any schema or contract validation fails.
- Block publication unless Publish QA returns `decision=pass` and `publish_safe=true`.
- Never let the Agent change payment settings, issue refunds, post to communities, or deploy without the approved policy.

## Production Data Contract

Every real Agent case must include:

- evidence IDs, source URLs, capture timestamps, and local evidence paths
- signal IDs linked to valid evidence IDs
- current guide inventory
- deterministic opportunity scorecard
- payment readiness flag
- constraints for public sources, no guaranteed outcomes, no cheats/exploits, no RMT, and owner approval for external posting

No real guide should be generated directly from loose prose or screenshots without structured source records.

## Acceptance Gates

- [x] Five project-scoped Skills created.
- [x] Structured output contracts created.
- [x] Fail-closed runner created.
- [x] Validation-only sample case supported.
- [x] Regression tests added for contract safety.
- [ ] VPS account, price, region, and renewal terms confirmed.
- [ ] Repository cloned to the VPS.
- [ ] Codex device login completed on the VPS.
- [ ] Secrets and backups configured.
- [ ] One real source case runs in validation-only mode.
- [ ] One real Agent case runs with `--execute` and QA pass.
- [ ] Owner confirms a Chinese review summary before first public Agent-generated publish.
