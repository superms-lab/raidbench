import assert from "node:assert/strict";
import fs from "node:fs";

const source = JSON.parse(fs.readFileSync("content/rust-raid-data.json", "utf8"));
const publicData = JSON.parse(fs.readFileSync("rust-raid-costs.json", "utf8"));
const csv = fs.readFileSync("rust-raid-costs.csv", "utf8").trim().split("\n");

assert.equal(publicData.verifiedAt, source.verifiedAt);
assert.equal(publicData.targets.length, source.targets.length);
assert.equal(csv.length, source.targets.length + 1);
assert.ok(csv[0].includes("rockets_sulfur"));
assert.ok(publicData.sources.every((item) => item.url.startsWith("https://")));

const garageDoor = publicData.targets.find((target) => target.target_id === "garage-door");
assert.equal(garageDoor.rockets, 3);
assert.equal(garageDoor.rockets_sulfur, 4200);
assert.equal(garageDoor.c4_sulfur, 4400);

console.log("Public raid data tests passed.");
