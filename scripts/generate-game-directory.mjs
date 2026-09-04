import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const registryPath = path.join(root, "content", "game-registry.json");
const registry = JSON.parse(fs.readFileSync(registryPath, "utf8"));
const baselinePath = path.join(root, "content", "multigame-baseline-guides.json");
const baselinePacks = fs.existsSync(baselinePath)
  ? JSON.parse(fs.readFileSync(baselinePath, "utf8")).packs
  : [];
const baselineByGame = new Map(baselinePacks.map((pack) => [pack.gameId, pack.guides]));
const toolsPath = path.join(root, "content", "multigame-tools.json");
const toolsByGame = new Map(
  (fs.existsSync(toolsPath) ? JSON.parse(fs.readFileSync(toolsPath, "utf8")).tools : [])
    .map((tool) => [tool.gameId, tool]),
);
const productPath = path.join(root, "content", "multigame-products.json");
const liveProductByGame = new Map(
  (fs.existsSync(productPath) ? JSON.parse(fs.readFileSync(productPath, "utf8")).products : [])
    .filter((product) => product.status === "ready_live")
    .map((product) => [product.gameId, product]),
);

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function cleanHtml(value) {
  return String(value).replace(/[ \t]+\n/g, "\n");
}

function assertRegistry() {
  if (registry.schemaVersion !== "1.0.0" || registry.siteName !== "RaidBench") {
    throw new Error("Unsupported game registry version or site name");
  }
  if (!Array.isArray(registry.games) || registry.games.length !== 12) {
    throw new Error("The RaidBench game registry must contain exactly 12 games");
  }
  const ids = new Set();
  const paths = new Set();
  for (const game of registry.games) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(game.id)) throw new Error(`Invalid game id: ${game.id}`);
    if (ids.has(game.id)) throw new Error(`Duplicate game id: ${game.id}`);
    if (paths.has(game.hubPath)) throw new Error(`Duplicate hub path: ${game.hubPath}`);
    if (game.hubPath !== `/games/${game.id}/`) throw new Error(`Hub path does not match id: ${game.id}`);
    if (!Array.isArray(game.decisionAreas) || game.decisionAreas.length !== 4) {
      throw new Error(`Game ${game.id} must define four decision areas`);
    }
    if (!Array.isArray(game.seedQuestions) || game.seedQuestions.length !== 3) {
      throw new Error(`Game ${game.id} must define three seed questions`);
    }
    ids.add(game.id);
    paths.add(game.hubPath);
  }
}

function loadJsonArray(relative) {
  const file = path.join(root, relative);
  if (!fs.existsSync(file)) return [];
  const value = JSON.parse(fs.readFileSync(file, "utf8"));
  return Array.isArray(value) ? value : [];
}

function isEditorialReady(guide) {
  return guide.table?.rows?.[0]?.[0] !== "Context";
}

function guidesFor(game) {
  const sources = [
    `content/${game.id}-problem-guides.json`,
    game.id === "poe2" ? "content/poe2-problem-guides.json" : "",
    game.id === "rust" ? "content/rust-problem-guides.json" : "",
    game.id === "palworld" ? "content/palworld-problem-guides.json" : "",
  ].filter(Boolean);
  const generated = sources.flatMap(loadJsonArray).filter(isEditorialReady);
  const manual = loadJsonArray("content/manual-guides.json").filter((guide) => guide.game === game.shortName || guide.game === game.name);
  const agent = loadJsonArray("content/agent-guides.json").filter((guide) => guide.game === game.shortName || guide.game === game.name);
  const baseline = baselineByGame.get(game.id) || [];
  return [...new Map([...generated, ...manual, ...agent, ...baseline].map((guide) => [guide.slug, guide])).values()]
    .filter((guide) => !/(paid|product|credit|premium|audit-product)/i.test(guide.slug || ""));
}

function rootNav(prefix = "./", current = "") {
  const links = [
    ["games", "Games", `${prefix}games.html`],
    ["guides", "Guides", `${prefix}guides.html`],
    ["tools", "Tools", `${prefix}tools.html`],
    ["updates", "Patch Watch", `${prefix}updates.html`],
    ["about", "About", `${prefix}about.html`],
  ];
  return `<nav class="nav" aria-label="Primary">${links
    .map(([id, label, href]) => `<a href="${href}"${current === id ? ' aria-current="page"' : ""}>${label}</a>`)
    .join("")}</nav>`;
}

function paidStatus(game) {
  if (game.paidAnswers === "enabled") return "Verified paid answers available";
  if (game.paidAnswers === "content-only") return "Free editorial coverage live";
  return "Paid answers remain closed until review coverage is ready";
}

