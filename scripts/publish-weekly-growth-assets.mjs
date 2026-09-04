import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";


const root = process.cwd();
const stateDir = path.resolve(process.env.RAIDBENCH_AUTOMATION_STATE_DIR || path.join(root, "private-data", "content-automation"));
const statePath = path.join(stateDir, "weekly-growth-assets-state.json");
const sourcePath = path.join(root, "content", "rust-route-presets.json");
const force = process.argv.includes("--force");
const today = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return fallback;
    throw error;
  }
}

function run(command, args, timeout = 300_000) {
  return execFileSync(command, args, {
    cwd: root,
    env: process.env,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout,
    maxBuffer: 10 * 1024 * 1024,
  });
}

const source = readJson(sourcePath, []);
const releasedCount = source.filter((preset) => preset.availableFrom <= today).length;
const state = readJson(statePath, {});
if (!force && Number(state.releasedCount || 0) >= releasedCount) {
  console.log(JSON.stringify({ status: "no_new_weekly_assets", releasedCount, day: today }));
  process.exit(0);
}

run("node", ["scripts/generate-rust-route-presets.mjs"]);
run("node", ["scripts/generate-multigame-baseline-guides.mjs"]);
run("node", ["scripts/validate-multigame-launch-gates.mjs"]);
run("node", ["scripts/generate-multigame-tools.mjs"]);
run("node", ["scripts/generate-game-directory.mjs"]);
run("node", ["scripts/generate-guide-index.mjs"]);
run("node", ["scripts/apply-site-navigation.mjs"]);
run("node", ["scripts/generate-sitemap.mjs"]);
run("node", ["scripts/generate-discovery-feeds.mjs"]);
run("node", ["scripts/validate-public-site.mjs"]);
const dist = path.join(stateDir, "growth-assets-dist");
run("node", ["scripts/build-public-dist.mjs"], 300_000);

let deploymentUrl = "";
const autoDeploy = /^(1|true|yes|on)$/i.test(process.env.RAIDBENCH_AUTO_DEPLOY || "");
if (autoDeploy) {
  const wrangler = process.env.RAIDBENCH_WRANGLER_BIN || "wrangler";
  const output = run(wrangler, [
    "pages",
    "deploy",
    process.env.RAIDBENCH_DIST_DIR || "/tmp/raidbench-pages",
    "--project-name",
    "raidbench",
    "--branch",
    "main",
    "--commit-message",
    `RaidBench weekly route presets: ${releasedCount}`,
  ], 900_000);
  deploymentUrl = output.match(/https:\/\/[a-z0-9-]+\.raidbench\.pages\.dev/i)?.[0] || "";
  try {
    run("node", ["scripts/submit-indexnow.mjs", "https://raidbench.com/rust-route-presets"], 90_000);
  } catch {
    // The public page remains deployed even if IndexNow is temporarily unavailable.
  }
}

fs.mkdirSync(stateDir, { recursive: true });
const temporary = `${statePath}.tmp`;
fs.writeFileSync(temporary, `${JSON.stringify({
  lastPreparedAt: new Date().toISOString(),
  lastPublishedAt: autoDeploy ? new Date().toISOString() : "",
  day: today,
  releasedCount,
  deploymentUrl,
}, null, 2)}\n`);
fs.renameSync(temporary, statePath);
console.log(JSON.stringify({ status: autoDeploy ? "weekly_assets_published" : "weekly_assets_staged", releasedCount, deploymentUrl }));
