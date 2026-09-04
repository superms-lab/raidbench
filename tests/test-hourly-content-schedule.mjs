import assert from "node:assert/strict";
import fs from "node:fs";

const registry = JSON.parse(fs.readFileSync("content/source-registry.json", "utf8"));
const quotas = JSON.parse(fs.readFileSync("config/growth-quotas.json", "utf8"));
const sourceTimer = fs.readFileSync("deploy/raidbench-source-scout.timer", "utf8");
const publisherTimer = fs.readFileSync("deploy/raidbench-content-agent.timer", "utf8");
const publisherEnvironment = fs.readFileSync("deploy/content-agent.env.example", "utf8");
const publisherPipeline = fs.readFileSync("scripts/run_automatic_content_pipeline.py", "utf8");

const factSources = registry.sources.filter((source) => source.role === "fact");
assert.equal(factSources.length, 25);
assert.deepEqual(factSources.map((source) => source.minuteOffsetUtc), Array.from({ length: 25 }, (_, index) => index * 2));
assert.equal(registry.policy.maxFactSourcesPerRun, 2);
assert.match(sourceTimer, /OnCalendar=\*-\*-\* \*:\*:20/);
assert.doesNotMatch(sourceTimer, /RandomizedDelaySec/);

assert.equal(quotas.publicGuides.hourlyMinimum, 1);
assert.equal(quotas.publicGuides.dailyMinimum, 24);
assert.equal(Object.values(quotas.publicGuides.weeklyMinimum).reduce((sum, value) => sum + value, 0), 168);
assert.ok(Object.values(quotas.publicGuides.weeklyMinimum).every((value) => value === 14));
assert.equal("hourlyMaximum" in quotas.publicGuides, false);
assert.equal("dailyMaximum" in quotas.publicGuides, false);
assert.equal("weekly" in quotas.publicGuides, false);
assert.match(publisherTimer, /OnCalendar=\*-\*-\* \*:05,15,25,35,45,55:30/);
assert.match(publisherEnvironment, /RAIDBENCH_MIN_NEW_GUIDES_PER_HOUR=1/);
assert.match(publisherEnvironment, /RAIDBENCH_MIN_NEW_GUIDES_PER_DAY=24/);
assert.doesNotMatch(publisherEnvironment, /RAIDBENCH_MAX_NEW_GUIDES/);
assert.doesNotMatch(publisherPipeline, /limit_reached|RAIDBENCH_MAX_NEW_GUIDES/);

console.log("Hourly staggered collection and non-blocking publication minimum tests passed.");
