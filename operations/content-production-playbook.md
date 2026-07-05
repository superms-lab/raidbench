# Game Guide Content Production Playbook

Last updated: 2026-07-05

## Current Gap

The site is live, but it is not ready to reliably make money yet.

What is missing:

1. Real Search Console and GA4 data.
2. A real PayPal checkout link.
3. A real delivery file for the paid `Rust Raid Prep Pack`.
4. More specific guide pages that answer one player problem each.
5. A repeatable source-update workflow so game patches do not make content stale.
6. A community-distribution plan that does not rely on spam comments.

## What Actually Makes Money

The money is not from "writing game articles" in a generic sense.

The money comes from repeatedly solving painful player problems:

- How many resources do I need?
- Which path is cheaper?
- What should I bring before a raid?
- Why did my base decay?
- Which build guide should I trust?
- What should I change before a boss fight?
- What can I ignore so I do not waste time?

The page should reduce uncertainty and save time.

## Content Source Workflow

Use this order for every page:

1. Official source
   - Rust: Facepunch news, changes, roadmap, official wiki.
   - POE2: official site, official news, official forum/patch notes, Steam page.
2. In-game verification
   - Check numbers, UI labels, item names, and obvious mechanics in-game when possible.
3. Community demand
   - Reddit threads, Steam discussions, Discord questions, YouTube comments, search suggestions.
   - Use these for questions, not as final truth.
4. Competitor pages
   - Check what is missing, outdated, too long, or hard to use.
5. Your page
   - Give a short answer, table/checklist, example, and next action.

## Page Formula

Each page should answer one question.

Recommended structure:

1. H1: exact problem keyword.
2. Short answer: 2-4 sentences.
3. Table or checklist.
4. Example scenario.
5. Common mistakes.
6. Link to calculator or related guide.
7. Last checked date and source notes.

## Rust Content That Solves Problems

Best first topics:

- sheet metal door raid cost
- garage door raid cost
- stone wall raid cost
- armored wall raid cost
- cheapest raid method by target
- explosive ammo vs rockets
- sulfur farming target by raid path
- tool cupboard upkeep weekly calculator
- why did my base decay
- solo raid checklist
- duo raid roles checklist
- wipe day base upgrade order
- early-game raid target scoring
- raid profit calculator
- softcore raid window checklist if relevant to server type

## POE2 Content That Solves Problems

Best first topics:

- starter build checklist
- how to judge if a build guide is outdated
- boss attempt checklist
- loot filter basics
- class/skill intake form
- leveling vs endgame build differences
- defense checklist before maps/endgame
- trade/budget checklist
- build planner roadmap

Avoid early:

- full passive tree simulation
- DPS formulas
- complete item database
- exact economy claims that need constant updates

## Paid Product: First Version

The first paid product should not be huge.

Product:

```text
Rust Raid Prep Pack
Price: USD 9
Format: PDF or Google Sheet export
```

Contents:

1. Raid target scoring sheet.
2. Sulfur planning worksheet.
3. Solo raid checklist.
4. Duo raid checklist.
5. Tool cupboard weekly upkeep worksheet.
6. Post-raid review checklist.

Why someone pays:

- Saves time before wipe night.
- Gives a repeatable process.
- Helps beginners avoid bad raids.
- Works even without an account system.

## How To Know A Page Is Worth Expanding

Expand when one of these happens:

- Search Console shows impressions.
- GA4 shows guide clicks or calculator events.
- A Reddit/Steam/forum question repeats the same problem.
- A visitor clicks premium from that page.
- A paid-product topic overlaps with that page.

Do not expand based only on your own interest.

## Safe Promotion

Good:

- Post useful answer first, link only when it genuinely helps.
- Share calculator in feedback threads where someone asks for numbers.
- Make short YouTube/Bilibili/TikTok clips showing the tool solving one problem.
- Add links in your own profile/resources.

Bad:

- Generic comment spam.
- Fake testimonials.
- Misleading "official" claims.
- Copying other guides without source checking.

## Weekly Operating Loop

Every week:

1. Check official updates.
2. Check Search Console queries.
3. Check GA4 events.
4. Pick 3 pages to improve or create.
5. Publish updates.
6. Share one useful problem-solution post in a relevant community.
7. Record what happened.

## Immediate Next Step

Make the first paid deliverable real before enabling PayPal.

Next file to finish:

```text
operations/raid-prep-pack-v1.md
```
