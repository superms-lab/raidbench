const HOUR_MS = 60 * 60 * 1000;

export function latestScheduledAt(runAt, minuteOffsetUtc) {
  const current = new Date(runAt);
  const offset = Number(minuteOffsetUtc);
  if (!Number.isFinite(current.getTime())) throw new Error("Invalid source-schedule run time");
  if (!Number.isInteger(offset) || offset < 0 || offset > 59) {
    throw new Error(`Invalid source minute offset: ${minuteOffsetUtc}`);
  }
  const scheduled = new Date(current);
  scheduled.setUTCMinutes(offset, 0, 0);
  if (scheduled.getTime() > current.getTime()) {
    scheduled.setTime(scheduled.getTime() - HOUR_MS);
  }
  return scheduled;
}

export function selectDueSources(
  sources,
  runAt,
  { forceRun = false, maxSourcesPerRun = 2, retryBackoffMinutes = 15 } = {},
) {
  const now = new Date(runAt);
  const retryBackoffMs = Math.max(0, Number(retryBackoffMinutes)) * 60 * 1000;
  const limit = Math.max(1, Number(maxSourcesPerRun) || 1);
  const due = sources.map((source) => {
    const scheduledAt = latestScheduledAt(now, source.minuteOffsetUtc);
    const lastSuccessfulAt = Date.parse(source.lastSuccessfulAt || "");
    const lastAttemptAt = Date.parse(source.lastAttemptAt || "");
    const missedSchedule = !Number.isFinite(lastSuccessfulAt) || lastSuccessfulAt < scheduledAt.getTime();
    const retryBlocked = Number.isFinite(lastAttemptAt)
      && lastAttemptAt >= scheduledAt.getTime()
      && now.getTime() - lastAttemptAt < retryBackoffMs;
    return { source, scheduledAt, due: forceRun || (missedSchedule && !retryBlocked) };
  }).filter((entry) => entry.due)
    .sort((a, b) => (
      a.scheduledAt.getTime() - b.scheduledAt.getTime()
      || Number(a.source.minuteOffsetUtc) - Number(b.source.minuteOffsetUtc)
      || String(a.source.id).localeCompare(String(b.source.id))
    ));

  return {
    due,
    selected: due.slice(0, limit).map((entry) => entry.source),
    deferred: due.slice(limit).map((entry) => entry.source),
  };
}
