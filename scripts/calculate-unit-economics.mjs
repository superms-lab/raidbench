import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(scriptPath), "..");

function money(value) {
  return `$${Number(value).toFixed(2)}`;
}

export function calculateProduct(product, provider, scenario, monthlyFixedTotal) {
  const price = Number(product.price);
  const paymentFee = price * Number(provider.percentageFee) / 100 + Number(provider.fixedFee);
  const fxAndWithdrawal = price * Number(scenario.fxAndWithdrawalPercent) / 100;
  const taxReserve = price * Number(scenario.taxReservePercent) / 100;
  const refundReserve = price * Number(scenario.refundReservePercent) / 100;
  const labor = (Number(product.reviewMinutes) + Number(product.supportMinutes)) / 60 * Number(scenario.reviewerHourlyCost);
  const ai = Number(product.aiResearchAndDraftCost) + Number(product.aiIndependentReviewCost);
  const fixedAllocation = monthlyFixedTotal / Math.max(1, Number(scenario.monthlyOrders));
  const variableCostBeforeAds = paymentFee + fxAndWithdrawal + taxReserve + refundReserve
    + Number(scenario.chargebackReservePerOrder) + ai + labor + Number(product.deliveryCost);
  const contributionBeforeAds = price - variableCostBeforeAds;
  const contributionBeforeFixed = contributionBeforeAds - Number(scenario.advertisingCac);
  const netPerOrder = contributionBeforeFixed - fixedAllocation;
  const marginPercent = price ? netPerOrder / price * 100 : 0;
  const breakEvenOrders = contributionBeforeFixed > 0 ? Math.ceil(monthlyFixedTotal / contributionBeforeFixed) : null;

  return {
    sku: product.sku,
    name: product.name,
    price,
    paymentFee,
    fxAndWithdrawal,
    taxReserve,
    refundReserve,
    chargebackReserve: Number(scenario.chargebackReservePerOrder),
    ai,
    labor,
    deliveryCost: Number(product.deliveryCost),
    advertisingCac: Number(scenario.advertisingCac),
    fixedAllocation,
    variableCostBeforeAds,
    contributionBeforeAds,
    contributionBeforeFixed,
    netPerOrder,
    marginPercent,
    breakEvenOrders,
    targetMargin: Number(product.targetContributionMarginPercent),
    status: contributionBeforeFixed <= 0 || marginPercent < Number(product.targetContributionMarginPercent) ? "hold" : "viable"
  };
}

export function calculateCreditAudit(skus, model, provider, scenario) {
  const activePacks = (skus.packs || []).filter((pack) => pack.status !== "retired");
  const profiles = new Map((model.creditDeliveryProfiles || []).map((profile) => [profile.id, profile]));

  return (skus.actions || []).map((action) => {
    if (!String(action.status).startsWith("ready")) {
      return {
        id: action.id,
        label: action.label,
        credits: Number(action.credits),
        impliedGrossRevenue: 0,
        minimumKnownDeliveryCost: 0,
        gap: 0,
        marginPercent: 0,
        status: "blocked"
      };
    }
    const profile = profiles.get(action.deliveryClass);
    if (!profile) throw new Error(`Missing delivery profile: ${action.deliveryClass}`);
    const packCases = activePacks.map((pack) => {
      const share = Number(action.credits) / Number(pack.credits);
      const gross = Number(pack.prices.USD) * share;
      const payment = gross * Number(provider.percentageFee) / 100 + Number(provider.fixedFee) * share;
      const reserves = gross * (
        Number(scenario.fxAndWithdrawalPercent)
        + Number(scenario.taxReservePercent)
        + Number(scenario.refundReservePercent)
      ) / 100;
      const chargeback = Number(scenario.chargebackReservePerOrder) * share;
      const labor = (Number(profile.reviewMinutes) + Number(profile.supportMinutes)) / 60
        * Number(scenario.reviewerHourlyCost);
      const delivery = Number(profile.aiCost) + labor + Number(profile.deliveryCost);
      const cost = payment + reserves + chargeback + delivery;
      return { gross, cost, contribution: gross - cost };
    });
    const conservative = packCases.sort((a, b) => a.contribution - b.contribution)[0];
    const marginPercent = conservative.gross ? conservative.contribution / conservative.gross * 100 : 0;
    const targetMargin = Number(profile.targetContributionMarginPercent);
    return {
      id: action.id,
      label: action.label,
      credits: Number(action.credits),
      deliveryClass: action.deliveryClass,
      impliedGrossRevenue: conservative.gross,
      minimumKnownDeliveryCost: conservative.cost,
      gap: conservative.contribution,
      marginPercent,
      targetMargin,
      status: conservative.contribution > 0 && marginPercent >= targetMargin ? "viable" : "failed"
    };
  });
}

