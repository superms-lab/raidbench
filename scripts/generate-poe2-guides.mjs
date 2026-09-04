import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dataPath = path.join(root, "content", "poe2-problem-guides.json");
const pagesDir = path.join(root, "pages");
const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const publishedAt = "2026-07-15";
const lastmod = "2026-07-17";
const hiddenPattern = /(paid|product|credit|audit-product)/i;

function isEditorialReady(guide) {
  return guide.table?.rows?.[0]?.[0] !== "Context";
}

const editorialReadySlugs = new Set(data.filter(isEditorialReady).map((guide) => guide.slug));

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

function tableHtml(table) {
  if (!table) return "";
  return `
          <div class="table-scroll" tabindex="0" role="region" aria-label="Decision comparison">
            <table>
              <thead>
                <tr>${table.headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr>
              </thead>
              <tbody>
                ${table.rows
                  .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`)
                  .join("\n                ")}
              </tbody>
            </table>
          </div>`;
}

function listHtml(items = []) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function relatedLabel(item) {
  return item
    .replace(".html", "")
    .replaceAll("-", " ")
    .replace(/\bpoe2\b/gi, "POE2");
}

function relatedHtml(items = []) {
  const publicItems = items.filter(
    (item) => !hiddenPattern.test(item) && editorialReadySlugs.has(item.replace(/\.html$/, "")),
  );
  if (!publicItems.length) return "";
  return `
        <article class="article-card">
          <h2>Related POE2 guides</h2>
          <div class="article-cta">
            <a class="primary-action" href="../poe2.html">Open POE2 Lab</a>
            ${publicItems.map((item) => `<a class="secondary-action" href="./${escapeHtml(item)}">${escapeHtml(relatedLabel(item))}</a>`).join("")}
          </div>
        </article>`;
}

function sourceUrl(source = "") {
  if (/patch|news|official path of exile/i.test(source)) return "https://www.pathofexile.com/forum/view-forum/2212";
  if (/product information/i.test(source)) return "https://www.pathofexile.com/game";
  if (/community|demand/i.test(source)) return "../about.html";
  return "";
}

function sourceHtml(items = []) {
  return `<ul>${items
    .map((source) => {
      const href = sourceUrl(source);
      const label = /community|demand/i.test(source) ? `${source} (topic selection only)` : source;
      if (!href) return `<li>${escapeHtml(label)}</li>`;
      const external = href.startsWith("http") ? ' target="_blank" rel="noopener noreferrer"' : "";
      return `<li><a href="${escapeHtml(href)}"${external}>${escapeHtml(label)}</a></li>`;
    })
    .join("")}</ul>`;
}

function pageHtml(guide) {
  const title = escapeHtml(guide.title);
  const description = escapeHtml(guide.description);
  const canonical = `https://raidbench.com/pages/${guide.slug}`;
  const hiddenDraft = hiddenPattern.test(guide.slug);
  const editorialReady = isEditorialReady(guide);
  const citations = [...new Set((guide.sources || []).map(sourceUrl).filter((url) => url.startsWith("http")))];
  const schema = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: guide.title,
    description: guide.description,
    datePublished: publishedAt,
    dateModified: lastmod,
    author: { "@type": "Organization", name: "RaidBench Editorial", url: "https://raidbench.com/about" },
    publisher: { "@type": "Organization", name: "RaidBench", url: "https://raidbench.com/" },
    mainEntityOfPage: canonical,
    about: { "@type": "VideoGame", name: "Path of Exile 2" },
    citation: citations
  };

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${title} - RaidBench</title>
    <meta name="description" content="${description}" />
    <meta name="robots" content="${hiddenDraft ? "noindex,nofollow" : editorialReady ? "index,follow" : "noindex,follow"}" />
    <link rel="canonical" href="${canonical}" />
    <meta property="og:title" content="${title}" />
    <meta property="og:description" content="${description}" />
    <meta property="og:type" content="article" />
    <meta property="article:published_time" content="${publishedAt}" />
    <meta property="article:modified_time" content="${lastmod}" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="../styles.css?v=20260717a" />
    <script type="application/ld+json">${jsonLd(schema)}</script>
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="../index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      <nav class="nav" aria-label="Primary"><a href="../games.html">Games</a><a href="../guides.html">Guides</a><a href="../updates.html">Patch Watch</a><a href="../about.html">About</a></nav>
      <a class="header-action" href="../poe2.html">Open POE2 Lab</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="../poe2.html">RaidBench / POE2 Lab</a>
      <section class="article-hero">
        <h1>${title}</h1>
        <p>${description}</p>
        <div class="article-cta">
          <a class="primary-action" href="#checklist">Run the checklist</a>
          <a class="secondary-action" href="../guides.html">Search all guides</a>
        </div>
        <div class="editorial-meta"><span>Reviewed ${lastmod}</span><span>Patch-sensitive guidance</span><a href="../about.html">Editorial standards</a></div>
      </section>
      <section class="article-grid">
        <article class="article-card">
          <h2>${escapeHtml(guide.problem || "Short answer")}</h2>
          <div class="answer-callout"><strong>Short answer</strong><p>${escapeHtml(guide.shortAnswer)}</p></div>
          ${tableHtml(guide.table)}
        </article>
        <article class="article-card" id="checklist">
          <h2>Checklist</h2>
          ${listHtml(guide.checklist)}
        </article>
        <article class="article-card">
          <h2>Example</h2>
          <p>${escapeHtml(guide.example)}</p>
        </article>
        <article class="article-card">
          <h2>Common mistakes</h2>
          ${listHtml(guide.mistakes)}
        </article>
        ${relatedHtml(guide.related)}
        <article class="article-card source-list">
          <h2>Sources and review notes</h2>
          ${sourceHtml(guide.sources)}
          <p>Reviewed ${lastmod}. Recheck after POE2 patch notes, hotfixes, or economy changes that affect this decision.</p>
        </article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is independent and is not affiliated with or endorsed by Grinding Gear Games.</p><p class="footer-links"><a href="../updates.html">Patch Watch</a><a href="../about.html">Editorial standards</a><a href="../privacy.html">Privacy</a><a href="../terms.html">Terms</a><a href="../refund-policy.html">Refunds</a></p></footer>
    <script src="../config.js?v=20260717a"></script>
    <script src="../analytics.js?v=20260717a"></script>
  </body>
</html>
`;
}

fs.mkdirSync(pagesDir, { recursive: true });

for (const guide of data) {
  if (hiddenPattern.test(guide.slug)) continue;
  fs.writeFileSync(path.join(pagesDir, `${guide.slug}.html`), pageHtml(guide));
}

console.log(
  `Generated ${data.filter((guide) => !hiddenPattern.test(guide.slug)).length} POE2 pages; ${data.filter((guide) => !hiddenPattern.test(guide.slug) && isEditorialReady(guide)).length} passed the editorial index gate.`,
);
