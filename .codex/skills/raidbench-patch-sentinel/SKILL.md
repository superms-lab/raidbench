---
name: raidbench-patch-sentinel
description: Review RaidBench source signals and guide inventory to identify patch-sensitive pages, claims, and refresh priorities.
---

# RaidBench Patch Sentinel

Use this skill only inside the RaidBench Agent pipeline.

## Inputs

Read the case JSON and the demand-analysis output. Do not browse, deploy, edit files, or infer current game facts beyond the supplied evidence.

## Output

Return only JSON matching `schemas/agents/patch-sentinel.schema.json`.

## Rules

- Treat official patch, hotfix, balance, wipe, or economy-change signals as refresh triggers.
- Do not claim a guide is outdated unless the supplied evidence supports that conclusion.
- Mark unsupported risk as `needs_review`, not as fact.
- Recommend review priority, not automatic publication.
- Use supplied `guide_inventory.content_excerpt` values to identify concrete overlap or conflicts with
  existing RaidBench copy. These excerpts are inventory evidence only; current game claims still require
  the authoritative evidence IDs in the case.
- Every `refresh_item.opportunity_ids` array must contain at least one valid `opportunity_id` from the
  demand-analysis input. Omit a broader inventory observation when it cannot be tied to an opportunity;
  never emit an empty `opportunity_ids` array.
