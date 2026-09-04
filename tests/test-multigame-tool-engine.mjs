import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
const engine = require(path.join(process.cwd(), "multi-game-tool-engine.js"));
const config = JSON.parse(fs.readFileSync(path.join(process.cwd(), "content", "multigame-tools.json"), "utf8"));
const byFormula = new Map(config.tools.map((tool) => [tool.formula, tool]));

assert.equal(config.tools.length, 9);
assert.equal(new Set(config.tools.map((tool) => tool.gameId)).size, 9);
assert.equal(new Set(config.tools.map((tool) => tool.slug)).size, 9);

const lowRisk = engine.calculate(byFormula.get("save-change-risk"), {
  saveImportance: 1, modCount: 0, changeScope: 1, compatibilityConfidence: 5, backupReady: 1,
});
const highRisk = engine.calculate(byFormula.get("save-change-risk"), {
  saveImportance: 5, modCount: 30, changeScope: 5, compatibilityConfidence: 1, backupReady: 0,
});
assert.equal(lowRisk.primary, 0);
assert.equal(highRisk.primary, 100);

const tarkov = engine.calculate(byFormula.get("tarkov-loadout-budget"), {
  weaponCost: 100, magazines: 2, magazineCost: 10, rounds: 10, roundCost: 2,
  armorCost: 50, supportCost: 10, copies: 2, reservePercent: 10, availableBudget: 500,
});
assert.equal(tarkov.primary, 440);
assert.equal(tarkov.metrics[0].value, 200);
assert.equal(tarkov.metrics[2].value, 0);

const ark = engine.calculate(byFormula.get("ark-roster-materials"), {
  creatures: 2, replacements: 1, hidePerSaddle: 100, fiberPerSaddle: 50,
  metalPerSaddle: 25, reservePercent: 10,
});
assert.deepEqual(ark.metrics.map((item) => item.value), [330, 165, 83]);

const arkIntegerReserve = engine.calculate(byFormula.get("ark-roster-materials"), {
  creatures: 18, replacements: 2, hidePerSaddle: 350, fiberPerSaddle: 180,
  metalPerSaddle: 60, reservePercent: 10,
});
assert.deepEqual(arkIntegerReserve.metrics.map((item) => item.value), [7700, 3960, 1320]);

const cs2 = engine.calculate(byFormula.get("cs2-team-buy-budget"), {
  players: 5, averageCash: 5000, carriedValue: 0, targetKitCost: 4000, nextRoundReserve: 5000,
});
assert.equal(cs2.primary, 0);
assert.equal(cs2.metrics[2].value, 5);

const warframeTool = config.tools.find((tool) => tool.gameId === "warframe");
const comparisonValues = { optionA: "A", optionB: "B" };
for (const criterion of warframeTool.criteria) {
  comparisonValues[`${criterion.id}A`] = 5;
  comparisonValues[`${criterion.id}B`] = 2;
}
const comparison = engine.calculate(warframeTool, comparisonValues);
assert.equal(comparison.primary, "A");
assert.equal(comparison.metrics[0].value, 100);
assert.equal(comparison.metrics[1].value, 40);

const pubg = engine.calculate(byFormula.get("pubg-rotation-timing"), {
  distanceKm: 3, speedKmh: 60, terrainDelay: 1, contactDelay: 1, timeRemaining: 8,
});
assert.equal(pubg.primary, 5);
assert.equal(pubg.metrics[0].value, 3);
assert.equal(pubg.metrics[1].value, 1);

for (const tool of config.tools) {
  const page = fs.readFileSync(path.join(process.cwd(), "tools", tool.slug, "index.html"), "utf8");
  assert.match(page, /<meta name="robots" content="index,follow"/);
  assert.ok(page.includes("data-multigame-tool"));
  assert.ok(page.includes("data-download-worksheet"));
  assert.ok(page.includes("No paid answer offered"));
  assert.equal(/data-live-commerce|Get a verified answer|Buy credits/i.test(page), false);
  const worksheet = JSON.parse(fs.readFileSync(path.join(process.cwd(), "downloads", `${tool.slug}-worksheet.json`), "utf8"));
  assert.equal(worksheet.toolId, tool.id);
  assert.equal(worksheet.gameId, tool.gameId);
}

console.log("Multi-game tool engine and generated page tests passed.");
