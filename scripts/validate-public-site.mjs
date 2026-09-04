import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const pagesDir = path.join(root, "pages");
const hiddenPattern = /(owner-[a-z-]+-zh|premium|paid-product|audit-product|customer)/i;
const forbiddenPublicCopy = [
  /validation mode/i,
  /payments? (?:are|is) not enabled/i,
  /paid drafts?/i,
  /future audit products?/i,
  /designed for search traffic/i,
  /MVP demo/i,
  /get raid prep pack/i,
  /paid worksheet angle/i
];

function htmlFiles() {
  const rootFiles = fs
    .readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".html"))
    .map((entry) => entry.name);
  function walk(dir, prefix) {
    if (!fs.existsSync(dir)) return [];
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const relative = path.posix.join(prefix, entry.name);
      const absolute = path.join(dir, entry.name);
      if (entry.isDirectory()) return walk(absolute, relative);
      return entry.isFile() && entry.name.endsWith(".html") ? [relative] : [];
    });
  }
  return [...rootFiles, ...walk(pagesDir, "pages"), ...walk(path.join(root, "games"), "games"), ...walk(path.join(root, "tools"), "tools")].sort();
}

function firstMatch(html, expression) {
  return html.match(expression)?.[1]?.trim() || "";
}

function countMatches(html, expression) {
  return [...html.matchAll(expression)].length;
}

function isNoindex(html) {
  return /<meta\s+name=["']robots["']\s+content=["'][^"']*noindex/i.test(html);
}

function publicUrlFor(relative) {
  if (relative === "index.html") return "https://raidbench.com/";
  if (relative.endsWith("/index.html")) return `https://raidbench.com/${relative.slice(0, -"index.html".length)}`;
  return `https://raidbench.com/${relative.replace(/\.html$/, "")}`;
}

function publicFileFor(pathname) {
  if (pathname === "/") return "index.html";
  if (pathname.endsWith("/")) return `${pathname.replace(/^\//, "")}index.html`;
  const relative = pathname.replace(/^\//, "");
  return path.posix.extname(relative) ? relative : `${relative}.html`;
}

function resolveLocalLink(relative, href) {
  const clean = href.split("#")[0].split("?")[0];
  if (!clean) return null;
  const base = clean.startsWith("/") ? clean.slice(1) : path.posix.join(path.posix.dirname(relative), clean);
  const normalized = path.posix.normalize(base);
  if (normalized.startsWith("../")) return { error: `escapes public root: ${href}` };
  const candidates = normalized.endsWith("/")
    ? [path.posix.join(normalized, "index.html")]
    : path.posix.extname(normalized)
      ? [normalized]
      : [normalized, `${normalized}.html`, path.posix.join(normalized, "index.html")];
  return { candidates };
}

const files = htmlFiles();
const errors = [];
const warnings = [];
const indexable = [];
const canonicalOwners = new Map();

for (const relative of files) {
  const html = fs.readFileSync(path.join(root, relative), "utf8");
  const hidden = hiddenPattern.test(relative);
  const noindex = isNoindex(html);
  const title = firstMatch(html, /<title>([\s\S]*?)<\/title>/i);
  const description = firstMatch(html, /<meta\s+name=["']description["']\s+content=["']([^"']*)["']/i);
  const canonical = firstMatch(html, /<link\s+rel=["']canonical["']\s+href=["']([^"']+)["']/i);
  const h1Count = countMatches(html, /<h1\b[^>]*>/gi);

  if (hidden) {
    if (!noindex) errors.push(`${relative}: hidden or monetization page must be noindex`);
    continue;
  }

  if (!title) errors.push(`${relative}: missing title`);
  if (!description) errors.push(`${relative}: missing meta description`);
  if (!canonical) errors.push(`${relative}: missing canonical URL`);
  if (h1Count !== 1) errors.push(`${relative}: expected one h1, found ${h1Count}`);
  if (!/<link\s+rel=["']icon["']/i.test(html)) errors.push(`${relative}: missing favicon link`);
  if (!/<link\s+rel=["']stylesheet["']/i.test(html)) errors.push(`${relative}: missing stylesheet`);
  if (!noindex) {
    indexable.push(relative);
    if (canonical) {
      const expectedCanonical = publicUrlFor(relative);
      if (canonical !== expectedCanonical) {
        errors.push(`${relative}: canonical must match final Cloudflare URL (${expectedCanonical})`);
      }
      const owner = canonicalOwners.get(canonical);
      if (owner) errors.push(`${relative}: duplicate canonical also used by ${owner}`);
      canonicalOwners.set(canonical, relative);
    }
    for (const expression of forbiddenPublicCopy) {
      if (expression.test(html)) errors.push(`${relative}: contains internal or prelaunch copy (${expression})`);
    }
  }

  for (const match of html.matchAll(/<script\s+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    try {
      JSON.parse(match[1]);
    } catch (error) {
      errors.push(`${relative}: invalid JSON-LD (${error.message})`);
    }
  }

  for (const match of html.matchAll(/\bhref=["']([^"']+)["']/gi)) {
    const href = match[1];
    if (!noindex && /(premium|paid-product|audit-product)/i.test(href)) {
      errors.push(`${relative}: public page links to a hidden monetization route (${href})`);
    }
    if (/^(?:https?:|mailto:|tel:|javascript:|data:|#)/i.test(href)) continue;
    const resolved = resolveLocalLink(relative, href);
    if (!resolved) continue;
    if (resolved.error) {
      errors.push(`${relative}: ${resolved.error}`);
      continue;
    }
    if (!resolved.candidates.some((candidate) => fs.existsSync(path.join(root, candidate)))) {
      errors.push(`${relative}: broken internal link ${href}`);
    }
  }
}

const sitemapPath = path.join(root, "sitemap.xml");
if (!fs.existsSync(sitemapPath)) {
  errors.push("sitemap.xml: missing");
} else {
  const sitemap = fs.readFileSync(sitemapPath, "utf8");
  const locations = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]);
  const locationSet = new Set(locations);
  if (locationSet.size !== locations.length) errors.push("sitemap.xml: duplicate URLs found");

  for (const relative of indexable) {
    const expected = publicUrlFor(relative);
    if (!locationSet.has(expected)) errors.push(`${relative}: indexable page missing from sitemap`);
  }

  for (const location of locations) {
    const pathname = new URL(location).pathname;
    const relative = publicFileFor(pathname);
    const absolute = path.join(root, relative);
    if (!fs.existsSync(absolute)) {
      errors.push(`sitemap.xml: URL has no public file (${location})`);
      continue;
    }
    const html = fs.readFileSync(absolute, "utf8");
    if (isNoindex(html) || hiddenPattern.test(relative)) errors.push(`sitemap.xml: includes hidden or noindex page (${location})`);
  }
}

const indexedGuides = indexable.filter((relative) => relative.startsWith("pages/")).length;
const indexedTools = indexable.filter((relative) => relative.startsWith("tools/")).length;
if (indexedGuides < 20) warnings.push(`Only ${indexedGuides} indexable guide pages are ready.`);

console.log(`Checked ${files.length} HTML files.`);
console.log(`Indexable public pages: ${indexable.length}; indexable guide/update pages: ${indexedGuides}; interactive tools: ${indexedTools}.`);
for (const warning of warnings) console.warn(`WARN: ${warning}`);
if (errors.length) {
  for (const error of errors) console.error(`ERROR: ${error}`);
  console.error(`Public-site validation failed with ${errors.length} error(s).`);
  process.exit(1);
}
console.log("Public-site validation passed.");
