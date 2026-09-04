import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";


const root = process.cwd();
const run = spawnSync(process.execPath, ["scripts/calculate-multigame-product-economics.mjs"], {
  cwd: root,
  encoding: "utf8",
});
assert.equal(run.status, 0, run.stderr || run.stdout);

const catalog = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-products.json"), "utf8"));
const economics = JSON.parse(fs.readFileSync(path.join(root, "local", "multigame-product-economics.json"), "utf8"));

assert.equal(catalog.products.length, 11);
assert.equal(new Set(catalog.products.map((product) => product.id)).size, 11);
assert.deepEqual(catalog.products.filter((product) => product.status === "ready_live").map((product) => product.id), ["palworld-base-progression-review"]);
assert.equal(catalog.products.filter((product) => product.status === "hidden_pending_qa").length, 10);
assert.deepEqual(economics.summary, {
  products: 11,
  checkoutVisible: 1,
  viablePendingQa: 10,
  pricingHolds: 0,
});
assert.equal(economics.provider.percentageFee, 4.4);
assert.equal(economics.provider.fixedFee, 0.3);
assert.equal(economics.scenario.fxAndWithdrawalPercent, 2.5);
assert.equal(economics.monthlyFixedTotal, 78.5);
assert.deepEqual(
  economics.products.find((product) => product.id === "palworld-base-progression-review").minimumSinglePack,
  { sku: "credits-palworld-80", credits: 80, priceUsd: 13 },
);
assert.deepEqual(economics.products.filter((product) => product.checkoutVisible).map((product) => product.id), ["palworld-base-progression-review"]);
assert.equal(economics.products.filter((product) => product.economicStatus === "viable_pending_qa").length, 10);
assert.equal(economics.products.filter((product) => product.economicStatus === "viable_live").length, 1);
assert.ok(economics.products.every((product) => product.contributionMarginPercent >= product.targetMarginPercent));

console.log("Multi-game product economics tests passed for one live and ten hidden products.");
