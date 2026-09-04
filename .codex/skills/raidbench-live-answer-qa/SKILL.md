---
name: raidbench-live-answer-qa
description: Independently verify one bounded customer Palworld answer against its closed evidence packet and block unsupported delivery.
---

# RaidBench Live Answer QA

Use this skill only as the independent second stage of the controlled customer-answer worker.

## Inputs

Read only `case-input.json` and `01-answer-candidate.json`. Do not browse, edit files, contact anyone, inspect prior reasoning, or access commerce data.

## Output

Return only JSON matching `schemas/agents/live-answer-review.schema.json`.

## Rules

- Review every claim directly against the supplied evidence excerpts; do not trust the author's conclusion.
- Confirm that `versionScope` exactly matches the case's honest player-version and publisher-source-check scope.
- Publisher evidence proves only its literal excerpt. Player input proves only the player's report.
- A measured workflow boundary may be diagnosed from controlled player observations without claiming a game mechanic or cause. Do not block a bounded one-variable observation plan merely because the packet lacks mechanic documentation.
- Block invented mechanics, causes, values, observations, patch effects, or outcome promises.
- Compare the candidate with the full product promise: one supported bottleneck, prioritized actions, assumptions, limitations, and a bounded verification checklist.
- `decision=approve` requires every critical claim to be supported, the version scope to be honest, all limitations to be sufficient, and the complete paid promise to be materially delivered.
- Use `decision=no_charge` only when the author correctly refuses because the closed evidence cannot support the full product.
- If the author refused too broadly, use `decision=block`; the system will still hold the request without charging. For every `no_charge` candidate, keep `claimReviews` empty because the candidate contains no formal claims.
- The reviewer identity must remain `multigame-answer-independent-reviewer` and must differ from the author.
- When uncertain, block.
