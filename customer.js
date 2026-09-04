const state = {
  config: null,
  catalog: null,
  multigameCatalog: { products: [] },
  targetData: null,
  customer: null,
  questions: [],
  orders: [],
  activeTab: "ask",
  answerMode: "instant",
  authMode: "login",
  authView: "access",
  resetToken: "",
  selectedQuestionId: null,
  checkoutConsent: false,
  purchaseIntent: "",
  routePrefill: [],
  instantPrefill: null,
  planLines: [{ targetId: "sheet-door", quantity: 1, method: "satchels" }],
};

const el = (id) => document.getElementById(id);
const number = new Intl.NumberFormat("en-US");
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const date = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });

function trackEvent(name, params = {}) {
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

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.idempotent ? { "Idempotency-Key": crypto.randomUUID() } : {}),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error?.message || `Request failed (${response.status})`);
    error.code = payload.error?.code;
    error.status = response.status;
    throw error;
  }
  return payload;
}

let toastTimer;
function showToast(message, isError = false) {
  const toast = el("account-toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 5000);
}

function setBusy(button, busy, busyLabel) {
  if (!button.dataset.defaultLabel) button.dataset.defaultLabel = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? busyLabel : button.dataset.defaultLabel;
}

function renderAuthView() {
  el("auth-access-view").hidden = state.authView !== "access";
  el("reset-request-view").hidden = state.authView !== "reset_request";
  el("reset-confirm-view").hidden = state.authView !== "reset_confirm";

  const emailReady = Boolean(state.config?.passwordResetEnabled);
  const supportEmail = state.config?.merchant?.supportEmail || "support@raidbench.com";
  const supportLink = el("password-help").querySelector("a");
  supportLink.textContent = supportEmail;
  supportLink.href = `mailto:${supportEmail}`;
  el("forgot-password").hidden = !emailReady || state.authMode !== "login";
  el("password-help").hidden = emailReady || state.authMode !== "login";
}

function setAuthMode(mode) {
  state.authMode = mode;
  el("auth-form").dataset.mode = mode;
  document.querySelectorAll("[data-auth-mode]").forEach((item) => {
    item.setAttribute("aria-selected", String(item.dataset.authMode === mode));
  });
  document.querySelectorAll(".register-only").forEach((item) => { item.hidden = mode !== "register"; });
  el("auth-submit").textContent = mode === "register" ? "Create account" : "Sign in";
  el("auth-form").elements.password.autocomplete = mode === "register" ? "new-password" : "current-password";
  renderAuthView();
}

function renderPurchaseIntent(intent) {
  const offers = {
    instant: {
      title: "Personalized Rust route check - $5 starter",
      copy: "Compare all four breach methods against your priority and available explosives. The 20-credit starter covers two personalized 10-credit route checks.",
    },
    plan: {
      title: "Complete Rust raid plan - $19",
      copy: "Create an account to continue. The 120-credit pack covers one source-checked multi-layer raid plan.",
    },
    palworld: {
      title: "Palworld base and progression review - 80 credits",
      copy: "Describe one measurable bottleneck. Credits are reserved at submission and charged only after the answer passes independent QA.",
    },
  };
  const offer = offers[intent];
  el("purchase-intent").hidden = !offer;
  if (!offer) return;
  el("purchase-intent-title").textContent = offer.title;
  el("purchase-intent-copy").textContent = offer.copy;
}

function showAuth(view = state.authView) {
  state.authView = view;
  el("auth-view").hidden = false;
  el("app-view").hidden = true;
  el("signout-button").hidden = true;
  renderAuthView();
}

function showApp() {
  el("auth-view").hidden = true;
  el("app-view").hidden = false;
  el("signout-button").hidden = false;
  renderAccount();
}

function renderAccount() {
  const name = state.customer.display_name || state.customer.email.split("@")[0];
  el("account-greeting").textContent = `${name}, your next decision starts with a cleaner route.`;
  const totalCredits = state.customer.creditBalance || 0;
  const reserved = state.customer.reservedCredits || 0;
  const available = state.customer.availableCredits ?? Math.max(0, totalCredits - reserved);
  el("credit-balance").textContent = number.format(available);
  el("reserved-credits").hidden = reserved <= 0;
  el("reserved-credits").textContent = reserved > 0
    ? `${number.format(reserved)} reserved pending QA · ${number.format(totalCredits)} total`
    : "";
  el("answer-count").textContent = String(state.questions.length);
  renderTabs();
  renderRequestForms();
  renderAnswers();
  renderCredits();
}

function renderTabs() {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.setAttribute("aria-selected", String(button.dataset.tab === state.activeTab));
  });
  document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.tabPanel !== state.activeTab;
  });
}

function action(actionId) {
  return state.catalog.actions.find((item) => item.id === actionId);
}

function targetOptions(selected) {
  return state.targetData.targets.map((target) => (
    `<option value="${escapeHtml(target.id)}" ${target.id === selected ? "selected" : ""}>${escapeHtml(target.label)}</option>`
  )).join("");
}

