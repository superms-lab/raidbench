import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dataPath = path.join(root, "content", "palworld-problem-guides.json");
const pagesDir = path.join(root, "pages");
const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const lastmod = "2026-07-15";
const hiddenPattern = /(paid|product|credit)/i;

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
  const publicItems = items.filter((item) => !hiddenPattern.test(item));
  if (!publicItems.length) return "";
  return `
        <article class="article-card">
          <h2>Related Palworld guides</h2>
          <div class="article-cta">
            <a class="primary-action" href="../palworld.html">Open Palworld Lab</a>
            ${publicItems.map((item) => `<a class="secondary-action" href="./${escapeHtml(item)}">${escapeHtml(item.replace(".html", "").replaceAll("-", " "))}</a>`).join("")}
          </div>
        </article>`;
}

function pageHtml(guide) {
  const title = escapeHtml(guide.title);
  const description = escapeHtml(guide.description);
  const canonical = `https://raidbench.com/pages/${guide.slug}.html`;
  const hiddenDraft = hiddenPattern.test(guide.slug);

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${title} - RaidBench</title>
    <meta name="description" content="${description}" />
    <meta name="robots" content="${hiddenDraft ? "noindex,nofollow" : "index,follow"}" />
    <link rel="canonical" href="${canonical}" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />
    <meta name="theme-color" content="#101312" />
    <link rel="stylesheet" href="../styles.css?v=20260715d" />
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="../index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      <nav class="nav" aria-label="Primary"><a href="../palworld.html">Palworld Lab</a><a href="../poe2.html">POE2 Lab</a><a href="../index.html#guides">Rust Guides</a></nav>
      <a class="header-action" href="../palworld.html">Open Lab</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="../palworld.html">RaidBench / Palworld Lab</a>
      <section class="article-hero">
        <h1>${title}</h1>
        <p>${description}</p>
        <div class="article-cta">
          <a class="primary-action" href="#checklist">Run the checklist</a>
          <a class="secondary-action" href="../palworld.html">Back to Palworld Lab</a>
        </div>
      </section>
      <section class="article-grid">
        <article class="article-card">
          <h2>Short answer</h2>
          <p>${escapeHtml(guide.shortAnswer)}</p>
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
          <h2>Source notes</h2>
          ${listHtml(guide.sources)}
          <p>Last checked: ${lastmod}. Refresh after major Palworld updates, balance changes, or repeated community questions.</p>
        </article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is an unofficial Palworld guide lab and is not affiliated with or endorsed by Pocketpair.</p><p>Palworld names belong to their respective owners.</p><p class="footer-links"><a href="../privacy.html">Privacy</a><a href="../terms.html">Terms</a><a href="../refund-policy.html">Refund Policy</a></p></footer>
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
  .filter((guide) => !hiddenPattern.test(guide.slug))
  .map((guide) => `https://raidbench.com/pages/${guide.slug}.html`)
  .filter((url) => !existingUrls.has(url))
  .map(
    (url) => `  <url>
    <loc>${url}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>`,
  )
  .join("\n");

if (newUrls) {
  sitemap = sitemap.replace(insertBefore, `\n${newUrls}${insertBefore}`);
  fs.writeFileSync(sitemapPath, sitemap);
}

console.log(`Generated ${data.length} Palworld problem guide pages.`);
