import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "raidbench-source-empty-slot-"));
const database = path.join(temporary, "source.db");
const registry = JSON.parse(fs.readFileSync("content/source-registry.json", "utf8"));
const environment = {
  ...process.env,
  RAIDBENCH_LOCAL_DB_PATH: database,
  RAIDBENCH_SCOUT_INBOX_DIR: path.join(temporary, "inbox"),
  RAIDBENCH_SCOUT_OPERATIONS_DIR: path.join(temporary, "operations"),
};

let result = spawnSync(process.execPath, ["scripts/sync-source-registry.mjs"], {
  cwd: process.cwd(),
  encoding: "utf8",
  env: environment,
});
assert.equal(result.status, 0, result.stderr || result.stdout);

const sourceIds = registry.sources.filter((source) => source.role === "fact").map((source) => source.id);
const sqlValue = (value) => `'${String(value).replaceAll("'", "''")}'`;
const seedSql = [
  "PRAGMA foreign_keys=ON;",
  "INSERT INTO agent_runs (id,run_type,status,started_at,finished_at,summary_json) VALUES ('seed','content_sync','completed','2026-09-04T06:06:30Z','2026-09-04T06:06:30Z','{}');",
  ...sourceIds.map((sourceId, index) => (
    `INSERT INTO source_snapshots (id,run_id,source_id,fetched_at,ok,status_code,title,body_sample,error,content_hash) VALUES ('seed_${index}','seed',${sqlValue(sourceId)},'2026-09-04T06:06:30Z',1,200,'seed','','','seed');`
  )),
].join("\n");
result = spawnSync("sqlite3", [database], { input: seedSql, encoding: "utf8" });
assert.equal(result.status, 0, result.stderr || result.stdout);

result = spawnSync(process.execPath, ["scripts/run-content-agents.mjs"], {
  cwd: process.cwd(),
  encoding: "utf8",
  env: { ...environment, RAIDBENCH_SCOUT_RUN_AT: "2026-09-04T06:07:20Z" },
});
assert.equal(result.status, 0, result.stderr || result.stdout);
assert.match(result.stdout, /no run row was created/i);
const count = spawnSync("sqlite3", [database, "SELECT count(*) FROM agent_runs;"], { encoding: "utf8" });
assert.equal(count.status, 0, count.stderr || count.stdout);
assert.equal(count.stdout.trim(), "1");

fs.rmSync(temporary, { recursive: true, force: true });
console.log("Empty source slots exit without creating database run rows.");
