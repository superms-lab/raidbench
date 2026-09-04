import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const data = JSON.parse(fs.readFileSync(path.join(root, "content", "patch-watch.json"), "utf8"));
const pagesDir = path.join(root, "pages");

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function jsonLd(value) {
  return JSON.stringify(value).replaceAll("<", "\\u003c");
}

function labelForRelated(value) {
  return value
    .replace(".html", "")
    .replaceAll("-", " ")
    .replace(/\b(poe2|rust|palworld)\b/gi, (match) => match.toUpperCase());
}

function articlePage(item) {
  const canonical = `https://raidbench.com/pages/${item.slug}`;
  const schema = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: item.title,
    description: item.description,
    datePublished: item.publishedAt,
    dateModified: item.reviewedAt,
    author: {
      "@type": "Organization",
      name: "RaidBench Editorial",
      url: "https://raidbench.com/about"
    },
    publisher: {
      "@type": "Organization",
      name: "RaidBench",
      url: "https://raidbench.com/"
    },
    mainEntityOfPage: canonical,
    about: {
      "@type": "VideoGame",
      name: item.game
    },
    citation: item.source.url
  };

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(item.title)} | RaidBench</title>
    <meta name="description" content="${escapeHtml(item.description)}" />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="${canonical}" />
    <meta property="og:title" content="${escapeHtml(item.title)}" />
    <meta property="og:description" content="${escapeHtml(item.description)}" />
    <meta property="og:type" content="article" />
    <meta property="article:published_time" content="${item.publishedAt}" />
    <meta property="article:modified_time" content="${item.reviewedAt}" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="../styles.css?v=20260717a" />
    <script type="application/ld+json">${jsonLd(schema)}</script>
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="../index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      <nav class="nav" aria-label="Primary"><a href="../games.html">Games</a><a href="../guides.html">Guides</a><a href="../updates.html" aria-current="page">Patch Watch</a><a href="../about.html">About</a></nav>
      <a class="header-action" href="../updates.html">Latest Updates</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="../updates.html">RaidBench / Patch Watch / ${escapeHtml(item.game)}</a>
      <section class="article-hero">
        <p class="eyebrow">${escapeHtml(item.game)} · ${escapeHtml(item.version)}</p>
        <h1>${escapeHtml(item.title)}</h1>
        <p>${escapeHtml(item.description)}</p>
        <div class="editorial-meta">
          <span>${escapeHtml(item.status)}</span>
          <span>Official update: ${escapeHtml(item.publishedAt)}</span>
          <span>Reviewed: ${escapeHtml(item.reviewedAt)}</span>
          <a href="../about.html">How RaidBench reviews updates</a>
        </div>
      </section>

      <section class="article-grid">
        <article class="article-card">
          <h2>${escapeHtml(item.question)}</h2>
          <div class="answer-callout"><strong>Short answer</strong><p>${escapeHtml(item.shortAnswer)}</p></div>
          <div class="table-scroll" tabindex="0" role="region" aria-label="Player impact summary">
            <table>
              <thead><tr><th>Area</th><th>What it means</th></tr></thead>
              <tbody>${item.impact.map((row) => `<tr><td>${escapeHtml(row[0])}</td><td>${escapeHtml(row[1])}</td></tr>`).join("")}</tbody>
            </table>
          </div>
        </article>

        <article class="article-card" id="checklist">
          <h2>Player checklist</h2>
          <ol>${item.checklist.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
        </article>

        <article class="article-card">
          <h2>What this update does not prove</h2>
          <p>${escapeHtml(item.notChanged)}</p>
          <h3>Refresh trigger</h3>
          <p>${escapeHtml(item.refreshTrigger)}</p>
        </article>

        <article class="article-card source-list">
          <h2>Official source</h2>
          <p><a href="${escapeHtml(item.source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.source.label)}</a></p>
          <p>RaidBench summary reviewed on ${escapeHtml(item.reviewedAt)}. Follow the official source when a later update conflicts with this page.</p>
        </article>

        <article class="article-card">
          <h2>Related guides</h2>
          <div class="article-cta">
            ${item.related.map((related) => `<a class="secondary-action" href="./${escapeHtml(related)}">${escapeHtml(labelForRelated(related))}</a>`).join("")}
          </div>
        </article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is an independent, unofficial player resource.</p><p class="footer-links"><a href="../updates.html">Patch Watch</a><a href="../about.html">Editorial standards</a><a href="../privacy.html">Privacy</a><a href="../terms.html">Terms</a><a href="../refund-policy.html">Refunds</a></p></footer>
    <script src="../config.js?v=20260717a"></script>
    <script src="../analytics.js?v=20260717a"></script>
  </body>
</html>`;
}

function card(item) {
  return `<a class="patch-card" href="./pages/${escapeHtml(item.slug)}.html">
          <div class="patch-meta"><span class="status-pill">${escapeHtml(item.game)}</span><span>${escapeHtml(item.version)}</span><span>${escapeHtml(item.publishedAt)}</span></div>
          <h2>${escapeHtml(item.title)}</h2>
          <p>${escapeHtml(item.description)}</p>
          <span class="patch-impact">Read the player impact summary</span>
        </a>`;
}

const updatesSchema = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  name: "RaidBench Patch Watch",
  description: "Official-source game update summaries for Rust, Path of Exile 2, and Palworld.",
  url: "https://raidbench.com/updates",
  hasPart: data.map((item) => ({
    "@type": "Article",
    headline: item.title,
    url: `https://raidbench.com/pages/${item.slug}`,
    dateModified: item.reviewedAt
  }))
};

