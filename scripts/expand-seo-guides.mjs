import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

const rustTopics = [
  ["rust-armored-door-raid-cost", "Rust armored door raid cost", "How much boom you need for an armored door, and when the door path is still worth following.", "How much does it cost to raid an armored door?", "Armored doors are expensive enough that the door path deserves a second scout. Compare rockets, C4, satchels, and explosive ammo, then add a buffer for the next layer."],
  ["rust-sheet-metal-wall-raid-cost", "Rust sheet metal wall raid cost", "A practical sulfur estimate for sheet metal walls and when splash damage changes the choice.", "How much does it cost to raid a sheet metal wall?", "A sheet metal wall is usually a serious wall-side commitment. C4 is direct, rockets create splash value, and explosive ammo only works when the shooting angle is safe."],
  ["rust-wooden-door-raid-cost", "Rust wooden door raid cost", "Early wipe wooden door raid options, risk, and when a cheap raid still wastes time.", "What is the cheapest way to break a wooden door?", "Wooden doors are cheap targets, but the question is whether the loot path continues. Use them for fast early opportunities, not blind commitment."],
  ["rust-high-external-wall-raid-cost", "Rust high external wall raid cost", "How to think about external walls, compound entry, and sulfur risk.", "Should I raid through a high external wall?", "External walls are often about access, not final loot. Count the follow-up path before spending boom on the compound."],
  ["rust-ladder-hatch-raid-cost", "Rust ladder hatch raid cost", "Ladder hatch raid estimates and when vertical entry is worth the exposure.", "How much does a ladder hatch cost to raid?", "A ladder hatch can be a strong entry point, but vertical control and counters matter as much as raw sulfur."],
  ["rust-compound-bow-raid-plan", "Rust compound bow raid plan", "A low-tech early raid plan for weak doors, soft-side opportunities, and realistic stop points.", "Can I raid early without full boom?", "Early low-tech raids should target obvious weakness, not force expensive paths with bad tools."],
  ["rust-satchel-raid-risk-checklist", "Rust satchel raid risk checklist", "A checklist for using satchels without losing the raid to timing, noise, and counters.", "When are satchels worth using?", "Satchels are budget-friendly but noisy and unreliable. They are best when the target is small and you can survive the delay."],
  ["rust-c4-vs-rockets", "Rust C4 vs rockets", "Compare C4 and rockets by sulfur, speed, splash, inventory pressure, and raid control.", "Should I use C4 or rockets?", "C4 wins on direct damage and simplicity. Rockets win when splash damage or flexible target switching creates extra value."],
  ["rust-online-vs-offline-raid-cost", "Rust online vs offline raid cost", "Why online raids need different buffers, roles, and exit rules than offline raids.", "How much extra boom should I bring for an online raid?", "Online raids need more buffer because defenders repair, seal, move loot, and punish slow decisions."],
  ["rust-counter-raid-escape-plan", "Rust counter raid escape plan", "How to plan exits, banking, and stop conditions before counters arrive.", "How do I avoid losing a raid to counters?", "Counter-risk is not solved after the alarm starts. Decide banking routes, seal timing, and stop rules before placing boom."],
  ["rust-sealing-after-raid-checklist", "Rust sealing after raid checklist", "What to bring and what to decide before sealing a breach.", "What should I bring to seal a raid?", "Sealing is a raid phase, not an afterthought. Building plan, materials, doors, locks, and role clarity protect the result."],
  ["rust-small-base-raid-path", "Rust small base raid path", "How to evaluate common 1x2 and 2x2 raid paths without guessing.", "What is the best path into a small base?", "Small bases are won by path discipline. Door path, wall path, roof entry, and expected TC location should be compared before crafting."],
  ["rust-honeycomb-raid-decision", "Rust honeycomb raid decision", "When honeycomb makes wall-side entry too expensive and when it reveals a better plan.", "Should I raid through honeycomb?", "Honeycomb raises cost and uncertainty. Treat it as a warning to rescout the door path and roof options."],
  ["rust-turret-compound-raid-prep", "Rust turret compound raid prep", "A raid prep checklist for turrets, sight lines, ladders, and recovery.", "How should I prepare for a turret compound raid?", "Turret compounds demand visibility and route planning. Explosives are only one part of the cost."],
  ["rust-boom-crafting-order", "Rust boom crafting order", "How to craft rockets, C4, satchels, and ammo without locking yourself into the wrong raid plan.", "What boom should I craft first?", "Craft flexible boom after scouting. Crafting everything too early can turn a better path into a sunk-cost mistake."],
  ["rust-sulfur-to-gunpowder-conversion", "Rust sulfur to gunpowder conversion", "Fast sulfur-to-gunpowder planning for players preparing a raid budget.", "How much gunpowder do I need for my sulfur target?", "Use sulfur as the planning unit, then convert to gunpowder only after the target path is clear."],
  ["rust-raid-buffer-calculator-guide", "Rust raid buffer calculator guide", "How much extra boom to bring for hidden doors, repairs, counters, and mistakes.", "How much extra boom should I bring?", "Exact raid math fails when the base is not exact. A realistic buffer protects the raid from one bad assumption."],
  ["rust-weekly-upkeep-buffer", "Rust weekly upkeep buffer", "How to choose a weekly upkeep buffer without over-farming or decaying.", "How many days of upkeep should I keep?", "A good upkeep buffer protects your base while leaving resources for progression. More is not always better if it delays defense."],
  ["rust-solo-sulfur-farming-target", "Rust solo sulfur farming target", "Solo sulfur targets for small raids, wall paths, and emergency buffers.", "How much sulfur should a solo farm before raiding?", "A solo target should match one clear raid plan plus a fallback. Farming endlessly without a target wastes wipe time."],
  ["rust-duo-raid-comms-checklist", "Rust duo raid comms checklist", "A communication checklist for duo raid roles, timing, and counter calls.", "What should a duo call out during a raid?", "Good comms shorten decision time. Call target, boom count, counter direction, seal status, loot priority, and stop condition."]
];

