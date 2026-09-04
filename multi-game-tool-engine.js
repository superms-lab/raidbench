(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.RaidBenchToolEngine = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function numeric(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

  function metric(label, value, unit = "") {
    return { label, value, unit };
  }

  function stableCeil(value) {
    const correction = Number.EPSILON * Math.max(1, Math.abs(value)) * 4;
    return Math.ceil(value - correction);
  }

  function calculateRisk(values) {
    const saveImportance = clamp(numeric(values.saveImportance, 1), 1, 5);
    const modCount = clamp(numeric(values.modCount), 0, 200);
    const changeScope = clamp(numeric(values.changeScope, 1), 1, 5);
    const confidence = clamp(numeric(values.compatibilityConfidence, 1), 1, 5);
    const backupReady = numeric(values.backupReady) >= 1;
    const raw = saveImportance * 8 + Math.min(modCount, 20) * 1.2 + changeScope * 7 + (5 - confidence) * 6 - (backupReady ? 25 : 0);
    const score = Math.round(clamp(raw, 0, 100));
    const level = score >= 65 ? "High change risk" : score >= 35 ? "Moderate change risk" : "Lower change risk";
    const verdict = score >= 65
      ? "Use a copied save and test one variable at a time before touching the original."
      : score >= 35
        ? "Create and test-load a backup, then run a controlled comparison."
        : "The plan is bounded, but keep a rollback until the changed world survives repeated tests.";
    return {
      primaryLabel: "Planning risk score",
      primary: score,
      primaryUnit: "/ 100",
      verdict,
      metrics: [metric("Risk level", level), metric("Verified backup", backupReady ? "Yes" : "No"), metric("Mods counted", Math.round(modCount))],
      breakdown: [
        ["Save importance", Math.round(saveImportance * 8)],
        ["Mod complexity", Math.round(Math.min(modCount, 20) * 1.2)],
        ["Change scope", Math.round(changeScope * 7)],
        ["Evidence uncertainty", Math.round((5 - confidence) * 6)],
        ["Verified backup credit", backupReady ? -25 : 0],
      ],
    };
  }

  function calculateTarkovBudget(values) {
    const weapon = Math.max(0, numeric(values.weaponCost));
    const magazines = Math.max(0, numeric(values.magazines));
    const magazineCost = Math.max(0, numeric(values.magazineCost));
    const rounds = Math.max(0, numeric(values.rounds));
    const roundCost = Math.max(0, numeric(values.roundCost));
    const armor = Math.max(0, numeric(values.armorCost));
    const support = Math.max(0, numeric(values.supportCost));
    const copies = Math.max(1, Math.floor(numeric(values.copies, 1)));
    const reserve = clamp(numeric(values.reservePercent), 0, 100) / 100;
    const available = Math.max(0, numeric(values.availableBudget));
    const perKit = weapon + magazines * magazineCost + rounds * roundCost + armor + support;
    const protectedKit = perKit * (1 + reserve);
    const batch = protectedKit * copies;
    const affordable = protectedKit > 0 ? Math.floor(available / protectedKit) : copies;
    const shortfall = Math.max(0, batch - available);
    return {
      primaryLabel: "Protected batch budget",
      primary: Math.round(batch),
      primaryUnit: "currency",
      verdict: shortfall > 0
        ? `The planned batch is short by ${Math.round(shortfall).toLocaleString("en-US")}. Reduce the kit, copies, or reserve before relying on it.`
        : `The entered budget covers ${copies} kit${copies === 1 ? "" : "s"} with the selected reserve.`,
      metrics: [metric("Cost per kit", Math.round(perKit), "currency"), metric("Kits affordable", affordable), metric("Current shortfall", Math.round(shortfall), "currency")],
      breakdown: [["Weapon and modifications", weapon], ["Magazines", magazines * magazineCost], ["Ammunition", rounds * roundCost], ["Armor and rig", armor], ["Support equipment", support]],
    };
  }

  function calculateArkMaterials(values) {
    const creatures = Math.max(1, Math.floor(numeric(values.creatures, 1)));
    const replacements = Math.max(0, Math.floor(numeric(values.replacements)));
    const reserve = 1 + clamp(numeric(values.reservePercent), 0, 100) / 100;
    const saddleCount = creatures + replacements;
    const hide = stableCeil(saddleCount * Math.max(0, numeric(values.hidePerSaddle)) * reserve);
    const fiber = stableCeil(saddleCount * Math.max(0, numeric(values.fiberPerSaddle)) * reserve);
    const metal = stableCeil(saddleCount * Math.max(0, numeric(values.metalPerSaddle)) * reserve);
    return {
      primaryLabel: "Saddles budgeted",
      primary: saddleCount,
      primaryUnit: "saddles",
      verdict: hide + fiber + metal === 0
        ? "Enter the material requirements shown on the current blueprint to calculate the roster."
        : "Totals include the selected replacement count and material reserve, rounded upward.",
      metrics: [metric("Hide total", hide), metric("Fiber total", fiber), metric("Metal total", metal)],
      breakdown: [["Creature roster", creatures], ["Replacement saddles", replacements], ["Reserve percent", clamp(numeric(values.reservePercent), 0, 100)]],
    };
  }

  function calculateCs2Budget(values) {
    const players = clamp(Math.floor(numeric(values.players, 1)), 1, 5);
    const cash = Math.max(0, numeric(values.averageCash));
    const carried = Math.max(0, numeric(values.carriedValue));
    const kitCost = Math.max(0, numeric(values.targetKitCost));
    const reserve = Math.max(0, numeric(values.nextRoundReserve));
    const available = players * cash + carried;
    const required = players * kitCost + reserve;
    const gap = available - required;
    const kitsAffordable = kitCost > 0 ? Math.min(players, Math.floor(Math.max(0, available - reserve) / kitCost)) : players;
    return {
      primaryLabel: gap >= 0 ? "Team money after target buy" : "Target-buy shortfall",
      primary: Math.round(Math.abs(gap)),
      primaryUnit: "money",
      verdict: gap >= 0
        ? "The averaged team budget covers the entered target kits and reserve. Check individual player extremes before buying."
        : `Only ${kitsAffordable} of ${players} target kits fit while protecting the entered reserve. Coordinate a cheaper plan or save.`,
      metrics: [metric("Team resources", Math.round(available), "money"), metric("Required with reserve", Math.round(required), "money"), metric("Full kits affordable", kitsAffordable)],
      breakdown: [["Cash pool", players * cash], ["Carried equipment value", carried], ["Target kit total", players * kitCost], ["Next-round reserve", reserve]],
    };
  }

  function calculateComparison(config, values) {
    const names = [String(values.optionA || config.optionDefaults?.[0] || "Option A"), String(values.optionB || config.optionDefaults?.[1] || "Option B")];
    const totalWeight = config.criteria.reduce((sum, criterion) => sum + numeric(criterion.weight), 0) || 1;
    const scoreFor = (side) => config.criteria.reduce((sum, criterion) => {
      return sum + clamp(numeric(values[`${criterion.id}${side}`], 1), 1, 5) * numeric(criterion.weight);
    }, 0) / totalWeight * 20;
    const scores = [scoreFor("A"), scoreFor("B")];
    const difference = Math.abs(scores[0] - scores[1]);
    const winner = scores[0] >= scores[1] ? 0 : 1;
    const verdict = difference < 4
      ? "The options are too close for a confident ranking. Use a controlled test or improve the lowest-confidence criterion."
      : `${names[winner]} has the stronger fit under the entered priorities. Recheck any score based on stale patch information.`;
    return {
      primaryLabel: difference < 4 ? "Close comparison" : "Higher-fit option",
      primary: difference < 4 ? "Test required" : names[winner],
      primaryUnit: "",
      verdict,
      metrics: [metric(names[0], Math.round(scores[0]), "/ 100"), metric(names[1], Math.round(scores[1]), "/ 100"), metric("Score gap", Math.round(difference), "points")],
      breakdown: config.criteria.map((criterion) => [criterion.label, `${values[`${criterion.id}A`]} vs ${values[`${criterion.id}B`]} (${criterion.weight}%)`]),
    };
  }

  function calculatePubgTiming(values) {
    const distance = Math.max(0, numeric(values.distanceKm));
    const speed = Math.max(1, numeric(values.speedKmh, 1));
    const terrain = Math.max(0, numeric(values.terrainDelay));
    const contact = Math.max(0, numeric(values.contactDelay));
    const remaining = Math.max(0, numeric(values.timeRemaining));
    const movement = distance / speed * 60;
    const travel = movement + terrain + contact;
    const margin = remaining - travel;
    const departureIn = Math.max(0, margin - 2);
    const verdict = margin < 0
      ? "The entered plan arrives late even before extra disruption. Leave now or choose a shorter route."
      : margin < 2
        ? "The route has less than two minutes of planning margin. Leave now and protect a fallback."
        : `The route has about ${margin.toFixed(1)} minutes of margin; waiting more than ${departureIn.toFixed(1)} minutes removes the two-minute buffer.`;
    return {
      primaryLabel: "Estimated route time",
      primary: Number(travel.toFixed(1)),
      primaryUnit: "minutes",
      verdict,
      metrics: [metric("Arrival margin", Number(margin.toFixed(1)), "minutes"), metric("Latest departure in", Number(departureIn.toFixed(1)), "minutes"), metric("Movement time", Number(movement.toFixed(1)), "minutes")],
      breakdown: [["Movement", Number(movement.toFixed(2))], ["Terrain delay", terrain], ["Contact delay", contact], ["Time available", remaining]],
    };
  }

  function calculate(config, values) {
    switch (config.formula) {
      case "save-change-risk": return calculateRisk(values);
      case "tarkov-loadout-budget": return calculateTarkovBudget(values);
      case "ark-roster-materials": return calculateArkMaterials(values);
      case "cs2-team-buy-budget": return calculateCs2Budget(values);
      case "weighted-comparison": return calculateComparison(config, values);
      case "pubg-rotation-timing": return calculatePubgTiming(values);
      default: throw new Error(`Unsupported RaidBench tool formula: ${config.formula}`);
    }
  }

  return { calculate, clamp, numeric, stableCeil };
});
