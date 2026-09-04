---
name: raidbench-owner-localization
description: Produce Chinese owner-facing summaries for RaidBench Agent outputs without changing the English commercial substance.
---

# RaidBench Owner Localization

Use this skill only inside the RaidBench Agent pipeline.

## Inputs

Read the case JSON plus prior stage outputs. Do not browse, deploy, edit files, or contact users.

## Output

Return only JSON matching `schemas/agents/owner-localization.schema.json`.

## Rules

- The owner summary is private and Chinese.
- Preserve opportunity IDs, draft IDs, priorities, risks, and publish decisions exactly.
- Explain what the English page would say and what risk exists.
- Do not soften compliance warnings.
- The owner should not need to judge English quality line by line.
- Preserve the counted entity, qualifier, and scope of every number exactly across English and Chinese;
  do not turn a count of affected Pals into a count of Partner Skills, items, changes, or other entities.
- Copy the current case's `run_context` and constraints exactly when describing external-action boundaries.
  Do not introduce Reddit, OAuth, commercial permission, direct messages, promotional approval, or any other
  platform-specific rule unless that exact channel and rule are present in the closed case input.
- When `publish_mode` is `automatic_owned_site_only`, state only that this run may publish the owned-site page
  after QA and performs no external posting. Do not turn a generic community-answer artifact into an external
  publication plan.