export function calculateModel(model, skus, scenarioId = model.defaultScenarioId, providerId = model.defaultProviderId) {
  const scenario = model.scenarios.find((item) => item.id === scenarioId);
  const provider = model.providers.find((item) => item.id === providerId);
  if (!scenario) throw new Error(`Unknown scenario: ${scenarioId}`);
  if (!provider) throw new Error(`Unknown provider: ${providerId}`);
  const monthlyFixedTotal = model.monthlyFixedCosts.reduce((sum, item) => sum + Number(item.amount), 0);
  const products = model.products.map((product) => calculateProduct(product, provider, scenario, monthlyFixedTotal));
  return {
    generatedAt: new Date().toISOString(),
    modelAsOf: model.asOf,
    scenario,
    provider,
    monthlyFixedTotal,
    products,
    creditAudit: calculateCreditAudit(skus, model, provider, scenario)
  };
}

function report(result, model) {
  const productRows = result.products.map((item) =>
    `| ${item.name} | ${money(item.price)} | ${money(item.variableCostBeforeAds)} | ${money(item.advertisingCac)} | ${money(item.netPerOrder)} | ${item.marginPercent.toFixed(1)}% | ${item.status === "viable" ? "VIABLE" : "HOLD"} |`,
  ).join("\n");
  const creditRows = result.creditAudit.map((item) =>
    `| ${item.label} | ${item.credits} | ${money(item.impliedGrossRevenue)} | ${money(item.minimumKnownDeliveryCost)} | ${money(item.gap)} | ${item.status === "viable" ? `${item.marginPercent.toFixed(1)}%` : "-"} | ${item.status.toUpperCase()} |`,
  ).join("\n");
  const targetRows = result.products.map((item) => {
    const orders = [2000, 5000, 20000].map((target) => item.contributionBeforeFixed > 0
      ? Math.ceil((target + result.monthlyFixedTotal) / item.contributionBeforeFixed)
      : "N/A");
    return `| ${item.name} | ${orders[0]} | ${orders[1]} | ${orders[2]} |`;
  }).join("\n");

  return `# RaidBench Unit Economics\n\nGenerated: ${result.generatedAt}\nModel as of: ${result.modelAsOf}\nProvider: ${result.provider.name}\nScenario: ${result.scenario.name}\n\n## Decision\n\nThe North America credit packs pass the modeled cost floor for both launch-ready Rust actions. POE2 actions remain blocked until their evidence QA is complete. Paid acquisition remains a separate scenario and must not be scaled from this organic-launch result.\n\n## Product Economics\n\n| Product | Price | Variable cost before ads | CAC | Net per order after fixed allocation | Net margin | Decision |\n|---|---:|---:|---:|---:|---:|---|\n${productRows}\n\nMonthly fixed-cost planning reserve: ${money(result.monthlyFixedTotal)}. Monthly order assumption: ${result.scenario.monthlyOrders}.\n\n## Credit Action Audit\n\nEach ready action is tested against the least profitable pack allocation, including allocated payment fees, withdrawal reserve, tax reserve, refund reserve, chargeback reserve, and its own delivery profile. Blocked products are not treated as sellable revenue.\n\n| Action | Credits | Conservative gross | Modeled variable cost | Contribution | Margin | Decision |\n|---|---:|---:|---:|---:|---:|---|\n${creditRows}\n\n## Orders Needed For Monthly Net Target\n\n| Product | $2,000 net | $5,000 net | $20,000 net |\n|---|---:|---:|---:|\n${targetRows}\n\n## Cost Sources And Limits\n\n- Payment fee source: ${result.provider.sourceUrl}\n- ${result.provider.sourceNote}\n${model.planningNotes.map((note) => `- ${note}`).join("\n")}\n`;
}

if (process.argv[1] && path.resolve(process.argv[1]) === scriptPath) {
  const model = JSON.parse(fs.readFileSync(path.join(root, "content", "unit-economics.json"), "utf8"));
  const skus = JSON.parse(fs.readFileSync(path.join(root, "content", "skus.json"), "utf8"));
  const scenarioId = process.argv[2] || model.defaultScenarioId;
  const providerId = process.argv[3] || model.defaultProviderId;
  const result = calculateModel(model, skus, scenarioId, providerId);
  const output = path.join(root, "operations", "unit-economics-report.md");
  const localJson = path.join(root, "local", "unit-economics-latest.json");
  fs.mkdirSync(path.dirname(localJson), { recursive: true });
  fs.writeFileSync(output, report(result, model));
  fs.writeFileSync(localJson, `${JSON.stringify(result, null, 2)}\n`);
  console.log(`Wrote ${output}`);
  console.log(`Wrote ${localJson}`);
  for (const item of result.products) {
    console.log(`${item.sku}: ${money(item.netPerOrder)} net/order, ${item.marginPercent.toFixed(1)}%, ${item.status}`);
  }
  const launchReady = result.creditAudit.filter((item) => item.status !== "blocked");
  console.log(`Launch-ready credit actions failing cost floor: ${launchReady.filter((item) => item.status === "failed").length}/${launchReady.length}`);
}
