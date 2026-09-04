import assert from "node:assert/strict";
import fs from "node:fs";
import { evaluateSuite } from "../scripts/evaluate-shadow-calculations.mjs";


const blueprints = JSON.parse(fs.readFileSync("content/multigame-shadow-blueprints.json", "utf8"));
const suite = {
  cases: blueprints.blueprints.map((item) => ({
    caseId: `test_${item.gameId}`,
    productId: item.productId,
    calculationFixture: item.calculationFixture,
  })),
};
const report = evaluateSuite(suite);

assert.equal(report.cases, 9);
assert.equal(report.assertions, 28);
assert.equal(report.passed, true);
assert.ok(report.results.every((item) => item.passed));
assert.equal(new Set(report.results.map((item) => item.productId)).size, 9);

const pubg = report.results.find((item) => item.productId === "pubg-battlegrounds-rotation-review");
assert.equal(pubg.assertions.find((item) => item.calculationId === "estimated_route_time").actual, 6.8);

console.log("Shadow calculation fixtures passed for 9 products and 28 assertions.");
