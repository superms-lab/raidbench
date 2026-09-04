# RaidBench First-Customer Outreach

Updated: 2026-08-28
Status: both approved emails sent; provider accepted, final delivery unverified

## Verified Funnel Snapshot

- Last 7 days: 57 page views.
- Last 30 days: 498 page views, 1 account entry, 0 checkout starts, 0 payments.
- Production checkout is enabled with live PayPal and a ready webhook.
- The daily Reddit scout was failing to write new drafts because the private queue directory had the wrong owner. The service and directory ownership were repaired on 2026-08-28.
- The first-party analytics and production database show no unrelated paid customer yet.

## Immediate Motion

1. Publish one current, link-free answer to a relevant `r/playrust` question.
2. Publish the disclosed RaidBench post on the owner's Reddit profile so helpful replies have a legitimate path to the free tool and the $5 offer.
3. Offer the free calculator/widget to two existing Rust traffic owners. Keep the first message useful and specific; do not ask for a paid sponsorship.
4. Measure the `reddit_profile` and partner UTM campaigns before changing price or buying ads.

## Draft 1: AxentHost Partnership

Sourced context:

- AxentHost publicly lists Rust hosting and directs partnership or affiliate proposals to `contact@axenthost.com`.
- Source: https://axenthost.com/contact/

Fit hypothesis:

- AxentHost already serves people setting up Rust servers. A free raid-route calculator or data reference can add a useful player-facing resource to its Rust knowledge base without requiring AxentHost to build or maintain the calculation engine.

To: `contact@axenthost.com`

Subject: `Free Rust raid-route calculator for your Rust hosting resources`

```text
Hi AxentHost team,

I operate RaidBench, an independent Rust planning site for vanilla PC players. I noticed that AxentHost supports Rust and asks partnership proposals to use this address.

RaidBench has a free raid-cost calculator, shareable multi-layer route links, an embeddable calculator, and reviewed JSON/CSV raid data. I would be happy to provide the widget or a clean resource link for an AxentHost Rust guide or onboarding page at no cost. Your team would not need to maintain the calculations, and the free tools do not require a player account.

The useful angle for a hosting audience is practical: players can compare a full breach route and weekly upkeep before choosing how they want to play a wipe. RaidBench is independent, clearly discloses that it is not affiliated with Facepunch, and keeps custom-server claims outside the verified vanilla scope.

Free widget and planner:
https://raidbench.com/rust-raid-calculator-widget?utm_source=axenthost&utm_medium=partner_outreach&utm_campaign=free_widget

Would this be useful for one of your Rust knowledge-base or community resource pages? I can provide a compact embed snippet and adjust the surrounding copy to fit your page.

Best,
RaidBench
support@raidbench.com
```

## Draft 2: Pillar Of Gaming Contributor Pitch

Sourced context:

- Pillar Of Gaming explicitly requests original articles of at least 700 words, two relevant images, and names Rust among the games it wants covered.
- It asks applicants to email `pillarofgaming.com@gmail.com` with previous work, game focus, and an example.
- Source: https://pillarofgaming.com/write-for-us/

Fit hypothesis:

- A source-backed Rust route-comparison article can earn qualified search/referral traffic while giving the publisher an original guide rather than an advertisement.

To: `pillarofgaming.com@gmail.com`

Subject: `Rust contributor pitch: compare a complete raid route before crafting boom`

```text
Hi Pillar Of Gaming team,

I would like to contribute an original Rust guide. I operate RaidBench, an independent vanilla Rust PC planning site, and my focus is turning raid-cost data into practical route decisions.

Proposed article:
"How to Compare a Complete Rust Raid Route Before Crafting Boom"

The guide would be over 700 words and would explain how to count mixed door and wall layers, compare rockets, C4, satchels, and explosive ammo, add a realistic resource buffer, check the boom already in base, and set a stop condition before the raid becomes a sunk-cost decision. I can provide two original screenshots from the calculator and keep the article unique to Pillar Of Gaming.

Relevant work examples:
https://raidbench.com/rust-raid-plan
https://raidbench.com/pages/rust-c4-vs-rockets

RaidBench is not affiliated with Facepunch, and I would disclose my relationship to the tool wherever it is referenced. Please let me know whether this topic fits your current Rust coverage and any house style requirements you would like me to follow.

Best,
RaidBench
support@raidbench.com
```

## Measurement Rules

- `reddit_profile` visit but no account entry: strengthen the sample result and explain the $5 outcome more concretely.
- Account entry but no checkout start: inspect registration, consent, trust, and PayPal handoff before changing price.
- Partner reply but no placement: offer the embed snippet and one original supporting paragraph; do not add a paid sponsorship.
- No qualified visit after three published Reddit replies and the profile post: test a capped paid-search experiment only after an explicit budget decision.

## Send Record

- AxentHost: sent 2026-08-28 15:25 UTC through the verified SMTP2GO sender; provider message id retained in the private VPS state.
- Pillar Of Gaming: sent 2026-08-28 15:25 UTC through the verified SMTP2GO sender; provider message id retained in the private VPS state.
- Reply-To for both messages: `support@raidbench.com`.
- Incoming replies continue to the owner Gmail inbox. The temporary email-to-Feishu alert was disabled on 2026-08-30 at the owner's request.

## Evidence Gaps

- The owner has not confirmed whether the 2026-08-18 Gmail registration was an unrelated visitor or an owner test. It is excluded from outreach until ownership is known.
- The in-app browser could not complete a live rendered-page navigation during this run. API health, public HTML, production configuration, database state, and analytics were verified directly; visual checkout QA remains pending.
