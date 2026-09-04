import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const games = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8")).games;
const registry = JSON.parse(fs.readFileSync(path.join(root, "content", "source-registry.json"), "utf8"));
const gameIds = new Set(games.map((game) => game.id));
const sourceIds = new Set(registry.sources.map((source) => source.id));

assert.equal(gameIds.size, 12);
assert.equal(sourceIds.size, registry.sources.length);
assert.equal(registry.policy.communityIsDemandOnly, true);
assert.equal(registry.policy.redditDataApiAllowed, false);
assert.equal(registry.policy.bulkCommunityScrapingAllowed, false);
assert.equal(registry.policy.automaticExternalPostingAllowed, false);
assert.equal(registry.sources.some((source) => source.sourceType === "reddit-json"), false);

for (const gameId of gameIds) {
  const sources = registry.sources.filter((source) => source.gameId === gameId);
  const facts = sources.filter((source) => source.role === "fact");
  const demand = sources.filter((source) => source.role === "demand");
  assert.ok(facts.length >= 2, `${gameId} needs at least two factual sources`);
  assert.equal(demand.length, 1, `${gameId} needs one demand profile`);
  assert.equal(demand[0].fetchMode, "search-only");
  assert.equal(demand[0].generationEligible, false);
  assert.ok(demand[0].redditCommunities.length >= 1);
  assert.match(demand[0].steamAppId, /^[0-9]+$/);
  assert.ok(demand[0].topics.length >= 5);
  for (const source of sources) {
    assert.ok(source.url.startsWith("https://"));
    if (source.role === "fact") assert.notEqual(source.authority, "community");
  }
}

assert.deepEqual(
  registry.sources.filter((source) => source.generationEligible).map((source) => source.gameId).sort(),
  ["poe2", "poe2", "rust", "rust"],
);

console.log("Multi-game source registry tests passed.");
