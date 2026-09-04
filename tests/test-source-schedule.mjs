import assert from "node:assert/strict";
import { latestScheduledAt, selectDueSources } from "../scripts/source-schedule.mjs";

const runAt = new Date("2026-09-04T12:10:20Z");
assert.equal(latestScheduledAt(runAt, 10).toISOString(), "2026-09-04T12:10:00.000Z");
assert.equal(latestScheduledAt(runAt, 12).toISOString(), "2026-09-04T11:12:00.000Z");

const sources = [
  { id: "on-time", minuteOffsetUtc: 10, lastSuccessfulAt: "2026-09-04T11:10:30Z", lastAttemptAt: "2026-09-04T11:10:30Z" },
  { id: "future-slot", minuteOffsetUtc: 12, lastSuccessfulAt: "2026-09-04T11:12:20Z", lastAttemptAt: "2026-09-04T11:12:20Z" },
  { id: "already-done", minuteOffsetUtc: 8, lastSuccessfulAt: "2026-09-04T12:08:20Z", lastAttemptAt: "2026-09-04T12:08:20Z" },
];
const regular = selectDueSources(sources, runAt, { maxSourcesPerRun: 2 });
assert.deepEqual(regular.selected.map((source) => source.id), ["on-time"]);

const backlog = [
  { id: "slot-six", minuteOffsetUtc: 6, lastSuccessfulAt: "2026-09-04T10:06:20Z", lastAttemptAt: "2026-09-04T10:06:20Z" },
  { id: "slot-eight", minuteOffsetUtc: 8, lastSuccessfulAt: "2026-09-04T10:08:20Z", lastAttemptAt: "2026-09-04T10:08:20Z" },
  { id: "slot-ten", minuteOffsetUtc: 10, lastSuccessfulAt: "2026-09-04T10:10:20Z", lastAttemptAt: "2026-09-04T10:10:20Z" },
];
const capped = selectDueSources(backlog, runAt, { maxSourcesPerRun: 2 });
assert.equal(capped.due.length, 3);
assert.deepEqual(capped.selected.map((source) => source.id), ["slot-six", "slot-eight"]);
assert.deepEqual(capped.deferred.map((source) => source.id), ["slot-ten"]);

const retry = selectDueSources([
  { id: "recent-failure", minuteOffsetUtc: 10, lastSuccessfulAt: "2026-09-04T10:10:20Z", lastAttemptAt: "2026-09-04T12:10:05Z" },
], runAt, { retryBackoffMinutes: 15 });
assert.equal(retry.selected.length, 0);

console.log("Staggered source schedule tests passed.");
