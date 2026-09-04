import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const gameRegistry = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8")).games;
const baselinePath = path.join(root, "content", "multigame-baseline-guides.json");
const baselineByGame = new Map(
  (fs.existsSync(baselinePath) ? JSON.parse(fs.readFileSync(baselinePath, "utf8")).packs : [])
    .map((pack) => [pack.gameId, pack.guides]),
);

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function isEditorialReady(guide) {
  return guide.table?.rows?.[0]?.[0] !== "Context";
}

function loadGuides(file, game, hub) {
  return JSON.parse(fs.readFileSync(path.join(root, "content", file), "utf8"))
    .filter((guide) => !/(paid|product|credit|audit-product)/i.test(guide.slug))
    .filter(isEditorialReady)
    .map((guide) => ({ ...guide, game, hub }));
}

function loadManualGuides(game, hub) {
  return JSON.parse(fs.readFileSync(path.join(root, "content", "manual-guides.json"), "utf8"))
    .filter((guide) => guide.game === game.name || guide.game === game.shortName)
    .map((guide) => ({ ...guide, hub }));
}

function loadAgentGuides(game, hub) {
  const file = path.join(root, "content", "agent-guides.json");
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, "utf8"))
    .filter((guide) => guide.game === game.name || guide.game === game.shortName)
    .map((guide) => ({ ...guide, hub }));
}

function uniqueGuides(guides) {
  return [...new Map(guides.map((guide) => [guide.slug, guide])).values()];
}

const groups = gameRegistry
  .map((game) => {
    const problemFile = path.join(root, "content", `${game.id}-problem-guides.json`);
    const hub = `.${game.hubPath}`;
    const generated = fs.existsSync(problemFile)
      ? loadGuides(`${game.id}-problem-guides.json`, game.shortName, hub)
      : [];
    return {
      game,
      guides: uniqueGuides([
        ...generated,
        ...loadManualGuides(game, hub),
        ...loadAgentGuides(game, hub),
        ...(baselineByGame.get(game.id) || []).map((guide) => ({ ...guide, game: game.shortName, hub })),
      ]),
    };
  })
  .filter((group) => group.guides.length > 0);

const total = groups.reduce((sum, group) => sum + group.guides.length, 0);

function guideList(guides, game) {
  const gameKey = game.id;
  return guides
    .map(
      (guide, index) => `<a class="guide-item" data-guide-card data-game="${gameKey}" data-search="${escapeHtml(`${guide.title} ${guide.description} ${guide.problem || guide.question || ""}`)}" href="./pages/${escapeHtml(guide.slug)}.html">
              <span>${String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>${escapeHtml(guide.title)}</h3>
                <p>${escapeHtml(guide.description)}</p>
              </div>
            </a>`,
    )
    .join("\n            ");
}

const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Game Guide Library | RaidBench</title>
    <meta name="description" content="Search practical RaidBench game guides by problem, item, build, route, resource, map, or patch-sensitive decision." />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="https://raidbench.com/guides" />
    <meta property="og:title" content="RaidBench Game Guide Library" />
    <meta property="og:description" content="Fast answers, checklists, and decision tools across the RaidBench game directory." />
    <meta property="og:type" content="website" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="./styles.css?v=20260717a" />
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="./index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      <nav class="nav" aria-label="Primary"><a href="./games.html">Games</a><a href="./guides.html" aria-current="page">Guides</a><a href="./tools.html">Tools</a><a href="./updates.html">Patch Watch</a><a href="./about.html">About</a></nav>
      <a class="header-action" href="./games.html">Choose a game</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="./index.html">RaidBench / Guide Library</a>
      <section class="article-hero">
        <p class="eyebrow">Practical game intelligence</p>
        <h1>Find the answer before the next mistake gets expensive.</h1>
        <p>Search ${total} reviewed guides across the live RaidBench game sections. Each page is built around one player question, explicit assumptions, and one useful next move.</p>
        <div class="hook-strip" aria-label="Guide index summary">
          <span>${total} reviewed guides</span>
          <span>${gameRegistry.length} games</span>
          <span>Official-source review</span>
          <span>Patch monitoring</span>
        </div>
      </section>

      <section class="guide-index-toolbar" aria-label="Guide filters">
        <label class="guide-search" for="guide-search">
          <span>Search by problem, item, boss, route, or resource</span>
          <input id="guide-search" type="search" placeholder="Try: outdated build, raid cost, base automation" autocomplete="off" />
        </label>
        <div class="guide-filters" aria-label="Filter by game">
          <button class="guide-filter" type="button" data-guide-filter="all" aria-pressed="true">All</button>
          ${groups.map(({ game }) => `<button class="guide-filter" type="button" data-guide-filter="${escapeHtml(game.id)}" aria-pressed="false">${escapeHtml(game.shortName)}</button>`).join("\n          ")}
        </div>
      </section>
      <p class="guide-index-status" id="guide-index-status" aria-live="polite"></p>
      <div class="guide-index-empty" id="guide-index-empty" hidden>No matching guide yet. Try a broader term or open Patch Watch for the latest update-sensitive topics.</div>

      ${groups
        .map(
          ({ game, guides }) => `<section class="guide-band guide-index-section" data-guide-section>
        <div class="section-head">
          <h2>${escapeHtml(game.shortName)} guides</h2>
          <p>${escapeHtml(game.summary)}</p>
        </div>
        <div class="guide-list">
            ${guideList(guides, game)}
        </div>
      </section>`,
        )
        .join("\n      ")}
    </main>
    <footer class="footer"><p>RaidBench is an independent, unofficial player resource. All game names and trademarks belong to their respective owners.</p><p class="footer-links"><a href="./games.html">Games</a><a href="./updates.html">Patch Watch</a><a href="./about.html">How we review guides</a><a href="./privacy.html">Privacy</a><a href="./terms.html">Terms</a><a href="./refund-policy.html">Refunds</a></p></footer>
    <script src="./config.js?v=20260717a"></script>
    <script src="./analytics.js?v=20260717a"></script>
    <script src="./guide-index.js?v=20260717a"></script>
  </body>
</html>
`;

fs.writeFileSync(path.join(root, "guides.html"), html);

console.log(`Generated guides.html with ${total} guides.`);
