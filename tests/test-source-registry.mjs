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
assert.equal(registry.policy.factCadence, "1h");
assert.equal(registry.policy.factIntervalMinutes, 2);
assert.equal(registry.policy.maxFactSourcesPerRun, 2);
assert.equal(registry.policy.publisherMinuteUtc, 55);
assert.equal(registry.policy.demandCadence, "24h");
assert.equal(registry.sources.some((source) => source.sourceType === "reddit-json"), false);

for (const gameId of gameIds) {
  const sources = registry.sources.filter((source) => source.gameId === gameId);
  const facts = sources.filter((source) => source.role === "fact");
  const demand = sources.filter((source) => source.role === "demand");
  assert.ok(facts.length >= 2, `${gameId} needs at least two factual sources`);
  assert.equal(demand.length, 1, `${gameId} needs one demand profile`);
  assert.equal(demand[0].fetchMode, "search-only");
  assert.equal(demand[0].cadence, registry.policy.demandCadence);
  assert.equal("minuteOffsetUtc" in demand[0], false);
  assert.equal(demand[0].generationEligible, false);
  assert.ok(demand[0].redditCommunities.length >= 1);
  assert.match(demand[0].steamAppId, /^[0-9]+$/);
  assert.ok(demand[0].topics.length >= 5);
  for (const source of sources) {
    assert.ok(source.url.startsWith("https://"));
    if (source.role === "fact") {
      assert.notEqual(source.authority, "community");
      assert.equal(source.cadence, registry.policy.factCadence, `${source.id} must match the Rust hourly fact cadence`);
      assert.equal(Number.isInteger(source.minuteOffsetUtc), true);
    }
  }
}

const facts = registry.sources.filter((source) => source.role === "fact");
assert.deepEqual(facts.map((source) => source.minuteOffsetUtc), Array.from({ length: 25 }, (_, index) => index * 2));
assert.equal(new Set(facts.map((source) => source.minuteOffsetUtc)).size, 25);
assert.equal(facts.filter((source) => source.generationEligible).length, 24);
assert.equal(registry.sources.find((source) => source.id === "rust-commit-stream").generationEligible, false);
for (const gameId of gameIds) {
  assert.equal(
    registry.sources.filter((source) => source.gameId === gameId && source.role === "fact" && source.generationEligible).length,
    2,
    `${gameId} needs two publication-eligible factual sources`,
  );
}

console.log("Multi-game source registry tests passed.");
