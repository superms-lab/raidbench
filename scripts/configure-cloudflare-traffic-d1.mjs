import { execFileSync } from "node:child_process";

const accountId = "3b4bce1bd83d0de85c69ef3286a59eb7";
const projectName = "raidbench";
const databaseName = "raidbench-analytics";
const bindingName = "ANALYTICS_DB";

function parseJsonOutput(output) {
  const starts = [output.indexOf("["), output.indexOf("{")].filter((index) => index >= 0);
  if (!starts.length) throw new Error("Command did not return JSON.");
  return JSON.parse(output.slice(Math.min(...starts)));
}

function wranglerJson(args) {
  const output = execFileSync("npx", ["wrangler", ...args], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  });
  return parseJsonOutput(output);
}

function findBearerToken(value, key = "") {
  if (
    typeof value === "string" &&
    /^(access_?token|oauth_?token|api_?token|token)$/i.test(key) &&
    value.length > 20
  ) {
    return value.replace(/^Bearer\s+/i, "");
  }
  if (!value || typeof value !== "object") return "";
  for (const [childKey, childValue] of Object.entries(value)) {
    const token = findBearerToken(childValue, childKey);
    if (token) return token;
  }
  return "";
}

const database = wranglerJson(["d1", "list", "--json"]).find((item) => item.name === databaseName);
if (!database) throw new Error(`D1 database not found: ${databaseName}`);

const token = findBearerToken(wranglerJson(["auth", "token", "--json"]));
if (!token) throw new Error("Could not obtain a usable Wrangler OAuth token.");

async function cloudflare(path, options = {}) {
  const result = await fetch(`https://api.cloudflare.com/client/v4${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await result.json();
  if (!result.ok || !payload.success) {
    const message = payload.errors?.map((error) => error.message).join("; ") || `HTTP ${result.status}`;
    throw new Error(message);
  }
  return payload.result;
}

const project = await cloudflare(`/accounts/${accountId}/pages/projects/${projectName}`);
const productionBindings = project.deployment_configs?.production?.d1_databases || {};
const previewBindings = project.deployment_configs?.preview?.d1_databases || {};

await cloudflare(`/accounts/${accountId}/pages/projects/${projectName}`, {
  method: "PATCH",
  body: JSON.stringify({
    deployment_configs: {
      production: {
        d1_databases: {
          ...productionBindings,
          [bindingName]: { id: database.uuid },
        },
      },
      preview: {
        d1_databases: {
          ...previewBindings,
          [bindingName]: { id: database.uuid },
        },
      },
    },
  }),
});

const verified = await cloudflare(`/accounts/${accountId}/pages/projects/${projectName}`);
const productionId = verified.deployment_configs?.production?.d1_databases?.[bindingName]?.id;
const previewId = verified.deployment_configs?.preview?.d1_databases?.[bindingName]?.id;

console.log(
  JSON.stringify(
    {
      project: projectName,
      database: databaseName,
      binding: bindingName,
      productionBound: productionId === database.uuid,
      previewBound: previewId === database.uuid,
    },
    null,
    2,
  ),
);
