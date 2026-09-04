import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const outputDir = path.join(root, "operations");
const contentDir = path.join(root, "content");

function loadGuides(file, game, hubUrl) {
  const guides = JSON.parse(fs.readFileSync(path.join(contentDir, file), "utf8"));
  return guides
    .filter((guide) => !/(paid|product|credit|audit-product)/i.test(guide.slug))
    .map((guide) => ({ ...guide, game, hubUrl }));
}

const guides = [
  ...loadGuides("rust-problem-guides.json", "Rust", "/"),
  ...loadGuides("poe2-problem-guides.json", "POE2", "/poe2.html"),
  ...loadGuides("palworld-problem-guides.json", "Palworld", "/palworld.html"),
];

function inferIntent(guide) {
  const text = `${guide.slug} ${guide.title} ${guide.description} ${guide.problem || ""}`.toLowerCase();
  if (/calculator|cost|sulfur|price|value|scorecard|planner|route/.test(text)) return "tool_or_scorecard";
  if (/why|fix|dying|decay|fail|problem|outdated|risk/.test(text)) return "troubleshooting";
  if (/checklist|prep|prepare|review/.test(text)) return "checklist";
  if (/vs|compare|which|cheapest|best/.test(text)) return "comparison";
  return "definition";
}

function inferRefreshTrigger(guide) {
  const text = `${guide.slug} ${guide.title} ${guide.description}`.toLowerCase();
  if (/poe2|build|item|currency|boss|route|filter/.test(text)) return "major patch, economy change, or repeated community question";
  if (/rust|raid|cost|sulfur|upkeep|decay|door|wall/.test(text)) return "Rust patch, item damage change, upkeep change, or wipe-meta shift";
  if (/palworld|base|boss|breeding|resource/.test(text)) return "Palworld update, balance change, or repeated base/progression question";
  return "source update or Search Console query movement";
}

function inferConversionPath(guide) {
  if (guide.game === "POE2") return "future POE2 audit credits after checkout is ready";
  if (guide.game === "Rust") return "future Rust raid-prep credits or worksheet pack after checkout is ready";
  return "future Palworld operations audit credits after checkout is ready";
}

function riskLevel(guide) {
  const text = `${guide.slug} ${guide.title} ${guide.description}`.toLowerCase();
  if (/paid|audit|product/.test(text)) return "yellow";
  if (/exploit|bug|cheat|rmt|boost/.test(text)) return "red";
  return "green";
}

const opportunities = guides.map((guide, index) => ({
  id: `geo_${String(index + 1).padStart(4, "0")}`,
  project: "RaidBench",
  audience: "English-speaking game players searching for practical help",
  game: guide.game,
  entity: guide.title,
  problem: guide.problem || guide.description,
  intent_type: inferIntent(guide),
  source_evidence: (guide.sources || []).join("; "),
  answer_asset: `/pages/${guide.slug}.html`,
  hub_asset: guide.hubUrl,
  risk_level: riskLevel(guide),
  distribution_channel: "owned_site",
  conversion_path: inferConversionPath(guide),
  refresh_trigger: inferRefreshTrigger(guide),
  status: "owned_page_ready",
}));

fs.writeFileSync(
  path.join(contentDir, "geo-opportunity-map.json"),
  `${JSON.stringify({ generatedAt: new Date().toISOString(), opportunities }, null, 2)}\n`,
);

const csvHeader = [
  "id",
  "game",
  "intent_type",
  "risk_level",
  "problem",
  "answer_asset",
  "conversion_path",
  "refresh_trigger",
  "status",
];
const csvRows = opportunities.map((item) =>
  csvHeader
    .map((key) => `"${String(item[key] || "").replaceAll('"', '""')}"`)
    .join(","),
);
fs.writeFileSync(path.join(outputDir, "geo-opportunity-map.csv"), `${csvHeader.join(",")}\n${csvRows.join("\n")}\n`);

const calendarRows = opportunities.slice(0, 30).map((item, index) => {
  const day = String(index + 1).padStart(2, "0");
  return [
    `2026-08-${day}`,
    "owned_site_update",
    item.game,
    item.entity,
    item.answer_asset,
    index < 10 ? "planned" : "backlog",
    item.risk_level,
    "Improve short answer, FAQ-style headings, source note, and internal links.",
    "",
    "",
  ]
    .map((value) => `"${String(value).replaceAll('"', '""')}"`)
    .join(",");
});

const calendarHeader = "date,channel,game,title_or_topic,target_url,status,risk_level,owner_notes,result_url,metrics_notes";
fs.writeFileSync(
  path.join(outputDir, "geo-30-day-calendar.csv"),
  `${calendarHeader}\n${calendarRows.join("\n")}\n`,
);

const summary = [
  "# RaidBench GEO Operating Map",
  "",
  `Generated at: ${new Date().toISOString()}`,
  "",
  `Total owned opportunities: ${opportunities.length}`,
  "",
  "## By Game",
  "",
  ...Object.entries(
    opportunities.reduce((acc, item) => {
      acc[item.game] = (acc[item.game] || 0) + 1;
      return acc;
    }, {}),
  ).map(([game, count]) => `- ${game}: ${count}`),
  "",
  "## By Intent",
  "",
  ...Object.entries(
    opportunities.reduce((acc, item) => {
      acc[item.intent_type] = (acc[item.intent_type] || 0) + 1;
      return acc;
    }, {}),
  ).map(([intent, count]) => `- ${intent}: ${count}`),
  "",
  "## Next Use",
  "",
  "- Use `content/geo-opportunity-map.json` as Agent input.",
  "- Use `operations/geo-opportunity-map.csv` for owner review.",
  "- Use `operations/geo-30-day-calendar.csv` as the next owned-site update queue.",
  "- External posts still require `operations/geo-publishing-guardrails.md`.",
  "",
].join("\n");

fs.writeFileSync(path.join(outputDir, "geo-operating-map-summary.md"), summary);

console.log(`Generated ${opportunities.length} GEO opportunities.`);
