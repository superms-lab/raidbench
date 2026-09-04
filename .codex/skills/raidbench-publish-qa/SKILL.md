---
name: raidbench-publish-qa
description: Fail-closed QA for RaidBench generated guides, owner summaries, source references, and compliance boundaries before publication.
---

# RaidBench Publish QA

Use this skill only inside the RaidBench Agent pipeline.

## Inputs

Read the closed input set: case JSON and all prior stage outputs. Do not browse, deploy, edit files, or perform external actions.

## Output

Return only JSON matching `schemas/agents/publish-qa.schema.json`.

## Rules

- Block publication if evidence references are missing or unsupported.
- Block any paid checkout wording if `payment_ready` is false.
- Block claims that guarantee profit, rankings, loot, build performance, revenue, or outcomes.
- Block content that sells, transfers, or promotes in-game currency, items, accounts, boosting, cheating,
  exploits, gambling, or real-money trading. Source-backed informational guidance about legitimate in-game
  economy, drops, crafting, farming, or item decisions is allowed when it does not facilitate those services.
- Block if the Chinese owner summary changes the decision, priority, or risk level.
- Check at least one substantive guide claim for every draft and attach the exact supplied evidence IDs.
- A pass requires every checked claim to be `supported`; `needs_revision` and `unsupported` always block.
- Block a draft whose slug already exists in `guide_inventory`; automated runs publish new pages only.
- When relevant inventory entries include `content_excerpt`, perform the overlap and conflict review from
  that closed input. Do not block solely for a separate owner comparison if the supplied excerpt is enough
  to verify differentiation; block when a material conflict remains unresolved or the excerpt is insufficient.
- Block a community answer containing a URL, RaidBench mention, sales language, copied community wording,
  or a claim that is not supported by the closed evidence set.
- If uncertain, return `decision=block`.
