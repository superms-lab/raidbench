import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const context = { window: {} };
vm.runInNewContext(fs.readFileSync("raid-data.js", "utf8"), context);
const data = context.window.RAIDBENCH_RAID_DATA;
const canonical = JSON.parse(fs.readFileSync("content/rust-raid-data.json", "utf8"));

assert.deepEqual(JSON.parse(JSON.stringify(data)), canonical, "Browser raid data must match the canonical JSON used by the backend");

assert.match(data.verifiedAt, /^\d{4}-\d{2}-\d{2}$/);
assert.equal(data.verification.lastAutomatedCheckAt.slice(0, 10), data.verifiedAt);
assert(data.sources.length >= 2);
assert(data.sources.some((source) => source.url.includes("wiki.facepunch.com")));

assert.deepEqual({ ...data.sulfurPerItem }, { rockets: 1400, c4: 2200, satchels: 480, explosiveAmmo: 25 });
assert.deepEqual({ ...data.gunpowderPerItem }, { rockets: 650, c4: 1000, satchels: 240, explosiveAmmo: 10 });

const expected = {
  "sheet-door": [2, 1, 4, 63],
  "garage-door": [3, 2, 9, 150],
  "armored-door": [5, 3, 15, 250],
  "stone-wall": [4, 2, 10, 185],
  "sheet-wall": [8, 4, 23, 400],
  "armored-wall": [15, 8, 46, 799]
};
for (const target of data.targets) {
  assert.deepEqual(
    [target.rockets, target.c4, target.satchels, target.explosiveAmmo],
    expected[target.id],
    `Unexpected raid counts for ${target.id}`,
  );
}

const defaultPlan = [
  { targetId: "sheet-door", quantity: 2, method: "satchels" },
  { targetId: "stone-wall", quantity: 1, method: "rockets" }
];
const totals = defaultPlan.reduce((sum, item) => {
  const target = data.targets.find((candidate) => candidate.id === item.targetId);
  const count = target[item.method] * item.quantity;
  sum.sulfur += count * data.sulfurPerItem[item.method];
  sum.gunpowder += count * data.gunpowderPerItem[item.method];
  return sum;
}, { sulfur: 0, gunpowder: 0 });
assert.deepEqual(totals, { sulfur: 9440, gunpowder: 4520 });

console.log("Rust raid-data tests passed.");
