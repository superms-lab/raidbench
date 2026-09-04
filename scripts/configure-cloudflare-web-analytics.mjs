import { execFileSync } from "node:child_process";

const accountId = "3b4bce1bd83d0de85c69ef3286a59eb7";
const domain = "raidbench.com";
const enable = process.argv.includes("--enable");
const diagnoseAuth = process.argv.includes("--diagnose-auth");
const checkPages = process.argv.includes("--check-pages");
const checkRum = process.argv.includes("--check-rum");
const checkZones = process.argv.includes("--check-zones");
const zoneAnalytics = process.argv.includes("--zone-analytics");

function parseWranglerAuth() {
  const output = execFileSync("npx", ["wrangler", "auth", "token", "--json"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"]
  });
  const start = output.indexOf("{");
  if (start < 0) throw new Error("Wrangler did not return JSON credentials.");
  return JSON.parse(output.slice(start));
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

function describeAuth(value) {
  if (Array.isArray(value)) return value.map(describeAuth);
  if (!value || typeof value !== "object") {
    return typeof value === "string" ? { type: "string", length: value.length } : typeof value;
  }
  return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, describeAuth(child)]));
}

const auth = parseWranglerAuth();
if (diagnoseAuth) {
  console.log(JSON.stringify(describeAuth(auth), null, 2));
  process.exit(0);
}

const token = findBearerToken(auth);
if (!token) throw new Error("Could not obtain a usable Wrangler OAuth token.");

async function cloudflare(path, options = {}) {
  const response = await fetch(`https://api.cloudflare.com/client/v4${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const payload = await response.json();
  if (!response.ok || !payload.success) {
    const message = payload.errors?.map((error) => error.message).join("; ") || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload.result;
}

if (checkPages) {
  const project = await cloudflare(`/accounts/${accountId}/pages/projects/raidbench`);
  console.log(
    JSON.stringify(
      {
        project: project.name,
        webAnalyticsTagConfigured: Boolean(project.build_config?.web_analytics_tag),
        webAnalyticsTokenConfigured: Boolean(project.build_config?.web_analytics_token),
        productionD1Bindings: Object.keys(project.deployment_configs?.production?.d1_databases || {}),
        previewD1Bindings: Object.keys(project.deployment_configs?.preview?.d1_databases || {})
      },
      null,
      2
    )
  );
  process.exit(0);
}

if (checkRum) {
  const sites = await cloudflare(`/accounts/${accountId}/rum/site_info/list?per_page=100`);
  console.log(
    JSON.stringify(
      sites.map((site) => ({
        host: site.host || site.ruleset?.zone_name || site.rules?.[0]?.host || null,
        enabled: Boolean(site.ruleset?.enabled ?? site.auto_install),
        autoInstall: Boolean(site.auto_install),
        hasSiteTag: Boolean(site.site_tag),
        hasSiteToken: Boolean(site.site_token)
      })),
      null,
      2
    )
  );
  process.exit(0);
}

if (checkZones) {
  const zones = await cloudflare(`/zones?name=${encodeURIComponent(domain)}`);
  console.log(
    JSON.stringify(
      zones.map((zone) => ({ name: zone.name, status: zone.status, accountId: zone.account?.id || null })),
      null,
      2
    )
  );
  process.exit(0);
}

if (zoneAnalytics) {
  const zones = await cloudflare(`/zones?name=${encodeURIComponent(domain)}`);
  const zone = zones.find((candidate) => candidate.name === domain);
  if (!zone) throw new Error(`Cloudflare zone not found: ${domain}`);

  const until = new Date();
  const since = new Date(until.getTime() - 7 * 24 * 60 * 60 * 1000);
  const analytics = await cloudflare(
    `/zones/${zone.id}/analytics/dashboard?since=${encodeURIComponent(since.toISOString())}&until=${encodeURIComponent(until.toISOString())}&continuous=true`
  );
  const totals = analytics.totals || {};
  const countries = Object.entries(totals.requests?.country || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([country, requests]) => ({ country, requests }));

  console.log(
    JSON.stringify(
      {
        domain,
        periodStart: totals.since || since.toISOString(),
        periodEnd: totals.until || until.toISOString(),
        requests: totals.requests?.all || 0,
        pageViews: totals.pageviews?.all || 0,
        uniqueVisitors: totals.uniques?.all || 0,
        bandwidthBytes: totals.bandwidth?.all || 0,
        topCountries: countries
      },
      null,
      2
    )
  );
  process.exit(0);
}

const zones = await cloudflare(`/zones?name=${encodeURIComponent(domain)}`);
const zone = zones.find((candidate) => candidate.name === domain);
if (!zone) throw new Error(`Cloudflare zone not found: ${domain}`);

const sites = await cloudflare(`/accounts/${accountId}/rum/site_info/list?per_page=100`);
let site = sites.find(
  (candidate) =>
    candidate.ruleset?.zone_tag === zone.id ||
    candidate.ruleset?.zone_name === domain ||
    candidate.rules?.some((rule) => rule.host === domain)
);

if (!site && enable) {
  site = await cloudflare(`/accounts/${accountId}/rum/site_info`, {
    method: "POST",
    body: JSON.stringify({ auto_install: true, host: domain, zone_tag: zone.id })
  });
} else if (site && enable && (!site.auto_install || site.ruleset?.enabled === false)) {
  site = await cloudflare(`/accounts/${accountId}/rum/site_info/${site.site_tag}`, {
    method: "PUT",
    body: JSON.stringify({ auto_install: true, enabled: true, host: domain, zone_tag: zone.id })
  });
}

console.log(
  JSON.stringify(
    {
      domain,
      configured: Boolean(site),
      enabled: Boolean(site?.ruleset?.enabled ?? site?.auto_install),
      autoInstall: Boolean(site?.auto_install),
      siteTag: site?.site_tag || null,
      action: enable ? (site ? "enabled" : "not-created") : "check-only"
    },
    null,
    2
  )
);