function liveStatus(game) {
  return game.status === "live" ? "Live coverage" : "Editorial build in progress";
}

function hubGuideList(game, guides) {
  if (!guides.length) {
    return `<ol class="question-list">
          ${game.seedQuestions.map((question) => `<li><span>Research queue</span><strong>${escapeHtml(question)}</strong></li>`).join("\n          ")}
        </ol>`;
  }
  return `<div class="game-guide-list">
          ${guides
            .slice(0, 6)
            .map(
              (guide) => `<a href="../../pages/${escapeHtml(guide.slug)}.html">
            <span>${escapeHtml(game.code)}</span>
            <div><strong>${escapeHtml(guide.title)}</strong><p>${escapeHtml(guide.description)}</p></div>
          </a>`,
            )
            .join("\n          ")}
        </div>`;
}

function gameHub(game) {
  const guides = guidesFor(game);
  const gameTool = toolsByGame.get(game.id);
  const liveProduct = liveProductByGame.get(game.id);
  const robots = game.indexable ? "index,follow" : "noindex,follow";
  const primaryHref = liveProduct ? "/customer.html?intent=palworld" : game.featuredLinks[0]?.href || (gameTool ? `/tools/${gameTool.slug}/` : "/games");
  const primaryLabel = liveProduct ? "Get an independent review" : game.featuredLinks[0]?.label || (gameTool ? `Open ${gameTool.title}` : "Browse all games");
  const headerActionHref = liveProduct ? "../../customer.html?intent=palworld" : guides.length ? `../../guides.html?game=${game.id}` : "../../games.html";
  const headerActionLabel = liveProduct ? "Review my bottleneck" : guides.length ? "Browse guides" : "Browse games";
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${game.name} guides and decision tools`,
    url: `https://raidbench.com${game.hubPath}`,
    description: game.summary,
    isPartOf: { "@type": "WebSite", name: "RaidBench", url: "https://raidbench.com/" },
  };
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(game.name)} Guides &amp; Decision Tools | RaidBench</title>
    <meta name="description" content="${escapeHtml(game.summary)}" />
    <meta name="robots" content="${robots}" />
    <link rel="canonical" href="https://raidbench.com${game.hubPath}" />
    <meta property="og:title" content="${escapeHtml(game.name)} Guides &amp; Decision Tools | RaidBench" />
    <meta property="og:description" content="${escapeHtml(game.summary)}" />
    <meta property="og:type" content="website" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="../../styles.css?v=20260903b" />
    <script type="application/ld+json">${JSON.stringify(structuredData)}</script>
  </head>
  <body data-game="${escapeHtml(game.id)}">
    <header class="site-header">
      <a class="brand" href="../../index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      ${rootNav("../../")}
      <a class="header-action" href="${escapeHtml(headerActionHref)}">${headerActionLabel}</a>
    </header>
    <main class="article-main game-hub-main">
      <a class="breadcrumb" href="../../games.html">RaidBench / Games / ${escapeHtml(game.shortName)}</a>
      <section class="game-hub-hero">
        <div class="game-code" aria-hidden="true">${escapeHtml(game.code)}</div>
        <div>
          <p class="game-coverage-status">${liveStatus(game)}</p>
          <h1>${escapeHtml(game.name)} guides and decision tools</h1>
          <p>${escapeHtml(game.summary)}</p>
          <div class="lab-actions">
            <a class="primary-action" href="../..${escapeHtml(primaryHref)}"${liveProduct ? ' data-commerce-cta data-track-event="palworld_review_open"' : ""}>${escapeHtml(primaryLabel)}</a>
            <a class="secondary-action" href="${liveProduct ? "../../pages/palworld-base-automation-scorecard" : "../../about.html"}">${liveProduct ? "Start with the free scorecard" : "Review standards"}</a>
          </div>
        </div>
      </section>

      ${liveProduct ? `<section class="game-paid-review-band" aria-labelledby="paid-review-${escapeHtml(game.id)}">
        <div>
          <p class="eyebrow">For the problem your save actually has</p>
          <h2 id="paid-review-${escapeHtml(game.id)}">A busy base is not the same thing as a productive one.</h2>
          <p>Send one measurable base or progression bottleneck with your version and server context. RaidBench returns one prioritized diagnosis, practical next actions, explicit limitations, and a controlled retest after independent QA.</p>
          <ul><li>Player observations kept separate from inferred causes</li><li>Current publisher evidence checked before release</li><li>Delivered inside your account, with a 14-day factual correction window</li></ul>
        </div>
        <div class="paid-review-action">
          <span>Controlled launch price</span>
          <strong>${escapeHtml(liveProduct.credits)} credits</strong>
          <small>Reserved when submitted. Charged only after QA approval; otherwise 0 credits.</small>
          <a class="primary-action" href="../../customer.html?intent=palworld" data-commerce-cta data-track-event="palworld_review_open">Start my review</a>
        </div>
      </section>` : ""}

      <section class="game-focus-band" aria-labelledby="focus-${escapeHtml(game.id)}">
        <div class="section-head">
          <h2 id="focus-${escapeHtml(game.id)}">Decisions this game asks players to make</h2>
          <p>RaidBench organizes coverage around concrete decisions, current assumptions, and a next action that can be checked.</p>
        </div>
        <ul class="decision-rail">
          ${game.decisionAreas.map((area) => `<li>${escapeHtml(area)}</li>`).join("\n          ")}
        </ul>
      </section>

      <section class="game-question-band" aria-labelledby="questions-${escapeHtml(game.id)}">
        <div class="section-head">
          <h2 id="questions-${escapeHtml(game.id)}">${guides.length ? "Start with a current decision guide" : "Questions in the editorial queue"}</h2>
          <p>${guides.length ? `${guides.length} reviewed public guide${guides.length === 1 ? " is" : "s are"} currently assigned to this game.` : "These topics remain outside search indexing until their sources and answers pass review."}</p>
        </div>
        ${hubGuideList(game, guides)}
      </section>

      ${gameTool ? `<section class="game-tool-band" aria-labelledby="tool-${escapeHtml(game.id)}"><div><h2 id="tool-${escapeHtml(game.id)}">${escapeHtml(gameTool.title)}</h2><p>${escapeHtml(gameTool.description)}</p></div><a class="primary-action" href="../../tools/${escapeHtml(gameTool.slug)}/" data-track-event="game_tool_open" data-game="${escapeHtml(game.id)}">Open free tool</a></section>` : ""}

      <section class="game-standard-band">
        <div><h2>Coverage status</h2><p>${escapeHtml(paidStatus(game))}. Version-sensitive claims require a visible review date and source boundary.</p></div>
        <a class="secondary-action" href="../../updates.html">Open Patch Watch</a>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is an independent, unofficial player resource. All game names and trademarks belong to their respective owners.</p><p class="footer-links"><a href="../../games.html">Games</a><a href="../../about.html">Editorial standards</a><a href="../../privacy.html">Privacy</a><a href="../../terms.html">Terms</a></p></footer>
    <script src="../../config.js?v=20260903b"></script>
    <script src="../../analytics.js?v=20260903b"></script>
  </body>
