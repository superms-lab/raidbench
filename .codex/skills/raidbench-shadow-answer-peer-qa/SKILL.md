---
name: raidbench-shadow-answer-peer-qa
description: Provide a second blind review of complex RaidBench match-answer candidates and no-charge decisions.
---

# RaidBench Shadow Answer Peer QA

Use this skill only as the second independent review for a complex-match shadow benchmark.

## Inputs

Read only `case-input.json` and `01-shadow-answer.json`. Do not read the first review, prior Agent reasoning, other benchmark outcomes, or external sources. Do not browse, edit files, contact users, or access commerce data.

## Output

Return only JSON matching `schemas/agents/shadow-answer-peer-review.schema.json`.

## Rules

- Decide from the closed evidence and product contract independently of any other reviewer.
- Confirm `versionScope` exactly matches the case and that every claim uses applicable supplied evidence.
- Reproduce every deterministic calculation.
- A free calculator result is not a complete paid replay, round, position, or match review.
- `productPromiseSatisfied=true` only when every core dimension promised by the product is materially delivered.
- Return `decision=no_charge` when the author correctly refuses a request whose evidence cannot support the full product.
- When the author returns `no_charge`, keep `claimReviews` empty. Use `decision=no_charge` to agree or `decision=block` to reject the refusal, and explain why without inventing a pseudo-claim.
- Block unsupported mechanics, prices, replay observations, universal rankings, guarantees, internal evidence IDs, and partial paid outputs.
- Use reviewer ID `shadow-answer-peer-reviewer` and stage `shadow_answer_peer_qa`.
- When uncertain, block.
