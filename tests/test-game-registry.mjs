import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const registry = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8"));

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

assert.equal(registry.schemaVersion, "1.0.0");
assert.equal(registry.games.length, 12);
assert.equal(new Set(registry.games.map((game) => game.id)).size, 12);
assert.equal(new Set(registry.games.map((game) => game.hubPath)).size, 12);
assert.deepEqual(
  registry.games.filter((game) => game.indexable).map((game) => game.id),
  registry.games.map((game) => game.id),
);
assert.deepEqual(
  registry.games.filter((game) => game.paidAnswers === "enabled").map((game) => game.id),
  ["rust", "palworld"],
);

for (const game of registry.games) {
  assert.equal(game.hubPath, `/games/${game.id}/`);
  assert.equal(game.decisionAreas.length, 4);
  assert.equal(game.seedQuestions.length, 3);
  const hub = path.join(root, game.hubPath, "index.html");
  assert.equal(fs.existsSync(hub), true, `Missing generated hub for ${game.id}`);
  const html = fs.readFileSync(hub, "utf8");
  assert.ok(html.includes(`<h1>${escapeHtml(game.name)} guides and decision tools</h1>`));
  assert.match(html, new RegExp(`<meta name="robots" content="${game.indexable ? "index,follow" : "noindex,follow"}"`));
}

const directory = fs.readFileSync(path.join(root, "games.html"), "utf8");
assert.equal((directory.match(/data-game-row/g) || []).length, 12);
assert.equal((directory.match(/data-game-filter=/g) || []).length, 5);

console.log("Game registry and generated hub tests passed.");