</html>
`;
}

function gameRows() {
  return registry.games
    .map(
      (game) => `<a class="game-directory-row" data-game-row data-genre="${escapeHtml(game.genreKey)}" href=".${escapeHtml(game.hubPath)}">
          <span class="game-directory-code">${escapeHtml(game.code)}</span>
          <span class="game-directory-copy"><strong>${escapeHtml(game.name)}</strong><small>${escapeHtml(game.summary)}</small></span>
          <span class="game-directory-meta"><span>${escapeHtml(game.genre)}</span><small>${liveStatus(game)}</small></span>
        </a>`,
    )
    .join("\n        ");
}

function gamesPage() {
  const liveCount = registry.games.filter((game) => game.status === "live").length;
  const coverageCopy = liveCount === registry.games.length
    ? "All twelve game sections now contain a first reviewed content set. Each section remains tied to the same source, freshness, and correction standards."
    : `RaidBench covers twelve games through one editorial system. ${liveCount} sections contain reviewed guides now; the remaining sections stay outside search indexing until their first useful content set passes review.`;
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "RaidBench game guide directory",
    url: "https://raidbench.com/games",
    description: "Browse RaidBench game guides, calculators, decision tools, and patch-aware coverage across twelve complex games.",
    mainEntity: {
      "@type": "ItemList",
      itemListElement: registry.games.map((game, index) => ({
        "@type": "ListItem",
        position: index + 1,
        name: game.name,
        url: `https://raidbench.com${game.hubPath}`,
      })),
    },
  };
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Game Guides, Calculators &amp; Decision Tools | RaidBench</title>
    <meta name="description" content="Browse RaidBench coverage for Rust, Path of Exile 2, Palworld, Project Zomboid, Tarkov, ARK, Warframe, Once Human, CS2, Dota 2, PUBG, and Rainbow Six Siege." />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="https://raidbench.com/games" />
    <meta property="og:title" content="RaidBench Game Directory" />
    <meta property="og:description" content="Practical guides and decision tools for twelve complex games." />
    <meta property="og:type" content="website" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="./styles.css?v=20260903b" />
    <script type="application/ld+json">${JSON.stringify(structuredData)}</script>
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="./index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      ${rootNav("./", "games")}
      <a class="header-action" href="./guides.html">Search guides</a>
    </header>
    <main class="article-main game-directory-main">
      <a class="breadcrumb" href="./index.html">RaidBench / Games</a>
      <section class="game-directory-hero">
        <h1>Choose the game. Start with the decision.</h1>
        <p>${coverageCopy}</p>
      </section>
      <section class="game-directory-toolbar" aria-label="Filter games by genre">
        <button type="button" data-game-filter="all" aria-pressed="true">All games</button>
        <button type="button" data-game-filter="survival" aria-pressed="false">Survival</button>
        <button type="button" data-game-filter="rpg" aria-pressed="false">RPG</button>
        <button type="button" data-game-filter="extraction" aria-pressed="false">Extraction</button>
        <button type="button" data-game-filter="competitive" aria-pressed="false">Competitive</button>
      </section>
      <p class="guide-index-status" id="game-directory-status" aria-live="polite"></p>
      <section class="game-directory-list" aria-label="RaidBench games">
        ${gameRows()}
      </section>
    </main>
    <footer class="footer"><p>RaidBench is an independent, unofficial player resource. All game names and trademarks belong to their respective owners.</p><p class="footer-links"><a href="./guides.html">Guides</a><a href="./updates.html">Patch Watch</a><a href="./about.html">Editorial standards</a><a href="./privacy.html">Privacy</a></p></footer>
    <script src="./config.js?v=20260903b"></script>
    <script src="./analytics.js?v=20260903b"></script>
    <script src="./game-directory.js?v=20260903b"></script>
  </body>
