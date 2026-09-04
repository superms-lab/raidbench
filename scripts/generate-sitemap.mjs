import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const defaultLastmod = "2026-07-17";
const patchWatch = JSON.parse(fs.readFileSync(path.join(root, "content", "patch-watch.json"), "utf8"));
const currentSiteLastmod = patchWatch.map((item) => item.reviewedAt).sort().at(-1) || defaultLastmod;
const hiddenPattern = /(owner-review-zh|premium|paid-product|audit-product)/i;
const skippedDirectories = new Set([
  ".git",
  ".github",
  "cloud",
  "content",
  "local",
  "node_modules",
  "operations",
  "private-data",
  "schemas",
  "scripts",
  "templates",
  "tests"
]);

function walkHtml(dir, prefix = "") {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const relative = path.posix.join(prefix, entry.name);
    const absolute = path.join(dir, entry.name);
    if (entry.isDirectory()) return skippedDirectories.has(entry.name) ? [] : walkHtml(absolute, relative);
    if (!entry.isFile() || !entry.name.endsWith(".html")) return [];
    return [relative];
  });
}

function xmlEscape(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function priorityFor(relative) {
  if (relative === "index.html") return "1.0";
  if (["updates.html", "guides.html", "games.html", "tools.html"].includes(relative)) return "0.9";
  if (relative.startsWith("games/") && relative.endsWith("/index.html")) return "0.8";
  if (relative.startsWith("tools/") && relative.endsWith("/index.html")) return "0.8";
  if (["poe2.html", "palworld.html"].includes(relative)) return "0.5";
  if (relative.startsWith("pages/")) return "0.7";
  if (["privacy.html", "terms.html", "refund-policy.html", "about.html"].includes(relative)) return "0.4";
  return "0.6";
}

function lastmodFor(relative) {
  const html = fs.readFileSync(path.join(root, relative), "utf8");
  const articleDate = html.match(/<meta\s+property="article:modified_time"\s+content="(\d{4}-\d{2}-\d{2})"/i)?.[1];
  if (articleDate) return articleDate;
  if (["index.html", "guides.html", "games.html", "tools.html", "updates.html", "rust-raid-plan.html"].includes(relative) || relative.startsWith("games/") || relative.startsWith("tools/")) return currentSiteLastmod;
  return defaultLastmod;
}

function publicUrlFor(relative) {
  if (relative === "index.html") return "https://raidbench.com/";
  if (relative.endsWith("/index.html")) return `https://raidbench.com/${relative.slice(0, -"index.html".length)}`;
  return `https://raidbench.com/${relative.replace(/\.html$/, "")}`;
}

const publicFiles = walkHtml(root)
  .filter((relative) => !hiddenPattern.test(relative))
  .filter((relative) => {
    const html = fs.readFileSync(path.join(root, relative), "utf8");
    return !/<meta\s+name="robots"\s+content="[^"]*noindex/i.test(html);
  })
  .sort((a, b) => {
    if (a === "index.html") return -1;
    if (b === "index.html") return 1;
    return a.localeCompare(b);
  });

const blocks = publicFiles.map((relative) => {
  const url = publicUrlFor(relative);
  const changefreq = relative.startsWith("pages/") || relative.startsWith("games/") || relative.startsWith("tools/") || ["updates.html", "guides.html", "games.html", "tools.html"].includes(relative) ? "weekly" : "monthly";
  return `  <url>\n    <loc>${xmlEscape(url)}</loc>\n    <lastmod>${lastmodFor(relative)}</lastmod>\n    <changefreq>${changefreq}</changefreq>\n    <priority>${priorityFor(relative)}</priority>\n  </url>`;
});

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${blocks.join("\n")}\n</urlset>\n`;
fs.writeFileSync(path.join(root, "sitemap.xml"), sitemap);
console.log(`Generated sitemap.xml with ${publicFiles.length} public URLs.`);
