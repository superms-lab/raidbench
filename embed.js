(function () {
  const data = window.RAIDBENCH_RAID_DATA;
  if (!data) return;

  const targetSelect = document.querySelector("#embed-target");
  const methodSelect = document.querySelector("#embed-method");
  const quantityInput = document.querySelector("#embed-quantity");
  const itemsOutput = document.querySelector("#embed-items");
  const sulfurOutput = document.querySelector("#embed-sulfur");
  const gunpowderOutput = document.querySelector("#embed-gunpowder");
  const reviewedOutput = document.querySelector("#embed-reviewed");
  const fullRouteLink = document.querySelector("#embed-full-route");
  const formatNumber = (value) => new Intl.NumberFormat("en-US").format(value);

  targetSelect.innerHTML = data.targets
    .map((target) => `<option value="${target.id}">${target.label}</option>`)
    .join("");
  reviewedOutput.textContent = `Verified ${data.verifiedAt}`;

  function render() {
    const target = data.targets.find((item) => item.id === targetSelect.value) || data.targets[0];
    const method = methodSelect.value;
    const quantity = Math.max(1, Math.min(99, Math.trunc(Number(quantityInput.value) || 1)));
    const itemCount = target[method] * quantity;
    const route = window.RAIDBENCH_ROUTE_STATE?.encode([{ targetId: target.id, quantity, method }]) || "";
    const url = new URL("https://raidbench.com/");
    url.searchParams.set("route", route);
    url.searchParams.set("utm_source", "embed");
    url.searchParams.set("utm_medium", "referral");
    url.searchParams.set("utm_campaign", "rust_widget");
    url.hash = "raid-calculator";

    quantityInput.value = quantity;
    itemsOutput.textContent = formatNumber(itemCount);
    sulfurOutput.textContent = formatNumber(itemCount * data.sulfurPerItem[method]);
    gunpowderOutput.textContent = formatNumber(itemCount * data.gunpowderPerItem[method]);
    fullRouteLink.href = url.toString();
  }

  targetSelect.addEventListener("change", render);
  methodSelect.addEventListener("change", render);
  quantityInput.addEventListener("input", render);
  fullRouteLink.addEventListener("click", () => window.RaidBenchAnalytics?.track("embed_full_route_click"));
  render();
})();
