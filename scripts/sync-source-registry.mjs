import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dbPath = process.env.RAIDBENCH_LOCAL_DB_PATH
  ? path.resolve(process.env.RAIDBENCH_LOCAL_DB_PATH)
  : path.join(root, "local", "raidbench.local.db");
const gameRegistry = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8"));
const sourceRegistry = JSON.parse(fs.readFileSync(path.join(root, "content", "source-registry.json"), "utf8"));
const schema = fs.readFileSync(path.join(root, "local", "raidbench-local-schema.sql"), "utf8");

function sqlValue(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "number") return String(value);
  return `'${String(value).replaceAll("'", "''")}'`;
}

function runSql(sql) {
  return execFileSync("sqlite3", [dbPath], { input: sql, encoding: "utf8" });
}

function validate() {
  if (gameRegistry.schemaVersion !== "1.0.0" || sourceRegistry.schemaVersion !== "1.0.0") {
    throw new Error("Unsupported game or source registry version");
  }
  const games = new Set(gameRegistry.games.map((game) => game.id));
  if (games.size !== 12) throw new Error("Source synchronization requires twelve unique games");
  const sourceIds = new Set();
  const coverage = new Map([...games].map((gameId) => [gameId, { fact: 0, demand: 0 }]));
  for (const source of sourceRegistry.sources) {
    if (!games.has(source.gameId)) throw new Error(`Unknown source game: ${source.gameId}`);
    if (sourceIds.has(source.id)) throw new Error(`Duplicate source id: ${source.id}`);
    if (!String(source.url).startsWith("https://")) throw new Error(`Non-HTTPS source: ${source.id}`);
    if (source.role === "demand" && (source.fetchMode !== "search-only" || source.generationEligible)) {
      throw new Error(`Community demand source cannot be directly fetched or generation eligible: ${source.id}`);
    }
    if (source.role === "fact" && source.authority === "community") {
      throw new Error(`Community source cannot be factual authority: ${source.id}`);
    }
    sourceIds.add(source.id);
    coverage.get(source.gameId)[source.role] += 1;
  }
  for (const [gameId, counts] of coverage) {
    if (counts.fact < 2 || counts.demand !== 1) {
      throw new Error(`Game ${gameId} requires at least two fact sources and exactly one demand profile`);
    }
  }
}

validate();
fs.mkdirSync(path.dirname(dbPath), { recursive: true });
runSql(schema);

const now = new Date().toISOString();
const gamesById = new Map(gameRegistry.games.map((game) => [game.id, game]));
let sql = "BEGIN;\n";
sql += "UPDATE content_sources SET active = 0 WHERE source_type IN ('official','steam-rss','reddit-json','community-web-search');\n";

for (const game of gameRegistry.games) {
  sql += `INSERT INTO game_catalog (id,name,short_name,genre,status,indexable,paid_answers,registry_version,updated_at)
VALUES (${sqlValue(game.id)},${sqlValue(game.name)},${sqlValue(game.shortName)},${sqlValue(game.genre)},${sqlValue(game.status)},${game.indexable ? 1 : 0},${sqlValue(game.paidAnswers)},${sqlValue(gameRegistry.schemaVersion)},${sqlValue(now)})
ON CONFLICT(id) DO UPDATE SET name=excluded.name,short_name=excluded.short_name,genre=excluded.genre,status=excluded.status,indexable=excluded.indexable,paid_answers=excluded.paid_answers,registry_version=excluded.registry_version,updated_at=excluded.updated_at;\n`;
}

for (const source of sourceRegistry.sources) {
  const game = gamesById.get(source.gameId);
  const active = source.fetchMode === "direct" ? 1 : 0;
  const policy = {
    topics: source.topics || [],
    queryTerms: source.queryTerms || [],
    steamAppId: source.steamAppId || "",
    redditCommunities: source.redditCommunities || [],
    demandOnly: source.role === "demand",
    minuteOffsetUtc: source.minuteOffsetUtc ?? null,
    notes: source.notes,
  };
  sql += `INSERT INTO content_sources (id,game,source_type,url,cadence,active,notes)
VALUES (${sqlValue(source.id)},${sqlValue(game.shortName)},${sqlValue(source.sourceType)},${sqlValue(source.url)},${sqlValue(source.cadence)},${active},${sqlValue(source.notes)})
ON CONFLICT(id) DO UPDATE SET game=excluded.game,source_type=excluded.source_type,url=excluded.url,cadence=excluded.cadence,active=excluded.active,notes=excluded.notes;\n`;
  sql += `INSERT INTO content_source_profiles (source_id,game_id,source_role,authority,fetch_mode,freshness_hours,generation_eligible,policy_json,updated_at)
VALUES (${sqlValue(source.id)},${sqlValue(source.gameId)},${sqlValue(source.role)},${sqlValue(source.authority)},${sqlValue(source.fetchMode)},${Number(source.freshnessHours)},${source.generationEligible ? 1 : 0},${sqlValue(JSON.stringify(policy))},${sqlValue(now)})
ON CONFLICT(source_id) DO UPDATE SET game_id=excluded.game_id,source_role=excluded.source_role,authority=excluded.authority,fetch_mode=excluded.fetch_mode,freshness_hours=excluded.freshness_hours,generation_eligible=excluded.generation_eligible,policy_json=excluded.policy_json,updated_at=excluded.updated_at;\n`;
}

sql += "COMMIT;\n";
runSql(sql);

const summary = JSON.parse(execFileSync("sqlite3", ["-json", dbPath, `
SELECT
  (SELECT count(*) FROM game_catalog) AS games,
  (SELECT count(*) FROM content_source_profiles) AS registeredSources,
  (SELECT count(*) FROM content_sources WHERE active=1) AS directSources,
  (SELECT count(*) FROM content_source_profiles WHERE source_role='demand') AS demandProfiles,
  (SELECT count(*) FROM content_sources WHERE source_type='reddit-json' AND active=1) AS activeRedditApiSources;
`], { encoding: "utf8" }) || "[]")[0];

console.log(JSON.stringify({ status: "source_registry_synced", ...summary }, null, 2));
