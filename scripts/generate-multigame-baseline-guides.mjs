import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const pagesDir = path.join(root, "pages");
const baseline = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-baseline-guides.json"), "utf8"));
const games = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8")).games;
const sources = JSON.parse(fs.readFileSync(path.join(root, "content", "source-registry.json"), "utf8")).sources;
const packets = JSON.parse(fs.readFileSync(path.join(root, "content", "inbox", "multigame-source-packets-2026-09-03.json"), "utf8")).packets;
const gamesById = new Map(games.map((game) => [game.id, game]));
const packetsById = new Map(packets.map((packet) => [packet.gameId, packet]));

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

function list(items) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function table(rows) {
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="Decision checks">
            <table><thead><tr><th>Decision signal</th><th>What to verify</th><th>Next move</th></tr></thead>
              <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
            </table>
          </div>`;
}

function sourceList(packet, guide) {
  const facts = packet.factSources.map((source) => `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.notes)}</a> - ${source.authority === "publisher" ? "publisher-controlled source" : "publisher announcement via Steam"}.</li>`);
  if (guide.usesDemandSignal && packet.demandSignal) {
    facts.push(`<li><a href="${escapeHtml(packet.demandSignal.url)}" target="_blank" rel="noopener noreferrer">Community demand thread</a> - topic selection only; not factual evidence.</li>`);
  }
  return `<ul>${facts.join("")}</ul>`;
}

function relatedLinks(pack, guide) {
  const bySlug = new Map(pack.guides.map((item) => [item.slug, item]));
  return guide.related.map((slug) => {
    const related = bySlug.get(slug);
    if (!related) throw new Error(`${guide.slug} references missing related guide ${slug}`);
    return `<a class="secondary-action" href="./${escapeHtml(slug)}.html">${escapeHtml(related.title)}</a>`;
  }).join("");
}

function pageHtml(pack, guide) {
  const game = gamesById.get(pack.gameId);
  const packet = packetsById.get(pack.gameId);
  if (!game || !packet) throw new Error(`Missing game or source packet for ${pack.gameId}`);
  if (guide.usesDemandSignal && !packet.demandSignal) throw new Error(`${guide.slug} requires a missing demand signal`);
  const canonical = `https://raidbench.com/pages/${guide.slug}`;
  const citations = packet.factSources.map((source) => source.url);
  const schema = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: guide.title,
    description: guide.description,
    datePublished: baseline.reviewedAt,
    dateModified: baseline.reviewedAt,
    author: { "@type": "Organization", name: "RaidBench Editorial", url: "https://raidbench.com/about" },
    publisher: { "@type": "Organization", name: "RaidBench", url: "https://raidbench.com/" },
    mainEntityOfPage: canonical,
    about: { "@type": "VideoGame", name: game.name },
    citation: citations,
  };
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(guide.title)} | RaidBench</title>
    <meta name="description" content="${escapeHtml(guide.description)}" />
    <meta name="robots" content="${game.indexable ? "index,follow" : "noindex,follow"}" />
    <link rel="canonical" href="${canonical}" />
    <meta property="og:title" content="${escapeHtml(guide.title)}" />
    <meta property="og:description" content="${escapeHtml(guide.description)}" />
    <meta property="og:type" content="article" />
    <meta property="article:published_time" content="${baseline.reviewedAt}" />
    <meta property="article:modified_time" content="${baseline.reviewedAt}" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="../styles.css?v=20260903c" />
    <script type="application/ld+json">${jsonLd(schema)}</script>
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="../index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      <nav class="nav" aria-label="Primary"><a href="../games.html">Games</a><a href="../guides.html">Guides</a><a href="../updates.html">Patch Watch</a><a href="../about.html">About</a></nav>
      <a class="header-action" href="../games/${escapeHtml(game.id)}/">${escapeHtml(game.shortName)} guides</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="../games/${escapeHtml(game.id)}/">RaidBench / ${escapeHtml(game.shortName)} / Decision guide</a>
      <section class="article-hero">
        <h1>${escapeHtml(guide.title)}</h1>
        <p>${escapeHtml(guide.description)}</p>
        <div class="article-cta"><a class="primary-action" href="#checklist">Run the checklist</a><a class="secondary-action" href="../games/${escapeHtml(game.id)}/">Open ${escapeHtml(game.shortName)} hub</a></div>
        <div class="editorial-meta"><span>Reviewed ${baseline.reviewedAt}</span><span>${guide.patchSensitive ? "Patch-sensitive" : "Evergreen framework"}</span><span>No paid answer offered</span><a href="../about.html">Editorial standards</a></div>
      </section>
      <section class="article-grid">
        <article class="article-card">
          <h2>${escapeHtml(guide.question)}</h2>
          <div class="answer-callout"><strong>Direct answer</strong><p>${escapeHtml(guide.answer)}</p></div>
          ${table(guide.decisionRows)}
        </article>
        <article class="article-card" id="checklist"><h2>Decision checklist</h2>${list(guide.checklist)}</article>
        <article class="article-card"><h2>Stop and recheck when</h2>${list(guide.stopConditions)}</article>
        <article class="article-card"><h2>Common mistakes</h2>${list(guide.mistakes)}</article>
        <article class="article-card"><h2>Related ${escapeHtml(game.shortName)} guides</h2><div class="article-cta">${relatedLinks(pack, guide)}</div></article>
        <article class="article-card source-list"><h2>Sources and evidence boundary</h2>${sourceList(packet, guide)}<p>${escapeHtml(pack.scope)}</p><p>Reviewed ${baseline.reviewedAt}. ${escapeHtml(packet.evidenceBoundary)}</p></article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is independent and is not affiliated with or endorsed by the game publisher.</p><p class="footer-links"><a href="../games.html">Games</a><a href="../updates.html">Patch Watch</a><a href="../about.html">Editorial standards</a><a href="../privacy.html">Privacy</a><a href="../terms.html">Terms</a></p></footer>
    <script src="../config.js?v=20260903c"></script>
    <script src="../analytics.js?v=20260903c"></script>
  </body>
</html>
`;
}

if (baseline.schemaVersion !== "1.0.0" || baseline.packs.length !== 9) throw new Error("Expected nine Phase 3 baseline packs");
const slugs = new Set();
fs.mkdirSync(pagesDir, { recursive: true });
for (const pack of baseline.packs) {
  if (pack.guides.length !== 6) throw new Error(`${pack.gameId} must contain six baseline guides`);
  for (const guide of pack.guides) {
    if (slugs.has(guide.slug)) throw new Error(`Duplicate baseline guide slug: ${guide.slug}`);
    slugs.add(guide.slug);
    fs.writeFileSync(path.join(pagesDir, `${guide.slug}.html`), pageHtml(pack, guide));
  }
}

console.log(`Generated ${slugs.size} Phase 3 baseline guide pages across ${baseline.packs.length} games.`);
