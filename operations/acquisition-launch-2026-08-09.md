# RaidBench North America Acquisition Launch

Updated: 2026-08-10
Primary market: United States and Canada
Primary product: verified Rust raid answers and reviewed raid plans

## Commercial status

The technical purchase loop is production-ready: account, PayPal Live checkout, webhook, credit ledger, in-account answer delivery, refund policy, and password recovery are connected. The commercial loop is not yet proven because RaidBench has zero completed customer orders and zero paid answers delivered.

Current 30-day baseline before this launch:

- 669 aggregate page views across 51 measured pages.
- 495 page views reported from the United States.
- 16 search-referred page views: Google 11 and Bing 5.
- Zero completed orders. Existing traffic is not yet sufficient to validate conversion.

Page views are anonymous aggregates, not unique people, and can include tests or automated traffic.

## Revenue path

1. A player discovers a current answer through search, AI search, or a permitted community contribution.
2. The free page resolves the immediate question and exposes assumptions, source links, review date, calculator, and related decisions.
3. A player with a target-specific route opens the Player Account.
4. The player buys a one-time USD credit pack through PayPal.
5. Credits are added only after capture confirmation.
6. A supported question produces an in-account answer; unsupported or stale requests are held without a credit charge.
7. First-party aggregate events show which source reached account entry, checkout, payment confirmation, and answer delivery.

## Launch content cluster

- `/pages/rust-power-trip-raid-meta-guide`: current official update and raid-preparation impact.
- `/pages/rust-fast-vs-efficient-raiding`: risk-adjusted method choice.
- `/pages/rust-c4-vs-rockets`: sulfur, direct damage, and useful splash.
- `/pages/rust-small-base-raid-path`: door path versus wall path.
- `/pages/rust-raid-profit-calculator-outline`: interactive break-even tool.
- `/pages/rust-100-rocket-base-worth-raiding`: expensive-target decision framework.

These pages form one question cluster rather than six unrelated articles. Each page must link to the free calculator, two or more relevant guides, official evidence where mechanics are stated, and the paid account only when the production readiness check passes.

## Channel rules

### Google and Gemini

- Publish crawlable, people-first text with visible sources, assumptions, review dates, canonical URLs, internal links, and matching structured data.
- Submit the Sitemap through Search Console after owner verification.
- Do not create AI-only doorway pages, fake FAQs, or mass-generated variants.
- Measure impressions, queries, clicks, account-entry events, and checkout events. AI feature inclusion is eligible, never guaranteed.

### Bing, Copilot, and participating IndexNow engines

- Keep `sitemap.xml` current.
- Submit the latest modified URLs through `node scripts/submit-indexnow.mjs` after every verified production deploy.
- Monitor crawl and index status in Bing Webmaster Tools when the owner account is connected.

### Reddit

- Use current questions for demand discovery and answer them in full before considering a link.
- Never automate posting, mass replies, votes, follows, direct messages, or repeated promotional comments.
- Check the subreddit and thread rules at action time. If a relevant link is permitted and genuinely adds detail, disclose ownership in the same comment.
- Do not revive an old thread solely to place a RaidBench link.

### Steam Discussions

- Use only for demand research and genuinely non-commercial, text-only help.
- Do not place RaidBench links or promotional references; Steam's general discussion rules prohibit commercial content unless a space explicitly says otherwise.

### Discord

- Join manually, read each server's rules, and contribute only in permitted help or resource channels.
- No self-bots, unsolicited DMs, repeated links, or copied answers across servers.
- Share a RaidBench link only after a moderator or channel rule clearly permits it, with ownership disclosed.

### Quora and independent forums

- Answer the complete question on-platform.
- Link only when the destination adds a calculator, current source audit, or table that cannot be reproduced cleanly in the answer.
- Disclose ownership and vary every response to the actual question. No template spraying.

## Fourteen-day test

Days 1-2: deploy the six-page Rust cluster, submit IndexNow, submit the Sitemap to Google and Bing, and verify all URLs return indexable content.

Days 3-7: contribute five answer-first community responses across permitted channels. Most responses should contain no link. Record the target, rule check, date, and result in the post queue.

Days 8-10: inspect search queries, top pages, account-entry clicks, and checkout starts. Improve pages that receive impressions but fail to earn a click or next action.

Days 11-14: publish two follow-up pages only from observed demand. Pause any channel that produces low-quality visits, moderation friction, or no meaningful downstream action.

## Decision gates

- Continue a topic when it earns qualified search impressions, useful community discussion, calculator usage, or account entries.
- Rewrite the offer when account entries occur but checkout starts remain zero.
- Investigate trust, price, or payment UX when checkout starts occur but payments remain zero.
- Investigate product quality when payments occur but answers are held, corrected, refunded, or not revisited.
- Do not claim that revenue is proven until an unrelated customer completes payment and receives a verified answer successfully.

## Action-time approval boundary

Owned-site publishing, Sitemap generation, IndexNow submission, and aggregate measurement can run automatically. After Reddit separately approves the commercial use case and OAuth credentials are active, an exact-thread, link-free Reddit reply may run without owner review under the reply rate limit and community allowlist. Standalone posts, links, promotional copy, Discord, Steam, Quora, forum, email, and direct-message publication still require a fresh rule check and owner confirmation.

## Execution record

- 2026-08-09: six-page Rust cluster and the Power Trip update were deployed to production.
- 2026-08-09: all 58 Sitemap URLs returned a successful final response without a canonical redirect.
- 2026-08-09: IndexNow accepted the 10 latest URLs with HTTP 202.
- Google Search Console Sitemap submission remains pending owner-property access.
- 2026-08-10 06:42 CST: the first link-free Reddit answer was posted to the current r/playrust discussion and verified publicly visible at `https://www.reddit.com/r/playrust/comments/1vdgzxq/comment/p2qbdza/`. The reply contains no RaidBench link, site name, or call to action.
- 2026-08-11: PayPal Live checkout, the dedicated signed Webhook, and owner payment/refund notifications were verified ready in production. The production database still contains zero completed orders, so commercial validation remains open.
- 2026-08-11: source scouting, content generation, paid-content checking, and SQLite backup timers were verified enabled and active. Interrupted content runs now recover automatically, and existing public guide excerpts are included in closed-set overlap review.
- 2026-08-11: the public Sitemap contained 59 URLs and robots allowed crawling. IndexNow accepted the latest modified RaidBench URL with HTTP 200; earlier launch URLs had already been submitted.
- 2026-08-11: source scouting, content automation, and paid-data checks were moved to an hourly staggered schedule. Reddit remains platform-gated; the owner-review exception applies only to future approved, link-free replies, not standalone posts.
- 2026-08-11 15:20 UTC: the first verified hourly collection window fetched all 8 currently permitted sources, produced 21 signals and 4 high-value signals, and recorded 1 failed source without bypassing it.
- 2026-08-11 15:29 UTC: the hourly Agent retry passed all five QA stages and published `https://raidbench.com/pages/palworld-1-0-returning-player-revalidation`. Production verification returned HTTP 200, IndexNow accepted the URL with HTTP 200, and the public Sitemap increased to 60 URLs.
- 2026-08-11 15:44 UTC: the obsolete Palworld news URL was replaced with `https://news.palworldgame.com/`. A forced verification fetched all 8 permitted sources successfully, produced 22 signals and 4 high-value signals, and reported zero failed sources.
