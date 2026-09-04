import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const host = "raidbench.com";
const key = "47053f498731c73aed917414b9b81816";
const keyLocation = `https://${host}/${key}.txt`;
const dryRun = process.argv.includes("--dry-run");
const requestedUrls = process.argv.slice(2).filter((value) => !value.startsWith("--"));

function sitemapEntries() {
  const xml = fs.readFileSync(path.join(root, "sitemap.xml"), "utf8");
  return [...xml.matchAll(/<url>\s*<loc>(.*?)<\/loc>\s*<lastmod>(.*?)<\/lastmod>[\s\S]*?<\/url>/g)]
    .map((match) => ({ url: match[1], lastmod: match[2] }));
}

const entries = sitemapEntries();
const newestDate = entries.map((entry) => entry.lastmod).sort().at(-1);
const urls = requestedUrls.length
  ? requestedUrls
  : entries.filter((entry) => entry.lastmod === newestDate).map((entry) => entry.url);

if (!urls.length) throw new Error("No URLs selected for IndexNow submission.");
if (urls.length > 10000) throw new Error("IndexNow accepts at most 10,000 URLs per request.");
for (const value of urls) {
  const url = new URL(value);
  if (url.protocol !== "https:" || url.hostname !== host) {
    throw new Error(`Refusing to submit an external URL: ${value}`);
  }
}

const payload = { host, key, keyLocation, urlList: urls };
if (dryRun) {
  console.log(JSON.stringify({ newestDate, ...payload }, null, 2));
  process.exit(0);
}

const response = await fetch("https://api.indexnow.org/indexnow", {
  method: "POST",
  headers: { "Content-Type": "application/json; charset=utf-8" },
  body: JSON.stringify(payload),
});

if (![200, 202].includes(response.status)) {
  throw new Error(`IndexNow rejected the submission with HTTP ${response.status}: ${await response.text()}`);
}

console.log(`IndexNow accepted ${urls.length} RaidBench URL(s) with HTTP ${response.status}.`);
