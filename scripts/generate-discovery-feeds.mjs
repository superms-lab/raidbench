import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const patchWatch = JSON.parse(fs.readFileSync(path.join(root, "content", "patch-watch.json"), "utf8"));
const rustGuides = JSON.parse(fs.readFileSync(path.join(root, "content", "rust-problem-guides.json"), "utf8"));
const gameRegistry = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8")).games;
const liveGames = gameRegistry.filter((game) => game.indexable);
const multigameTools = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-tools.json"), "utf8")).tools;
const guideBySlug = new Map(rustGuides.map((guide) => [guide.slug, guide]));
const reviewedAt = patchWatch.map((item) => item.reviewedAt).sort().at(-1) || new Date().toISOString().slice(0, 10);

function xmlEscape(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function absoluteGuideUrl(slug) {
  return `https://raidbench.com/pages/${slug}`;
}

const featuredGuideSlugs = [
  "rust-raid-cost-calculator",
  "rust-c4-vs-rockets",
  "rust-garage-door-raid-cost",
  "rust-small-base-raid-path",
  "rust-raid-profit-calculator-outline",
  "rust-100-rocket-base-worth-raiding",
];

const featuredGuides = featuredGuideSlugs
  .map((slug) => guideBySlug.get(slug))
  .filter(Boolean);

const llms = `# RaidBench

> RaidBench is an independent, patch-aware game planning site. Its current paid product is a verified vanilla Rust PC raid-cost answer or multi-layer raid plan delivered inside a player account.

Last reviewed: ${reviewedAt}

## Game directory

- [All RaidBench games](https://raidbench.com/games): The shared directory for twelve game sections.
${liveGames.map((game) => `- [${game.name}](https://raidbench.com${game.hubPath}): ${game.summary}`).join("\n")}

## Free multi-game decision tools

- [All free tools](https://raidbench.com/tools): Calculators, comparisons, risk planners, and downloadable results using player-entered assumptions.
${multigameTools.map((tool) => `- [${tool.title}](https://raidbench.com/tools/${tool.slug}/): ${tool.description}`).join("\n")}

## Free Rust tools

- [Rust Raid Cost and Upkeep Calculator](https://raidbench.com/): Build a route, compare rockets, C4, satchels, and explosive ammo, estimate sulfur and gunpowder, and copy a shareable route link.
- [Rust raid-cost dataset (JSON)](https://raidbench.com/rust-raid-costs.json): Verified vanilla Rust PC target counts, sulfur roll-ups, source links, and freshness metadata.
- [Rust raid-cost table (CSV)](https://raidbench.com/rust-raid-costs.csv): Reusable raid-cost rows for spreadsheets, tools, and independent analysis.
- [Free Rust raid-cost widget](https://raidbench.com/rust-raid-calculator-widget): A compact calculator that community and guide sites can embed without an account or API key.
- [Verified Rust Answer Offer](https://raidbench.com/rust-raid-plan): One verified target answer starts at $5; a complete multi-layer raid plan is $19. Unsupported or stale requests are held without a credit charge.

## High-intent Rust guides

${featuredGuides.map((guide) => `- [${guide.title}](${absoluteGuideUrl(guide.slug)}): ${guide.description}`).join("\n")}

## Current update briefs

${patchWatch.slice(0, 7).map((item) => `- [${item.title}](${absoluteGuideUrl(item.slug)}): ${item.description}`).join("\n")}

## Editorial and commercial policies

- [Editorial standards](https://raidbench.com/about): Sources, freshness windows, review boundaries, and correction policy.
- [Privacy](https://raidbench.com/privacy)
- [Terms](https://raidbench.com/terms)
- [Refund policy](https://raidbench.com/refund-policy)

## Important limitations

- Rust calculations are scoped to vanilla Rust PC. Custom and modded servers can differ.
- Hidden base layers, player execution, counters, loot, and server-specific rules cannot be guaranteed.
- RaidBench is independent and is not affiliated with or endorsed by Facepunch Studios or other game publishers.
`;

const rssItems = patchWatch.slice(0, 20).map((item) => `    <item>
      <title>${xmlEscape(item.title)}</title>
      <link>${absoluteGuideUrl(item.slug)}</link>
      <guid isPermaLink="true">${absoluteGuideUrl(item.slug)}</guid>
      <pubDate>${new Date(`${item.reviewedAt}T12:00:00Z`).toUTCString()}</pubDate>
      <category>${xmlEscape(item.game)}</category>
      <description>${xmlEscape(item.description)}</description>
    </item>`).join("\n");

const feed = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>RaidBench Patch Watch</title>
    <link>https://raidbench.com/updates</link>
    <description>Official-source game update summaries and practical player checklists.</description>
    <language>en-us</language>
    <lastBuildDate>${new Date(`${reviewedAt}T12:00:00Z`).toUTCString()}</lastBuildDate>
    <atom:link href="https://raidbench.com/feed.xml" rel="self" type="application/rss+xml" />
${rssItems}
  </channel>
</rss>
`;

const jsonFeed = {
  version: "https://jsonfeed.org/version/1.1",
  title: "RaidBench Patch Watch",
  home_page_url: "https://raidbench.com/updates",
  feed_url: "https://raidbench.com/feed.json",
  description: "Official-source game update summaries and practical player checklists.",
  language: "en-US",
  items: patchWatch.slice(0, 20).map((item) => ({
    id: absoluteGuideUrl(item.slug),
    url: absoluteGuideUrl(item.slug),
    title: item.title,
    summary: item.description,
    date_published: `${item.publishedAt}T12:00:00Z`,
    date_modified: `${item.reviewedAt}T12:00:00Z`,
    tags: [item.game, item.version, "Patch Watch"],
  })),
};

fs.writeFileSync(path.join(root, "llms.txt"), llms);
fs.writeFileSync(path.join(root, "feed.xml"), feed);
fs.writeFileSync(path.join(root, "feed.json"), `${JSON.stringify(jsonFeed, null, 2)}\n`);
console.log(`Generated llms.txt and discovery feeds with ${patchWatch.length} update brief(s).`);
