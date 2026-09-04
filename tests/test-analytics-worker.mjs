import assert from "node:assert/strict";
import worker from "../_worker.js";

class FakeDatabase {
  constructor(batchResults = null) {
    this.statements = [];
    this.batches = [];
    this.batchResults = batchResults;
  }

  prepare(sql) {
    const statement = {
      sql,
      values: [],
      bind: (...values) => {
        statement.values = values;
        return statement;
      },
    };
    this.statements.push(statement);
    return statement;
  }

  async batch(statements) {
    this.batches.push(statements);
    if (this.batchResults) return this.batchResults;
    return statements.map(() => ({ success: true }));
  }
}

const assets = {
  fetch: async () => new Response("asset", { status: 200 }),
};

{
  const db = new FakeDatabase();
  const request = new Request("https://raidbench.com/api/analytics/pageview", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: "https://raidbench.com",
    },
    body: JSON.stringify({ path: "/pages/rust-solo-raid-guide.html", referrerHost: "google.com" }),
  });
  const result = await worker.fetch(request, { ANALYTICS_DB: db, ASSETS: assets });
  assert.equal(result.status, 204);
  assert.equal(db.batches.length, 1);
  assert.equal(db.statements[0].values[1], "/pages/rust-solo-raid-guide.html");
  assert.equal(db.statements[0].values[2], "google.com");
  assert.match(db.statements[1].sql, /acquisition_page_views/);
  assert.deepEqual(db.statements[1].values.slice(2, 5), ["google.com", "referral", "none"]);
}

{
  const db = new FakeDatabase();
  const request = new Request("https://raidbench.com/api/analytics/pageview", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: "https://raidbench.com",
    },
    body: JSON.stringify({
      path: "/rust-raid-plan",
      referrerHost: "direct",
      source: "reddit_profile",
      medium: "owned_profile",
      campaign: "first_sale_launch",
    }),
  });
  const result = await worker.fetch(request, { ANALYTICS_DB: db, ASSETS: assets });
  assert.equal(result.status, 204);
  assert.deepEqual(db.statements[1].values.slice(1, 6), [
    "/rust-raid-plan",
    "reddit_profile",
    "owned_profile",
    "first_sale_launch",
    "XX",
  ]);
}

{
  const db = new FakeDatabase();
  const request = new Request("https://raidbench.com/api/analytics/event", {
    method: "POST",
    headers: { Origin: "https://raidbench.com" },
    body: JSON.stringify({ eventName: "raid_plan_share_copy", pagePath: "/" }),
  });
  const result = await worker.fetch(request, { ANALYTICS_DB: db, ASSETS: assets });
  assert.equal(result.status, 204);
  assert.equal(db.statements[0].values[1], "raid_plan_share_copy");
}

{
  const db = new FakeDatabase();
  const request = new Request("https://raidbench.pages.dev/api/analytics/pageview", {
    method: "POST",
    body: JSON.stringify({ path: "/", referrerHost: "direct" }),
  });
  const result = await worker.fetch(request, { ANALYTICS_DB: db, ASSETS: assets });
  assert.equal(result.status, 204);
  assert.equal(db.batches.length, 0);
}

{
  const db = new FakeDatabase();
  const result = await worker.fetch(
    new Request("https://raidbench.com/api/analytics/summary"),
    { ANALYTICS_DB: db, ASSETS: assets, RAIDBENCH_ORIGIN_KEY: "private-test-key" },
  );
  assert.equal(result.status, 404);
  assert.equal(db.batches.length, 0);
}

{
  const db = new FakeDatabase([
    { results: [{ today: 9, yesterday: 7, last_7_days: 44, last_30_days: 180, measured_pages: 31 }] },
    { results: [{ day: "2026-09-04", views: 9 }] },
    { results: [{ path: "/games/poe2/", views: 12 }] },
    { results: [{ referrer_host: "google.com", views: 5 }] },
    { results: [{ account_entries: 2, checkout_starts: 1, payment_successes: 0, tracked_events: 18 }] },
  ]);
  const result = await worker.fetch(
    new Request("https://raidbench.com/api/analytics/summary", {
      headers: { "X-RaidBench-Analytics-Key": "private-test-key" },
    }),
    { ANALYTICS_DB: db, ASSETS: assets, RAIDBENCH_ORIGIN_KEY: "private-test-key" },
  );
  const body = await result.json();
  assert.equal(result.status, 200);
  assert.equal(body.metrics.today, 9);
  assert.equal(body.metrics.yesterday, 7);
  assert.equal(body.topPages[0].path, "/games/poe2/");
  assert.equal(body.funnel.checkoutStarts, 1);
  assert.equal(db.batches.length, 1);
}

{
  const db = new FakeDatabase();
  const request = new Request("https://raidbench.com/api/analytics/event", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: "https://raidbench.com",
    },
    body: JSON.stringify({
      eventName: "checkout_start",
      pagePath: "/customer",
      source: "reddit",
      medium: "community",
      campaign: "rust_fast_vs_efficient",
    }),
  });
  const result = await worker.fetch(request, { ANALYTICS_DB: db, ASSETS: assets });
  assert.equal(result.status, 204);
  assert.equal(db.batches.length, 1);
  assert.match(db.statements[0].sql, /conversion_events/);
  assert.deepEqual(db.statements[0].values.slice(1, 6), [
    "checkout_start",
    "/customer",
    "reddit",
    "community",
    "rust_fast_vs_efficient",
  ]);
}

{
  const db = new FakeDatabase();
  const request = new Request("https://raidbench.com/api/analytics/event", {
    method: "POST",
    headers: { Origin: "https://raidbench.com" },
    body: JSON.stringify({ eventName: "email_address", pagePath: "/customer" }),
  });
  const result = await worker.fetch(request, { ANALYTICS_DB: db, ASSETS: assets });
  assert.equal(result.status, 400);
  assert.equal(db.batches.length, 0);
}

{
  const db = new FakeDatabase();
  const request = new Request("https://raidbench.com/api/analytics/pageview", {
    method: "POST",
    headers: { Origin: "https://example.com" },
    body: JSON.stringify({ path: "/", referrerHost: "direct" }),
  });
  const result = await worker.fetch(request, { ANALYTICS_DB: db, ASSETS: assets });
  assert.equal(result.status, 403);
  assert.equal(db.batches.length, 0);
}

{
  let assetCalls = 0;
  const result = await worker.fetch(
    new Request("https://raidbench.com/draft-review/withdrawn-token"),
    {
      ANALYTICS_DB: new FakeDatabase(),
      ASSETS: { fetch: async () => { assetCalls += 1; return new Response("asset"); } },
    },
  );
  assert.equal(result.status, 410);
  assert.equal(result.headers.get("x-robots-tag"), "noindex, nofollow, noarchive");
  assert.equal(assetCalls, 0);
}

{
  const result = await worker.fetch(new Request("https://raidbench.com/guides.html"), {
    ANALYTICS_DB: new FakeDatabase(),
    ASSETS: assets,
  });
  assert.equal(result.status, 200);
  assert.equal(await result.text(), "asset");
}

console.log("Analytics worker tests passed.");
