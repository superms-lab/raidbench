import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const config = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-tools.json"), "utf8"));
const games = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8")).games;
const sources = JSON.parse(fs.readFileSync(path.join(root, "content", "source-registry.json"), "utf8")).sources;
const baseline = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-baseline-guides.json"), "utf8"));
const gamesById = new Map(games.map((game) => [game.id, game]));
const sourcesById = new Map(sources.map((source) => [source.id, source]));
const guidesBySlug = new Map(baseline.packs.flatMap((pack) => pack.guides).map((guide) => [guide.slug, guide]));

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function jsonLd(value) {
  return JSON.stringify(value).replaceAll("<", "\\u003c");
}

function selectOptions(options, selected) {
  return options.map((option) => `<option value="${escapeHtml(option.value)}"${Number(option.value) === Number(selected) ? " selected" : ""}>${escapeHtml(option.label)}</option>`).join("");
}

function fieldsHtml(tool) {
  if (tool.type === "compare") {
    const scale = [1, 2, 3, 4, 5].map((value) => ({ value, label: `${value} / 5` }));
    return `<div class="comparison-names">
            <label>Option A<input type="text" data-field="optionA" value="${escapeHtml(tool.optionDefaults[0])}" maxlength="48" /></label>
            <label>Option B<input type="text" data-field="optionB" value="${escapeHtml(tool.optionDefaults[1])}" maxlength="48" /></label>
          </div>
          <div class="table-scroll" tabindex="0" role="region" aria-label="Option scoring criteria">
            <table class="comparison-table"><thead><tr><th>Criterion</th><th>Weight</th><th>Option A</th><th>Option B</th></tr></thead><tbody>
              ${tool.criteria.map((criterion) => `<tr><td>${escapeHtml(criterion.label)}</td><td>${criterion.weight}%</td><td><label class="sr-only" for="${criterion.id}-a">${escapeHtml(criterion.label)} for option A</label><select id="${criterion.id}-a" data-field="${criterion.id}A">${selectOptions(scale, criterion.defaultA)}</select></td><td><label class="sr-only" for="${criterion.id}-b">${escapeHtml(criterion.label)} for option B</label><select id="${criterion.id}-b" data-field="${criterion.id}B">${selectOptions(scale, criterion.defaultB)}</select></td></tr>`).join("")}
            </tbody></table>
          </div>`;
  }
  return `<div class="tool-input-grid">${tool.fields.map((field) => {
    const inputId = `${tool.id}-${field.id}`;
    return `<label for="${escapeHtml(inputId)}">${escapeHtml(field.label)}${field.inputType === "select"
      ? `<select id="${escapeHtml(inputId)}" aria-label="${escapeHtml(field.label)}" data-field="${escapeHtml(field.id)}">${selectOptions(field.options, field.default)}</select>`
      : `<span class="tool-input-wrap"><input id="${escapeHtml(inputId)}" aria-label="${escapeHtml(field.label)}" type="number" data-field="${escapeHtml(field.id)}" min="${field.min}" max="${field.max}" step="${field.step}" value="${field.default}" /><small>${escapeHtml(field.unit || "")}</small></span>`}</label>`;
  }).join("")}</div>`;
}

function sourcesHtml(tool) {
  return tool.sourceIds.map((sourceId) => {
    const source = sourcesById.get(sourceId);
    if (!source || source.role !== "fact") throw new Error(`${tool.id} has an invalid factual source ${sourceId}`);
    return `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.notes)}</a></li>`;
  }).join("");
}

function guidesHtml(tool) {
  return tool.guideSlugs.map((slug) => {
    const guide = guidesBySlug.get(slug);
    if (!guide) throw new Error(`${tool.id} has an invalid guide ${slug}`);
    return `<a class="secondary-action" href="../../pages/${escapeHtml(slug)}.html">${escapeHtml(guide.title)}</a>`;
  }).join("");
}

function defaultInputs(tool) {
  if (tool.type === "compare") {
    const values = { optionA: tool.optionDefaults[0], optionB: tool.optionDefaults[1] };
    for (const criterion of tool.criteria) {
      values[`${criterion.id}A`] = criterion.defaultA;
      values[`${criterion.id}B`] = criterion.defaultB;
    }
    return values;
  }
  return Object.fromEntries(tool.fields.map((field) => [field.id, field.default]));
}

