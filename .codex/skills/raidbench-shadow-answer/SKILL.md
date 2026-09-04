---
name: raidbench-shadow-answer
description: Draft a no-charge RaidBench shadow answer from one closed benchmark case without browsing or inventing game facts.
---

# RaidBench Shadow Answer

Use this skill only inside the RaidBench paid-answer benchmark pipeline.

## Inputs

Read only the supplied `case-input.json`. It contains the product contract, customer-style inputs, captured evidence, verified calculation assertions, and the active answer policy. Do not browse, edit files, contact anyone, access commerce data, or perform external actions.

## Output

Return only JSON matching `schemas/agents/shadow-answer.schema.json`.

## Rules

- This is shadow mode. No payment exists and no credits may be charged.
- Copy the case's `gameVersion` exactly into `versionScope`; this becomes customer-visible answer metadata.
- Use only evidence IDs present in the closed case. Never create a source, URL, patch detail, item behavior, price, statistic, replay observation, or mechanic.
- Put evidence IDs only in each claim's structured `evidenceIds` array. Do not expose internal `ev_...` identifiers, raw citations, or source URLs in the customer-facing `answerText`.
- Publisher evidence supports only what its captured excerpt actually says. A publisher listing does not prove an unrelated game mechanic.
- Customer input supports only the facts the benchmark says the player supplied.
- Every `customer_context` claim must cite the supplied `customer_input` evidence ID.
- Deterministic test evidence supports only the exact formula and expected value recorded in the case.
- Keep observation, arithmetic, inference, and recommendation visibly separate.
- A candidate answer must contain at least one critical claim, and every critical claim must cite at least two supplied evidence IDs including an applicable authoritative source.
- Numeric claims must reproduce the supplied calculation assertions exactly and cite their deterministic-test evidence.
- The answer must materially satisfy every core dimension in the product's `output` promise. A narrow calculator result, cautious request for more evidence, or partial checklist is not a paid deliverable.
- Before choosing `answer_candidate`, compare the available evidence with the entire product promise. If any promised diagnosis, review dimension, prioritized action, or retest component cannot be delivered, choose `no_charge` immediately.
- If the evidence cannot support the promised diagnosis, comparison, prioritized actions, and retest plan within the product scope, return `disposition=no_charge`; explain the missing evidence without attempting a partial or generic answer.
- When returning `no_charge`, both `claims` and `calculations` must be empty arrays. Use only `noChargeReason`, `answerText`, and `limitations` to explain the evidence gap.
- When `disposition=no_charge`, `claims` and `calculations` must both be empty arrays. Put only the evidence gap and required next input in `noChargeReason`, `answerText`, and `limitations`; do not attach a partial answer as formal claims.
- Do not promise an outcome or recommend cheating, exploits, account services, boosting, or real-money trading.
- State limitations plainly and give a bounded retest or next decision where evidence allows it.
