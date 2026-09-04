import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const context = { window: {} };
vm.runInNewContext(fs.readFileSync("config.js", "utf8"), context);

const isReady = context.window.RAIDBENCH_CONFIG.isLiveCommerceReady;
const readyConfig = {
  mode: "production",
  checkoutEnabled: true,
  paypalEnvironment: "live",
  paypalWebhookReady: true,
  liveReadiness: {
    merchantIdentityReady: true,
    taxPolicyConfirmed: true,
  },
};

assert.equal(isReady(readyConfig), true);
assert.equal(isReady({ ...readyConfig, paypalEnvironment: "sandbox" }), false);
assert.equal(isReady({ ...readyConfig, checkoutEnabled: false }), false);
assert.equal(
  isReady({
    ...readyConfig,
    liveReadiness: { ...readyConfig.liveReadiness, taxPolicyConfirmed: false },
  }),
  false,
);
assert.equal(isReady(null), false);

const homepage = fs.readFileSync("index.html", "utf8");
assert.match(homepage, /data-live-commerce hidden/);
assert.match(homepage, /href="\.\/customer"/);

console.log("Live commerce gate tests passed.");
