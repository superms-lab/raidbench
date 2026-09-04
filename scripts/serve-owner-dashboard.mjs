import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDirectory, "..");
const host = "127.0.0.1";
const port = Number(process.env.PORT || 4289);
const dashboardPath = path.join(root, "local", "traffic-dashboard.json");
const refreshScript = path.join(scriptDirectory, "fetch-traffic-dashboard.mjs");
const allowedFiles = new Map([
  ["/owner-traffic-zh.html", ["owner-traffic-zh.html", "text/html; charset=utf-8"]],
  ["/owner-costs-zh.html", ["owner-costs-zh.html", "text/html; charset=utf-8"]],
  ["/owner-acquisition-zh.html", ["owner-acquisition-zh.html", "text/html; charset=utf-8"]],
  ["/owner-demand-zh.html", ["owner-demand-zh.html", "text/html; charset=utf-8"]],
  ["/owner-products-zh.html", ["owner-products-zh.html", "text/html; charset=utf-8"]],
  ["/styles.css", ["styles.css", "text/css; charset=utf-8"]],
  ["/favicon.svg", ["favicon.svg", "image/svg+xml"]],
  ["/local/traffic-dashboard.json", ["local/traffic-dashboard.json", "application/json; charset=utf-8"]],
  ["/content/unit-economics.json", ["content/unit-economics.json", "application/json; charset=utf-8"]],
  ["/content/skus.json", ["content/skus.json", "application/json; charset=utf-8"]],
  ["/content/multigame-products.json", ["content/multigame-products.json", "application/json; charset=utf-8"]],
  ["/local/multigame-product-economics.json", ["local/multigame-product-economics.json", "application/json; charset=utf-8"]],
]);

let activeRefresh = null;
let lastRefreshAt = 0;
const acquisitionScript = "/opt/raidbench-publisher/workspace/scripts/export_acquisition_inbox.py";
const growthScript = "/opt/raidbench-publisher/workspace/scripts/export_growth_status.py";
const demandScript = "/opt/raidbench-publisher/workspace/scripts/export_multigame_demand.py";
const shadowReadinessPath = "/opt/raidbench-agent/artifacts/shadow-benchmarks/latest-readiness.json";
const multigameLiveScript = "/opt/raidbench-publisher/workspace/scripts/export_multigame_live_status.py";
const acquisitionArgs = [
  "--draft-dir", "/opt/raidbench-agent/artifacts/content-automation/community-drafts",
  "--draft-dir", "/opt/raidbench-publisher/workspace/private-data/content-automation/community-drafts",
  "--digest-state", "/opt/raidbench-agent/artifacts/acquisition-digest-state.json",
];

async function readDashboard({ force = false } = {}) {
  const freshEnough = Date.now() - lastRefreshAt < 15_000;
  if (!force && freshEnough) return fs.readFile(dashboardPath, "utf8");

  if (!activeRefresh) {
    activeRefresh = run(process.execPath, [refreshScript], {
      cwd: root,
      timeout: 60_000,
      maxBuffer: 10 * 1024 * 1024,
    }).finally(() => {
      activeRefresh = null;
    });
  }

  await activeRefresh;
  lastRefreshAt = Date.now();
  return fs.readFile(dashboardPath, "utf8");
}

function send(response, status, body, contentType) {
  response.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Type": contentType,
    "X-Content-Type-Options": "nosniff",
  });
  response.end(body);
}

async function readBody(request) {
  let body = "";
  for await (const chunk of request) {
    body += chunk;
    if (body.length > 16_384) throw new Error("request_too_large");
  }
  return JSON.parse(body || "{}");
}

async function acquisitionInbox(extraArgs = []) {
  const { stdout } = await run("ssh", [
    "leadauditlab-vps",
    "python3",
    acquisitionScript,
    ...acquisitionArgs,
    ...extraArgs,
  ], { timeout: 30_000, maxBuffer: 4 * 1024 * 1024 });
  return stdout;
}

async function growthStatus() {
  const { stdout } = await run("ssh", [
    "leadauditlab-vps",
    "python3",
    growthScript,
    "--database", "/opt/raidbench-agent/data/raidbench.local.db",
    "--quota", "/opt/raidbench-publisher/workspace/config/growth-quotas.json",
    "--draft-dir", "/opt/raidbench-agent/artifacts/content-automation/community-drafts",
    "--partner-state", "/opt/raidbench-agent/artifacts/acquisition-outreach/weekly-partner-state.json",
    "--asset-source", "/opt/raidbench-publisher/workspace/content/rust-route-presets.json",
    "--patch-state", "/opt/raidbench-agent/artifacts/content-automation/patch-refresh-state.json",
  ], { timeout: 30_000, maxBuffer: 2 * 1024 * 1024 });
  return stdout;
}

