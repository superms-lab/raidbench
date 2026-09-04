import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dataPath = process.env.RAIDBENCH_AGENT_GUIDES_PATH || path.join(root, "content", "agent-guides.json");
const pagesDir = process.env.RAIDBENCH_AGENT_PAGES_DIR || path.join(root, "pages");
const games = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8")).games;
const gameByName = new Map(games.flatMap((game) => [[game.name, game], [game.shortName, game]]));
const marker = "<!-- raidbench-agent-generated -->";

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

function requireString(value, label) {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string`);
  return value.trim();
}

function requireList(value, label, minimum = 1) {
  if (!Array.isArray(value) || value.length < minimum) throw new Error(`${label} must contain at least ${minimum} item(s)`);
  return value;
}

function safeExternalUrl(value, label) {
  const url = new URL(requireString(value, label));
  if (url.protocol !== "https:") throw new Error(`${label} must use HTTPS`);
  return url.href;
}

function titleFromSlug(slug) {
  return slug
    .split("-")
    .map((part) => ["rust", "poe2"].includes(part.toLowerCase()) ? part.toUpperCase() : `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function validateGuide(guide, index) {
  const label = `agent-guides[${index}]`;
  for (const field of ["slug", "game", "title", "description", "problem", "shortAnswer", "example", "reviewedAt", "status", "sourceNote"]) {
    requireString(guide[field], `${label}.${field}`);
  }
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(guide.slug)) throw new Error(`${label}.slug is not URL-safe`);
  if (!gameByName.has(guide.game)) throw new Error(`${label}.game is unsupported`);
  requireList(guide.sections, `${label}.sections`, 2);
  requireList(guide.checklist, `${label}.checklist`, 3);
  requireList(guide.mistakes, `${label}.mistakes`, 2);
  requireList(guide.faqs, `${label}.faqs`, 2);
  requireList(guide.related, `${label}.related`, 1);
  requireList(guide.sources, `${label}.sources`, 1);
  for (const [sourceIndex, source] of guide.sources.entries()) {
    requireString(source.label, `${label}.sources[${sourceIndex}].label`);
    safeExternalUrl(source.url, `${label}.sources[${sourceIndex}].url`);
  }
}

function listHtml(items) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function sectionsHtml(sections) {
  return sections
    .map((section) => `
        <article class="article-card">
          <h2>${escapeHtml(section.title)}</h2>
          <p>${escapeHtml(section.purpose)}</p>
          ${listHtml(section.bullets)}
        </article>`)
    .join("");
}

function faqHtml(faqs) {
  return `
        <article class="article-card faq-card">
          <h2>Frequently asked questions</h2>
          ${faqs.map((item) => `<details><summary>${escapeHtml(item.question)}</summary><p>${escapeHtml(item.answer)}</p></details>`).join("")}
        </article>`;
}

function sourceHtml(sources) {
  return `<ul>${sources.map((source) => `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)}</a>${source.note ? ` - ${escapeHtml(source.note)}` : ""}</li>`).join("")}</ul>`;
}

function relatedHtml(related) {
  return related
    .map((slug) => `<a class="secondary-action" href="./${escapeHtml(slug)}.html">${escapeHtml(titleFromSlug(slug))}</a>`)
    .join("");
}

function gameHub(game) {
  const registered = gameByName.get(game);
  if (!registered) throw new Error(`Unsupported guide game: ${game}`);
  return {
    href: `../games/${registered.id}/`,
    label: `${registered.shortName} guides`,
    publicUrl: `https://raidbench.com/games/${registered.id}/`,
  };
}

