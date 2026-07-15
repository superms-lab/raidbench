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
    id: "poe2-reddit-hot",
    type: "reddit-listing",
    url: "https://www.reddit.com/r/PathOfExile2/hot.json?limit=25",
    purpose: "Current high-engagement POE2 community questions and complaints",
  },
  {
    id: "poe2-reddit-build-help",
    type: "reddit-search",
    url: "https://www.reddit.com/r/PathOfExile2/search.json?q=build%20help&restrict_sr=1&sort=new&limit=25",
    purpose: "Recent build-help demand",
  },
  {
    id: "poe2-reddit-boss-help",
    type: "reddit-search",
    url: "https://www.reddit.com/r/PathOfExile2/search.json?q=boss%20help&restrict_sr=1&sort=new&limit=25",
    purpose: "Recent boss-prep demand",
  },
  {
    id: "poe2-reddit-loot-filter",
    type: "reddit-search",
    url: "https://www.reddit.com/r/PathOfExile2/search.json?q=loot%20filter&restrict_sr=1&sort=new&limit=25",
    purpose: "Recent loot-filter demand",
  },
  {
    id: "poe2-official-news",
    type: "html-title",
    url: "https://www.pathofexile.com/news",
    purpose: "Official patch and news context",
  },
  {
    id: "poe2-official-site",
    type: "html-title",
    url: "https://pathofexile2.com/",
    purpose: "Official product context",
  },
];

function titleFromHtml(html) {
  return html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]?.replace(/\s+/g, " ").trim() || "";
}

function extractRedditPosts(json) {
  const children = json?.data?.children || [];
  return children.map(({ data }) => ({
    title: data.title,
    score: data.score,
    comments: data.num_comments,
    createdUtc: data.created_utc,
    url: data.url,
    permalink: data.permalink ? `https://www.reddit.com${data.permalink}` : "",
  }));
}

fs.mkdirSync(outDir, { recursive: true });

const results = [];
for (const source of sources) {
  try {
    const response = await fetch(source.url, {
      headers: {
        "accept": source.type.startsWith("reddit") ? "application/json" : "text/html",
        "user-agent": "RaidBench content research bot; contact support@raidbench.com",
      },
      signal: AbortSignal.timeout(15000),
    });

    const contentType = response.headers.get("content-type") || "";
    const record = {
      ...source,
      ok: response.ok,
      status: response.status,
      fetchedAt: new Date().toISOString(),
      contentType,
    };

    if (source.type.startsWith("reddit") && contentType.includes("json")) {
      record.posts = extractRedditPosts(await response.json());
      record.postCount = record.posts.length;
    } else {
      const html = await response.text();
      record.title = titleFromHtml(html);
      record.bytesSampled = Math.min(html.length, 80000);
    }

    results.push(record);
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

const outputPath = path.join(outDir, `poe2-demand-${today}.json`);
fs.writeFileSync(outputPath, `${JSON.stringify(results, null, 2)}\n`);
console.log(`Wrote ${outputPath}`);
