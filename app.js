const { sulfurPerItem, gunpowderPerItem, targets } = window.RAIDBENCH_RAID_DATA;
const routeCodec = window.RAIDBENCH_ROUTE_STATE;

const methodLabels = {
  rockets: "Rockets",
  c4: "C4",
  satchels: "Satchels",
  explosiveAmmo: "Explosive ammo",
};

const raidState = [
  { targetId: "sheet-door", qty: 2, method: "satchels" },
  { targetId: "stone-wall", qty: 1, method: "rockets" },
];

const targetSelect = document.querySelector("#target-select");
const methodSelect = document.querySelector("#method-select");
const targetQty = document.querySelector("#target-qty");
const raidList = document.querySelector("#raid-list");
const raidItems = document.querySelector("#raid-items");
const sulfurTotal = document.querySelector("#sulfur-total");
const gunpowderTotal = document.querySelector("#gunpowder-total");
const targetTable = document.querySelector("#target-table");
const copyRaidLink = document.querySelector("#copy-raid-link");
const shareStatus = document.querySelector("#share-status");
const verifyRaid = document.querySelector("#verify-raid");
const verificationTitle = document.querySelector("#verification-title");
const verificationCopy = document.querySelector("#verification-copy");

const formatNumber = (value) => new Intl.NumberFormat("en-US").format(Math.round(value));

function trackEvent(name, params = {}) {
  window.RaidBenchAnalytics?.track(name, params);
}