async function demandStatus() {
  const { stdout } = await run("ssh", [
    "leadauditlab-vps",
    "python3",
    demandScript,
    "--database", "/opt/raidbench-agent/data/raidbench.local.db",
    "--limit", "60",
  ], { timeout: 30_000, maxBuffer: 4 * 1024 * 1024 });
  return stdout;
}

async function shadowReadiness() {
  const { stdout } = await run("ssh", ["leadauditlab-vps", "cat", shadowReadinessPath], {
    timeout: 30_000,
    maxBuffer: 4 * 1024 * 1024,
  });
  return stdout;
}

async function multigameLiveStatus() {
  const { stdout } = await run("ssh", [
    "leadauditlab-vps",
    "python3",
    multigameLiveScript,
  ], { timeout: 30_000, maxBuffer: 2 * 1024 * 1024 });
  return stdout;
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url || "/", `http://${host}:${port}`);

  if (request.method === "GET" && url.pathname === "/") {
    response.writeHead(302, { Location: "/owner-traffic-zh.html" });
    response.end();
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/owner/traffic") {
    try {
      const body = await readDashboard({ force: url.searchParams.get("refresh") === "1" });
      send(response, 200, body, "application/json; charset=utf-8");
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown_error";
      send(response, 502, JSON.stringify({ error: "cloud_sync_failed", message }), "application/json; charset=utf-8");
    }
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/owner/acquisition") {
    try {
      send(response, 200, await acquisitionInbox(), "application/json; charset=utf-8");
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown_error";
      send(response, 502, JSON.stringify({ error: "acquisition_sync_failed", message }), "application/json; charset=utf-8");
    }
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/owner/growth") {
    try {
      send(response, 200, await growthStatus(), "application/json; charset=utf-8");
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown_error";
      send(response, 502, JSON.stringify({ error: "growth_sync_failed", message }), "application/json; charset=utf-8");
    }
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/owner/demand") {
    try {
      send(response, 200, await demandStatus(), "application/json; charset=utf-8");
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown_error";
      send(response, 502, JSON.stringify({ error: "demand_sync_failed", message }), "application/json; charset=utf-8");
    }
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/owner/shadow-readiness") {
    try {
      send(response, 200, await shadowReadiness(), "application/json; charset=utf-8");
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown_error";
      send(response, 502, JSON.stringify({ error: "shadow_readiness_sync_failed", message }), "application/json; charset=utf-8");
    }
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/owner/multigame-live") {
    try {
      send(response, 200, await multigameLiveStatus(), "application/json; charset=utf-8");
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown_error";
      send(response, 502, JSON.stringify({ error: "multigame_live_sync_failed", message }), "application/json; charset=utf-8");
    }
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/owner/acquisition/mark") {
    try {
      const payload = await readBody(request);
      const draftId = String(payload.draftId || "");
      const status = String(payload.status || "");
      if (!/^[A-Za-z0-9_-]{1,120}$/.test(draftId) || !["replied", "published", "cancelled", "rejected"].includes(status)) {
        send(response, 422, JSON.stringify({ error: "invalid_draft_update" }), "application/json; charset=utf-8");
        return;
      }
      send(response, 200, await acquisitionInbox(["--mark", draftId, "--status", status]), "application/json; charset=utf-8");
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown_error";
      send(response, 502, JSON.stringify({ error: "acquisition_update_failed", message }), "application/json; charset=utf-8");
    }
    return;
  }

  if (request.method !== "GET") {
    send(response, 405, "Method Not Allowed", "text/plain; charset=utf-8");
    return;
  }

  const file = allowedFiles.get(url.pathname);
  if (!file) {
    send(response, 404, "Not Found", "text/plain; charset=utf-8");
    return;
  }

  try {
    send(response, 200, await fs.readFile(path.join(root, file[0])), file[1]);
  } catch {
    send(response, 404, "Not Found", "text/plain; charset=utf-8");
  }
});

server.listen(port, host, () => {
  console.log(`RaidBench owner traffic dashboard: http://${host}:${port}/owner-traffic-zh.html`);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
