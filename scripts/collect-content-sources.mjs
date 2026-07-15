import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const outDir = path.join(root, "content", "inbox");
const today = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());
const sources = [
  {
    id: "rust-official",
    track: "Rust",
    url: "https://rust.facepunch.com/news",
    purpose: "Official Rust news and patch context",
  },
  {
    id: "rust-commits",
    track: "Rust",
    url: "https://commits.facepunch.com/r/rust_reboot",
    purpose: "Official Rust commit stream for change awareness",
  },
  {
    id: "poe2-official",
    track: "POE2",
    url: "https://pathofexile2.com/",
    purpose: "Official Path of Exile 2 product and update context",
  },
  {
    id: "poe-news",
    track: "POE2",
    url: "https://www.pathofexile.com/news",
    purpose: "Official Path of Exile news and patch context",
  },
  {
    id: "poe2-steam",
    track: "POE2",
    url: "https://store.steampowered.com/app/2694490/Path_of_Exile_2/",
    purpose: "Steam store positioning and player-facing metadata",
  },
];

function extractTitle(html) {
  const match = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return match ? match[1].replace(/\s+/g, " ").trim() : "";
}

function extractDescription(html) {
  const match = html.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']/i);
  return match ? match[1].replace(/\s+/g, " ").trim() : "";
}

fs.mkdirSync(outDir, { recursive: true });

const results = [];
for (const source of sources) {
  try {
    const response = await fetch(source.url, {
      headers: {
        "user-agent": "RaidBench content research bot; contact via site owner",
      },
    });
    const html = await response.text();
    results.push({
      ...source,
      ok: response.ok,
      status: response.status,
      fetchedAt: new Date().toISOString(),
      title: extractTitle(html),
      description: extractDescription(html),
      bytesSampled: Math.min(html.length, 120000),
    });
  } catch (error) {
    results.push({
      ...source,
      ok: false,
      status: 0,
      fetchedAt: new Date().toISOString(),
      error: String(error.message || error),
    });
  }
}

const outputPath = path.join(outDir, `source-snapshot-${today}.json`);
fs.writeFileSync(outputPath, `${JSON.stringify(results, null, 2)}\n`);
console.log(`Wrote ${outputPath}`);