async function revealLiveCommerce() {
  const commerceNodes = document.querySelectorAll("[data-live-commerce]");
  if (!commerceNodes.length) return;

  try {
    const response = await fetch("/api/config", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return;

    const apiConfig = await response.json();
    if (!window.RAIDBENCH_CONFIG?.isLiveCommerceReady?.(apiConfig)) return;

    commerceNodes.forEach((node) => {
      node.hidden = false;
    });
  } catch {
    // Commerce stays hidden whenever readiness cannot be verified.
  }
}

function findTarget(targetId) {
  return targets.find((target) => target.id === targetId);
}

function loadSharedRoute() {
  const entries = routeCodec?.decode(new URLSearchParams(window.location.search).get("route")) || [];
  const validEntries = entries.filter((entry) => findTarget(entry.targetId));
  if (!validEntries.length) return;
  raidState.splice(0, raidState.length, ...validEntries.map((entry) => ({
    targetId: entry.targetId,
    qty: entry.quantity,
    method: entry.method,
  })));
  trackEvent("raid_shared_route_open", { rows: raidState.length });
}

function encodedRoute() {
  return routeCodec?.encode(raidState) || "";
}

function sharedRouteUrl() {
  const url = new URL("/", window.location.origin);
  url.searchParams.set("route", encodedRoute());
  url.searchParams.set("utm_source", "share_link");
  url.searchParams.set("utm_medium", "player_share");
  url.searchParams.set("utm_campaign", "rust_raid_route");
  url.hash = "raid-calculator";
  return url.toString();
}

function updateConversionRoute() {
  const rowCount = raidState.length;
  copyRaidLink.disabled = rowCount === 0;
  if (!rowCount) return;

  const intent = rowCount === 1 ? "instant" : "plan";
  const customerUrl = new URL("/customer", window.location.origin);
  customerUrl.searchParams.set("intent", intent);
  customerUrl.searchParams.set("route", encodedRoute());
  customerUrl.searchParams.set("utm_source", "calculator");
  customerUrl.searchParams.set("utm_medium", "internal");
  customerUrl.searchParams.set("utm_campaign", intent === "instant" ? "rust_route_check" : "rust_raid_plan");
  verifyRaid.href = `${customerUrl.pathname}${customerUrl.search}`;
  verifyRaid.textContent = rowCount === 1 ? "Compare this target" : "Review this route";
  verificationTitle.textContent = rowCount === 1
    ? "Want all four methods compared against the boom already in base?"
    : "Want this complete route reviewed before you craft?";
  verificationCopy.textContent = rowCount === 1
    ? "The $5 starter includes two route checks. Each applies your sulfur or placement priority, shows exact shortfalls, and is not charged when current evidence is unsupported."
    : "A $19 plan compares the selected, lower-sulfur, and fewer-placement routes, then adds the buffer and execution checks.";
}

function populateTargets() {
  targetSelect.innerHTML = targets
    .map((target) => `<option value="${target.id}">${target.label}</option>`)
    .join("");

  targetTable.innerHTML = targets
    .map(
      (target) => `
        <tr>
          <td>${target.label}</td>
          <td>${target.rockets}</td>
          <td>${target.c4}</td>
          <td>${target.satchels}</td>
          <td>${target.explosiveAmmo}</td>
        </tr>
      `,
    )
    .join("");
}

function renderRaidList() {
  raidList.innerHTML = raidState
    .map((entry, index) => {
      const target = findTarget(entry.targetId);
      const itemCount = target[entry.method] * entry.qty;
      const sulfur = itemCount * sulfurPerItem[entry.method];

      return `
        <div class="raid-row">
          <div>
            <strong>${entry.qty} x ${target.label}</strong>
            <span>${methodLabels[entry.method]}</span>
          </div>
          <span>${formatNumber(itemCount)} items</span>
          <span>${formatNumber(sulfur)} sulfur</span>
          <button class="remove-row" type="button" data-index="${index}">Remove</button>
        </div>
      `;
    })
    .join("");

  if (!raidState.length) {
    raidList.innerHTML = `<div class="raid-row"><span>Add a target to start planning.</span></div>`;
  }

  updateRaidTotals();
}

function updateRaidTotals() {
  const totals = raidState.reduce(
    (acc, entry) => {
      const target = findTarget(entry.targetId);
      const itemCount = target[entry.method] * entry.qty;
      acc.items += itemCount;
      acc.sulfur += itemCount * sulfurPerItem[entry.method];
      acc.gunpowder += itemCount * gunpowderPerItem[entry.method];
      return acc;
    },
    { items: 0, sulfur: 0, gunpowder: 0 },
  );

  raidItems.textContent = formatNumber(totals.items);
  sulfurTotal.textContent = formatNumber(totals.sulfur);
  gunpowderTotal.textContent = formatNumber(totals.gunpowder);
  updateConversionRoute();

  return totals;
}

async function copySharedRoute() {
  const url = sharedRouteUrl();
  try {
    await navigator.clipboard.writeText(url);
  } catch {
    const input = document.createElement("textarea");
    input.value = url;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
  }
  shareStatus.textContent = "Share link copied. Anyone opening it will see this route and its totals.";
  trackEvent("raid_plan_share_copy", { rows: raidState.length });
  window.setTimeout(() => {
    shareStatus.textContent = "Share this exact route without re-entering the targets.";
  }, 5000);
}

function addTarget() {
  const qty = Math.max(1, Math.min(99, Number(targetQty.value) || 1));
  const target = findTarget(targetSelect.value);
  raidState.push({
    targetId: targetSelect.value,
    qty,
    method: methodSelect.value,
  });
  renderRaidList();
  trackEvent("raid_add_target", {
    target_id: targetSelect.value,
    target_label: target?.label,
    quantity: qty,
    method: methodSelect.value,
    rows: raidState.length,
  });
}

document.querySelector("#add-target").addEventListener("click", addTarget);

document.querySelector("#reset-raid").addEventListener("click", () => {
  raidState.splice(0, raidState.length);
  renderRaidList();
  trackEvent("raid_reset");
});

raidList.addEventListener("click", (event) => {
  const button = event.target.closest(".remove-row");
  if (!button) return;
  const removed = raidState[Number(button.dataset.index)];
  raidState.splice(Number(button.dataset.index), 1);
  renderRaidList();
  trackEvent("raid_remove_target", {
    target_id: removed?.targetId,
    method: removed?.method,
    rows: raidState.length,
  });
});

const upkeepInputs = {
  wood: document.querySelector("#wood-day"),
  stone: document.querySelector("#stone-day"),
  metal: document.querySelector("#metal-day"),
  hqm: document.querySelector("#hqm-day"),
};

const upkeepOutputs = {
  wood: document.querySelector("#wood-week"),
  stone: document.querySelector("#stone-week"),
  metal: document.querySelector("#metal-week"),
  hqm: document.querySelector("#hqm-week"),
};

function updateUpkeep() {
  Object.keys(upkeepInputs).forEach((key) => {
    const daily = Math.max(0, Number(upkeepInputs[key].value) || 0);
    upkeepOutputs[key].textContent = formatNumber(daily * 7);
  });
}

Object.values(upkeepInputs).forEach((input) => {
  input.addEventListener("input", updateUpkeep);
  input.addEventListener("change", () => {
    trackEvent("upkeep_input_change", {
      resource: input.id.replace("-day", ""),
      daily_value: Math.max(0, Number(input.value) || 0),
    });
  });
});

copyRaidLink.addEventListener("click", copySharedRoute);
loadSharedRoute();
populateTargets();
renderRaidList();
updateUpkeep();
trackEvent("calculator_ready", {
  default_rows: raidState.length,
});

document.querySelectorAll("[data-commerce-cta]").forEach((link) => {
  link.addEventListener("click", () => trackEvent("live_account_cta_click"));
});

revealLiveCommerce();