function methodOptions(selected) {
  return state.targetData.methods.map((method) => (
    `<option value="${escapeHtml(method.id)}" ${method.id === selected ? "selected" : ""}>${escapeHtml(method.label)}</option>`
  )).join("");
}

function renderRequestForms() {
  const palworldProduct = state.multigameCatalog.products.find((item) => item.id === "palworld-base-progression-review");
  const palworldMode = el("palworld-mode");
  palworldMode.hidden = !palworldProduct;
  palworldMode.closest(".answer-mode").classList.toggle("has-multigame", Boolean(palworldProduct));
  if (!palworldProduct && state.answerMode === "palworld") state.answerMode = "instant";
  document.querySelectorAll("[data-answer-mode]").forEach((button) => {
    button.setAttribute("aria-selected", String(button.dataset.answerMode === state.answerMode));
  });
  el("instant-form").hidden = state.answerMode !== "instant";
  el("plan-form").hidden = state.answerMode !== "raid_plan";
  el("palworld-form").hidden = state.answerMode !== "palworld" || !palworldProduct;
  const instantAction = action("rust-instant-raid-answer");
  const planAction = action("rust-raid-prep");
  el("instant-price").textContent = `${instantAction?.credits ?? 10} credits`;
  el("plan-price").textContent = `${planAction?.credits ?? 120} credits`;
  el("palworld-price").textContent = `${palworldProduct?.credits ?? 80} credits`;
  if (!el("instant-target").options.length) {
    el("instant-target").innerHTML = targetOptions(state.instantPrefill?.targetId || "sheet-door");
    el("instant-method").innerHTML = methodOptions(state.instantPrefill?.method || "satchels");
    if (state.instantPrefill) el("instant-form").elements.quantity.value = state.instantPrefill.quantity;
  }
  renderPlanLines();
}

function applyRoutePrefill() {
  const targetIds = new Set(state.targetData.targets.map((target) => target.id));
  const methodIds = new Set(state.targetData.methods.map((method) => method.id));
  const route = state.routePrefill.filter((entry) => targetIds.has(entry.targetId) && methodIds.has(entry.method));
  if (!route.length) return;
  state.routePrefill = route;
  state.instantPrefill = route[0];
  state.planLines = route.map((entry) => ({ ...entry }));
}

function renderPlanLines() {
  el("route-lines").innerHTML = state.planLines.map((line, index) => `
    <div class="route-line" data-route-index="${index}">
      <label>
        <span class="route-number">Layer ${index + 1}</span>
        Target
        <select data-route-field="targetId">${targetOptions(line.targetId)}</select>
      </label>
      <label>
        Quantity
        <input data-route-field="quantity" type="number" min="1" max="99" value="${line.quantity}" />
      </label>
      <label>
        Breach method
        <select data-route-field="method">${methodOptions(line.method)}</select>
      </label>
      <button class="secondary-action remove-route" type="button" data-remove-route="${index}" ${state.planLines.length === 1 ? "disabled" : ""}>Remove</button>
    </div>
  `).join("");
  el("add-route").disabled = state.planLines.length >= 12;
}

function questionTitle(question) {
  if (question.answer?.title) return question.answer.title;
  if (question.questionType === "palworld-base-progression-review") return "Palworld base and progression review";
  return question.questionType === "raid_plan" ? "Rust raid plan review" : "Rust raid cost review";
}

function statusLabel(question) {
  if (question.status === "ready") return "Ready";
  if (question.status === "queued") return "QA in progress";
  return "Held - no charge";
}

function renderAnswers() {
  const list = el("answer-list");
  if (!state.questions.length) {
    list.innerHTML = `<div class="empty-answer"><h3>No answers yet</h3><p>Your first verified result will appear here.</p></div>`;
    return;
  }
  if (!state.selectedQuestionId) state.selectedQuestionId = state.questions[0].id;
  list.innerHTML = state.questions.map((question) => {
    const statusClass = question.status === "queued" ? "queued" : question.status === "ready" ? "" : "held";
    const creditCopy = question.status === "queued"
      ? `${number.format(question.creditsCost)} credits reserved · 0 charged`
      : `${number.format(question.creditsCharged)} credits charged`;
    return `
    <button type="button" data-question-id="${escapeHtml(question.id)}" aria-current="${question.id === state.selectedQuestionId}">
      <span class="status-line">
        <span class="status-tag ${statusClass}">${escapeHtml(statusLabel(question))}</span>
        <span>${escapeHtml(date.format(new Date(question.submittedAt)))}</span>
      </span>
      <strong>${escapeHtml(questionTitle(question))}</strong>
      <span>${creditCopy}</span>
    </button>
  `; }).join("");
  const selected = state.questions.find((question) => question.id === state.selectedQuestionId) || state.questions[0];
  renderAnswerDetail(selected);
}

