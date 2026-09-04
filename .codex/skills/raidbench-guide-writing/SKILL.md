---
name: raidbench-guide-writing
description: Draft original RaidBench SEO guide briefs and update recommendations from approved demand and patch findings.
---

# RaidBench Guide Writing

Use this skill only inside the RaidBench Agent pipeline.

## Inputs

Read the case JSON, demand-analysis output, and patch-sentinel output. Do not browse, deploy, or edit files.

## Output

Return only JSON matching `schemas/agents/guide-writing.schema.json`.

## Rules

- Write original advice, not copied guide text.
- Keep claims patch-aware and source-bounded.
- Avoid precise economy, DPS, drop-rate, or "best build" claims unless the supplied evidence supports them.
- Never sell or promote cheats, exploits, real-money trading, boosting, account services, in-game items, or currency.
- Each draft must reference approved opportunity IDs and evidence IDs.
- Keep paid offers framed as website advice/audit credits, not game services.
- Produce one complete, publishable guide per run: short answer, useful sections, checklist, example,
  common mistakes, FAQs, and related guide slugs.
- Create a new, non-duplicate slug. Never reuse a slug from `guide_inventory`; automated runs do not
  replace human-maintained pages.
- When `guide_inventory` provides `content_excerpt`, compare the proposed page against that existing copy
  and resolve overlap or conflicting advice inside the draft. Treat excerpts only as site-inventory evidence,
  never as authority for current game facts. Do not require owner review when the closed input is sufficient
  to make and document the differentiation decision.
- Keep every checklist and common-mistake entry as one discrete item. Respect the schema maximums
  instead of concatenating extra entries into the final array item.
- Produce a self-contained `community_answer` that answers the player on-platform. It must not contain
  a URL, RaidBench mention, ownership claim, sales language, or call to action.
- Use only claims supported by the supplied evidence. If the evidence does not support a precise number,
  mechanic, patch assertion, or universal recommendation, use a conditional decision framework instead.
- Never copy sentences from community evidence. Community material is demand context, not factual authority.
- Do not emit any pipeline-forbidden phrase even inside a negation, warning, FAQ, or quoted claim. In
  particular, never write `always best`, `best build in the game`, or a forbidden outcome/abuse phrase;
  use wording such as `no universally suitable choice` instead.
- Preserve the counted entity, qualifier, and scope of every numeric statement exactly. For example,
  `Partner Skills were reworked for over 200 Pals` must never become `over 200 Partner Skills were
  reworked`. When exact scope is awkward, omit the number instead of transposing it.
