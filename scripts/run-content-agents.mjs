import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dbPath = process.env.RAIDBENCH_LOCAL_DB_PATH
  ? path.resolve(process.env.RAIDBENCH_LOCAL_DB_PATH)
  : path.join(root, "local", "raidbench.local.db");
const inboxDir = process.env.RAIDBENCH_SCOUT_INBOX_DIR
  ? path.resolve(process.env.RAIDBENCH_SCOUT_INBOX_DIR)
  : path.join(root, "content", "inbox");
const operationsDir = process.env.RAIDBENCH_SCOUT_OPERATIONS_DIR
  ? path.resolve(process.env.RAIDBENCH_SCOUT_OPERATIONS_DIR)
  : path.join(root, "operations");
const runAt = new Date();
const forceRun = process.argv.includes("--force");
const cadenceToleranceMs = Math.max(
  0,
  Number(process.env.RAIDBENCH_SCOUT_CADENCE_TOLERANCE_MINUTES || "10"),
) * 60 * 1000;
const day = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(runAt);
const runId = `run_${runAt.toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
const lastFetchByHost = new Map();

const topicRules = [
  ["patch", /patch|hotfix|update|balance|nerf|buff|changed|fixed/i, 4, 3, true],
  ["build_help", /build|starter|class|skill|passive|respec|gear/i, 5, 5, true],
  ["boss_help", /boss|one-shot|oneshot|die|defense|survive|attempt/i, 5, 4, true],
  ["loot_value", /loot|filter|item|price|value|sell|craft|stash/i, 4, 5, true],
  ["currency_route", /currency|farm|profit|route|mapping|endgame|trade/i, 4, 5, true],
  ["raid_cost", /\braid\b|rocket|c4|satchel|explosive|sulfur|garage|door|\bwall\b/i, 5, 5, true],
  ["upkeep", /upkeep|decay|tool cupboard|tc|base/i, 4, 4, true],
  ["base_automation", /base|automation|resource|breeding|worker|production/i, 4, 4, true],
  ["quest_route", /quest|mission|extract|extraction|trader/i, 5, 5, true],
  ["loadout", /loadout|weapon|ammo|armor|armour|attachment|modding/i, 5, 5, true],
  ["strategy", /operator|hero|counter|lineup|utility|lane|rotation|position|objective/i, 4, 4, true],
  ["settings", /settings|sensitivity|server|sandbox|configuration/i, 4, 4, true],
  ["progression", /progress|returning player|beginner|new player|what next|priority/i, 5, 4, true]
];

const lowIntentPattern = /wallpaper|microtransaction|cosmetic|bundle|trailer|showcase|sale|soundtrack|contest|giveaway/i;
const patchExcerptPattern = /\b(?:patch|hotfix|changelog|bug fixes?|version update|latest update)\b|this month(?:'s|s)? update/i;

function sqlValue(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "number") return String(value);
  return `'${String(value).replaceAll("'", "''")}'`;
}

function runSql(sql) {
  execFileSync("sqlite3", [dbPath], { input: sql, stdio: ["pipe", "pipe", "pipe"] });
}

function querySql(sql) {
  return execFileSync("sqlite3", ["-json", dbPath, sql], { encoding: "utf8" }).trim();
}

function hash(value) {
  return crypto.createHash("sha1").update(value).digest("hex");
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function pacedFetch(source) {
  const host = new URL(source.url).hostname;
  const minimumGapMs = host.includes("steampowered.com") ? 900 : 200;
  const elapsed = Date.now() - Number(lastFetchByHost.get(host) || 0);
  if (elapsed < minimumGapMs) await sleep(minimumGapMs - elapsed);
  let lastError;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetch(source.url, {
        headers: { accept: "*/*", "user-agent": "RaidBench content research bot; public pages only; support@raidbench.com" },
        signal: AbortSignal.timeout(18000),
      });
      lastFetchByHost.set(host, Date.now());
      if ((response.status === 429 || response.status >= 500) && attempt === 0) {
        await response.body?.cancel();
        await sleep(1800);
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      lastFetchByHost.set(host, Date.now());
      if (attempt === 0) {
        await sleep(1800);
        continue;
      }
    }
  }
  throw lastError || new Error(`Fetch failed for ${source.id}`);
}

function cadenceMilliseconds(cadence) {
  const match = String(cadence || "").match(/^(\d+)h$/i);
  return match ? Number(match[1]) * 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
}