function renderReviewedMultigameAnswer(question, answer) {
  const detail = el("answer-detail");
  const claims = Array.isArray(answer.claims) ? answer.claims : [];
  const claimRows = claims.map((claim) => `
    <div class="claim-record">
      <small>${escapeHtml(String(claim.claimType || "review point").replaceAll("_", " "))}</small>
      <strong>${escapeHtml(claim.text || "")}</strong>
      ${(claim.assumptions || []).length ? `<p>Assumptions: ${escapeHtml(claim.assumptions.join(" "))}</p>` : ""}
    </div>`).join("");
  const limitations = (answer.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const evidence = [];
  const seen = new Set();
  claims.forEach((claim) => {
    (claim.evidence || []).forEach((source) => {
      const key = `${source.sourceType || ""}|${source.title || ""}|${source.url || ""}`;
      if (seen.has(key)) return;
      seen.add(key);
      evidence.push(source);
    });
  });
  const sourceRows = evidence.map((source) => source.url
    ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer"><strong>${escapeHtml(source.title)}</strong><small>${escapeHtml(source.supports || "Publisher evidence checked for this review.")}</small></a>`
    : `<div class="saved-context"><strong>${escapeHtml(source.title || "Player-supplied context")}</strong><p>${escapeHtml(source.supports || "Used only as player-reported context.")}</p></div>`
  ).join("");
  const events = question.events.map((event) => `
    <div><span><strong>${escapeHtml(event.label)}</strong><br /><small>${escapeHtml(event.detail)}</small></span></div>`).join("");
  const reviewedAt = answer.qa?.reviewedAt ? date.format(new Date(answer.qa.reviewedAt)) : "the recorded review time";
  detail.innerHTML = `
    <div class="answer-hero">
      <span class="status-tag">Independent QA approved</span>
      <h3>${escapeHtml(questionTitle(question))}</h3>
      <p>${escapeHtml(answer.gameVersion || question.game)}</p>
      <div class="answer-decision review-answer-text">${escapeHtml(answer.answerText || "")}</div>
    </div>
    <section class="answer-section">
      <h4>Verified decision points</h4>
      <div class="claim-list">${claimRows}</div>
    </section>
    <section class="answer-section">
      <h4>Scope and limitations</h4>
      <ul class="answer-list-plain">${limitations}</ul>
      <p class="answer-note">Material factual errors reported within ${number.format(answer.delivery?.correctionWindowDays || 14)} days are corrected without an additional credit charge.</p>
    </section>
    <section class="answer-section">
      <h4>Quality record</h4>
      <div class="qa-line">A separate reviewer checked the critical claims, version scope, limitations, and complete product promise. Reviewed ${escapeHtml(reviewedAt)}.</div>
    </section>
    <section class="answer-section">
      <h4>Evidence</h4>
      <div class="source-links">${sourceRows}</div>
    </section>
    <section class="answer-section">
      <h4>Delivery timeline</h4>
      <div class="event-list">${events}</div>
    </section>`;
}

function renderAnswerDetail(question) {
  const detail = el("answer-detail");
  if (question?.status === "queued") {
    detail.innerHTML = `
      <div class="queued-answer">
        <span class="status-tag queued">Independent QA in progress</span>
        <h3>${escapeHtml(questionTitle(question))}</h3>
        <p>Your ${number.format(question.creditsCost)} credits are reserved, not charged. This page checks for the reviewed answer automatically; most requests finish within 10 minutes.</p>
        <p>If the evidence, version scope, or independent review is insufficient, the request will close at 0 credits and the reservation will be released.</p>
      </div>`;
    return;
  }
  if (!question || question.status !== "ready") {
    detail.innerHTML = `
      <div class="held-answer">
        <span class="status-tag held">Held - no charge</span>
        <h3>${escapeHtml(questionTitle(question || {}))}</h3>
        <p>${escapeHtml(question?.blockedReason || "This request needs additional evidence before it can be sold as an answer.")}</p>
        <p><strong>Credits charged:</strong> 0</p>
      </div>`;
    return;
  }
  const answer = question.answer;
  if (!answer.totals && answer.policyVersion) {
    renderReviewedMultigameAnswer(question, answer);
    return;
  }
  const totals = answer.totals;
  const lineRows = totals.lineItems.map((line) => `
    <tr>
      <td>${escapeHtml(line.quantity)} x ${escapeHtml(line.targetLabel)}</td>
      <td>${escapeHtml(line.methodLabel)}</td>
      <td>${number.format(line.itemCount)}</td>
      <td>${number.format(line.sulfur)}</td>
      <td>${number.format(line.gunpowder)}</td>
    </tr>`).join("");
  const sourceLinks = answer.evidence.map((source) => `
    <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">
      <strong>${escapeHtml(source.title)}</strong>
      <small>${escapeHtml(source.supports)}</small>
    </a>`).join("");
  const events = question.events.map((event) => `
    <div><span><strong>${escapeHtml(event.label)}</strong><br /><small>${escapeHtml(event.detail)}</small></span></div>`).join("");
  const crafting = answer.crafting;
  const craftingSection = crafting ? `
    <section class="answer-section">
      <h4>Crafting queue</h4>
      <div class="detail-rows">
        <div><strong>${number.format(crafting.batches)} workbench batches</strong><p>${number.format(crafting.gunpowderProduced)} gunpowder produced for a ${number.format(crafting.gunpowderRequired)} requirement.</p></div>
        <div><strong>${number.format(crafting.charcoalRequired)} charcoal</strong><p>${number.format(crafting.sulfurRequired)} sulfur is used inside the standard gunpowder recipe.</p></div>
      </div>
      <p class="answer-note">${escapeHtml(crafting.note)}</p>
    </section>` : "";
  const routeReview = answer.routeReview;
  const methodLabels = {
    rockets: "Rockets",
    c4: "C4",
    satchels: "Satchels",
    explosiveAmmo: "Explosive ammo",
  };
  const routeReviewSection = routeReview ? (() => {
    const recommended = routeReview.options.find((option) => option.id === routeReview.recommendationId);
    const optionRows = routeReview.options.map((option) => `
      <tr>
        <td>${escapeHtml(option.label)}${option.id === routeReview.recommendationId ? " · Recommended" : ""}</td>
        <td>${number.format(option.itemCount)}</td>
        <td>${number.format(option.sulfur)}</td>
        <td>${number.format(option.gunpowder)}</td>
      </tr>`).join("");
    const comparisonRows = routeReview.lineComparisons.flatMap((comparison) => comparison.alternatives.map((alternative) => `
      <tr>
        <td>${escapeHtml(comparison.quantity)} x ${escapeHtml(comparison.targetLabel)}</td>
        <td>${escapeHtml(alternative.methodLabel)}${alternative.method === comparison.selectedMethod ? " · Selected" : ""}</td>
        <td>${number.format(alternative.itemCount)}</td>
        <td>${number.format(alternative.sulfur)}</td>
      </tr>`)).join("");
    const shortfalls = Object.entries(routeReview.inventory?.recommended?.shortfalls || {})
      .filter(([, value]) => Number(value) > 0)
      .map(([method, value]) => `${number.format(value)} ${methodLabels[method] || method}`);
    const inventoryCopy = routeReview.inventory?.provided
      ? shortfalls.length
        ? `Inventory shortfall: ${shortfalls.join(", ")}.`
        : "The recommended route fits the explosive inventory entered."
      : "Add explosive inventory on a future check to turn this comparison into an exact shortfall list.";
    return `
      <section class="answer-section route-review-section">
        <h4>Route recommendation</h4>
        <div class="plan-readiness" data-readiness="${routeReview.inventory?.provided && !shortfalls.length ? "ready_to_stage" : "stock_check_required"}">
          <strong>${escapeHtml(recommended?.label || routeReview.recommendationLabel)}</strong>
          <span>${escapeHtml(routeReview.recommendationReason)} ${escapeHtml(inventoryCopy)}</span>
        </div>
        <div class="table-scroll route-option-table" tabindex="0">
          <table class="answer-table">
            <thead><tr><th>Route option</th><th>Items</th><th>Sulfur</th><th>Gunpowder</th></tr></thead>
            <tbody>${optionRows}</tbody>
          </table>
        </div>
        <h4 class="comparison-heading">Method-by-method check</h4>
        <div class="table-scroll" tabindex="0">
          <table class="answer-table">
            <thead><tr><th>Target</th><th>Method</th><th>Items</th><th>Sulfur</th></tr></thead>
            <tbody>${comparisonRows}</tbody>
          </table>
        </div>
        <p class="answer-note">${escapeHtml(routeReview.scopeNote)}</p>
      </section>`;
  })() : "";
  const plan = answer.plan;
  const planSection = plan ? `
    <section class="answer-section">
      <h4>Go / hold decision</h4>
      <div class="plan-readiness" data-readiness="${escapeHtml(plan.readiness)}">
        <strong>${escapeHtml(plan.readinessLabel)}</strong>
        <span>${escapeHtml(plan.readinessReason)}</span>
      </div>
    </section>
    <section class="answer-section">
      <h4>Team assignment</h4>
      <div class="detail-rows">${plan.teamRoles.map((role) => `
        <div><strong>${escapeHtml(role.role)}</strong><p>${escapeHtml(role.instruction)}</p></div>`).join("")}</div>
    </section>
    <section class="answer-section">
      <h4>Execution checkpoints</h4>
      <div class="detail-rows numbered">${plan.checkpoints.map((checkpoint, index) => `
        <div><span>${String(index + 1).padStart(2, "0")}</span><strong>${escapeHtml(checkpoint.phase)}</strong><p>${escapeHtml(checkpoint.action)}</p></div>`).join("")}</div>
    </section>
    <section class="answer-section">
      <h4>Stop conditions</h4>
      <ul class="answer-list-plain">${plan.stopConditions.map((condition) => `<li>${escapeHtml(condition)}</li>`).join("")}</ul>
      ${plan.savedNotes ? `<div class="saved-context"><strong>Saved planning context</strong><p>${escapeHtml(plan.savedNotes)}</p></div>` : ""}
    </section>` : "";
  const assumptions = (answer.assumptions || []).map((assumption) => `<li>${escapeHtml(assumption)}</li>`).join("");
  detail.innerHTML = `
    <div class="answer-hero">
      <span class="status-tag">QA approved</span>
      <h3>${escapeHtml(answer.title)}</h3>
      <p>${escapeHtml(answer.summary)}</p>
      <div class="answer-decision">${escapeHtml(answer.decision)}</div>
    </div>
    <div class="answer-metrics">
      <div><span>Breach items</span><strong>${number.format(totals.itemCount)}</strong></div>
      <div><span>Sulfur</span><strong>${number.format(totals.sulfur)}</strong></div>
      <div><span>Gunpowder</span><strong>${number.format(totals.gunpowder)}</strong></div>
      <div><span>Buffered sulfur</span><strong>${number.format(totals.bufferedSulfur)}</strong></div>
    </div>
    <section class="answer-section">
      <h4>Route calculation</h4>
      <div class="table-scroll" tabindex="0">
        <table class="answer-table">
          <thead><tr><th>Target</th><th>Method</th><th>Items</th><th>Sulfur</th><th>Gunpowder</th></tr></thead>
          <tbody>${lineRows}</tbody>
        </table>
      </div>
    </section>
    ${routeReviewSection}
    ${craftingSection}
    ${planSection}
    <section class="answer-section">
      <h4>Scope and assumptions</h4>
      <ul class="answer-list-plain">${assumptions}</ul>
      <p class="answer-note">${escapeHtml(answer.correctionPolicy || "")}</p>
    </section>
    <section class="answer-section">
      <h4>Quality record</h4>
      <div class="qa-line">Approved after source-window checks and a separate deterministic recalculation. Reviewed ${escapeHtml(answer.reviewedAt)} for ${escapeHtml(answer.gameScope)}</div>
    </section>
    <section class="answer-section">
      <h4>Evidence</h4>
      <div class="source-links">${sourceLinks}</div>
    </section>
    <section class="answer-section">
      <h4>Delivery timeline</h4>
      <div class="event-list">${events}</div>
    </section>`;
}

function renderCredits() {
  if (!state.catalog) return;
  const paymentAvailable = state.config.demoPaymentsEnabled || state.config.checkoutEnabled;
  const isSandbox = state.config.paypalEnvironment === "sandbox" || state.config.demoPaymentsEnabled;
  const merchant = state.config.merchant || {};
  el("checkout-state").textContent = state.config.demoPaymentsEnabled
    ? "Local PayPal sandbox simulation is active."
    : state.config.checkoutEnabled
      ? `${isSandbox ? "PayPal sandbox" : "PayPal"} checkout is active.`
      : "Checkout is temporarily unavailable.";
  const packDescriptions = {
    "credits-starter-20": "Covers two personalized 10-credit route checks with no stranded starter balance.",
    "credits-palworld-80": "Covers one independently reviewed Palworld base or progression bottleneck with no stranded balance.",
    "credits-scout-120": "Covers one complete 120-credit Rust raid plan with route alternatives and execution checks.",
    "credits-strategist-250": "Best for several route checks or two complete raid plans.",
    "credits-command-450": "For teams that want repeat planning across a wipe."
  };
  const recommendedSku = state.purchaseIntent === "plan"
    ? "credits-scout-120"
    : state.purchaseIntent === "palworld" ? "credits-palworld-80" : "credits-starter-20";
  el("credit-pack-list").innerHTML = state.catalog.packs.map((pack) => `
    <div class="credit-pack ${pack.sku === recommendedSku ? "recommended-pack" : ""}">
      <div>${pack.sku === recommendedSku ? `<span class="pack-match">Selected for this request</span>` : ""}<h3>${escapeHtml(pack.name)}</h3><p>${escapeHtml(packDescriptions[pack.sku] || "One-time purchase. Credits are stored after PayPal confirms payment.")}</p></div>
      <strong>${number.format(pack.credits)} credits</strong>
      <strong class="pack-price">${money.format(pack.price_usd)}</strong>
      <button class="primary-action" type="button" data-buy-sku="${escapeHtml(pack.sku)}" ${!paymentAvailable || !state.checkoutConsent ? "disabled" : ""}>
        ${state.config.demoPaymentsEnabled ? "Simulate PayPal" : "Pay with PayPal"}
      </button>
    </div>`).join("");
  el("merchant-disclosure").innerHTML = `
    <strong>${isSandbox ? "Test checkout" : `Sold by ${escapeHtml(merchant.legalName || "RaidBench")}`}</strong>
    <span>${isSandbox
      ? "No real money moves in this environment."
      : `${escapeHtml(merchant.country || "")} · USD one-time purchase · Delivered to this RaidBench account.`}</span>
    <span>Support: <a href="mailto:${escapeHtml(merchant.supportEmail || "support@raidbench.com")}">${escapeHtml(merchant.supportEmail || "support@raidbench.com")}</a></span>`;
  const consent = el("checkout-consent");
  consent.checked = state.checkoutConsent;
  consent.disabled = !paymentAvailable;
  el("order-history").innerHTML = state.orders.length
    ? state.orders.map((order) => `
      <div class="order-row">
        <div><strong>${escapeHtml(order.id)}</strong><span>${escapeHtml(date.format(new Date(order.createdAt)))}</span></div>
        <span>${number.format(order.credits)} credits</span>
        <span>${money.format(order.amount)}</span>
        <span class="order-status">${escapeHtml(order.status.replaceAll("_", " "))}</span>
      </div>`).join("")
    : `<p class="empty-orders">No purchases yet.</p>`;
}

async function refreshAccount() {
  const [mePayload, questionPayload, orderPayload] = await Promise.all([
    api("/api/me"),
    api("/api/questions"),
    api("/api/orders"),
  ]);
  state.customer = mePayload.customer;
  state.questions = questionPayload.questions;
  state.orders = orderPayload.orders;
}

async function refreshQueuedAnswers() {
  if (!state.customer || document.visibilityState === "hidden" || !state.questions.some((item) => item.status === "queued")) return;
  const previous = new Map(state.questions.map((item) => [item.id, item.status]));
  try {
    await refreshAccount();
    renderAccount();
    const completed = state.questions.find((item) => previous.get(item.id) === "queued" && item.status !== "queued");
    if (completed) {
      showToast(completed.status === "ready"
        ? "Independent QA approved your answer. It is ready in this account."
        : "The review closed without a charge because the answer could not be fully verified.");
    }
  } catch {
    // Keep the current account state; the next polling window will retry.
  }
}

async function enterDemo(button) {
  setBusy(button, true, "Opening account...");
  try {
    const payload = await api("/api/demo/session", { method: "POST" });
    state.customer = payload.customer;
    await refreshAccount();
    showApp();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function submitAuth(form) {
  const button = el("auth-submit");
  const mode = form.dataset.mode || "login";
  const values = Object.fromEntries(new FormData(form));
  trackEvent("account_auth_submit", { mode });
  setBusy(button, true, mode === "login" ? "Signing in..." : "Creating account...");
  try {
    const payload = await api(`/api/auth/${mode}`, { method: "POST", body: JSON.stringify(values) });
    state.customer = payload.customer;
    trackEvent("account_auth_success", { mode });
    await refreshAccount();
    showApp();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function submitResetRequest(form) {
  const button = el("reset-request-submit");
  const values = Object.fromEntries(new FormData(form));
  const status = el("reset-request-status");
  status.hidden = true;
  setBusy(button, true, "Sending secure link...");
  try {
    const payload = await api("/api/auth/password-reset/request", {
      method: "POST",
      body: JSON.stringify({ email: values.email }),
    });
    form.reset();
    status.textContent = payload.message;
    status.hidden = false;
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function submitResetConfirm(form) {
  const button = el("reset-confirm-submit");
  const values = Object.fromEntries(new FormData(form));
  if (values.password !== values.passwordConfirm) {
    showToast("The passwords do not match.", true);
    return;
  }
  setBusy(button, true, "Updating password...");
  try {
    const payload = await api("/api/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify({ token: state.resetToken, password: values.password }),
    });
    state.resetToken = "";
    state.authMode = "login";
    form.reset();
    document.querySelectorAll("[data-auth-mode]").forEach((item) => {
      item.setAttribute("aria-selected", String(item.dataset.authMode === "login"));
    });
    document.querySelectorAll(".register-only").forEach((item) => { item.hidden = true; });
    el("auth-form").dataset.mode = "login";
    el("auth-submit").textContent = "Sign in";
    el("auth-form").elements.password.autocomplete = "current-password";
    showAuth("access");
    showToast(payload.message);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function buyCredits(button) {
  const sku = button.dataset.buySku;
  if (!state.checkoutConsent) {
    showToast("Review and accept the purchase terms before opening PayPal.", true);
    return;
  }
  trackEvent("checkout_start", { sku });
  setBusy(button, true, "Confirming...");
  try {
    if (state.config.demoPaymentsEnabled) {
      const payload = await api("/api/demo/orders", {
        method: "POST",
        body: JSON.stringify({ sku }),
        idempotent: true,
      });
      state.customer.creditBalance = payload.creditBalance;
      await refreshAccount();
      state.activeTab = "ask";
      renderAccount();
      showToast(`${number.format(payload.order.creditsGranted)} test credits added to the local account.`);
    } else {
      sessionStorage.setItem("raidbench_checkout_context", JSON.stringify({
        intent: state.purchaseIntent,
        route: window.RAIDBENCH_ROUTE_STATE?.encode(state.routePrefill) || "",
      }));
      const payload = await api("/api/payments/paypal/create", {
        method: "POST",
        body: JSON.stringify({
          sku,
          acceptedTerms: true,
          acceptedRefundPolicy: true,
          acknowledgedDigitalDelivery: true,
          legalVersion: state.config.legalVersion,
        }),
        idempotent: true,
      });
      trackEvent("checkout_redirect", { sku });
      window.location.assign(payload.approvalUrl);
    }
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function submitInstant(form) {
  const button = form.querySelector("button[type='submit']");
  const values = Object.fromEntries(new FormData(form));
  values.quantity = Number(values.quantity);
  values.ownedInventory = {
    rockets: values.ownedRockets,
    c4: values.ownedC4,
    satchels: values.ownedSatchels,
    explosiveAmmo: values.ownedExplosiveAmmo,
  };
  for (const key of ["ownedRockets", "ownedC4", "ownedSatchels", "ownedExplosiveAmmo"]) delete values[key];
  await submitPaidAnswer(button, "/api/answers/instant", values, "Checking evidence...");
}

async function submitPlan(form) {
  const button = form.querySelector("button[type='submit']");
  document.querySelectorAll("[data-route-index]").forEach((row) => {
    const index = Number(row.dataset.routeIndex);
    state.planLines[index] = {
      targetId: row.querySelector("[data-route-field='targetId']").value,
      quantity: Number(row.querySelector("[data-route-field='quantity']").value),
      method: row.querySelector("[data-route-field='method']").value,
    };
  });
  const values = Object.fromEntries(new FormData(form));
  const payload = {
    ...values,
    targets: state.planLines,
    bufferPercent: Number(values.bufferPercent),
    teamSize: Number(values.teamSize),
    availableSulfur: values.availableSulfur === "" ? null : Number(values.availableSulfur),
  };
  await submitPaidAnswer(button, "/api/questions/raid-plan", payload, "Verifying route...");
}

async function submitPalworld(form) {
  const product = state.multigameCatalog.products.find((item) => item.id === "palworld-base-progression-review");
  if (!product) {
    showToast("The Palworld review is temporarily unavailable.", true);
    return;
  }
  const values = Object.fromEntries(new FormData(form));
  const payload = {
    productId: product.id,
    gameId: product.gameId,
    questionText: values.questionText,
    inputs: {
      gameVersion: values.gameVersion,
      serverType: values.serverType,
      currentGoal: values.currentGoal,
      baseOrProgressionState: values.baseOrProgressionState,
      observedProblem: values.observedProblem,
    },
  };
  const button = form.querySelector("button[type='submit']");
  await submitPaidAnswer(button, "/api/questions/multigame", payload, "Reserving review...");
}

async function submitPaidAnswer(button, path, payload, busyLabel) {
  const answerType = path.includes("multigame") ? "palworld_review" : path.includes("raid-plan") ? "raid_plan" : "instant";
  trackEvent("answer_submit", { answer_type: answerType });
  setBusy(button, true, busyLabel);
  try {
    const result = await api(path, {
      method: "POST",
      body: JSON.stringify(payload),
      idempotent: true,
    });
    state.customer = result.customer;
    await refreshAccount();
    state.selectedQuestionId = result.question.id;
    state.activeTab = "answers";
    const outcomeEvent = result.question.status === "ready"
      ? "answer_ready"
      : result.question.status === "queued" ? "answer_queued" : "answer_held";
    trackEvent(outcomeEvent, { answer_type: answerType });
    renderAccount();
    showToast(result.question.status === "ready"
      ? "Verified answer published directly to your account."
      : result.question.status === "queued"
        ? `${number.format(result.question.creditsCost)} credits reserved. Independent QA is now running; nothing has been charged.`
        : "Request held without a charge because current evidence is insufficient.");
  } catch (error) {
    if (error.code === "insufficient_credits") state.activeTab = "credits";
    renderAccount();
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function capturePayPalReturn() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("paypal") !== "return" || !params.get("token") || !state.customer) return;
  try {
    const payload = await api("/api/payments/paypal/capture", {
      method: "POST",
      body: JSON.stringify({ paypalOrderId: params.get("token") }),
      idempotent: true,
    });
    state.customer.creditBalance = payload.creditBalance;
    trackEvent("payment_capture_success");
    await refreshAccount();
    state.activeTab = "ask";
    sessionStorage.removeItem("raidbench_checkout_context");
    history.replaceState({}, "", "/customer.html");
    renderAccount();
    showToast("PayPal payment confirmed and credits added.");
  } catch (error) {
    showToast(error.message, true);
  }
}

function bindEvents() {
  el("demo-entry").addEventListener("click", (event) => enterDemo(event.currentTarget));
  el("auth-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitAuth(event.currentTarget);
  });
  el("forgot-password").addEventListener("click", () => {
    const currentEmail = el("auth-form").elements.email.value;
    el("reset-request-form").elements.email.value = currentEmail;
    el("reset-request-status").hidden = true;
    showAuth("reset_request");
  });
  el("reset-request-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitResetRequest(event.currentTarget);
  });
  el("reset-confirm-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitResetConfirm(event.currentTarget);
  });
  document.querySelectorAll("[data-auth-back]").forEach((button) => {
    button.addEventListener("click", () => showAuth("access"));
  });
  el("signout-button").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" }).catch(() => {});
    state.customer = null;
    state.questions = [];
    showAuth();
  });
  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => setAuthMode(button.dataset.authMode));
  });
  document.addEventListener("click", (event) => {
    const tabButton = event.target.closest("[data-tab], [data-open-tab]");
    if (tabButton) {
      state.activeTab = tabButton.dataset.tab || tabButton.dataset.openTab;
      renderTabs();
      return;
    }
    const modeButton = event.target.closest("[data-answer-mode]");
    if (modeButton) {
      state.answerMode = modeButton.dataset.answerMode;
      renderRequestForms();
      return;
    }
    const buyButton = event.target.closest("[data-buy-sku]");
    if (buyButton) {
      buyCredits(buyButton);
      return;
    }
    const questionButton = event.target.closest("[data-question-id]");
    if (questionButton) {
      state.selectedQuestionId = questionButton.dataset.questionId;
      renderAnswers();
      return;
    }
    const removeButton = event.target.closest("[data-remove-route]");
    if (removeButton && state.planLines.length > 1) {
      state.planLines.splice(Number(removeButton.dataset.removeRoute), 1);
      renderPlanLines();
    }
  });
  el("add-route").addEventListener("click", () => {
    if (state.planLines.length >= 12) return;
    state.planLines.push({ targetId: "sheet-door", quantity: 1, method: "satchels" });
    renderPlanLines();
  });
  el("checkout-consent").addEventListener("change", (event) => {
    state.checkoutConsent = event.currentTarget.checked;
    if (state.checkoutConsent) trackEvent("credit_consent");
    renderCredits();
  });
  el("instant-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitInstant(event.currentTarget);
  });
  el("plan-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitPlan(event.currentTarget);
  });
  el("palworld-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitPalworld(event.currentTarget);
  });
}

