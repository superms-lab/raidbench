(function () {
  const methods = new Set(["rockets", "c4", "satchels", "explosiveAmmo"]);
  const targetPattern = /^[a-z0-9-]{2,60}$/;

  function normalize(entries) {
    if (!Array.isArray(entries)) return [];
    return entries.slice(0, 12).flatMap((entry) => {
      const targetId = String(entry?.targetId || "");
      const method = String(entry?.method || "");
      const quantity = Math.max(1, Math.min(99, Math.trunc(Number(entry?.quantity ?? entry?.qty) || 0)));
      if (!targetPattern.test(targetId) || !methods.has(method)) return [];
      return [{ targetId, quantity, method }];
    });
  }

  function encode(entries) {
    return normalize(entries)
      .map((entry) => `${entry.targetId}~${entry.quantity}~${entry.method}`)
      .join(",");
  }

  function decode(value) {
    if (typeof value !== "string" || !value || value.length > 1200) return [];
    return normalize(value.split(",").map((part) => {
      const [targetId, quantity, method] = part.split("~");
      return { targetId, quantity, method };
    }));
  }

  window.RAIDBENCH_ROUTE_STATE = Object.freeze({ decode, encode, normalize });
})();
