import fs from "node:fs";
import path from "node:path";
import { calculateCreditAudit } from "./calculate-unit-economics.mjs";

const root = process.cwd();
const model = JSON.parse(fs.readFileSync(path.join(root, "content", "unit-economics.json"), "utf8"));
const skus = JSON.parse(fs.readFileSync(path.join(root, "content", "skus.json"), "utf8"));
const catalog = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-products.json"), "utf8"));
const games = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8")).games;
const gameById = new Map(games.map((game) => [game.id, game]));
const provider = model.providers.find((item) => item.id === model.defaultProviderId);
const scenario = model.scenarios.find((item) => item.id === model.defaultScenarioId);
if (!provider || !scenario) throw new Error("Default unit-economics provider or scenario is missing");

const modeledActions = catalog.products.map((product) => ({
  id: product.id,
  label: product.label,
  credits: product.credits,
  output: product.output,
  deliveryClass: product.deliveryClass,
  status: "ready_model_only",
}));
const audit = calculateCreditAudit({ packs: skus.packs, actions: modeledActions }, model, provider, scenario);
const auditById = new Map(audit.map((item) => [item.id, item]));

function minimumPack(credits) {
  return [...skus.packs]
    .filter((pack) => pack.status !== "retired" && Number(pack.credits) >= Number(credits))
    .sort((a, b) => Number(a.prices.USD) - Number(b.prices.USD))[0] || null;
}

const products = catalog.products.map((product) => {
  const economics = auditById.get(product.id);
  const pack = minimumPack(product.credits);
  return {
    id: product.id,
    gameId: product.gameId,
    game: gameById.get(product.gameId)?.shortName || product.gameId,
    label: product.label,
    credits: product.credits,
    deliveryClass: product.deliveryClass,
    catalogStatus: product.status,
    checkoutVisible: product.status === "ready_live",
    minimumSinglePack: pack ? { sku: pack.sku, credits: pack.credits, priceUsd: pack.prices.USD } : null,
    conservativeImpliedGross: economics.impliedGrossRevenue,
    modeledVariableCost: economics.minimumKnownDeliveryCost,
    contribution: economics.gap,
    contributionMarginPercent: economics.marginPercent,
    targetMarginPercent: economics.targetMargin,
    economicStatus: economics.status === "viable"
      ? product.status === "ready_live" ? "viable_live" : "viable_pending_qa"
      : "pricing_hold",
    activationGates: product.activationGates,
    noChargeReasons: product.noChargeReasons,
  };
});

const monthlyFixedTotal = model.monthlyFixedCosts.reduce((sum, item) => sum + Number(item.amount), 0);
const result = {
  generatedAt: new Date().toISOString(),
  catalogAsOf: catalog.asOf,
  modelAsOf: model.asOf,
  provider: {
    id: provider.id,
    name: provider.name,
    percentageFee: provider.percentageFee,
    fixedFee: provider.fixedFee,
    sourceUrl: provider.sourceUrl,
    sourceCheckedAt: provider.sourceCheckedAt || "",
  },
  scenario: {
    id: scenario.id,
    name: scenario.name,
    fxAndWithdrawalPercent: scenario.fxAndWithdrawalPercent,
    taxReservePercent: scenario.taxReservePercent,
    refundReservePercent: scenario.refundReservePercent,
  },
  monthlyFixedTotal,
  policy: catalog.policy,
  summary: {
    products: products.length,
    checkoutVisible: products.filter((product) => product.checkoutVisible).length,
    viablePendingQa: products.filter((product) => product.economicStatus === "viable_pending_qa").length,
    pricingHolds: products.filter((product) => product.economicStatus === "pricing_hold").length,
  },
  products,
};

function money(value) {
  return `$${Number(value).toFixed(2)}`;
}

const rows = products.map((product) => `| ${product.game} | ${product.label} | ${product.credits} | ${money(product.conservativeImpliedGross)} | ${money(product.modeledVariableCost)} | ${product.contributionMarginPercent.toFixed(1)}% | ${product.checkoutVisible ? "LIVE" : product.economicStatus === "viable_pending_qa" ? "QA HOLD" : "PRICE HOLD"} |`).join("\n");
const report = `# RaidBench Multi-Game Product Economics

Generated: ${result.generatedAt}
Model as of: ${result.modelAsOf}
Provider: ${provider.name}
Scenario: ${scenario.name}

## Decision

Only products that pass both economics and the independent answer-quality gates may appear in checkout. Palworld is the first controlled live product; all other multi-game products remain hidden.

| Game | Draft product | Credits | Conservative implied gross | Modeled variable cost | Contribution margin | Decision |
|---|---|---:|---:|---:|---:|---|
${rows}

Monthly fixed-cost reserve: ${money(monthlyFixedTotal)}. This includes one modeled PayPal wire withdrawal per month. Tax is a planning reserve, not a tax determination.

## Activation Rule

A product can move from hidden to live only after its shadow-case count, supported-case QA rate, critical-factual-drift, source freshness, no-charge behavior, idempotency, and in-account delivery gates all pass. Pricing cannot override a failed answer-quality gate.
`;

fs.mkdirSync(path.join(root, "local"), { recursive: true });
fs.writeFileSync(path.join(root, "local", "multigame-product-economics.json"), `${JSON.stringify(result, null, 2)}\n`);
fs.writeFileSync(path.join(root, "operations", "multigame-product-economics.md"), report);
console.log(JSON.stringify(result.summary));
console.log(`Wrote local/multigame-product-economics.json and operations/multigame-product-economics.md`);