const poe2Topics = [
  ["poe2-campaign-to-endgame-checklist", "POE2 campaign to endgame checklist", "A transition checklist for players who finish campaign and suddenly feel underbuilt.", "What should I check after finishing the POE2 campaign?", "The campaign-to-endgame jump exposes weak defenses, unclear upgrade goals, and bad item filters. Review the basics before rebuilding."],
  ["poe2-resistance-checklist", "POE2 resistance checklist", "A defensive checklist for resistance gaps, gear swaps, and patch-sensitive assumptions.", "Are my POE2 resistances good enough?", "Resistance problems often look like build failure. Check caps, content type, and gear assumptions before replacing damage pieces."],
  ["poe2-mobility-checklist", "POE2 mobility checklist", "How to review movement, recovery windows, and boss positioning.", "Why does my POE2 build feel too slow?", "Mobility is part of defense. Slow repositioning can make a strong build feel fragile in bosses and dense endgame encounters."],
  ["poe2-gear-upgrade-priority", "POE2 gear upgrade priority", "How to choose the next gear upgrade without spending currency in the wrong slot.", "Which POE2 gear slot should I upgrade first?", "Upgrade the bottleneck that blocks progress, not the slot with the most exciting tooltip gain."],
  ["poe2-budget-build-red-flags", "POE2 budget build red flags", "How to spot budget build claims that quietly require expensive gear.", "Is this POE2 budget build actually cheap?", "A true budget build explains required pieces, substitutions, and what still works before perfect gear."],
  ["poe2-unique-item-dependency-check", "POE2 unique item dependency check", "A checklist for builds that depend on specific uniques or rare affix combinations.", "Should I start a build that needs a unique item?", "Unique-dependent builds can be excellent, but they become traps when the unique is unavailable or overpriced."],
  ["poe2-damage-uptime-checklist", "POE2 damage uptime checklist", "Why tooltip damage is not the same as real boss damage.", "Why is my boss damage lower than expected?", "Real damage depends on uptime, positioning, resource sustain, and safe windows, not only tooltip numbers."],
  ["poe2-death-review-template", "POE2 death review template", "A simple template for reviewing deaths without guessing.", "How do I figure out why I died in POE2?", "A useful death review separates damage type, timing, movement, recovery, and whether the build or execution failed."],
  ["poe2-map-mod-risk-checklist", "POE2 map mod risk checklist", "How to compare map or area modifiers against your build's weaknesses.", "Which POE2 map mods are risky for my build?", "Risky modifiers depend on your build. Read mods through the lens of defenses, recovery, damage type, and mobility."],
  ["poe2-trade-friction-checklist", "POE2 trade friction checklist", "How trade time changes the real value of a farming route.", "Why does my farming route look profitable but feel slow?", "Paper profit can disappear in trade friction. Track what actually sells and how long it takes."],
  ["poe2-ten-run-profit-test", "POE2 ten-run profit test", "A small test for judging farming routes without being fooled by one lucky drop.", "How many runs should I test before judging a farm?", "Ten runs is not perfect science, but it is better than judging a route from one highlight or one unlucky failure."],
  ["poe2-stash-cleanup-flow", "POE2 stash cleanup flow", "A fast way to reduce stash clutter and preserve useful items.", "How do I clean my POE2 stash without deleting value?", "A good stash flow separates personal upgrades, trade candidates, craft tests, and items that are only emotional clutter."],
  ["poe2-crafting-test-decision", "POE2 crafting test decision", "When an item deserves a craft test and when it should be sold or ignored.", "Should I craft on this POE2 item?", "Craft-test only when the base, affixes, and upside justify the cost. Most uncertain items need triage first."],
  ["poe2-build-switch-decision", "POE2 build switch decision", "How to decide whether to fix your current build or switch entirely.", "Should I abandon my POE2 build?", "Switching builds is expensive. First identify whether the blocker is gear, defenses, skill choice, or unrealistic expectations."],
  ["poe2-low-playtime-progression", "POE2 low playtime progression", "A progression planning checklist for players with limited weekly time.", "How should I progress in POE2 with limited time?", "Limited playtime rewards focused goals, stable farming, and fewer experimental rebuilds."],
  ["poe2-boss-attempt-budget", "POE2 boss attempt budget", "How to budget attempts, gear swaps, and review time before pushing bosses.", "How many boss attempts should I budget?", "Boss progress costs more than entry items. Count attempts, learning time, gear swaps, and the point where review beats retrying."],
  ["poe2-squishy-build-fixes", "POE2 squishy build fixes", "Common ways to make a fragile build safer without rebuilding everything.", "How can I make my POE2 build less squishy?", "The fastest fix may be recovery, movement, resistance, or one gear swap rather than a full rebuild."],
  ["poe2-upgrade-before-farming", "POE2 upgrade before farming", "How to decide whether to farm now or upgrade first.", "Should I upgrade before farming currency?", "A small upgrade that stabilizes runs can beat pushing a route your build fails repeatedly."],
  ["poe2-item-price-check-flow", "POE2 item price check flow", "A disciplined flow for price-checking items without losing the whole session.", "How do I price-check POE2 items faster?", "Price-check only items with a clear buyer profile. Most drops should move quickly through a triage flow."],
  ["poe2-guide-comment-check", "POE2 guide comment check", "How guide comments reveal whether a build is still working.", "Should I read comments before following a POE2 guide?", "Comments often expose patch breaks, missing budget pieces, and boss problems faster than the original guide is updated."]
];

