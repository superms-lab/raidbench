(function () {
  const configNode = document.querySelector("#tool-config");
  const tool = document.querySelector("[data-multigame-tool]");
  if (!configNode || !tool || !window.RaidBenchToolEngine) return;
  const config = JSON.parse(configNode.textContent);
  const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
  let latestResult = null;

  function values() {
    const result = {};
    tool.querySelectorAll("[data-field]").forEach((input) => {
      result[input.dataset.field] = input.type === "text" ? input.value.trim() : Number(input.value);
    });
    return result;
  }

  function display(value, unit = "") {
    const rendered = typeof value === "number" ? number.format(value) : String(value);
    return unit ? `${rendered} ${unit}` : rendered;
  }

  function update() {
    latestResult = window.RaidBenchToolEngine.calculate(config, values());
    tool.querySelector("[data-primary-label]").textContent = latestResult.primaryLabel;
    tool.querySelector("[data-primary-result]").textContent = display(latestResult.primary, latestResult.primaryUnit);
    tool.querySelector("[data-result-verdict]").textContent = latestResult.verdict;
    tool.querySelector("[data-result-metrics]").innerHTML = latestResult.metrics
      .map((item) => `<div><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(display(item.value, item.unit))}</strong></div>`)
      .join("");
    tool.querySelector("[data-result-breakdown]").innerHTML = latestResult.breakdown
      .map((item) => `<tr><td>${escapeHtml(item[0])}</td><td>${escapeHtml(display(item[1]))}</td></tr>`)
      .join("");
  }

  function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  function resultPayload() {
    return {
      schemaVersion: "1.0.0",
      toolId: config.id,
      gameId: config.gameId,
      calculatedAt: new Date().toISOString(),
      inputs: values(),
      result: latestResult,
      assumptions: config.assumptions,
      reviewedAt: config.reviewedAt,
    };
  }

  async function copySummary(button) {
    const payload = resultPayload();
    const metrics = payload.result.metrics.map((item) => `${item.label}: ${display(item.value, item.unit)}`).join("\n");
    await navigator.clipboard.writeText(`${config.title}\n${payload.result.primaryLabel}: ${display(payload.result.primary, payload.result.primaryUnit)}\n${metrics}\n${payload.result.verdict}\nReviewed ${config.reviewedAt}`);
    const original = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => { button.textContent = original; }, 1400);
    window.RaidBenchAnalytics?.track("multigame_tool_copy", { game: config.gameId, tool: config.id });
  }

  async function copyShareLink(button) {
    const url = new URL(window.location.href);
    url.search = "";
    Object.entries(values()).forEach(([key, value]) => url.searchParams.set(key, String(value)));
    url.searchParams.set("utm_source", "tool_share");
    url.searchParams.set("utm_medium", "owned_tool");
    url.searchParams.set("utm_campaign", config.slug);
    await navigator.clipboard.writeText(url.toString());
    const original = button.textContent;
    button.textContent = "Link copied";
    setTimeout(() => { button.textContent = original; }, 1400);
    window.RaidBenchAnalytics?.track("multigame_tool_share", { game: config.gameId, tool: config.id });
  }

  const query = new URLSearchParams(window.location.search);
  tool.querySelectorAll("[data-field]").forEach((input) => {
    if (query.has(input.dataset.field)) input.value = query.get(input.dataset.field);
  });
  tool.addEventListener("input", update);
  tool.addEventListener("change", () => {
    update();
    window.RaidBenchAnalytics?.track("multigame_tool_calculate", { game: config.gameId, tool: config.id });
  });
  tool.querySelector("[data-copy-result]")?.addEventListener("click", (event) => copySummary(event.currentTarget));
  tool.querySelector("[data-download-worksheet]")?.addEventListener("click", () => {
    window.RaidBenchAnalytics?.track("multigame_tool_download", { game: config.gameId, tool: config.id });
  });
  tool.querySelector("[data-copy-share]")?.addEventListener("click", (event) => copyShareLink(event.currentTarget));
  update();
})();