async function init() {
  bindEvents();
  const pageParams = new URLSearchParams(window.location.search);
  let storedCheckout = {};
  try {
    storedCheckout = JSON.parse(sessionStorage.getItem("raidbench_checkout_context") || "{}");
  } catch {
    storedCheckout = {};
  }
  const purchaseIntent = pageParams.get("intent") || storedCheckout.intent || "";
  const routeValue = pageParams.get("route") || storedCheckout.route || "";
  state.purchaseIntent = purchaseIntent;
  state.routePrefill = window.RAIDBENCH_ROUTE_STATE?.decode(routeValue) || [];
  if (purchaseIntent === "plan") state.answerMode = "raid_plan";
  if (purchaseIntent === "instant") state.answerMode = "instant";
  if (purchaseIntent === "palworld") state.answerMode = "palworld";
  if (purchaseIntent === "instant" || purchaseIntent === "plan" || purchaseIntent === "palworld") state.activeTab = "credits";
  renderPurchaseIntent(purchaseIntent);
  if (purchaseIntent === "instant" || purchaseIntent === "plan" || purchaseIntent === "palworld") setAuthMode("register");
  const resetParams = new URLSearchParams(window.location.hash.slice(1));
  const resetToken = resetParams.get("reset") || "";
  if (/^[A-Za-z0-9_-]{32,200}$/.test(resetToken)) {
    state.resetToken = resetToken;
    state.authView = "reset_confirm";
    history.replaceState({}, "", `${window.location.pathname}${window.location.search}`);
  }
  try {
    [state.config, state.catalog, state.targetData, state.multigameCatalog] = await Promise.all([
      api("/api/config"),
      api("/api/catalog"),
      api("/api/targets"),
      api("/api/multigame/products"),
    ]);
    applyRoutePrefill();
    el("demo-entry").hidden = !state.config.demoPaymentsEnabled;
    const session = await api("/api/session");
    if (state.resetToken) {
      showAuth("reset_confirm");
    } else if (session.authenticated) {
      await refreshAccount();
      if (purchaseIntent === "palworld") {
        const product = state.multigameCatalog.products.find((item) => item.id === "palworld-base-progression-review");
        if (product && (state.customer.availableCredits ?? state.customer.creditBalance ?? 0) >= product.credits) {
          state.activeTab = "ask";
        }
      }
      showApp();
      await capturePayPalReturn();
      renderAccount();
    } else {
      showAuth();
    }
  } catch (error) {
    showAuth();
    showToast(`RaidBench local service is unavailable: ${error.message}`, true);
  }
}

init();
window.setInterval(refreshQueuedAnswers, 20_000);