function makeGuide(topic, game) {
  const [slug, title, description, problem, shortAnswer] = topic;
  const baseRelated = game === "Rust"
    ? ["rust-raid-cost-calculator.html", "rust-cheapest-raid-method.html", "rust-solo-raid-checklist.html"]
    : ["poe2-outdated-build-guide-checklist.html", "poe2-endgame-defense-checklist.html", "poe2-currency-farming-checklist.html"];
  return {
    slug,
    title,
    description,
    problem,
    shortAnswer,
    table: {
      headers: ["Decision area", "Check", "Why it matters"],
      rows: [
        ["Context", "Confirm patch, wipe, league, or progression stage.", "Advice without context ages quickly."],
        ["Cost", "Estimate resource, currency, time, or opportunity cost.", "A plan can be correct and still not worth doing now."],
        ["Risk", "Identify the failure mode before committing.", "Most losses come from ignored risk, not missing information."],
        ["Next step", "Choose one action to test first.", "Small tests reduce expensive mistakes."]
      ]
    },
    checklist: [
      "Write down the current patch or progression context.",
      "Identify the one decision this guide should help you make.",
      "Check whether the cost is acceptable before committing.",
      "Look for one safe test before spending major resources.",
      "Review the result and update the plan after new information."
    ],
    example: game === "Rust"
      ? "If a raid path looks cheap but exposes you for a long time, add counter risk to the decision instead of judging sulfur alone."
      : "If a build upgrade looks powerful but does not fix the content you are failing, delay the purchase and test the real blocker first.",
    mistakes: [
      "Following advice without checking the current patch context.",
      "Optimizing one number while ignoring risk and execution.",
      "Spending resources before confirming the next practical step.",
      "Treating a highlight result as a repeatable plan."
    ],
    related: baseRelated,
    sources: game === "Rust"
      ? ["RaidBench estimates", "Facepunch/Rust official updates", "Community question patterns"]
      : ["Official Path of Exile news and patch context", "Official Path of Exile 2 product information", "Community demand patterns"],
    monetization: game === "Rust"
      ? "This topic can feed a future Rust Raid Prep credit action after payment is enabled."
      : "This topic can feed a future POE2 audit credit action after payment is enabled."
  };
}

function mergeGuides(file, topics, game) {
  const dataPath = path.join(root, "content", file);
  const guides = JSON.parse(fs.readFileSync(dataPath, "utf8"));
  const seen = new Set(guides.map((guide) => guide.slug));
  let added = 0;
  for (const topic of topics) {
    if (seen.has(topic[0])) continue;
    guides.push(makeGuide(topic, game));
    added += 1;
  }
  guides.sort((a, b) => a.slug.localeCompare(b.slug));
  fs.writeFileSync(dataPath, `${JSON.stringify(guides, null, 2)}\n`);
  return { file, added, total: guides.length };
}

const results = [
  mergeGuides("rust-problem-guides.json", rustTopics, "Rust"),
  mergeGuides("poe2-problem-guides.json", poe2Topics, "POE2")
];

for (const result of results) {
  console.log(`${result.file}: added=${result.added} total=${result.total}`);
}