function sourceIsDue(source) {
  if (forceRun || !source.lastFetchedAt) return true;
  const lastFetchedAt = Date.parse(source.lastFetchedAt);
  const cadenceMs = cadenceMilliseconds(source.cadence);
  const toleranceMs = Math.min(cadenceToleranceMs, Math.floor(cadenceMs / 4));
  return !Number.isFinite(lastFetchedAt) || runAt.getTime() - lastFetchedAt >= cadenceMs - toleranceMs;
}

function titleFromHtml(html) {
  return html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]?.replace(/\s+/g, " ").trim() || "";
}

function stripTags(html) {
  return html.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function xmlTagText(block, tagName) {
  const match = block.match(new RegExp(`<${tagName}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tagName}>`, "i"));
  return (match?.[1] || "")
    .replace(/^<!\[CDATA\[/, "")
    .replace(/\]\]>$/, "")
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replace(/\s+/g, " ")
    .trim();
}

function extractRssItems(xml, source) {
  const freshnessCutoff = runAt.getTime() - Number(source.freshnessHours || 168) * 60 * 60 * 1000;
  return [...xml.matchAll(/<item>([\s\S]*?)<\/item>/gi)].slice(0, 15).map((match) => {
    const item = match[1];
    const rawPublishedAt = xmlTagText(item, "pubDate");
    const publishedTimestamp = Date.parse(rawPublishedAt);
    const description = xmlTagText(item, "description") || xmlTagText(item, "content:encoded");
    return {
      sourceId: source.id,
      game: source.game,
      title: xmlTagText(item, "title"),
      url: xmlTagText(item, "link") || source.url,
      publishedAt: Number.isFinite(publishedTimestamp) ? new Date(publishedTimestamp).toISOString() : "",
      excerpt: stripTags(description).slice(0, 8000)
    };
  }).filter((item) => item.title && (!item.publishedAt || Date.parse(item.publishedAt) >= freshnessCutoff));
}

function classifySignal(title) {
  if (lowIntentPattern.test(title)) {
    return { topic: "official_marketing", painScore: 1, commercialScore: 1, patchSensitive: false };
  }
  const matched = topicRules.find(([, pattern]) => pattern.test(title));
  if (!matched) return { topic: "general_research", painScore: 2, commercialScore: 1, patchSensitive: false };
  return {
    topic: matched[0],
    painScore: matched[2],
    commercialScore: matched[3],
    patchSensitive: matched[4]
  };
}

function makeSignal(source, title, url, evidence = {}) {
  const titleClassification = classifySignal(title);
  const classification = titleClassification.topic === "general_research" && patchExcerptPattern.test(evidence.excerpt || "")
    ? { topic: "patch", painScore: 4, commercialScore: 3, patchSensitive: true }
    : titleClassification;
  return {
    id: `sig_${hash(`${source.id}:${title}:${url}`).slice(0, 18)}`,
    runId,
    sourceId: source.id,
    gameId: source.gameId,
    game: source.game,
    title,
    url,
    evidence,
    ...classification
  };
}

if (!fs.existsSync(dbPath)) {
  execFileSync("node", ["scripts/init-local-db.mjs"], { cwd: root, stdio: "inherit" });
}
execFileSync("node", ["scripts/sync-source-registry.mjs"], {
  cwd: root,
  env: { ...process.env, RAIDBENCH_LOCAL_DB_PATH: dbPath },
  stdio: "inherit",
});

fs.mkdirSync(inboxDir, { recursive: true });
fs.mkdirSync(operationsDir, { recursive: true });

const sources = JSON.parse(querySql(`
  select
    source.id,
    source.game,
    source.source_type as sourceType,
    source.url,
    source.cadence,
    profile.game_id as gameId,
    profile.freshness_hours as freshnessHours,
    profile.generation_eligible as generationEligible,
    (select max(snapshot.fetched_at) from source_snapshots snapshot where snapshot.source_id = source.id) as lastFetchedAt,
    (select snapshot.content_hash from source_snapshots snapshot where snapshot.source_id = source.id and snapshot.ok=1 order by snapshot.fetched_at desc limit 1) as lastContentHash
  from content_sources source
  join content_source_profiles profile on profile.source_id = source.id
  where source.active = 1
    and profile.fetch_mode = 'direct'
    and profile.source_role = 'fact';
`) || "[]");
const eligibleSources = sources;
const dueSources = eligibleSources.filter(sourceIsDue);
const startedAt = runAt.toISOString();
runSql(`INSERT INTO agent_runs (id, run_type, status, started_at, summary_json) VALUES (${sqlValue(runId)}, 'content_sync', 'running', ${sqlValue(startedAt)}, '{}');`);

const snapshots = [];
const signals = [];

for (const source of dueSources) {
  const fetchedAt = new Date().toISOString();
  try {
    const response = await pacedFetch(source);
    const contentType = response.headers.get("content-type") || "";
    const body = await response.text();
    const title = source.sourceType === "steam-rss" ? `${source.game} Steam news feed` : titleFromHtml(body);
    const bodySample = stripTags(body).slice(0, 3000);
    const snapshot = {
      id: `snap_${hash(`${runId}:${source.id}`).slice(0, 18)}`,
      runId,
      sourceId: source.id,
      fetchedAt,
      ok: response.ok,
      statusCode: response.status,
      title,
      bodySample,
      contentHash: `v2:${hash(source.sourceType === "steam-rss" ? body : stripTags(body).slice(0, 120000))}`
    };
    snapshot.changed = Boolean(String(source.lastContentHash || "").startsWith("v2:") && source.lastContentHash !== snapshot.contentHash);
    snapshots.push(snapshot);

    if (source.sourceType === "steam-rss") {
      for (const item of extractRssItems(body, source)) {
        signals.push(makeSignal(source, item.title, item.url, {
          sourceType: "steam-rss",
          publishedAt: item.publishedAt,
          excerpt: item.excerpt
        }));
      }
    } else if ((title || bodySample) && snapshot.changed) {
      signals.push(makeSignal(source, title || `${source.game} source update`, source.url, {
        sourceType: source.sourceType,
        fetchedAt,
        excerpt: bodySample,
        contentHash: snapshot.contentHash,
      }));
    }
  } catch (error) {
    snapshots.push({
      id: `snap_${hash(`${runId}:${source.id}`).slice(0, 18)}`,
      runId,
      sourceId: source.id,
      fetchedAt,
      ok: false,
      statusCode: 0,
      title: "",
      bodySample: "",
      error: String(error.message || error),
      contentHash: ""
    });
  }
}

let sql = "BEGIN;\n";
for (const snapshot of snapshots) {
  sql += `INSERT OR REPLACE INTO source_snapshots (id, run_id, source_id, fetched_at, ok, status_code, title, body_sample, error, content_hash)
VALUES (${sqlValue(snapshot.id)}, ${sqlValue(snapshot.runId)}, ${sqlValue(snapshot.sourceId)}, ${sqlValue(snapshot.fetchedAt)}, ${snapshot.ok ? 1 : 0}, ${snapshot.statusCode || 0}, ${sqlValue(snapshot.title)}, ${sqlValue(snapshot.bodySample)}, ${sqlValue(snapshot.error || "")}, ${sqlValue(snapshot.contentHash)});\n`;
}
for (const signal of signals) {
  sql += `INSERT OR REPLACE INTO content_signals (id, run_id, source_id, game, topic, signal_title, signal_url, pain_score, commercial_score, patch_sensitive, evidence_json, created_at)
VALUES (${sqlValue(signal.id)}, ${sqlValue(signal.runId)}, ${sqlValue(signal.sourceId)}, ${sqlValue(signal.game)}, ${sqlValue(signal.topic)}, ${sqlValue(signal.title)}, ${sqlValue(signal.url)}, ${signal.painScore}, ${signal.commercialScore}, ${signal.patchSensitive ? 1 : 0}, ${sqlValue(JSON.stringify(signal.evidence || {}))}, ${sqlValue(new Date().toISOString())});\n`;
}

const highValue = signals.filter((signal) => signal.painScore >= 4 || signal.commercialScore >= 4);
for (const signal of highValue.slice(0, 20)) {
  const normalized = signal.title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const fingerprint = hash(`${signal.gameId}:${signal.topic}:${normalized}`).slice(0, 24);
  const demandId = `demand_${fingerprint}`;
  const freshnessScore = 5;
  const patchScore = signal.patchSensitive ? 5 : 2;
  const opportunityScore = Math.min(100, signal.painScore * 7 + signal.commercialScore * 7 + freshnessScore * 3 + patchScore * 3);
  const seenAt = new Date().toISOString();
  const evidence = JSON.stringify({ ...signal.evidence, demandOnly: false, sourceTrigger: true });
  sql += `INSERT INTO demand_backlog (id,game_id,fingerprint,source_id,source_type,source_url,source_title,normalized_question,topic,intent_zh,pain_score,commercial_score,freshness_score,patch_score,opportunity_score,patch_sensitive,status,occurrence_count,first_seen_at,last_seen_at,evidence_json)
VALUES (${sqlValue(demandId)},${sqlValue(signal.gameId)},${sqlValue(fingerprint)},${sqlValue(signal.sourceId)},${sqlValue("official-source-trigger")},${sqlValue(signal.url)},${sqlValue(signal.title)},${sqlValue(normalized)},${sqlValue(signal.topic)},'',${signal.painScore},${signal.commercialScore},${freshnessScore},${patchScore},${opportunityScore},${signal.patchSensitive ? 1 : 0},'source_trigger',1,${sqlValue(seenAt)},${sqlValue(seenAt)},${sqlValue(evidence)})
ON CONFLICT(game_id,fingerprint) DO UPDATE SET last_seen_at=excluded.last_seen_at,occurrence_count=demand_backlog.occurrence_count+1,opportunity_score=MAX(demand_backlog.opportunity_score,excluded.opportunity_score),evidence_json=excluded.evidence_json;\n`;
  const observationId = `obs_${hash(`${demandId}:${runId}`).slice(0, 20)}`;
  sql += `INSERT OR IGNORE INTO demand_observations (id,demand_id,source_url,source_title,published_at,observed_at,evidence_json)
VALUES (${sqlValue(observationId)},${sqlValue(demandId)},${sqlValue(signal.url)},${sqlValue(signal.title)},${sqlValue(signal.evidence?.publishedAt || "")},${sqlValue(seenAt)},${sqlValue(evidence)});\n`;
}

const summary = {
  sources: sources.length,
  eligibleSources: eligibleSources.length,
  platformRestrictedSources: 0,
  dueSources: dueSources.length,
  skippedSources: eligibleSources.length - dueSources.length,
  snapshots: snapshots.length,
  signals: signals.length,
  highValueSignals: highValue.length,
  failedSources: snapshots.filter((snapshot) => !snapshot.ok).length,
  transientFailures: snapshots.filter((snapshot) => !snapshot.ok && sources.find((source) => source.id === snapshot.sourceId)?.lastContentHash).length,
  unavailableSources: snapshots.filter((snapshot) => !snapshot.ok && !sources.find((source) => source.id === snapshot.sourceId)?.lastContentHash).length,
  changedSources: snapshots.filter((snapshot) => snapshot.ok && snapshot.changed).length
};
sql += `UPDATE agent_runs SET status = 'completed', finished_at = ${sqlValue(new Date().toISOString())}, summary_json = ${sqlValue(JSON.stringify(summary))} WHERE id = ${sqlValue(runId)};\n`;
sql += "COMMIT;\n";
runSql(sql);

const outJson = path.join(inboxDir, `agent-signals-${day}.json`);
const outMd = path.join(operationsDir, "latest-agent-run.md");

console.log(`Completed ${runId}`);
console.log(JSON.stringify(summary, null, 2));

if (dueSources.length > 0) {
  fs.writeFileSync(outJson, `${JSON.stringify({ runId, summary, snapshots, signals }, null, 2)}\n`);
  const topSignals = signals
    .sort((a, b) => b.painScore + b.commercialScore - (a.painScore + a.commercialScore))
    .slice(0, 12)
    .map((signal) => `- ${signal.game} / ${signal.topic} / pain ${signal.painScore} / commercial ${signal.commercialScore}: ${signal.title}`)
    .join("\n");

  fs.writeFileSync(
    outMd,
    `# Latest Agent Run\n\nRun ID: ${runId}\n\n${JSON.stringify(summary, null, 2)}\n\n## Top Signals\n\n${topSignals || "- No signals collected."}\n\n## Notes\n\nThis run uses permitted public sources only. Failed sources are recorded instead of bypassed. Reddit automation remains disabled until commercial platform permission is recorded.\n`,
  );

  console.log(`Wrote ${outJson}`);
  console.log(`Wrote ${outMd}`);
} else {
  console.log("No sources were due; preserved the latest non-empty Agent artifacts.");
}
