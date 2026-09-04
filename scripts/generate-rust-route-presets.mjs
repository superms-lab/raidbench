import fs from "node:fs";
import path from "node:path";


const root = process.cwd();
const sourcePath = path.join(root, "content", "rust-route-presets.json");
const dataPath = path.join(root, "content", "rust-raid-data.json");
const outputJson = path.join(root, "rust-route-presets.json");
const outputHtml = path.join(root, "rust-route-presets.html");
const today = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());

const presets = JSON.parse(fs.readFileSync(sourcePath, "utf8"));
const raidData = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const validTargets = new Set(raidData.targets.map((target) => target.id));
const validMethods = new Set(["rockets", "c4", "satchels", "explosiveAmmo"]);
const seen = new Set();

for (const preset of presets) {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(preset.slug) || seen.has(preset.slug)) {
    throw new Error(`Invalid or duplicate route preset slug: ${preset.slug}`);
  }
  seen.add(preset.slug);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(preset.availableFrom)) {
    throw new Error(`Invalid release date for ${preset.slug}`);
  }
  if (!Array.isArray(preset.targets) || !preset.targets.length || preset.targets.length > 12) {
    throw new Error(`Invalid route rows for ${preset.slug}`);
  }
  for (const row of preset.targets) {
    if (!validTargets.has(row.targetId) || !validMethods.has(row.method) || !Number.isInteger(row.quantity) || row.quantity < 1 || row.quantity > 99) {
      throw new Error(`Invalid route row in ${preset.slug}`);
    }
  }
}

const released = presets.filter((preset) => preset.availableFrom <= today);
const encodeRoute = (targets) => targets.map((row) => `${row.targetId}~${row.quantity}~${row.method}`).join(",");
const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");

const publicData = {
  schemaVersion: "1.0.0",
  generatedAt: new Date().toISOString(),
  reviewedDataDate: raidData.verifiedAt || raidData.reviewedAt || today,
  scope: "Vanilla Rust PC planning examples. Recheck after relevant patches and custom-server changes.",
  count: released.length,
  presets: released.map((preset) => ({
    ...preset,
    calculatorUrl: `https://raidbench.com/?route=${encodeURIComponent(encodeRoute(preset.targets))}&utm_source=preset_library&utm_medium=owned_tool&utm_campaign=${preset.slug}#raid-calculator`,
  })),
};

const cards = publicData.presets.map((preset, index) => `
        <article class="article-card">
          <p class="eyebrow">Preset ${String(index + 1).padStart(2, "0")}</p>
          <h2>${escapeHtml(preset.title)}</h2>
          <p>${escapeHtml(preset.description)}</p>
          <ul>
            ${preset.targets.map((row) => `<li>${row.quantity} × ${escapeHtml(raidData.targets.find((target) => target.id === row.targetId)?.label || row.targetId)} using ${escapeHtml(row.method)}</li>`).join("\n            ")}
          </ul>
          <p><strong>Planning priority:</strong> ${escapeHtml(preset.priority)}</p>
          <div class="article-cta"><a class="primary-action" href="${escapeHtml(preset.calculatorUrl)}">Open this route</a></div>
        </article>`).join("");

const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Rust Raid Route Presets | RaidBench</title>
    <meta name="description" content="Open practical Rust raid-route presets in the RaidBench calculator, compare mixed door and wall paths, and download the reviewed preset data." />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="https://raidbench.com/rust-route-presets" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="stylesheet" href="./styles.css?v=20260903a" />
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="./index.html" aria-label="RaidBench home"><span class="brand-mark">RB</span><span>RaidBench</span></a>
      <nav class="nav" aria-label="Primary"><a href="./games.html">Games</a><a href="./guides.html">Guides</a><a href="./updates.html">Patch Watch</a><a href="./about.html">About</a></nav>
      <a class="header-action" href="./index.html#raid-calculator">Open Calculator</a>
    </header>
    <main class="article-main">
      <a class="breadcrumb" href="./index.html">RaidBench / Rust Route Presets</a>
      <section class="article-hero">
        <p class="eyebrow">Three new planning assets per week</p>
        <h1>Start with a route, then challenge the assumption.</h1>
        <p>Open a practical mixed-layer route in the free calculator, compare its current sulfur and placement requirements, and change any row to match what you actually scouted.</p>
        <div class="article-cta"><a class="primary-action" href="./rust-route-presets.json" data-track-event="raid_data_download" data-asset-format="json">Download preset JSON</a><a class="secondary-action" href="./rust-raid-costs.csv" data-track-event="raid_data_download" data-asset-format="csv">Download raid costs</a></div>
      </section>
      <section class="article-grid">${cards}</section>
    </main>
    <footer class="footer"><p>Examples use the current RaidBench vanilla Rust PC dataset. Hidden layers, geometry, counters, and custom rules remain player risks.</p><p class="footer-links"><a href="./about.html">Review standards</a><a href="./privacy.html">Privacy</a><a href="./terms.html">Terms</a></p></footer>
    <script src="./config.js?v=20260801b"></script>
    <script src="./analytics.js?v=20260902a"></script>
  </body>
</html>`;

fs.writeFileSync(outputJson, `${JSON.stringify(publicData, null, 2)}\n`);
fs.writeFileSync(outputHtml, html);
console.log(`Generated ${released.length} released Rust route presets for ${today}.`);