function toolPage(tool) {
  const game = gamesById.get(tool.gameId);
  if (!game) throw new Error(`Unknown game for tool ${tool.id}`);
  const enriched = { ...tool, reviewedAt: config.reviewedAt };
  const canonical = `https://raidbench.com/tools/${tool.slug}/`;
  const schema = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: tool.title,
    description: tool.description,
    url: canonical,
    applicationCategory: "GameApplication",
    operatingSystem: "Any",
    isAccessibleForFree: true,
    about: { "@type": "VideoGame", name: game.name },
  };
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(tool.title)} | RaidBench</title>
    <meta name="description" content="${escapeHtml(tool.description)}" />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="${canonical}" />
    <meta property="og:title" content="${escapeHtml(tool.title)}" />
    <meta property="og:description" content="${escapeHtml(tool.description)}" />
    <meta property="og:type" content="website" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="../../styles.css?v=20260903d" />
    <script type="application/ld+json">${jsonLd(schema)}</script>
  </head>
  <body>
    <header class="site-header"><a class="brand" href="../../index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a><nav class="nav" aria-label="Primary"><a href="../../games.html">Games</a><a href="../../guides.html">Guides</a><a href="../../tools.html" aria-current="page">Tools</a><a href="../../updates.html">Patch Watch</a><a href="../../about.html">About</a></nav><a class="header-action" href="../../games/${escapeHtml(game.id)}/">${escapeHtml(game.shortName)} hub</a></header>
    <main class="article-main tool-page-main">
      <a class="breadcrumb" href="../../games/${escapeHtml(game.id)}/">RaidBench / ${escapeHtml(game.shortName)} / Free tool</a>
      <section class="article-hero"><h1>${escapeHtml(tool.title)}</h1><p>${escapeHtml(tool.description)}</p><div class="editorial-meta"><span>Reviewed ${config.reviewedAt}</span><span>User-entered assumptions</span><span>No account required</span><span>No paid answer offered</span></div></section>
      <section class="interactive-tool" data-multigame-tool>
        <div class="tool-surface-heading"><div><h2>${escapeHtml(tool.question)}</h2><p>Change the inputs to match the current game, account, server, or match context. Results update immediately.</p></div><button class="icon-button" type="button" data-copy-share>Copy share link</button></div>
        ${fieldsHtml(tool)}
        <div class="tool-result" aria-live="polite">
          <div class="tool-primary-result"><span data-primary-label>Result</span><strong data-primary-result>--</strong></div>
          <p data-result-verdict>Enter the current assumptions to calculate a result.</p>
        </div>
        <div class="tool-result-metrics" data-result-metrics></div>
        <div class="table-scroll tool-breakdown" tabindex="0" role="region" aria-label="Calculation breakdown"><table><thead><tr><th>Component</th><th>Value</th></tr></thead><tbody data-result-breakdown></tbody></table></div>
        <div class="tool-actions"><button class="secondary-action" type="button" data-copy-result>Copy result</button><a class="secondary-action" href="../../downloads/${escapeHtml(tool.slug)}-worksheet.json" download data-download-worksheet>Download worksheet JSON</a></div>
      </section>
      <section class="article-grid tool-support-grid">
        <article class="article-card"><h2>Assumptions</h2><ul>${tool.assumptions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article>
        <article class="article-card"><h2>Related decision guides</h2><div class="article-cta">${guidesHtml(tool)}</div></article>
        <article class="article-card source-list"><h2>Current-source boundary</h2><ul>${sourcesHtml(tool)}</ul><p>Reviewed ${config.reviewedAt}. The calculator uses only the values entered on this page; publisher sources are monitored for changes that may affect how those inputs should be interpreted.</p></article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is independent and is not affiliated with or endorsed by the game publisher.</p><p class="footer-links"><a href="../../tools.html">Tools</a><a href="../../games.html">Games</a><a href="../../about.html">Editorial standards</a><a href="../../privacy.html">Privacy</a><a href="../../terms.html">Terms</a></p></footer>
    <script id="tool-config" type="application/json">${jsonLd(enriched)}</script>
    <script src="../../config.js?v=20260903d"></script><script src="../../analytics.js?v=20260903d"></script><script src="../../multi-game-tool-engine.js?v=20260903d"></script><script src="../../multi-game-tools.js?v=20260903d"></script>
  </body>
</html>`;
}

function toolsIndex() {
  const rows = config.tools.map((tool) => {
    const game = gamesById.get(tool.gameId);
    return `<a class="game-directory-row" href="./tools/${escapeHtml(tool.slug)}/"><span class="game-directory-code">${escapeHtml(game.code)}</span><span class="game-directory-copy"><strong>${escapeHtml(tool.title)}</strong><small>${escapeHtml(tool.description)}</small></span><span class="game-directory-meta"><span>${escapeHtml(game.shortName)}</span><small>Free, no account required</small></span></a>`;
  }).join("");
  const schema = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "RaidBench free game tools",
    url: "https://raidbench.com/tools",
    description: "Free calculators, comparison tools, risk planners, and downloadable results for complex game decisions.",
  };
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>Free Game Calculators &amp; Decision Tools | RaidBench</title><meta name="description" content="Free RaidBench calculators, comparison tools, risk planners, and downloadable results for Rust and nine additional complex games." /><meta name="robots" content="index,follow" /><link rel="canonical" href="https://raidbench.com/tools" /><meta property="og:title" content="RaidBench Free Game Tools" /><meta property="og:description" content="Practical calculators and comparison tools built around player-entered assumptions." /><meta property="og:type" content="website" /><link rel="icon" href="/favicon.svg" type="image/svg+xml" /><link rel="manifest" href="/site.webmanifest" /><meta name="theme-color" content="#101312" /><link rel="stylesheet" href="./styles.css?v=20260903d" /><script type="application/ld+json">${jsonLd(schema)}</script></head>
<body><header class="site-header"><a class="brand" href="./index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a><nav class="nav" aria-label="Primary"><a href="./games.html">Games</a><a href="./guides.html">Guides</a><a href="./tools.html" aria-current="page">Tools</a><a href="./updates.html">Patch Watch</a><a href="./about.html">About</a></nav><a class="header-action" href="./index.html#raid-calculator">Rust calculator</a></header>
<main class="article-main game-directory-main"><a class="breadcrumb" href="./index.html">RaidBench / Tools</a><section class="game-directory-hero"><h1>Free tools for decisions worth checking twice.</h1><p>Use player-entered values to compare options, calculate budgets, measure planning margins, and download a result without creating an account.</p></section><section class="game-directory-list tool-directory-list" aria-label="Free RaidBench tools"><a class="game-directory-row" href="./#raid-calculator"><span class="game-directory-code">RU</span><span class="game-directory-copy"><strong>Rust raid cost calculator</strong><small>Build a complete breach route and compare sulfur, items, and methods.</small></span><span class="game-directory-meta"><span>Rust</span><small>Free, no account required</small></span></a>${rows}</section></main>
<footer class="footer"><p>Tool results depend on the values entered and do not guarantee an in-game outcome.</p><p class="footer-links"><a href="./games.html">Games</a><a href="./guides.html">Guides</a><a href="./about.html">Editorial standards</a><a href="./privacy.html">Privacy</a></p></footer><script src="./config.js?v=20260903d"></script><script src="./analytics.js?v=20260903d"></script></body></html>`;
}

