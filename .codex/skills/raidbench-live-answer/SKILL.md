---
name: raidbench-live-answer
description: Draft one bounded customer Palworld review from a closed signed-job evidence packet without browsing or accessing commerce data.
---

# RaidBench Live Answer

Use this skill only inside the controlled RaidBench customer-answer worker.

## Inputs

Read only the supplied `case-input.json`. It contains one privacy-minimized player request, the product promise, current captured publisher excerpts, and the active answer policy. Do not browse, edit files, contact anyone, inspect other jobs, or access accounts, email, payments, balances, or customer identity.

## Output

Return only JSON matching `schemas/agents/live-answer.schema.json`.

## Rules

- Credits have only been reserved. Your output cannot charge, refund, publish, or message anyone.
- Copy the case's `gameVersion` exactly into `versionScope`.
- Use only evidence IDs present in the closed case. Never invent a source, URL, patch detail, mechanic, item behavior, numeric value, observation, or outcome.
- Publisher evidence supports only the literal captured excerpt. Player input supports only what the player reported.
- Keep player observation, inference, recommendation, and verification steps distinct.
- An observation-supported workflow boundary is not a game-mechanic claim. When the player supplies controlled before-and-after values that locate a gap between two stages, you may name that boundary as the first measured bottleneck and prescribe a one-variable test without claiming why the game produced it.
- Do not require mechanic documentation merely to propose a reversible observation plan. Mechanic evidence is required only when asserting a specific game cause, behavior, rate, or outcome.
- Official publisher excerpts may establish current game and update context while customer evidence establishes the measured workflow gap; say exactly that when a critical recommendation uses both.
- A paid candidate must identify one evidence-supported bottleneck, prioritize practical next actions, state assumptions and limitations, and provide a one-variable verification checklist.
- Every critical claim must cite at least two supplied evidence items, including an applicable authoritative item. Player-context claims must cite the player-input record.
- Do not expose internal evidence IDs or raw internal artifact paths in `answerText`.
- If the supplied observations are too vague to locate even a measured workflow boundary, or the complete product promise otherwise cannot be supported, return `disposition=no_charge`. Leave `claims` and `calculations` empty and explain exactly which input or evidence is missing.
- Never recommend cheats, exploits, account services, boosting, real-money trading, or a guaranteed outcome.
- Prefer a precise refusal over a polished guess.
