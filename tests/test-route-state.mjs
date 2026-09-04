import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const context = { window: {} };
vm.runInNewContext(fs.readFileSync("route-state.js", "utf8"), context);

const codec = context.window.RAIDBENCH_ROUTE_STATE;
const route = [
  { targetId: "garage-door", quantity: 2, method: "rockets" },
  { targetId: "stone-wall", qty: 1, method: "c4" },
];

const encoded = codec.encode(route);
assert.equal(encoded, "garage-door~2~rockets,stone-wall~1~c4");
assert.deepEqual(JSON.parse(JSON.stringify(codec.decode(encoded))), [
  { targetId: "garage-door", quantity: 2, method: "rockets" },
  { targetId: "stone-wall", quantity: 1, method: "c4" },
]);
assert.deepEqual(JSON.parse(JSON.stringify(codec.decode("../../etc~1~rockets"))), []);
assert.deepEqual(JSON.parse(JSON.stringify(codec.decode("garage-door~1~unknown"))), []);
assert.equal(codec.decode("garage-door~999~rockets")[0].quantity, 99);

console.log("Route state tests passed.");
