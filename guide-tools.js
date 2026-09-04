(function () {
  const number = new Intl.NumberFormat("en-US");

  function track(name, params = {}) {
    window.RaidBenchAnalytics?.track(name, params);
  }

  async function revealLiveCommerce() {
    const nodes = document.querySelectorAll("[data-live-commerce]");
    if (!nodes.length) return;

    try {
      const response = await fetch("/api/config", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      const apiConfig = await response.json();
      if (!window.RAIDBENCH_CONFIG?.isLiveCommerceReady?.(apiConfig)) return;
      nodes.forEach((node) => { node.hidden = false; });
    } catch {
      // Paid entry points remain hidden if readiness cannot be verified.
    }
  }

  function bindBreakEvenCalculator() {
    document.querySelectorAll("[data-break-even-calculator]").forEach((calculator) => {
      const cost = calculator.querySelector("[data-break-even-cost]");
      const loot = calculator.querySelector("[data-break-even-loot]");
      const loss = calculator.querySelector("[data-break-even-loss]");
      const result = calculator.querySelector("[data-break-even-result]");
      const verdict = calculator.querySelector("[data-break-even-verdict]");

      function update() {
        const net = Math.max(0, Number(loot.value) || 0)
          - Math.max(0, Number(cost.value) || 0)
          - Math.max(0, Number(loss.value) || 0);
        const sign = net > 0 ? "+" : net < 0 ? "-" : "";
        result.textContent = `${sign}${number.format(Math.abs(Math.round(net)))} sulfur equivalent`;
        verdict.textContent = net > 0
          ? "Above resource break-even; now account for time, counters, and strategic value."
          : net < 0
            ? "Below resource break-even before time and counter risk."
            : "At resource break-even before time and counter risk.";
      }

      calculator.addEventListener("input", update);
      calculator.addEventListener("change", () => {
        update();
        track("break_even_calculated");
      });
      update();
    });
  }

  document.querySelectorAll("[data-commerce-cta]").forEach((link) => {
    link.addEventListener("click", () => track("live_account_cta_click"));
  });
  bindBreakEvenCalculator();
  revealLiveCommerce();
})();
