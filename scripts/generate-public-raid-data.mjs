import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const sourcePath = path.join(root, "content", "rust-raid-data.json");
const source = JSON.parse(fs.readFileSync(sourcePath, "utf8"));

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

const methods = ["rockets", "c4", "satchels", "explosiveAmmo"];
const rows = source.targets.map((target) => {
  const row = {
    target_id: target.id,
    target: target.label,
    rockets: target.rockets,
    c4: target.c4,
    satchels: target.satchels,
    explosive_ammo: target.explosiveAmmo,
  };

  for (const method of methods) {
    const key = method === "explosiveAmmo" ? "explosive_ammo_sulfur" : `${method}_sulfur`;
    row[key] = target[method] * source.sulfurPerItem[method];
  }
  return row;
});

const publicData = {
  name: "RaidBench Vanilla Rust PC Raid Cost Reference",
  url: "https://raidbench.com/rust-raid-costs.json",
  verifiedAt: source.verifiedAt,
  scope: source.scope,
  methodologyUrl: "https://raidbench.com/about",
  calculatorUrl: "https://raidbench.com/",
  fieldNotes: {
    counts: "Items required to destroy one full-health target.",
    sulfur: "Rolled-up sulfur required to craft the listed items using current vanilla recipes.",
  },
  sulfurPerItem: source.sulfurPerItem,
  targets: rows,
  sources: source.sources.map(({ id, type, label, url, supports }) => ({ id, type, label, url, supports })),
  disclaimer: "Custom servers, damaged targets, splash damage, and future patches can change the practical result.",
};

const headers = Object.keys(rows[0]);
const csv = [
  headers.join(","),
  ...rows.map((row) => headers.map((header) => csvCell(row[header])).join(",")),
].join("\n");

fs.writeFileSync(path.join(root, "rust-raid-costs.json"), `${JSON.stringify(publicData, null, 2)}\n`);
fs.writeFileSync(path.join(root, "rust-raid-costs.csv"), `${csv}\n`);
console.log(`Generated public Rust raid data with ${rows.length} target(s).`);
