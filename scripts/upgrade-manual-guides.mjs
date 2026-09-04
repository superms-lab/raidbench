import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const guides = JSON.parse(fs.readFileSync(path.join(root, "content", "manual-guides.json"), "utf8"));
const reviewedAt = "2026-07-17";
const publishedAt = "2026-07-15";
const marker = '<meta name="raidbench-editorial-upgrade" content="20260717" />';

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function gameDetails(game) {
  if (game === "POE2") {
    return {
      name: "Path of Exile 2",
      hub: "../poe2.html",
      hubLabel: "POE2 Lab",
      sourceUrl: "https://www.pathofexile.com/forum/view-forum/2212",
      sourceLabel: "Official POE2 patch notes",
      publisher: "Grinding Gear Games"
    };
  }
  return {
    name: "Rust",
    hub: "../index.html#raid-calculator",
    hubLabel: "Open Calculator",
    sourceUrl: "https://rust.facepunch.com/changes/",
    sourceLabel: "Official Rust changes",
    publisher: "Facepunch Studios"
  };
}

function addRustRevenuePath(html, guide) {
  if (guide.game !== "Rust") return html;
  const revenueMarker = 'data-revenue-path="rust-v1"';
  if (!html.includes(revenueMarker)) {
    const card = `        <article class="article-card conversion-card" data-live-commerce hidden ${revenueMarker}>
          <p class="eyebrow">Verified Rust answers from $5</p>
          <h2>Need this checked for your exact target and method?</h2>
          <p>The $5 starter pack covers two personalized route checks. Choose the full raid plan when you need multiple layers, a resource buffer, and a clear stop condition. Unsupported requests are not charged.</p>
          <div class="article-cta"><a class="primary-action" href="../customer?intent=instant&amp;utm_source=manual_guide&amp;utm_medium=internal&amp;utm_campaign=${escapeHtml(guide.slug)}" data-commerce-cta>Get a verified answer</a><a class="secondary-action" href="../rust-raid-plan">See prices and sample output</a></div>
        </article>
`;
    html = html.replace(/(\s*<article class="article-card source-list">)/, `\n${card}$1`);
  }
  if (!html.includes("../guide-tools.js")) {
    html = html.replace("  </body>", '    <script src="../guide-tools.js?v=20260820a"></script>\n  </body>');
  }
  return html;
}

function addRustSocialPreview(html, guide) {
  if (guide.game !== "Rust" || html.includes('property="og:image"')) return html;
  return html.replace(
    '<meta property="og:type" content="article" />',
    '<meta property="og:type" content="article" />\n    <meta property="og:image" content="https://raidbench.com/assets/raidbench-calculator-share.png" />\n    <meta property="og:image:alt" content="RaidBench Rust raid cost calculator with sulfur and gunpowder totals" />\n    <meta name="twitter:card" content="summary_large_image" />',
  );
}

for (const guide of guides) {
  const relative = `pages/${guide.slug}.html`;
  const absolute = path.join(root, relative);
  if (!fs.existsSync(absolute)) throw new Error(`Manual guide is missing: ${relative}`);
  let html = fs.readFileSync(absolute, "utf8");
  const cleanCanonical = `https://raidbench.com/${relative.replace(/\.html$/, "")}`;
  html = html.replaceAll(`https://raidbench.com/${relative}`, cleanCanonical);
  html = html.replaceAll("https://raidbench.com/about.html", "https://raidbench.com/about");
  html = html
    .replaceAll('../config.js"', '../config.js?v=20260717a"')
    .replaceAll('../analytics.js"', '../analytics.js?v=20260717a"');
  html = addRustSocialPreview(html, guide);
  if (html.includes(marker)) {
    html = addRustRevenuePath(html, guide);
    fs.writeFileSync(absolute, html);
    continue;
  }

  const details = gameDetails(guide.game);
  const canonical = cleanCanonical;
  const schema = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Article",
    headline: guide.title,
    description: guide.description,
    datePublished: publishedAt,
    dateModified: reviewedAt,
    author: { "@type": "Organization", name: "RaidBench Editorial", url: "https://raidbench.com/about" },
    publisher: { "@type": "Organization", name: "RaidBench", url: "https://raidbench.com/" },
    mainEntityOfPage: canonical,
    about: { "@type": "VideoGame", name: details.name },
    citation: [details.sourceUrl]
  }).replaceAll("<", "\\u003c");

  html = html.replace(/<link rel="stylesheet" href="\.\.\/styles\.css\?v=[^"]+" \/>/, '<link rel="stylesheet" href="../styles.css?v=20260717a" />');
  html = html.replace(
    "  </head>",
    `    ${marker}\n    <meta property="og:title" content="${escapeHtml(guide.title)}" />\n    <meta property="og:description" content="${escapeHtml(guide.description)}" />\n    <meta property="og:type" content="article" />\n    <meta property="article:published_time" content="${publishedAt}" />\n    <meta property="article:modified_time" content="${reviewedAt}" />\n    <script type="application/ld+json">${schema}</script>\n  </head>`,
  );

  html = html.replace(
    /<header class="site-header">[\s\S]*?<\/header>/,
    `<header class="site-header">\n      <a class="brand" href="../index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>\n      <nav class="nav" aria-label="Primary"><a href="../index.html#tools">Rust Tools</a><a href="../guides.html">Guides</a><a href="../updates.html">Patch Watch</a><a href="../palworld.html">Palworld</a><a href="../poe2.html">POE2</a></nav>\n      <a class="header-action" href="${details.hub}">${details.hubLabel}</a>\n    </header>`,
  );

  html = html.replace(
    /(<div class="article-cta"[\s\S]*?<\/div>)/,
    `$1\n        <div class="editorial-meta"><span>Reviewed ${reviewedAt}</span><span>Patch-sensitive guidance</span><a href="../about.html">Editorial standards</a></div>`,
  );

  html = html.replace(/(<table>[\s\S]*?<\/table>)/g, '<div class="table-scroll" tabindex="0" role="region" aria-label="Guide reference table">$1</div>');

  const reviewCard = `\n        <article class="article-card source-list">\n          <h2>Patch and editorial status</h2>\n          <p>Reviewed ${reviewedAt}. Check <a href="${details.sourceUrl}" target="_blank" rel="noopener noreferrer">${details.sourceLabel}</a> after balance, progression, item, building, or combat changes that affect this decision.</p>\n          <p><a href="../about.html">See how RaidBench selects sources and handles corrections.</a></p>\n        </article>`;
  html = html.replace(/\s*<\/section>\s*<\/main>/, `${reviewCard}\n      </section>\n    </main>`);

  html = html.replace(
    /<footer class="footer">[\s\S]*?<\/footer>/,
    `<footer class="footer"><p>RaidBench is independent and is not affiliated with or endorsed by ${details.publisher}.</p><p class="footer-links"><a href="../updates.html">Patch Watch</a><a href="../about.html">Editorial standards</a><a href="../privacy.html">Privacy</a><a href="../terms.html">Terms</a><a href="../refund-policy.html">Refunds</a></p></footer>`,
  );

  html = addRustRevenuePath(html, guide);

  fs.writeFileSync(absolute, html);
}

console.log(`Upgraded ${guides.length} manual guide pages with current navigation, review notes, sources, and Article schema.`);
