import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dbPath = process.env.RAIDBENCH_LOCAL_DB_PATH
  ? path.resolve(process.env.RAIDBENCH_LOCAL_DB_PATH)
  : path.join(root, "local", "raidbench.local.db");
const schemaPath = path.join(root, "local", "raidbench-local-schema.sql");
const skusPath = path.join(root, "content", "skus.json");

function sqlValue(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "number") return String(value);
  return `'${String(value).replaceAll("'", "''")}'`;
}

function runSql(sql) {
  execFileSync("sqlite3", [dbPath], { input: sql, stdio: ["pipe", "pipe", "pipe"] });
}

function id(prefix, value) {
  return `${prefix}_${crypto.createHash("sha1").update(value).digest("hex").slice(0, 16)}`;
}

fs.mkdirSync(path.dirname(dbPath), { recursive: true });
runSql(fs.readFileSync(schemaPath, "utf8"));
execFileSync(process.execPath, ["scripts/sync-source-registry.mjs"], {
  cwd: root,
  env: { ...process.env, RAIDBENCH_LOCAL_DB_PATH: dbPath },
  stdio: "inherit",
});

let sql = "BEGIN;\n";

const skuData = JSON.parse(fs.readFileSync(skusPath, "utf8"));
for (const pack of skuData.packs) {
  sql += `INSERT OR REPLACE INTO sku_packs (sku, name, credits, price_usd, price_eur, price_gbp, status)
VALUES (${sqlValue(pack.sku)}, ${sqlValue(pack.name)}, ${sqlValue(pack.credits)}, ${sqlValue(pack.prices.USD)}, ${sqlValue(pack.prices.EUR)}, ${sqlValue(pack.prices.GBP)}, ${sqlValue(pack.status)});\n`;
}
for (const action of skuData.actions) {
  sql += `INSERT OR REPLACE INTO credit_actions (id, label, credits, output, delivery_class, status)
VALUES (${sqlValue(action.id)}, ${sqlValue(action.label)}, ${sqlValue(action.credits)}, ${sqlValue(action.output)}, ${sqlValue(action.deliveryClass || "custom_verified")}, ${sqlValue(action.status || "draft")});\n`;
}

for (const file of ["rust-problem-guides.json", "poe2-problem-guides.json", "palworld-problem-guides.json"]) {
  const game = file.startsWith("rust") ? "Rust" : file.startsWith("poe2") ? "POE2" : "Palworld";
  const guides = JSON.parse(fs.readFileSync(path.join(root, "content", file), "utf8"));
  for (const guide of guides) {
    sql += `INSERT OR REPLACE INTO guide_pages (slug, game, title, status, last_checked_at, patch_sensitive, source_notes)
VALUES (${sqlValue(guide.slug)}, ${sqlValue(game)}, ${sqlValue(guide.title)}, 'published_or_draft', datetime('now'), 1, ${sqlValue((guide.sources || []).join("; "))});\n`;
  }
}

const baselinePath = path.join(root, "content", "multigame-baseline-guides.json");
if (fs.existsSync(baselinePath)) {
  const registry = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8"));
  const gameNames = new Map(registry.games.map((game) => [game.id, game.shortName]));
  const baseline = JSON.parse(fs.readFileSync(baselinePath, "utf8"));
  for (const pack of baseline.packs) {
    for (const guide of pack.guides) {
      sql += `INSERT OR REPLACE INTO guide_pages (slug, game, title, status, last_checked_at, patch_sensitive, source_notes)
VALUES (${sqlValue(guide.slug)}, ${sqlValue(gameNames.get(pack.gameId) || pack.gameId)}, ${sqlValue(guide.title)}, 'published', ${sqlValue(baseline.reviewedAt)}, ${guide.patchSensitive ? 1 : 0}, 'Phase 3 source packet; publisher facts plus demand-only community context');\n`;
    }
  }
}

sql += "COMMIT;\n";
runSql(sql);

const summary = execFileSync(
  "sqlite3",
  [
    dbPath,
    "select 'sources=' || count(*) from content_sources union all select 'sku_packs=' || count(*) from sku_packs union all select 'credit_actions=' || count(*) from credit_actions union all select 'guide_pages=' || count(*) from guide_pages;"
  ],
  { encoding: "utf8" },
);

console.log(`Initialized ${dbPath}`);
console.log(summary.trim());
console.log(`schema_id=${id("schema", fs.readFileSync(schemaPath, "utf8"))}`);
