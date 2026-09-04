import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dataPath = path.join(root, "content", "rust-problem-guides.json");
const pagesDir = path.join(root, "pages");
const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const defaultPublishedAt = "2026-07-15";
const defaultReviewedAt = "2026-07-17";
const hiddenPattern = /(paid|product|credit|audit-product)/i;
const targetGuideRoutes = {
  "rust-sheet-metal-door-raid-cost": "sheet-door~1~rockets",
  "rust-garage-door-raid-cost": "garage-door~1~rockets",
  "rust-armored-door-raid-cost": "armored-door~1~rockets",
  "rust-stone-wall-raid-cost": "stone-wall~1~rockets",
  "rust-sheet-metal-wall-raid-cost": "sheet-wall~1~rockets",
  "rust-armored-wall-raid-cost": "armored-wall~1~rockets",
};

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
          <div class="table-scroll" tabindex="0" role="region" aria-label="Raid planning comparison">
            <table>
              <thead><tr>${table.headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead>
              <tbody>${table.rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
            </table>
          </div>`;
}

function listHtml(items = []) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function relatedLabel(item) {
  const slug = item.replace(/\.html$/, "");
  const match = data.find((guide) => guide.slug === slug);
  if (match) return match.title;
  return item
    .replace(".html", "")
    .replaceAll("-", " ")
    .replace(/\brust\b/gi, "Rust");
}

function relatedHtml(items = [], calculatorHref = "../index.html#raid-calculator") {
  const publicItems = items.filter(
    (item) => !hiddenPattern.test(item) && editorialReadySlugs.has(item.replace(/\.html$/, "")),
  );
  if (!publicItems.length) return "";
  return `
        <article class="article-card">
          <h2>Related Rust tools and guides</h2>
          <div class="article-cta">
            <a class="primary-action" href="${calculatorHref}">Use raid calculator</a>
            ${publicItems.map((item) => `<a class="secondary-action" href="./${escapeHtml(item)}">${escapeHtml(relatedLabel(item))}</a>`).join("")}
          </div>
        </article>`;
}

function sourceUrl(source = "") {
  if (source && typeof source === "object") return source.url || "";
  if (/facepunch|official update|rust official/i.test(source)) return "https://rust.facepunch.com/news";
  if (/raidbench|in-game verification|community|question pattern/i.test(source)) return "../about.html";
  return "";
}

function sourceHtml(items = []) {
  return `<ul>${items
    .map((source) => {
      const href = sourceUrl(source);
      const rawLabel = typeof source === "object" ? source.label : source;
      const note = typeof source === "object" ? source.note : "";
      const label = /community|question pattern/i.test(rawLabel) ? `${rawLabel} (topic selection only)` : rawLabel;
      const suffix = note ? ` - ${note}` : "";
      if (!href) return `<li>${escapeHtml(label)}</li>`;
      const external = href.startsWith("http") ? ' target="_blank" rel="noopener noreferrer"' : "";
      return `<li><a href="${escapeHtml(href)}"${external}>${escapeHtml(label)}</a>${escapeHtml(suffix)}</li>`;
    })
    .join("")}</ul>`;
}

function sectionsHtml(items = []) {
  return items
    .map((section) => `
        <article class="article-card">
          <h2>${escapeHtml(section.title)}</h2>
          ${(section.paragraphs || []).map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}
          ${(section.bullets || []).length ? listHtml(section.bullets) : ""}
        </article>`)
    .join("");
}

function faqHtml(items = []) {
  if (!items.length) return "";
  return `
        <article class="article-card faq-card">
          <h2>Frequently asked questions</h2>
          ${items.map((item) => `<details><summary>${escapeHtml(item.question)}</summary><p>${escapeHtml(item.answer)}</p></details>`).join("")}
        </article>`;
}

function calculatorHtml(calculator) {
  if (calculator?.type !== "raid_break_even") return "";
  return `
        <article class="article-card decision-calculator" data-break-even-calculator>
          <h2>Raid break-even calculator</h2>
          <p>Use your own sulfur-equivalent estimates for recovered loot and lost kits. The result is a decision aid, not a universal price list.</p>
          <div class="calculator-inputs">
            <label>Boom used, sulfur equivalent<input type="number" min="0" step="25" value="4400" data-break-even-cost /></label>
            <label>Loot recovered, sulfur equivalent<input type="number" min="0" step="25" value="0" data-break-even-loot /></label>
            <label>Lost kits and supplies, sulfur equivalent<input type="number" min="0" step="25" value="0" data-break-even-loss /></label>
          </div>
          <div class="calculator-result" aria-live="polite"><span>Resource result</span><strong data-break-even-result>-4,400 sulfur equivalent</strong><p data-break-even-verdict>Below break-even before time and counter risk.</p></div>
        </article>`;
}

function pageHtml(guide) {
  const title = escapeHtml(guide.title);
  const description = escapeHtml(guide.description);
  const canonical = `https://raidbench.com/pages/${guide.slug}`;
  const editorialReady = isEditorialReady(guide);
  const publishedAt = guide.publishedAt || defaultPublishedAt;
  const reviewedAt = guide.reviewedAt || defaultReviewedAt;
  const route = targetGuideRoutes[guide.slug] || "";
  const routeQuery = route ? `&amp;route=${encodeURIComponent(route)}` : "";
  const calculatorHref = route
    ? `../?route=${encodeURIComponent(route)}&amp;utm_source=guide&amp;utm_medium=internal&amp;utm_campaign=${escapeHtml(guide.slug)}#raid-calculator`
    : "../index.html#raid-calculator";
  const purchaseHref = `../customer?intent=instant${routeQuery}&amp;utm_source=guide&amp;utm_medium=internal&amp;utm_campaign=${escapeHtml(guide.slug)}`;
  const citations = [...new Set((guide.sources || [])
    .filter((source) => !/community|question pattern/i.test(typeof source === "object" ? source.label : source))
    .map(sourceUrl)
    .filter((url) => url.startsWith("http")))];
  const graph = [
    {
      "@type": "Article",
      headline: guide.title,
      description: guide.description,
      datePublished: publishedAt,
      dateModified: reviewedAt,
      author: { "@type": "Organization", name: "RaidBench Editorial", url: "https://raidbench.com/about" },
      publisher: { "@type": "Organization", name: "RaidBench", url: "https://raidbench.com/" },
      mainEntityOfPage: canonical,
      about: { "@type": "VideoGame", name: "Rust" },
      citation: citations
    },
    {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "RaidBench", item: "https://raidbench.com/" },
        { "@type": "ListItem", position: 2, name: "Rust Guides", item: "https://raidbench.com/guides" },
        { "@type": "ListItem", position: 3, name: guide.title, item: canonical }
      ]
    }
  ];
  if (guide.faqs?.length) {
    graph.push({
      "@type": "FAQPage",
      mainEntity: guide.faqs.map((item) => ({
        "@type": "Question",
        name: item.question,
        acceptedAnswer: { "@type": "Answer", text: item.answer }
      }))
    });
  }
  const schema = { "@context": "https://schema.org", "@graph": graph };

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${title} - RaidBench</title>
    <meta name="description" content="${description}" />
    <meta name="robots" content="${editorialReady ? "index,follow" : "noindex,follow"}" />
    <link rel="canonical" href="${canonical}" />
    <meta property="og:title" content="${title}" />
    <meta property="og:description" content="${description}" />
    <meta property="og:type" content="article" />
    <meta property="og:image" content="https://raidbench.com/assets/raidbench-calculator-share.png" />
    <meta property="og:image:alt" content="RaidBench Rust raid cost calculator with sulfur and gunpowder totals" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta property="article:published_time" content="${publishedAt}" />
    <meta property="article:modified_time" content="${reviewedAt}" />
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
      <a class="header-action" href="../index.html#raid-calculator">Open Calculator</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="../guides.html">RaidBench / Rust Guides</a>
      <section class="article-hero">
        <h1>${title}</h1>
        <p>${description}</p>
        <div class="article-cta">
          <a class="primary-action" href="${calculatorHref}">Use calculator</a>
          <a class="secondary-action" href="../guides.html">Search all guides</a>
        </div>
        <div class="editorial-meta"><span>Reviewed ${reviewedAt}</span><span>${escapeHtml(guide.status || "Vanilla Rust PC; verify custom server rules")}</span><a href="../about.html">Editorial standards</a></div>
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
${calculatorHtml(guide.calculator)}
${sectionsHtml(guide.sections)}
        <article class="article-card">
          <h2>Common mistakes</h2>
          ${listHtml(guide.mistakes)}
        </article>
