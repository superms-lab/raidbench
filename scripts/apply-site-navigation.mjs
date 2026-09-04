import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const skipped = /^(?:owner-|customer|premium)/i;
const productCatalog = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-products.json"), "utf8"));
const palworldProduct = productCatalog.products.find((product) => (
  product.id === "palworld-base-progression-review" && product.status === "ready_live"
));

function walkHtml(dir, prefix = "") {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const relative = path.posix.join(prefix, entry.name);
    const absolute = path.join(dir, entry.name);
    if (entry.isDirectory()) return walkHtml(absolute, relative);
    return entry.isFile() && entry.name.endsWith(".html") ? [relative] : [];
  });
}

function currentSection(relative) {
  if (relative === "games.html" || relative.startsWith("games/")) return "games";
  if (relative === "guides.html" || relative.startsWith("pages/")) return "guides";
  if (relative === "tools.html" || relative.startsWith("tools/")) return "tools";
  if (relative === "updates.html") return "updates";
  if (relative === "about.html") return "about";
  return "";
}

function navigation(relative) {
  const depth = relative.split("/").length - 1;
  const prefix = depth ? "../".repeat(depth) : "./";
  const current = currentSection(relative);
  const links = [
    ["games", "Games", `${prefix}games.html`],
    ["guides", "Guides", `${prefix}guides.html`],
    ["tools", "Tools", `${prefix}tools.html`],
    ["updates", "Patch Watch", `${prefix}updates.html`],
    ["about", "About", `${prefix}about.html`],
  ];
  return `<nav class="nav" aria-label="Primary">${links
    .map(([id, label, href]) => `<a href="${href}"${id === current ? ' aria-current="page"' : ""}>${label}</a>`)
    .join("")}</nav>`;
}

function applyPalworldCommerce(relative, html) {
  const start = "<!-- PALWORLD_COMMERCE_START -->";
  const end = "<!-- PALWORLD_COMMERCE_END -->";
  let next = html.replace(new RegExp(`\\s*${start}[\\s\\S]*?${end}`), "");
  const eligible = /^pages\/palworld-.*\.html$/.test(relative)
    && relative !== "pages/palworld-paid-product-menu.html"
    && palworldProduct;
  if (!eligible) return next;
  const band = `
      ${start}
      <section class="guide-paid-review-band" aria-label="Personalized Palworld review">
        <div><p class="eyebrow">When the free checklist meets your actual save</p><h2>Bring one stubborn bottleneck. Leave with one testable next move.</h2><p>Include your version, server type, observed state, and goal. The ${palworldProduct.credits}-credit review separates observation from assumption, passes independent QA, and arrives inside your account.</p></div>
        <div><strong>${palworldProduct.credits} credits</strong><small>Reserved at submission. Charged only after QA approval; otherwise 0 credits.</small><a class="primary-action" href="../customer.html?intent=palworld" data-commerce-cta data-track-event="palworld_review_open">Review my bottleneck</a></div>
      </section>
      ${end}`;
  return next.replace(/\s*<\/main>/, `${band}\n    </main>`);
}

const rootHtml = fs.readdirSync(root, { withFileTypes: true })
  .filter((entry) => entry.isFile() && entry.name.endsWith(".html"))
  .map((entry) => entry.name);
const files = [...rootHtml, ...walkHtml(path.join(root, "pages"), "pages"), ...walkHtml(path.join(root, "games"), "games")]
  .filter((relative) => relative !== "index.html" && !skipped.test(path.posix.basename(relative)));

let updated = 0;
for (const relative of files) {
  const file = path.join(root, relative);
  const html = fs.readFileSync(file, "utf8");
  if (!/<nav class="nav" aria-label="Primary">[\s\S]*?<\/nav>/.test(html)) continue;
  let next = html
    .replace(/<nav class="nav" aria-label="Primary">[\s\S]*?<\/nav>/, navigation(relative))
    .replaceAll('href="./poe2.html"', 'href="./games/poe2/"')
    .replaceAll('href="./palworld.html"', 'href="./games/palworld/"')
    .replaceAll('href="../poe2.html"', 'href="../games/poe2/"')
    .replaceAll('href="../palworld.html"', 'href="../games/palworld/"');
  next = applyPalworldCommerce(relative, next);
  if (next !== html) {
    fs.writeFileSync(file, next);
    updated += 1;
  }
}

console.log(`Applied the shared game navigation to ${updated} HTML file(s).`);
