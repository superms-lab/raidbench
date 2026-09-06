(function () {
  "use strict";

  const initialParams = new URLSearchParams(window.location.search);
  let initialReportToken = "";
  if (window.location.hash.startsWith("#report=")) {
    try {
      initialReportToken = decodeURIComponent(window.location.hash.slice("#report=".length));
    } catch {
      initialReportToken = "";
    }
  }
  const initialPayment = {
    state: initialParams.get("paypal") || "",
    accessToken: initialParams.get("access") || "",
    paypalOrderId: initialParams.get("token") || "",
  };
  if (initialPayment.state || initialReportToken) {
    const cleanUrl = new URL(window.location.href);
    ["paypal", "access", "token", "PayerID"].forEach((key) => cleanUrl.searchParams.delete(key));
    if (initialReportToken) cleanUrl.hash = "";
    window.history.replaceState({}, "", `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`);
  }

  const methodLabels = {
    rockets: "Rockets",
    c4: "Timed Explosive Charges",
    satchels: "Satchel Charges",
    explosiveAmmo: "Explosive Ammo",
  };
  const inventoryLabels = {
    rockets: "Rockets",
    c4: "C4",
    satchels: "Satchels",
    explosiveAmmo: "Explosive ammo",
  };
  const reportTokenKey = "raidbench_staging_report_token";
  const routeCodec = window.RAIDBENCH_ROUTE_STATE;
  const defaultRoute = [
    { targetId: "sheet-door", quantity: 2, method: "satchels" },
    { targetId: "stone-wall", quantity: 1, method: "rockets" },
  ];
  const routeState = [];
  let targetMap = new Map();
  let product = null;
  let legalVersion = "";
  let latestPreviewSignature = "";
  let latestPayload = null;
  let activeReport = null;
  let activeAccessToken = "";

  const elements = Object.fromEntries([
    "staging-target", "staging-quantity", "staging-method", "add-route-line", "route-lines",
    "reset-route", "available-sulfur", "team-size", "route-preference", "owned-rockets",
    "owned-c4", "owned-satchels", "owned-explosive-ammo", "route-notes", "generate-preview",
    "builder-status", "preview-state", "preview-empty", "preview-result", "readiness-block",
    "readiness-label", "readiness-reason", "preview-items", "preview-sulfur", "preview-buffered",
    "preview-gunpowder", "gap-label", "gap-value", "locked-sections", "purchase-panel",
    "accept-terms", "accept-delivery", "unlock-report", "purchase-note", "evidence-fact",
    "staging-report", "report-title", "report-decision", "report-summary", "route-recommendation",
    "route-options", "line-comparisons", "inventory-table", "crafting-list", "execution-readiness",
    "team-roles", "checkpoints", "stop-conditions", "saved-note", "report-scope",
    "evidence-list", "qa-list", "correction-policy", "download-report", "print-report", "copy-private-report", "share-route",
  ].map((id) => [id, document.getElementById(id)]));

  const formatNumber = (value) => new Intl.NumberFormat("en-US").format(Number(value) || 0);

  function track(name, params = {}) {
    window.RaidBenchAnalytics?.track(name, params);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function api(path, body) {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: body === undefined ? { Accept: "application/json" } : {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let payload;
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload?.error?.message || "RaidBench could not complete this request.");
    }
    return payload;
  }

  function setBuilderStatus(message, error = false) {
    elements["builder-status"].textContent = message;
    elements["builder-status"].classList.toggle("is-error", error);
  }

  function setBusy(busy, label = "Check My Route Free") {
    elements["generate-preview"].disabled = busy;
    elements["generate-preview"].textContent = busy ? "Checking route..." : label;
  }

  function currentBuffer() {
    return Number(document.querySelector('input[name="buffer"]:checked')?.value || 0);
  }

  function numericValue(id, fallback = 0) {
    const raw = elements[id].value;
    if (raw === "") return "";
    const parsed = Math.trunc(Number(raw));
    return Number.isFinite(parsed) ? Math.max(0, parsed) : fallback;
  }

  function buildPayload() {
    return {
      serverType: "vanilla",
      targets: routeState.map((line) => ({ ...line })),
      bufferPercent: currentBuffer(),
      availableSulfur: numericValue("available-sulfur", 0),
      teamSize: Math.max(1, Math.min(20, Number(numericValue("team-size", 1)) || 1)),
      routePreference: elements["route-preference"].value,
      ownedInventory: {
        rockets: numericValue("owned-rockets", 0),
        c4: numericValue("owned-c4", 0),
        satchels: numericValue("owned-satchels", 0),
        explosiveAmmo: numericValue("owned-explosive-ammo", 0),
      },
      notes: elements["route-notes"].value.trim(),
    };
  }

  function payloadSignature(payload = buildPayload()) {
    return JSON.stringify(payload);
  }

  function markPreviewStale() {
    if (!latestPreviewSignature || latestPreviewSignature === payloadSignature()) return;
    elements["preview-state"].textContent = "Needs refresh";
    setBuilderStatus("Inputs changed. Run the free check again before checkout.");
    updateUnlockState();
  }

  function targetFor(id) {
    return targetMap.get(id);
  }

  function renderRouteLines() {
    if (!routeState.length) {
      elements["route-lines"].innerHTML = '<div class="staging-route-empty">Add at least one visible layer to begin.</div>';
      markPreviewStale();
      return;
    }
    elements["route-lines"].innerHTML = routeState.map((line, index) => {
      const target = targetFor(line.targetId);
      const placements = Number(target?.[line.method] || 0) * line.quantity;
      return `<div class="staging-route-row">
        <div><strong>${escapeHtml(line.quantity)} x ${escapeHtml(target?.label || line.targetId)}</strong><small>Layer ${index + 1}</small></div>
        <span>${escapeHtml(methodLabels[line.method])}</span>
        <span>${formatNumber(placements)}</span>
        <button class="staging-remove-line" type="button" data-index="${index}" aria-label="Remove layer ${index + 1}" title="Remove layer">&times;</button>
      </div>`;
    }).join("");
    markPreviewStale();
  }

  function addRouteLine() {
    if (routeState.length >= 12) {
      setBuilderStatus("A report supports up to 12 visible target layers.", true);
      return;
    }
    const targetId = elements["staging-target"].value;
    const quantity = Math.max(1, Math.min(99, Math.trunc(Number(elements["staging-quantity"].value) || 1)));
    const method = elements["staging-method"].value;
    if (!targetFor(targetId) || !methodLabels[method]) {
      setBuilderStatus("Choose a supported target and breach method.", true);
      return;
    }
    routeState.push({ targetId, quantity, method });
    renderRouteLines();
    track("raid_add_target", { target_id: targetId, quantity, method, rows: routeState.length });
  }

  function resetRoute() {
    routeState.splice(0, routeState.length, ...defaultRoute.map((line) => ({ ...line })));
    elements["available-sulfur"].value = "9000";
    elements["team-size"].value = "2";
    elements["route-preference"].value = "lowest_sulfur";
    elements["owned-rockets"].value = "2";
    elements["owned-c4"].value = "0";
    elements["owned-satchels"].value = "4";
    elements["owned-explosive-ammo"].value = "0";
    elements["route-notes"].value = "";
    document.querySelector('input[name="buffer"][value="15"]').checked = true;
    renderRouteLines();
    track("raid_reset");
  }

  function updateUnlockState() {
    const previewCurrent = Boolean(latestPreviewSignature && latestPreviewSignature === payloadSignature());
    const consented = elements["accept-terms"].checked && elements["accept-delivery"].checked;
    const available = Boolean(product?.available);
    elements["unlock-report"].disabled = !(previewCurrent && consented && available);
  }

  function configurePurchase() {
    if (!product) return;
    if (product.demo) {
      elements["unlock-report"].textContent = "Run Demo Unlock (No Payment)";
      elements["purchase-note"].textContent = "Local demo mode simulates confirmed payment and tests the full delivery path.";
    } else if (!product.available) {
      elements["unlock-report"].textContent = "Checkout Paused for Data Review";
      elements["purchase-note"].textContent = "The free builder remains available. Paid delivery resumes after the current Rust evidence gate passes.";
    } else {
      elements["unlock-report"].textContent = "Pay with PayPal and Unlock";
      elements["purchase-note"].textContent = "Secure PayPal checkout. The report opens here immediately after confirmed payment.";
    }
    updateUnlockState();
  }

  function renderPreview(preview) {
    elements["preview-empty"].hidden = true;
    elements["preview-result"].hidden = false;
    elements["preview-state"].textContent = "Checked";
    elements["readiness-label"].textContent = preview.readiness.label;
    elements["readiness-reason"].textContent = preview.readiness.reason;
    elements["readiness-block"].classList.toggle("is-hold", preview.readiness.status !== "ready_to_stage");
    elements["preview-items"].textContent = formatNumber(preview.selected.itemCount);
    elements["preview-sulfur"].textContent = formatNumber(preview.selected.sulfur);
    elements["preview-buffered"].textContent = formatNumber(preview.selected.bufferedSulfur);
    elements["preview-gunpowder"].textContent = formatNumber(preview.selected.gunpowder);
    elements["gap-label"].textContent = preview.primaryGap.label;
    elements["gap-value"].textContent = preview.primaryGap.amount
      ? `${formatNumber(preview.primaryGap.amount)} ${preview.primaryGap.unit}`
      : "No quantified shortfall in the information entered.";
    elements["locked-sections"].replaceChildren(...preview.lockedSections.map((label) => {
      const item = document.createElement("li");
      item.textContent = label;
      return item;
    }));
    elements["evidence-fact"].textContent = `Reviewed ${preview.reviewedAt}`;
    configurePurchase();
  }

  async function generatePreview() {
    if (!routeState.length) {
      setBuilderStatus("Add at least one target layer before running the check.", true);
      return;
    }
    const payload = buildPayload();
    setBusy(true);
    setBuilderStatus("Running the route through the current evidence and recalculation gates...");
    try {
      const result = await api("/api/guest/raid-pack/preview", payload);
      latestPayload = payload;
      latestPreviewSignature = payloadSignature(payload);
      if (result.product) product = result.product;
      renderPreview(result.preview);
      setBuilderStatus("Free check complete. Review the immediate finding before deciding whether to unlock the report.");
      track("staging_pack_preview", { rows: routeState.length, readiness: result.preview.readiness.status });
    } catch (error) {
      setBuilderStatus(error.message, true);
      elements["preview-state"].textContent = "Unavailable";
    } finally {
      setBusy(false);
    }
  }

  function saveAccessToken(token) {
    activeAccessToken = token;
    try {
      localStorage.setItem(reportTokenKey, token);
    } catch {
      // The return URL still carries the token when storage is unavailable.
    }
  }

  function clearAccessToken() {
    activeAccessToken = "";
    try {
      localStorage.removeItem(reportTokenKey);
    } catch {
      // Storage may be unavailable in hardened browser modes.
    }
  }

  function readAccessToken() {
    try {
      return localStorage.getItem(reportTokenKey) || "";
    } catch {
      return "";
    }
  }

  async function copyText(value) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      const field = document.createElement("textarea");
      field.value = value;
      field.setAttribute("readonly", "");
      field.style.position = "fixed";
      field.style.opacity = "0";
      document.body.appendChild(field);
      field.select();
      const copied = document.execCommand("copy");
      field.remove();
      return copied;
    }
  }

  async function unlockReport() {
    if (!latestPayload || latestPreviewSignature !== payloadSignature()) {
      setBuilderStatus("Run the free check again before checkout.", true);
      return;
    }
    elements["unlock-report"].disabled = true;
    elements["unlock-report"].textContent = product?.demo ? "Building demo report..." : "Opening PayPal...";
    try {
      if (product?.demo) {
        const result = await api("/api/guest/raid-pack/demo-complete", latestPayload);
        saveAccessToken(result.accessToken);
        renderDelivery(result.delivery);
        track("staging_pack_report_ready", { mode: "demo" });
        return;
      }
      const result = await api("/api/guest/raid-pack/checkout", {
        ...latestPayload,
        acceptedTerms: true,
        acceptedRefundPolicy: true,
        acknowledgedDigitalDelivery: true,
        legalVersion,
      });
      saveAccessToken(result.accessToken);
      track("staging_pack_checkout_start", { price_usd: 4.99, rows: routeState.length });
      window.location.assign(result.approvalUrl);
    } catch (error) {
      setBuilderStatus(error.message, true);
      configurePurchase();
    }
  }

  async function captureReturnedPayment(accessToken, paypalOrderId) {
    setBuilderStatus("PayPal returned successfully. Confirming payment and opening the report...");
    elements["preview-state"].textContent = "Confirming";
    try {
      const result = await api("/api/guest/raid-pack/capture", {
        accessToken,
        paypalOrderId,
      });
      saveAccessToken(accessToken);
      renderDelivery(result.delivery);
      track("staging_pack_report_ready", { mode: "live" });
    } catch (error) {
      setBuilderStatus(error.message, true);
      elements["preview-state"].textContent = "Payment review";
    }
  }

  async function restoreDelivery(accessToken, message = "") {
    if (!accessToken) return;
    try {
      const result = await api("/api/guest/raid-pack/access", { accessToken });
      if (result.delivery.ready) {
        renderDelivery(result.delivery);
        return;
      }
      renderPreview(result.delivery.preview);
      elements["preview-state"].textContent = result.delivery.deliveryStatus === "revoked" ? "Revoked" : "Awaiting payment";
      setBuilderStatus(message || "This saved report is awaiting confirmed payment.", result.delivery.deliveryStatus === "revoked");
      if (result.delivery.deliveryStatus === "revoked") clearAccessToken();
    } catch {
      clearAccessToken();
    }
  }

  function setList(container, items, renderer) {
    container.replaceChildren(...items.map((item, index) => {
      const li = document.createElement("li");
      renderer(li, item, index);
      return li;
    }));
  }

  function renderDelivery(delivery) {
    if (!delivery?.ready || !delivery.report) {
      setBuilderStatus("Payment has not been confirmed, so the paid report remains locked.", true);
      return;
    }
    activeReport = delivery.report;
    const report = delivery.report;
    elements["report-title"].textContent = report.title;
    elements["report-decision"].textContent = report.decision;
    elements["report-summary"].innerHTML = [
      ["Readiness", report.plan.readinessLabel],
      ["Base sulfur", formatNumber(report.totals.sulfur)],
      ["Buffered sulfur", formatNumber(report.totals.bufferedSulfur)],
      ["Gunpowder", formatNumber(report.totals.gunpowder)],
      ["Workbench charcoal", formatNumber(report.totals.workbenchCharcoal)],
    ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");

    const review = report.routeReview;
    elements["route-recommendation"].textContent = `${review.recommendationLabel}: ${review.recommendationReason}`;
    elements["route-options"].innerHTML = review.options.map((option) => `<tr class="${option.id === review.recommendationId ? "is-recommended" : ""}">
      <td>${escapeHtml(option.label)}</td><td>${formatNumber(option.itemCount)}</td><td>${formatNumber(option.sulfur)}</td><td>${formatNumber(option.gunpowder)}</td><td>${option.id === review.recommendationId ? "Recommended" : "Compared"}</td>
    </tr>`).join("");

    elements["line-comparisons"].innerHTML = review.lineComparisons.map((comparison) => `<div class="staging-comparison">
      <h4>${escapeHtml(comparison.quantity)} x ${escapeHtml(comparison.targetLabel)}</h4>
      <p>Selected method: ${escapeHtml(methodLabels[comparison.selectedMethod] || comparison.selectedMethod)}</p>
      <div class="staging-table-scroll" tabindex="0"><table><thead><tr><th>Method</th><th>Placements</th><th>Sulfur</th><th>Gunpowder</th></tr></thead><tbody>${comparison.alternatives.map((alternative) => `<tr><td>${escapeHtml(alternative.methodLabel)}</td><td>${formatNumber(alternative.itemCount)}</td><td>${formatNumber(alternative.sulfur)}</td><td>${formatNumber(alternative.gunpowder)}</td></tr>`).join("")}</tbody></table></div>
    </div>`).join("");

    const inventory = review.inventory;
    elements["inventory-table"].innerHTML = Object.keys(inventoryLabels).map((method) => `<div class="staging-inventory-row"><strong>${escapeHtml(inventoryLabels[method])}</strong><span>Owned ${formatNumber(inventory.owned[method])}</span><span>Need ${formatNumber(inventory.selected.shortfalls[method])}</span></div>`).join("");
    elements["crafting-list"].innerHTML = [
      ["Gunpowder required", formatNumber(report.crafting.gunpowderRequired)],
      ["Workbench batches", formatNumber(report.crafting.batches)],
      ["Sulfur for gunpowder", formatNumber(report.crafting.sulfurRequired)],
      ["Charcoal required", formatNumber(report.crafting.charcoalRequired)],
      ["Gunpowder produced", formatNumber(report.crafting.gunpowderProduced)],
    ].map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");

    elements["execution-readiness"].textContent = `${report.plan.readinessLabel}. ${report.plan.readinessReason}`;
    setList(elements["team-roles"], report.plan.teamRoles, (li, item) => {
      const strong = document.createElement("strong");
      strong.textContent = item.role;
      li.append(strong, document.createTextNode(item.instruction));
    });
    setList(elements.checkpoints, report.plan.checkpoints, (li, item) => {
      const strong = document.createElement("strong");
      strong.textContent = item.phase;
      li.append(strong, document.createTextNode(item.action));
    });
    setList(elements["stop-conditions"], report.plan.stopConditions, (li, item) => { li.textContent = item; });
    elements["saved-note"].textContent = report.plan.savedNotes || "No route note was entered.";

    elements["report-scope"].textContent = `${report.gameScope} Reviewed ${report.reviewedAt}; generated ${new Date(report.generatedAt).toLocaleString("en-US")}.`;
    setList(elements["evidence-list"], report.evidence, (li, item) => {
      const anchor = document.createElement("a");
      anchor.textContent = item.title;
      anchor.href = /^https:\/\//.test(item.url) ? item.url : "#";
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      const detail = document.createElement("span");
      detail.textContent = `${item.type === "official" ? "Official" : "Independent"}: ${item.supports}`;
      li.append(anchor, detail);
    });
    elements["qa-list"].innerHTML = report.qa.checks.map((check) => `<div class="staging-qa-row"><strong>${escapeHtml(check.replaceAll("_", " "))}</strong><span>Passed</span></div>`).join("") + `<div class="staging-qa-row"><strong>Report integrity</strong><span>${escapeHtml(delivery.reportSha256.slice(0, 12))}</span></div>`;
    elements["correction-policy"].textContent = report.correctionPolicy;

    elements["staging-report"].hidden = false;
    elements["preview-state"].textContent = "Delivered";
    elements["purchase-panel"].hidden = true;
    setBuilderStatus("Payment confirmed. The complete report is available below and remains accessible on this device.");
    elements["staging-report"].scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function downloadReport() {
    if (!activeReport) return;
    const blob = new Blob([JSON.stringify(activeReport, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `raidbench-rust-staging-${activeReport.generatedAt.slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    track("staging_pack_json_download");
  }

  async function copyRouteLink() {
    const url = new URL("/rust-raid-staging-pack", window.location.origin);
    url.searchParams.set("route", routeCodec.encode(routeState));
    url.searchParams.set("utm_source", "share_link");
    url.searchParams.set("utm_medium", "player_share");
    url.searchParams.set("utm_campaign", "rust_staging_pack");
    if (await copyText(url.toString())) {
      setBuilderStatus("Free route link copied. It shares the inputs, never the paid report token.");
      track("staging_pack_share");
    } else {
      setBuilderStatus("Your browser blocked clipboard access. Copy the current route from the address bar.", true);
    }
  }

  async function copyPrivateReportLink() {
    const token = activeAccessToken || readAccessToken();
    if (!token || !activeReport) {
      setBuilderStatus("The private report link is not available in this browser.", true);
      return;
    }
    const url = new URL("/rust-raid-staging-pack", window.location.origin);
    url.hash = `report=${encodeURIComponent(token)}`;
    if (await copyText(url.toString())) {
      setBuilderStatus("Private report link copied. Anyone with that link can open this paid report, so keep it private.");
      track("staging_pack_private_link_copy");
    } else {
      setBuilderStatus("Your browser blocked clipboard access. Download the JSON report for durable access.", true);
    }
  }

  async function initialize() {
    try {
      const [targetData, productData] = await Promise.all([
        api("/api/targets"),
        api("/api/guest/raid-pack/product"),
      ]);
      targetMap = new Map(targetData.targets.map((target) => [target.id, target]));
      product = productData.product;
      legalVersion = productData.legalVersion;
      elements["staging-target"].replaceChildren(...targetData.targets.map((target) => {
        const option = document.createElement("option");
        option.value = target.id;
        option.textContent = target.label;
        return option;
      }));

      const shared = routeCodec.decode(new URLSearchParams(window.location.search).get("route"));
      const validShared = shared.filter((line) => targetMap.has(line.targetId));
      routeState.push(...(validShared.length ? validShared : defaultRoute).map((line) => ({ ...line })));
      renderRouteLines();
      configurePurchase();
      elements["evidence-fact"].textContent = `Reviewed ${targetData.verifiedAt}`;

      const paypalState = initialPayment.state;
      const returnedAccess = initialPayment.accessToken;
      const paypalOrderId = initialPayment.paypalOrderId;
      if (returnedAccess) saveAccessToken(returnedAccess);

      if (paypalState === "return" && returnedAccess && paypalOrderId) {
        track("staging_pack_payment_return");
        await captureReturnedPayment(returnedAccess, paypalOrderId);
      } else if (paypalState === "cancel" && returnedAccess) {
        await restoreDelivery(returnedAccess, "PayPal checkout was cancelled. No payment was captured.");
      } else {
        const savedToken = initialReportToken || readAccessToken();
        if (savedToken) saveAccessToken(savedToken);
        await restoreDelivery(savedToken);
      }
    } catch (error) {
      setBuilderStatus(`${error.message} The planner could not load its current verified data.`, true);
      elements["preview-state"].textContent = "Unavailable";
      elements["generate-preview"].disabled = true;
    }
  }

  elements["add-route-line"].addEventListener("click", addRouteLine);
  elements["reset-route"].addEventListener("click", resetRoute);
  elements["route-lines"].addEventListener("click", (event) => {
    const button = event.target.closest("[data-index]");
    if (!button) return;
    const index = Number(button.dataset.index);
    const removed = routeState[index];
    routeState.splice(index, 1);
    renderRouteLines();
    track("raid_remove_target", { target_id: removed?.targetId, method: removed?.method, rows: routeState.length });
  });
  elements["generate-preview"].addEventListener("click", generatePreview);
  elements["accept-terms"].addEventListener("change", updateUnlockState);
  elements["accept-delivery"].addEventListener("change", updateUnlockState);
  elements["unlock-report"].addEventListener("click", unlockReport);
  elements["download-report"].addEventListener("click", downloadReport);
  elements["print-report"].addEventListener("click", () => { track("staging_pack_print"); window.print(); });
  elements["copy-private-report"].addEventListener("click", copyPrivateReportLink);
  elements["share-route"].addEventListener("click", copyRouteLink);
  document.querySelectorAll(".staging-builder input, .staging-builder select, .staging-builder textarea").forEach((input) => {
    input.addEventListener("input", markPreviewStale);
    input.addEventListener("change", markPreviewStale);
  });

  initialize();
})();