if (config.schemaVersion !== "1.0.0" || config.tools.length !== 9) throw new Error("Expected nine Phase 4 tools");
const slugs = new Set();
const downloadsDir = path.join(root, "downloads");
fs.mkdirSync(downloadsDir, { recursive: true });
for (const tool of config.tools) {
  if (slugs.has(tool.slug)) throw new Error(`Duplicate tool slug: ${tool.slug}`);
  slugs.add(tool.slug);
  const directory = path.join(root, "tools", tool.slug);
  fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(path.join(directory, "index.html"), toolPage(tool));
  fs.writeFileSync(path.join(downloadsDir, `${tool.slug}-worksheet.json`), `${JSON.stringify({
    schemaVersion: "1.0.0",
    toolId: tool.id,
    gameId: tool.gameId,
    reviewedAt: config.reviewedAt,
    instructions: "Replace the default inputs with current player-entered values, then retain the assumptions with any shared result.",
    inputs: defaultInputs(tool),
    assumptions: tool.assumptions,
  }, null, 2)}\n`);
}
fs.writeFileSync(path.join(root, "tools.html"), toolsIndex());
fs.writeFileSync(path.join(root, "multigame-tools.json"), `${JSON.stringify(config, null, 2)}\n`);
console.log(`Generated ${config.tools.length} interactive game tools and tools.html.`);
