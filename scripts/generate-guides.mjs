import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dataPath = path.join(root, "content", "rust-problem-guides.json");
const pagesDir = path.join(root, "pages");
const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tableHtml(table) {
  if (!table) return "";
  return `
          <table>
            <thead>
              <tr>${table.headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr>
            </thead>
            <tbody>
              ${table.rows
                .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`)
                .join("\n              ")}
            </tbody>
          </table>`;
}

function listHtml(items = []) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function relatedHtml(items = []) {
  if (!items.length) return "";
  return `
        <article class="article-card">
          <h2>Related tools and guides</h2>
          <div class="article-cta">
            <a class="primary-action" href="../index.html#raid-calculator">Use raid calculator</a>
            ${items.map((item) => `<a class="secondary-action" href="./${escapeHtml(item)}">${escapeHtml(item.replace(".html", "").replaceAll("-", " "))}</a>`).join("")}
          </div>
        </article>`;
}

function pageHtml(guide) {
  const title = escapeHtml(guide.title);
  const description = escapeHtml(guide.description);
  const canonical = `https://raidbench.com/pages/${guide.slug}.html`;

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${title} - RaidBench</title>
    <meta name="description" content="${description}" />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="${canonical}" />
    <link rel="stylesheet" href="../styles.css" />
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="../index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      <nav class="nav" aria-label="Primary"><a href="../index.html#tools">Tools</a><a href="../index.html#guides">Guides</a><a href="../premium.html">Premium</a><a href="../poe2.html">POE2 Lab</a></nav>
      <a class="header-action" href="../index.html#raid-calculator">Open Calculator</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="../index.html">RaidBench / Rust Guides</a>
      <section class="article-hero">
        <h1>${title}</h1>
        <p>${description}</p>
        <div class="article-cta">
          <a class="primary-action" href="../index.html#raid-calculator">Use calculator</a>
          <a class="secondary-action" href="../premium.html" data-offer-id="raid-prep-pack-9" data-price-usd="9">Get raid prep pack</a>
        </div>
      </section>
      <section class="article-grid">
        <article class="article-card">
          <h2>Short answer</h2>
          <p>${escapeHtml(guide.shortAnswer)}</p>
          ${tableHtml(guide.table)}
        </article>
        <article class="article-card">
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
          <h2>Source notes</h2>
          ${listHtml(guide.sources)}
          <p>Last checked: 2026-07-05. Verify after major Rust patches.</p>
        </article>
        <article class="article-card">
          <h2>Paid worksheet angle</h2>
          <p>${escapeHtml(guide.monetization)}</p>
        </article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is an unofficial fan-made Rust planning guide.</p><p>Verify numbers after major patches.</p></footer>
    <script src="../config.js"></script>
    <script src="../analytics.js"></script>
  </body>
</html>
`;
}

fs.mkdirSync(pagesDir, { recursive: true });

for (const guide of data) {
  fs.writeFileSync(path.join(pagesDir, `${guide.slug}.html`), pageHtml(guide));
}

const sitemapPath = path.join(root, "sitemap.xml");
let sitemap = fs.readFileSync(sitemapPath, "utf8");
const insertBefore = "\n</urlset>";
const existingUrls = new Set([...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]));
const newUrls = data
  .map((guide) => `https://raidbench.com/pages/${guide.slug}.html`)
  .filter((url) => !existingUrls.has(url))
  .map(
    (url) => `  <url>
    <loc>${url}</loc>
    <lastmod>2026-07-05</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>`,
  )
  .join("\n");

if (newUrls) {
  sitemap = sitemap.replace(insertBefore, `\n${newUrls}${insertBefore}`);
  fs.writeFileSync(sitemapPath, sitemap);
}

console.log(`Generated ${data.length} Rust problem guide pages.`);