function pageHtml(guide) {
  const canonical = `https://raidbench.com/pages/${guide.slug}`;
  const hub = gameHub(guide.game);
  const citations = guide.sources.map((source) => source.url);
  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        headline: guide.title,
        description: guide.description,
        datePublished: guide.publishedAt,
        dateModified: guide.reviewedAt,
        author: { "@type": "Organization", name: "RaidBench Editorial", url: "https://raidbench.com/about" },
        publisher: { "@type": "Organization", name: "RaidBench", url: "https://raidbench.com/" },
        mainEntityOfPage: canonical,
        about: { "@type": "VideoGame", name: guide.game },
        citation: citations
      },
      {
        "@type": "FAQPage",
        mainEntity: guide.faqs.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: { "@type": "Answer", text: item.answer }
        }))
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "RaidBench", item: "https://raidbench.com/" },
          { "@type": "ListItem", position: 2, name: guide.game, item: hub.publicUrl },
          { "@type": "ListItem", position: 3, name: guide.title, item: canonical }
        ]
      }
    ]
  };

  const conversion = guide.game === "Rust" ? `
        <article class="article-card conversion-card" data-live-commerce hidden>
          <p class="eyebrow">Verified Rust answers from $5</p>
          <h2>Need a source-checked answer for your exact route?</h2>
          <p>Start with one current raid-cost answer, or choose a complete multi-layer plan. Unsupported requests are not charged.</p>
          <div class="article-cta"><a class="primary-action" href="../customer?intent=instant&amp;utm_source=agent_guide&amp;utm_medium=internal&amp;utm_campaign=${escapeHtml(guide.slug)}" data-commerce-cta>Get a verified answer</a><a class="secondary-action" href="../rust-raid-plan">See prices and sample output</a></div>
        </article>` : "";

  return `<!doctype html>
${marker}
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(guide.title)} - RaidBench</title>
    <meta name="description" content="${escapeHtml(guide.description)}" />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="${canonical}" />
    <meta property="og:title" content="${escapeHtml(guide.title)}" />
    <meta property="og:description" content="${escapeHtml(guide.description)}" />
    <meta property="og:type" content="article" />
    <meta property="article:published_time" content="${escapeHtml(guide.publishedAt)}" />
    <meta property="article:modified_time" content="${escapeHtml(guide.reviewedAt)}" />
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
      <a class="header-action" href="../guides.html">Search Guides</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="${hub.href}">RaidBench / ${escapeHtml(hub.label)}</a>
      <section class="article-hero">
        <p class="eyebrow">Source-checked ${escapeHtml(guide.game)} decision guide</p>
        <h1>${escapeHtml(guide.title)}</h1>
        <p>${escapeHtml(guide.description)}</p>
        <div class="editorial-meta"><span>Reviewed ${escapeHtml(guide.reviewedAt)}</span><span>${escapeHtml(guide.status)}</span><a href="../about.html">Editorial standards</a></div>
      </section>
      <section class="article-grid">
        <article class="article-card">
          <h2>${escapeHtml(guide.problem)}</h2>
          <div class="answer-callout"><strong>Short answer</strong><p>${escapeHtml(guide.shortAnswer)}</p></div>
        </article>
${sectionsHtml(guide.sections)}
        <article class="article-card" id="checklist">
          <h2>Decision checklist</h2>
          ${listHtml(guide.checklist)}
        </article>
        <article class="article-card">
          <h2>Worked example</h2>
          <p>${escapeHtml(guide.example)}</p>
        </article>
        <article class="article-card">
          <h2>Common mistakes</h2>
          ${listHtml(guide.mistakes)}
        </article>
${faqHtml(guide.faqs)}
        <article class="article-card">
          <h2>Related guides</h2>
          <div class="article-cta">${relatedHtml(guide.related)}</div>
        </article>
${conversion}
        <article class="article-card source-list">
          <h2>Sources and review notes</h2>
          ${sourceHtml(guide.sources)}
          <p>${escapeHtml(guide.sourceNote)}</p>
          <p>Prepared with an automated research workflow and published only after evidence and policy checks.</p>
        </article>
      </section>
    </main>
    <footer class="footer"><p>RaidBench is an independent, unofficial player resource.</p><p class="footer-links"><a href="../updates.html">Patch Watch</a><a href="../about.html">Editorial standards</a><a href="../privacy.html">Privacy</a><a href="../terms.html">Terms</a><a href="../refund-policy.html">Refunds</a></p></footer>
    <script src="../config.js?v=20260717a"></script>
    <script src="../analytics.js?v=20260717a"></script>
    <script src="../guide-tools.js?v=20260809a"></script>
  </body>
</html>`;
}

const guides = JSON.parse(fs.readFileSync(dataPath, "utf8"));
if (!Array.isArray(guides)) throw new Error("content/agent-guides.json must be an array");
guides.forEach(validateGuide);

const slugs = new Set(guides.map((guide) => guide.slug));
if (slugs.size !== guides.length) throw new Error("content/agent-guides.json contains duplicate slugs");

fs.mkdirSync(pagesDir, { recursive: true });
for (const entry of fs.readdirSync(pagesDir, { withFileTypes: true })) {
  if (!entry.isFile() || !entry.name.endsWith(".html")) continue;
  const absolute = path.join(pagesDir, entry.name);
  if (fs.readFileSync(absolute, "utf8").includes(marker) && !slugs.has(entry.name.replace(/\.html$/, ""))) {
    fs.rmSync(absolute);
  }
}

for (const guide of guides) {
  fs.writeFileSync(path.join(pagesDir, `${guide.slug}.html`), pageHtml(guide));
}

console.log(`Generated ${guides.length} source-checked Agent guide page(s).`);
