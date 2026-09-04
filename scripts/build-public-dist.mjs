import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const output = process.env.RAIDBENCH_DIST_DIR || "/tmp/raidbench-pages";
const staticFiles = [
  "404.html",
  "47053f498731c73aed917414b9b81816.txt",
  "_headers",
  "_redirects",
  "_worker.js",
  "analytics.js",
  "app.js",
  "config.js",
  "customer.css",
  "customer.js",
  "embed.css",
  "embed.js",
  "embed/rust-raid-calculator.html",
  "favicon.svg",
  "feed.json",
  "feed.xml",
  "game-directory.js",
  "game-registry.json",
  "guide-tools.js",
  "guide-index.js",
  "raid-data.js",
  "rust-raid-costs.csv",
  "rust-raid-costs.json",
  "rust-route-presets.json",
  "route-state.js",
  "llms.txt",
  "multi-game-tool-engine.js",
  "multi-game-tools.js",
  "multigame-tools.json",
  "robots.txt",
  "site.webmanifest",
  "sitemap.xml",
  "styles.css",
  "widget-page.js"
];

function copyFile(relative) {
  const source = path.join(root, relative);
  if (!fs.existsSync(source)) throw new Error(`Missing public file: ${relative}`);
  const destination = path.join(output, relative);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.copyFileSync(source, destination);
}

function sitemapHtmlFiles() {
  const sitemap = fs.readFileSync(path.join(root, "sitemap.xml"), "utf8");
  return [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => {
    const pathname = new URL(match[1]).pathname;
    if (pathname === "/") return "index.html";
    if (pathname.endsWith("/")) return `${pathname.replace(/^\//, "")}index.html`;
    const relative = pathname.replace(/^\//, "");
    return path.posix.extname(relative) ? relative : `${relative}.html`;
  });
}

function registeredGameHubFiles() {
  const registry = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8"));
  return registry.games.map((game) => `${game.hubPath.replace(/^\//, "")}index.html`);
}

function localCandidates(relative, href) {
  const clean = href.split("#")[0].split("?")[0];
  if (!clean || /^(?:https?:|mailto:|tel:|javascript:|data:)/i.test(clean)) return [];
  const joined = clean.startsWith("/") ? clean.slice(1) : path.posix.join(path.posix.dirname(relative), clean);
  const normalized = path.posix.normalize(joined);
  if (path.posix.extname(normalized)) return [normalized];
  return [normalized, `${normalized}.html`, path.posix.join(normalized, "index.html")];
}

fs.rmSync(output, { recursive: true, force: true });
fs.mkdirSync(output, { recursive: true });

const publicHtmlFiles = [...new Set([...sitemapHtmlFiles(), ...registeredGameHubFiles()])];
publicHtmlFiles.push("customer.html");
for (const relative of [...staticFiles, ...publicHtmlFiles]) copyFile(relative);

const assets = path.join(root, "assets");
if (fs.existsSync(assets)) fs.cpSync(assets, path.join(output, "assets"), { recursive: true });
const downloads = path.join(root, "downloads");
if (fs.existsSync(downloads)) fs.cpSync(downloads, path.join(output, "downloads"), { recursive: true });

for (const relative of publicHtmlFiles) {
  const html = fs.readFileSync(path.join(output, relative), "utf8");
  for (const match of html.matchAll(/\bhref=["']([^"']+)["']/gi)) {
    const candidates = localCandidates(relative, match[1]);
    if (candidates.length && !candidates.some((candidate) => fs.existsSync(path.join(output, candidate)))) {
      throw new Error(`${relative} links to a file excluded from the public package: ${match[1]}`);
    }
  }
}

const copiedHtml = publicHtmlFiles.length;
console.log(`Built ${output} with ${copiedHtml} public HTML files and approved static assets.`);
