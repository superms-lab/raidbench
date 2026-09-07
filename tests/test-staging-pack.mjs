import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const html = read("rust-raid-staging-pack.html");
const script = read("staging-pack.js");
const headers = read("_headers");
const redirects = read("_redirects");
const sitemap = read("sitemap.xml");
const skus = JSON.parse(read("content/skus.json"));
const economics = JSON.parse(read("local/unit-economics-latest.json"));

assert.match(html, /<h1[^>]*>Rust Full Raid Staging Pack<\/h1>/);
assert.match(html, /"price":"4\.99","priceCurrency":"USD"/);
assert.match(html, /No account required/);
assert.match(html, /id="copy-private-report"/);
assert.match(html, /data-view-sample/);
assert.match(html, /id="download-route-card"/);
assert.match(html, /id="route-presets"/);
assert.ok(
  html.indexOf("staging-pack.js") < html.indexOf("analytics.js"),
  "the staging script must strip payment and private-link tokens before analytics loads",
);
assert.match(script, /\/api\/guest\/raid-pack\/preview/);
assert.match(script, /\/api\/guest\/raid-pack\/checkout/);
assert.match(script, /\/api\/guest\/raid-pack\/sample/);
assert.match(script, /staging_pack_card_download/);
assert.match(script, /staging_pack_preset/);
assert.match(script, /#report=/);
assert.match(headers, /\/rust-raid-staging-pack[\s\S]*Referrer-Policy: no-referrer/);
assert.match(redirects, /\/rust-raid-plan \/rust-raid-staging-pack 301/);
assert.match(sitemap, /https:\/\/raidbench\.com\/rust-raid-staging-pack/);
assert.match(read("games/rust/index.html"), /rust-raid-staging-pack/);
assert.ok(!fs.existsSync(path.join(root, "rust-raid-plan.html")));

const stagingSku = skus.packs.find((pack) => pack.sku === "rust-staging-pack-v1");
assert.deepEqual(stagingSku.prices, { USD: 4.99 });
assert.equal(stagingSku.credits, 0);
const stagingEconomics = economics.products.find((product) => product.sku === stagingSku.sku);
assert.equal(stagingEconomics.status, "viable");
assert.ok(stagingEconomics.contributionBeforeFixed > 0);

const rustPages = fs.readdirSync(path.join(root, "pages"))
  .filter((name) => name.startsWith("rust-") && name.endsWith(".html"))
  .map((name) => read(path.join("pages", name)));
assert.ok(rustPages.some((page) => page.includes("data-rust-staging-commerce")));
for (const page of rustPages) {
  assert.doesNotMatch(page, /customer\?intent=/);
  assert.doesNotMatch(page, /Verified Rust answers from \$5/);
}

console.log("Account-free Rust staging pack and conversion-path tests passed.");