${faqHtml(guide.faqs)}
${relatedHtml(guide.related, calculatorHref)}
        <article class="article-card conversion-card" data-live-commerce hidden>
          <p class="eyebrow">Verified Rust answers from $5</p>
          <h2>Check one target now, or build the complete raid route.</h2>
          <p>The $5 starter pack covers two personalized route checks. A $19 pack covers a complete multi-layer raid plan with resource buffer, evidence, and calculation checks. Unsupported requests are not charged.</p>
          <div class="article-cta"><a class="primary-action" href="${purchaseHref}" data-commerce-cta>Get a verified answer</a><a class="secondary-action" href="../rust-raid-plan">Compare both options</a></div>
        </article>
        <article class="article-card source-list">
          <h2>Sources and review notes</h2>
          ${sourceHtml(guide.sources)}
          <p>Reviewed ${reviewedAt}. Recheck after Rust building, explosive, upkeep, or Softcore rule changes, and verify custom server settings.</p>
        </article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is independent and is not affiliated with or endorsed by Facepunch Studios.</p><p class="footer-links"><a href="../updates.html">Patch Watch</a><a href="../about.html">Editorial standards</a><a href="../privacy.html">Privacy</a><a href="../terms.html">Terms</a><a href="../refund-policy.html">Refunds</a></p></footer>
    <script src="../config.js?v=20260717a"></script>
    <script src="../analytics.js?v=20260717a"></script>
    <script src="../guide-tools.js?v=20260809a"></script>
  </body>
</html>`;
}

fs.mkdirSync(pagesDir, { recursive: true });
for (const guide of data) {
  if (hiddenPattern.test(guide.slug)) continue;
  fs.writeFileSync(path.join(pagesDir, `${guide.slug}.html`), pageHtml(guide));
}

console.log(
  `Generated ${data.filter((guide) => !hiddenPattern.test(guide.slug)).length} Rust pages; ${data.filter((guide) => !hiddenPattern.test(guide.slug) && isEditorialReady(guide)).length} passed the editorial index gate.`,
);
