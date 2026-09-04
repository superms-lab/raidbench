import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const activate = process.argv.includes("--activate");
const baselinePath = path.join(root, "content", "multigame-baseline-guides.json");
const gameRegistryPath = path.join(root, "content", "game-registry.json");
const baseline = JSON.parse(fs.readFileSync(baselinePath, "utf8"));
const registry = JSON.parse(fs.readFileSync(gameRegistryPath, "utf8"));
const sources = JSON.parse(fs.readFileSync(path.join(root, "content", "source-registry.json"), "utf8")).sources;
const packets = JSON.parse(fs.readFileSync(path.join(root, "content", "inbox", "multigame-source-packets-2026-09-03.json"), "utf8")).packets;
const packetByGame = new Map(packets.map((packet) => [packet.gameId, packet]));
const sourceById = new Map(sources.map((source) => [source.id, source]));
const newGames = registry.games.filter((game) => !["rust", "poe2", "palworld"].includes(game.id));
const packByGame = new Map(baseline.packs.map((pack) => [pack.gameId, pack]));
const errors = [];

for (const game of newGames) {
  const pack = packByGame.get(game.id);
  const packet = packetByGame.get(game.id);
  if (!pack || pack.guides?.length !== 6) {
    errors.push(`${game.id}: expected six baseline guides`);
    continue;
  }
  if (!packet || packet.factSources?.length < 2) errors.push(`${game.id}: missing two factual sources`);
  for (const source of packet?.factSources || []) {
    const registered = sourceById.get(source.id);
    if (!registered || registered.role !== "fact" || registered.authority === "community") {
      errors.push(`${game.id}: invalid factual source ${source.id}`);
    }
  }
  if (packet?.demandSignal && pack.guides.filter((guide) => guide.usesDemandSignal).length !== 1) {
    errors.push(`${game.id}: exactly one guide must acknowledge the available demand signal`);
  }
  if (!packet?.demandSignal && pack.guides.some((guide) => guide.usesDemandSignal)) {
    errors.push(`${game.id}: guide claims a missing demand signal`);
  }
  const packSlugs = new Set(pack.guides.map((guide) => guide.slug));
  for (const guide of pack.guides) {
    if (!guide.slug.startsWith(`${game.id}-`)) errors.push(`${guide.slug}: slug must start with game id`);
    if (guide.answer.length < 80 || guide.description.length < 50) errors.push(`${guide.slug}: answer or description is too thin`);
    if (guide.checklist.length < 4 || guide.decisionRows.length < 3 || guide.mistakes.length < 3) errors.push(`${guide.slug}: incomplete decision structure`);
    if (!guide.related.every((slug) => packSlugs.has(slug) && slug !== guide.slug)) errors.push(`${guide.slug}: invalid related links`);
    const page = path.join(root, "pages", `${guide.slug}.html`);
    if (!fs.existsSync(page)) {
      errors.push(`${guide.slug}: generated page missing`);
      continue;
    }
    const html = fs.readFileSync(page, "utf8");
    if (!html.includes(`Reviewed ${baseline.reviewedAt}`)) errors.push(`${guide.slug}: visible review date missing`);
    if (/data-live-commerce|Get a verified answer|Buy credits/i.test(html)) errors.push(`${guide.slug}: paid entry must remain closed`);
    if (!/<h1>[^<]+<\/h1>/.test(html) || !/application\/ld\+json/.test(html)) errors.push(`${guide.slug}: missing article structure`);
  }
}

if (packByGame.size !== newGames.length) errors.push("Baseline pack count does not match the nine new games");
if (errors.length) {
  for (const error of errors) console.error(`ERROR: ${error}`);
  console.error(`Multi-game launch gate failed with ${errors.length} error(s).`);
  process.exit(1);
}

if (activate) {
  for (const game of registry.games) {
    if (!["rust", "poe2", "palworld"].includes(game.id)) {
      game.status = "live";
      game.indexable = true;
    }
  }
  fs.writeFileSync(gameRegistryPath, `${JSON.stringify(registry, null, 2)}\n`);
}

console.log(`Multi-game launch gate passed for ${newGames.length} games and ${baseline.packs.reduce((sum, pack) => sum + pack.guides.length, 0)} guides${activate ? "; registry activated" : ""}.`);
