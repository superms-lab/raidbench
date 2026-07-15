import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dataPath = path.join(root, "content", "poe2-problem-guides.json");
const pagesDir = path.join(root, "pages");
const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const lastmod = "2026-07-15";

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
          <h2>Related POE2 guides</h2>
          <div class="article-cta">
            <a class="primary-action" href="../poe2.html">Open POE2 Lab</a>
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
      <nav class="nav" aria-label="Primary"><a href="../poe2.html">POE2 Lab</a><a href="../premium.html">Premium</a><a href="../index.html#guides">Rust Guides</a></nav>
      <a class="header-action" href="../premium.html#poe2-credits">POE2 Credits</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="../poe2.html">RaidBench / POE2 Lab</a>
      <section class="article-hero">
        <h1>${title}</h1>
        <p>${description}</p>
        <div class="article-cta">
          <a class="primary-action" href="../premium.html#poe2-credits">View audit credits</a>
          <a class="secondary-action" href="../poe2.html">Back to POE2 Lab</a>
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
          <p>Last checked: ${lastmod}. Refresh after major POE2 updates or economy changes.</p>
        </article>
        <article class="article-card">
          <h2>Paid angle</h2>
          <p>${escapeHtml(guide.monetization)}</p>
        </article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is an unofficial POE2 guide lab and is not affiliated with or endorsed by Grinding Gear Games.</p><p>Path of Exile and Path of Exile 2 names belong to their respective owners.</p><p class="footer-links"><a href="../privacy.html">Privacy</a><a href="../terms.html">Terms</a><a href="../refund-policy.html">Refund Policy</a></p></footer>
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

console.log(`Generated ${data.length} POE2 problem guide pages.`);
