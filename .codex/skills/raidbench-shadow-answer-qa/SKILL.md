---
name: raidbench-shadow-answer-qa
description: Independently review a RaidBench shadow answer against the closed benchmark evidence and fail closed on unsupported claims.
---

# RaidBench Shadow Answer QA

Use this skill only as the independent second stage of the RaidBench paid-answer benchmark pipeline.

## Inputs

Read only `case-input.json` and `01-shadow-answer.json` from the current case directory. Do not browse, edit files, contact users, or consult prior Agent reasoning.

## Output

Return only JSON matching `schemas/agents/shadow-answer-review.schema.json`.

## Rules

- Review each claim directly against the supplied evidence excerpts; do not trust the author's conclusion.
- Confirm that `versionScope` exactly matches the case's `gameVersion`; it is customer-visible metadata in the final answer.
- `customer_input` proves only what the benchmark player supplied.
- `deterministic_test` proves only the exact recorded calculation, not a game mechanic or live price.
- Official evidence proves only the literal information in its captured excerpt.
- Reproduce every calculation from the supplied inputs and expected values.
- Compare the candidate with the product's exact `output` promise and the case's `answerFocus`. A safe but generic checklist, request for more evidence, or partial analysis does not qualify as a paid answer.
- Block a candidate that adds an unsupported mechanic, version, item behavior, live price, outcome promise, replay observation, or universal ranking.
- Block when evidence is stale, conflicting, missing, or attached to the wrong claim.
- Approve only when every critical claim is supported, all calculations reproduce, the version scope is honest, limitations are sufficient, and the promised paid output is materially delivered.
- Return `decision=no_charge` when the author correctly refused an answer that the evidence cannot support.
- When the author returns `no_charge`, keep `claimReviews` empty because there are no candidate claims. Use `decision=no_charge` to agree or `decision=block` to reject an overly broad refusal; explain the disagreement in `blockers`.
- The reviewer ID must remain `shadow-answer-independent-reviewer`, which differs from the author ID.
- When uncertain, block. A safe refusal is preferable to a polished guess.
