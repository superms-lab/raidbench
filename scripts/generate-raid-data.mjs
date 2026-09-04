import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(root, "content", "rust-raid-data.json");
const outputPath = path.join(root, "raid-data.js");
const data = JSON.parse(fs.readFileSync(sourcePath, "utf8"));

fs.writeFileSync(outputPath, `window.RAIDBENCH_RAID_DATA = ${JSON.stringify(data, null, 2)};\n`);
console.log(`Wrote ${outputPath}`);