const updatesHtml = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Game Patch Watch - Rust, POE2 &amp; Palworld | RaidBench</title>
    <meta name="description" content="Official-source patch summaries and practical player checklists for Rust, Path of Exile 2, and Palworld." />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="https://raidbench.com/updates" />
    <meta property="og:title" content="RaidBench Patch Watch" />
    <meta property="og:description" content="What changed, who is affected, and which old advice should be retired." />
    <meta property="og:type" content="website" />
    <link rel="alternate" type="application/rss+xml" title="RaidBench Patch Watch" href="https://raidbench.com/feed.xml" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="./styles.css?v=20260717a" />
    <script type="application/ld+json">${jsonLd(updatesSchema)}</script>
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="./index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      <nav class="nav" aria-label="Primary"><a href="./games.html">Games</a><a href="./guides.html">Guides</a><a href="./updates.html" aria-current="page">Patch Watch</a><a href="./about.html">About</a></nav>
      <a class="header-action" href="./guides.html">Find a Guide</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="./index.html">RaidBench / Patch Watch</a>
      <section class="article-hero">
        <p class="eyebrow">Official source in, player decision out</p>
        <h1>Patch notes are long. The part that changes your next move is not.</h1>
        <p>Patch Watch explains what changed, who is affected, which workaround is now obsolete, and what deserves a fresh test. Every summary links to the official update behind it.</p>
        <div class="fact-strip" aria-label="Patch Watch summary">
          <div><span>Tracked games</span><strong>Rust · POE2 · Palworld</strong></div>
          <div><span>Published briefs</span><strong>${data.length} source-backed updates</strong></div>
          <div><span>Review rule</span><strong>Recheck after every relevant patch</strong></div>
        </div>
      </section>

      <section class="patch-grid" aria-label="Latest patch briefs">
        ${data.map(card).join("\n        ")}
      </section>

      <section class="monetization-band diagnostic-band">
        <div>
          <h2>Need the evergreen answer instead?</h2>
          <p>Search the full guide library for raid math, build checks, base operations, boss prep, and progression decisions.</p>
        </div>
        <a class="primary-action" href="./guides.html">Search all guides</a>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is independent and is not affiliated with or endorsed by any game publisher.</p><p class="footer-links"><a href="./about.html">Editorial standards</a><a href="./guides.html">Guides</a><a href="./privacy.html">Privacy</a><a href="./terms.html">Terms</a><a href="./refund-policy.html">Refunds</a></p></footer>
    <script src="./config.js?v=20260717a"></script>
    <script src="./analytics.js?v=20260717a"></script>
  </body>
</html>`;

fs.mkdirSync(pagesDir, { recursive: true });
for (const item of data) {
  fs.writeFileSync(path.join(pagesDir, `${item.slug}.html`), articlePage(item));
}
fs.writeFileSync(path.join(root, "updates.html"), updatesHtml);

const sitemapPath = path.join(root, "sitemap.xml");
let sitemap = fs.readFileSync(sitemapPath, "utf8");
const existingUrls = new Set([...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]));
const urls = ["https://raidbench.com/updates", "https://raidbench.com/about", ...data.map((item) => `https://raidbench.com/pages/${item.slug}`)];
const blocks = urls
  .filter((url) => !existingUrls.has(url))
  .map((url) => `  <url>\n    <loc>${url}</loc>\n    <lastmod>2026-07-17</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>${url.endsWith("updates.html") ? "0.9" : "0.7"}</priority>\n  </url>`)
  .join("\n");

if (blocks) {
  sitemap = sitemap.replace("\n</urlset>", `\n${blocks}\n</urlset>`);
  fs.writeFileSync(sitemapPath, sitemap);
}

console.log(`Generated Patch Watch with ${data.length} source-backed pages.`);