</html>
`;
}

function homepageSelector() {
  const popular = registry.games
    .filter((game) => game.status === "live")
    .flatMap((game) => game.featuredLinks.slice(0, 1).map((link) => ({ ...link, game: game.shortName })))
    .slice(0, 3);
  return `<!-- GAME_SELECTOR_START -->
      <section class="game-selector-hero" id="games" aria-labelledby="game-selector-title">
        <div class="game-selector-copy">
          <h1 id="game-selector-title">Game guides and decision tools for the next costly choice.</h1>
          <p>Choose a game to find focused answers, calculators, patch checks, and planning tools built around decisions players actually need to make.</p>
          <div class="lab-actions">
            <a class="primary-action" href="./games.html">Explore all 12 games</a>
            <a class="secondary-action" href="./guides.html">Search every guide</a>
          </div>
        </div>
        <div class="game-selector-panel">
          <label for="homepage-game-select">Choose a game</label>
          <div class="game-selector-control">
            <select id="homepage-game-select">
              ${registry.games.map((game) => `<option value="${escapeHtml(game.hubPath)}">${escapeHtml(game.name)}</option>`).join("\n              ")}
            </select>
            <button class="primary-action" id="open-selected-game" type="button">Open game</button>
          </div>
          <p class="game-selector-note">One account and one editorial standard across every game section.</p>
        </div>
      </section>
      <section class="homepage-popular-band" aria-labelledby="popular-decisions-title">
        <div><h2 id="popular-decisions-title">Popular decisions</h2><p>Start with a reviewed answer or a working tool.</p></div>
        <div class="popular-question-list">
          ${popular.map((item) => `<a href=".${escapeHtml(item.href)}"><span>${escapeHtml(item.game)}</span><strong>${escapeHtml(item.label)}</strong></a>`).join("\n          ")}
        </div>
      </section>
      <!-- GAME_SELECTOR_END -->`;
}

function updateHomepage() {
  const file = path.join(root, "index.html");
  const html = fs.readFileSync(file, "utf8");
  const start = "<!-- GAME_SELECTOR_START -->";
  const end = "<!-- GAME_SELECTOR_END -->";
  if (!html.includes(start) || !html.includes(end)) {
    throw new Error("index.html is missing the game selector generation markers");
  }
  const next = cleanHtml(html.replace(new RegExp(`${start}[\\s\\S]*?${end}`), homepageSelector()));
  fs.writeFileSync(file, next);
}

assertRegistry();

for (const game of registry.games) {
  const directory = path.join(root, "games", game.id);
  fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(path.join(directory, "index.html"), cleanHtml(gameHub(game)));
}

fs.writeFileSync(path.join(root, "games.html"), cleanHtml(gamesPage()));
fs.writeFileSync(path.join(root, "game-registry.json"), `${JSON.stringify(registry, null, 2)}\n`);
updateHomepage();

console.log(`Generated games.html and ${registry.games.length} game hubs from content/game-registry.json.`);
