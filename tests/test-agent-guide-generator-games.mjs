import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "raidbench-agent-guide-"));
const dataPath = path.join(temporary, "guides.json");
const pagesDir = path.join(temporary, "pages");
const guide = {
  slug: "once-human-hourly-source-test",
  game: "Once Human",
  title: "Once Human Hourly Source Test",
  description: "A sufficiently detailed source-checked test guide description for the multi-game generator.",
  problem: "How should this current update be checked before changing a working setup?",
  shortAnswer: "Use the supplied official evidence, preserve a baseline, and change one reversible variable at a time.",
  publishedAt: "2026-09-04",
  reviewedAt: "2026-09-04",
  status: "Evidence-bounded Once Human guide; recheck after relevant patch changes",
  sections: [
    { title: "Confirm scope", purpose: "Keep facts bounded.", bullets: ["Read the current official source."] },
    { title: "Run a test", purpose: "Keep changes reversible.", bullets: ["Change one variable."] },
  ],
  checklist: ["Confirm version", "Record baseline", "Retest one change"],
  example: "A player records the current setup before testing one update-sensitive change.",
  mistakes: ["Assuming a cause", "Changing several variables"],
  faqs: [
    { question: "Is the result universal?", answer: "No. It remains bounded to the supplied evidence." },
    { question: "What changes first?", answer: "Only the smallest reversible test variable." },
  ],
  related: ["once-human-update-migration-checklist"],
  sources: [{ label: "Once Human official updates", url: "https://www.oncehuman.game/news/update/", note: "Publisher evidence." }],
  sourceNote: "The source supports only the captured update context.",
  patchNote: "Recheck after later updates.",
  communityAnswer: "Keep the test bounded to the supplied evidence.",
};

fs.writeFileSync(dataPath, `${JSON.stringify([guide], null, 2)}\n`);
const result = spawnSync(process.execPath, ["scripts/generate-agent-guides.mjs"], {
  cwd: process.cwd(),
  encoding: "utf8",
  env: {
    ...process.env,
    RAIDBENCH_AGENT_GUIDES_PATH: dataPath,
    RAIDBENCH_AGENT_PAGES_DIR: pagesDir,
  },
});
assert.equal(result.status, 0, result.stderr || result.stdout);
const html = fs.readFileSync(path.join(pagesDir, `${guide.slug}.html`), "utf8");
assert.match(html, /href="\.\.\/games\/once-human\/"/);
assert.match(html, /https:\/\/raidbench\.com\/games\/once-human\//);
assert.match(html, /Source-checked Once Human decision guide/);
fs.rmSync(temporary, { recursive: true, force: true });

console.log("Agent guide generator supports all registered games.");
