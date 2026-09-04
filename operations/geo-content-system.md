# RaidBench GEO Content System

Last updated: 2026-08-10

## Goal

Build search and AI-answer visibility for RaidBench without spam, fake community activity, copied guide text, or platform-risk behavior.

RaidBench GEO means:

```text
useful owned game pages -> crawlable structure -> patch-aware source notes -> careful community listening -> measured search/referral signals
```

It does not mean:

```text
mass Reddit comments, fake accounts, copied guides, hidden links, keyword stuffing, invented gameplay facts, exploit promotion, boosting, RMT, or buying mentions
```

## Shared Method

RaidBench uses the same GEO operating system as the other projects:

```text
real user question -> intent classification -> owned answer page -> evidence/source boundary -> internal links -> measured distribution -> update loop
```

The project-specific mapping is:

```text
player problem -> game / patch / guide / calculator page -> point credits or paid audit
```

## Owned Assets

Current owned assets:

- `https://raidbench.com/`
- `https://raidbench.com/guides.html`
- `https://raidbench.com/poe2.html`
- `https://raidbench.com/palworld.html`
- `https://raidbench.com/sitemap.xml`
- `https://raidbench.com/robots.txt`
- Rust calculator and Rust guide pages.
- POE2 guide/checklist pages.
- Palworld guide/checklist pages.

Owned site content is the source of truth. External posts should only point to owned content when the answer is already useful without a click.

## Content Pillars

### 1. Problem Definition Pages

Purpose: answer direct AI-search and Google questions.

Examples:

- What is a POE2 build audit?
- What is a Rust raid-cost calculator?
- What is a Palworld base automation scorecard?

### 2. Checklist Pages

Purpose: provide practical, quotable steps.

Examples:

- POE2 outdated build guide checklist.
- Rust solo raid checklist.
- Palworld boss prep checklist.

### 3. Calculator And Scorecard Pages

Purpose: make RaidBench more useful than a generic article.

Examples:

- Rust raid cost calculator.
- Rust upkeep planner.
- POE2 route scorecard.
- Palworld base automation scorecard.

### 4. Patch-Sensitive Refresh Pages

Purpose: preserve trust when games change.

Examples:

- Build-guide freshness checks.
- Patch impact summaries.
- Last reviewed and source notes.

### 5. Paid-Audit Intake Pages

Purpose: prepare future monetization without opening checkout early.

Rules:

- Keep paid checkout hidden until payment and delivery records work.
- Sell RaidBench website analysis/credits, not game services.
- Do not sell in-game currency, items, accounts, boosting, cheats, exploits, gambling, or top-ups.

## Page Formula

Each page should contain:

1. H1 matching one player problem.
2. Short answer in 2-4 sentences.
3. Table, checklist, scorecard, or calculator.
4. Example scenario.
5. Common mistakes.
6. Related internal links.
7. Last checked date and patch/source note.
8. Free next step first, paid path only when checkout is ready.

## Crawler Policy

Current default:

- Keep public guide pages crawlable.
- Keep private owner review, paid draft, and internal delivery files out of public navigation and sitemap.
- Allow normal search and AI-search retrieval unless there is a reason to restrict a specific crawler later.

Review crawler policy again before enabling paid delivery pages, private user pages, or internal owner review URLs.

## External Platform Plan

### Google / Bing

Primary channel.

Actions:

- Keep `sitemap.xml` accurate.
- Submit sitemap in Search Console and Bing Webmaster Tools.
- Submit each QA-approved URL to IndexNow after deployment; this helps participating engines discover it
  but does not guarantee crawling, indexing, ranking, traffic, or revenue.
- Expand pages based on impressions and clicks.
- Keep internal links between guides, hubs, and calculators.

### ChatGPT / Perplexity / AI Search

Primary GEO target.

Actions:

- Use short answers, tables, FAQ-style headings, and source notes.
- Keep pages concise and citation-friendly.
- Avoid fake authority claims.

There is no general "submit to Gemini" endpoint for ordinary RaidBench pages. GEO automation therefore
publishes crawlable HTML, canonical URLs, Article/FAQ/Breadcrumb structured data, dated source notes,
internal links, and sitemap entries. Search and AI systems decide whether to crawl or cite the page.

### Reddit

High ban risk.

Default:

- Use for listening first.
- No cold promotional threads.
- Link only when rules allow and the reply already answers the question.
- Disclose affiliation when linking.
- Do not use owner authorization as a substitute for Reddit's commercial developer permission.
- Automated posting is off. After an owned guide passes QA, the pipeline may prepare a link-free answer and
  send it to the owner's private Feishu group. This does not use Reddit's API and does not publish anything.
- The owner opens a genuinely relevant discussion, confirms the answer fits the question and current rules,
  then posts manually. Skip the draft when the context is weak; do not reuse identical copy across threads.
- Keep the answer self-contained. Add a RaidBench link only when the community explicitly allows it and disclose
  the relationship to the site.

### Steam

Research-first.

Steam community rules make commercial promotion risky. Use Steam for demand discovery and avoid direct promotional links unless a specific community context clearly allows it.

### Discord

Research and permitted help only.

Do not automate DMs, self-bots, or server spam. Use allowed resource/self-promo channels only when permission exists.

### Quora / Forums

Possible but yellow-risk.

Answer fully first. Link sparingly as optional further reading.

## First 60-Day Plan

Days 1-14:

- Work toward at least 24 QA-approved guides per day while allowing additional evidence-backed pages.
- Verify the timer, sitemap, production page, and IndexNow result from the VPS audit trail.
- No external link promotion except profiles/resources controlled by the owner.

Days 15-30:

- Review Search Console impressions.
- Improve 5 pages with impressions but weak CTR.
- Draft self-contained external answers, but keep automated dispatch disabled without platform permission.

Days 31-60:

- Add 10 more problem pages from repeated signals.
- Test 1-2 carefully reviewed community answers.
- Stop any channel that removes posts or creates account risk.

## Metrics

Track weekly:

- indexed pages
- Search Console impressions and clicks
- top query clusters
- guide index clicks
- calculator events
- AI/referral traffic if visible
- community removals or warnings
- pages leading to interest or checkout clicks

## Stop Conditions

Pause a channel when:

- content is removed twice
- account receives a warning
- replies mention spam or unwanted promotion
- community rules are unclear
- the channel requires hidden affiliation, mass posting, or behavior that risks the domain

## Automation Boundary

Automatic now:

- permitted public-source polling and 45-day RSS freshness checks
- deterministic demand scoring and bounded POE2 preference
- five-stage Codex generation and independent publish QA
- owned-site build, validation, Cloudflare Pages deployment, production verification, sitemap update,
  structured data, internal linking, and IndexNow submission
- private link-free community-draft generation, audited notification queue, and Feishu card delivery once the
  custom-bot webhook is configured

Not automatic or not guaranteed:

- Reddit, Steam, Discord, forum, or social posting; the owner remains the final manual publisher
- Google Search Console ownership actions and Google indexing decisions
- rankings, AI citations, traffic, conversion, or revenue
