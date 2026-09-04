import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const databaseName = "raidbench-analytics";
const outputPath = path.join(root, "local", "traffic-dashboard.json");
const projectWrangler = path.join(root, "cloudflare", "email-reply-monitor", "node_modules", ".bin", "wrangler");
const queries = `
SELECT
  COALESCE(SUM(CASE WHEN day = date('now') THEN views ELSE 0 END), 0) AS today,
  COALESCE(SUM(CASE WHEN day >= date('now', '-6 days') THEN views ELSE 0 END), 0) AS last_7_days,
  COALESCE(SUM(CASE WHEN day >= date('now', '-29 days') THEN views ELSE 0 END), 0) AS last_30_days,
  COUNT(DISTINCT path) AS measured_pages
FROM page_views
WHERE day >= date('now', '-29 days');

SELECT day, SUM(views) AS views
FROM page_views
WHERE day >= date('now', '-29 days')
GROUP BY day
ORDER BY day;

SELECT path, SUM(views) AS views
FROM page_views
WHERE day >= date('now', '-29 days')
GROUP BY path
ORDER BY views DESC, path
LIMIT 20;

SELECT referrer_host, SUM(views) AS views
FROM page_views
WHERE day >= date('now', '-29 days')
GROUP BY referrer_host
ORDER BY views DESC, referrer_host
LIMIT 15;

SELECT country, SUM(views) AS views
FROM page_views
WHERE day >= date('now', '-29 days')
GROUP BY country
ORDER BY views DESC, country
LIMIT 15;

SELECT source, medium, campaign, SUM(views) AS views
FROM acquisition_page_views
WHERE day >= date('now', '-29 days') AND source <> 'qa'
GROUP BY source, medium, campaign
ORDER BY views DESC, source, campaign
LIMIT 20;

SELECT
  COALESCE(SUM(CASE WHEN event_name = 'raid_data_download' THEN events ELSE 0 END), 0) AS data_downloads,
  COALESCE(SUM(CASE WHEN event_name = 'widget_embed_code_copy' THEN events ELSE 0 END), 0) AS widget_code_copies,
  COALESCE(SUM(CASE WHEN event_name = 'embed_full_route_click' THEN events ELSE 0 END), 0) AS embed_route_clicks,
  COALESCE(SUM(CASE WHEN event_name = 'raid_plan_share_copy' THEN events ELSE 0 END), 0) AS share_copies,
  COALESCE(SUM(CASE WHEN event_name = 'raid_shared_route_open' THEN events ELSE 0 END), 0) AS shared_route_opens,
  COALESCE(SUM(CASE WHEN event_name = 'live_account_cta_click' THEN events ELSE 0 END), 0) AS account_entries,
  COALESCE(SUM(CASE WHEN event_name = 'checkout_start' THEN events ELSE 0 END), 0) AS checkout_starts,
  COALESCE(SUM(CASE WHEN event_name = 'payment_capture_success' THEN events ELSE 0 END), 0) AS payment_successes,
  COALESCE(SUM(CASE WHEN event_name = 'answer_ready' THEN events ELSE 0 END), 0) AS answers_ready,
  COALESCE(SUM(events), 0) AS tracked_events
FROM conversion_events
WHERE day >= date('now', '-29 days') AND source <> 'qa';

SELECT event_name, SUM(events) AS events
FROM conversion_events
WHERE day >= date('now', '-29 days') AND source <> 'qa'
GROUP BY event_name
ORDER BY events DESC, event_name
LIMIT 20;

SELECT source, medium, campaign, SUM(events) AS events
FROM conversion_events
WHERE day >= date('now', '-29 days') AND source <> 'qa'
GROUP BY source, medium, campaign
ORDER BY events DESC, source, campaign
LIMIT 20;
`;

function parseJsonOutput(output) {
  const starts = [output.indexOf("["), output.indexOf("{")].filter((index) => index >= 0);
  if (!starts.length) throw new Error("Wrangler did not return JSON query results.");
  return JSON.parse(output.slice(Math.min(...starts)));
}

const configuredWrangler = process.env.RAIDBENCH_WRANGLER_BIN?.trim();
const useProjectWrangler = !configuredWrangler && fs.existsSync(projectWrangler);
const command = configuredWrangler || (useProjectWrangler ? projectWrangler : "npx");
const commandPrefix = command === "npx" ? ["--yes", "wrangler@4.127.1"] : [];
const output = execFileSync(
  command,
  [...commandPrefix, "d1", "execute", databaseName, "--remote", "--json", "--command", queries],
  {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
    maxBuffer: 10 * 1024 * 1024,
  },
);
const payload = parseJsonOutput(output);
const resultSets = (Array.isArray(payload) ? payload : [payload]).map((entry) => entry.results || []);
const [summaryRows = [], daily = [], topPages = [], referrers = [], countries = [], acquisitionSources = [], funnelRows = [], topEvents = [], campaigns = []] = resultSets;
const summary = summaryRows[0] || { today: 0, last_7_days: 0, last_30_days: 0, measured_pages: 0 };
const funnel = funnelRows[0] || { account_entries: 0, checkout_starts: 0, payment_successes: 0, answers_ready: 0, tracked_events: 0 };

const dashboard = {
  generatedAt: new Date().toISOString(),
  source: "RaidBench first-party aggregate analytics",
  periodDays: 30,
  metrics: {
    today: Number(summary.today || 0),
    last7Days: Number(summary.last_7_days || 0),
    last30Days: Number(summary.last_30_days || 0),
    measuredPages: Number(summary.measured_pages || 0),
  },
  daily: daily.map((row) => ({ day: row.day, views: Number(row.views || 0) })),
  topPages: topPages.map((row) => ({ path: row.path, views: Number(row.views || 0) })),
  referrers: referrers.map((row) => ({ host: row.referrer_host, views: Number(row.views || 0) })),
  countries: countries.map((row) => ({ country: row.country, views: Number(row.views || 0) })),
  acquisitionSources: acquisitionSources.map((row) => ({
    source: row.source,
    medium: row.medium,
    campaign: row.campaign,
    views: Number(row.views || 0),
  })),
  funnel: {
    dataDownloads: Number(funnel.data_downloads || 0),
    widgetCodeCopies: Number(funnel.widget_code_copies || 0),
    embedRouteClicks: Number(funnel.embed_route_clicks || 0),
    shareCopies: Number(funnel.share_copies || 0),
    sharedRouteOpens: Number(funnel.shared_route_opens || 0),
    accountEntries: Number(funnel.account_entries || 0),
    checkoutStarts: Number(funnel.checkout_starts || 0),
    paymentSuccesses: Number(funnel.payment_successes || 0),
    answersReady: Number(funnel.answers_ready || 0),
    trackedEvents: Number(funnel.tracked_events || 0),
  },
  topEvents: topEvents.map((row) => ({ name: row.event_name, events: Number(row.events || 0) })),
  campaigns: campaigns.map((row) => ({
    source: row.source,
    medium: row.medium,
    campaign: row.campaign,
    events: Number(row.events || 0),
  })),
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(dashboard, null, 2)}\n`);
console.log(`Updated ${outputPath}`);
