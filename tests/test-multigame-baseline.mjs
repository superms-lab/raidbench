import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const baseline = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-baseline-guides.json"), "utf8"));
const registry = JSON.parse(fs.readFileSync(path.join(root, "content", "game-registry.json"), "utf8"));
const packets = JSON.parse(fs.readFileSync(path.join(root, "content", "inbox", "multigame-source-packets-2026-09-03.json"), "utf8")).packets;
const packetByGame = new Map(packets.map((packet) => [packet.gameId, packet]));
const newGames = registry.games.filter((game) => !["rust", "poe2", "palworld"].includes(game.id));
const allGuides = baseline.packs.flatMap((pack) => pack.guides.map((guide) => ({ ...guide, gameId: pack.gameId })));

assert.equal(baseline.schemaVersion, "1.0.0");
assert.equal(baseline.packs.length, 9);
assert.equal(allGuides.length, 54);
assert.equal(new Set(allGuides.map((guide) => guide.slug)).size, 54);

for (const game of newGames) {
  const pack = baseline.packs.find((item) => item.gameId === game.id);
  const packet = packetByGame.get(game.id);
  assert.ok(pack, `Missing content pack for ${game.id}`);
  assert.equal(pack.guides.length, 6);
  assert.equal(game.indexable, true);
  assert.equal(game.status, "live");
  assert.equal(game.paidAnswers, "planned");
  assert.ok(packet.factSources.length >= 2);
  assert.equal(pack.guides.filter((guide) => guide.usesDemandSignal).length, packet.demandSignal ? 1 : 0);
  for (const guide of pack.guides) {
    assert.ok(guide.slug.startsWith(`${game.id}-`));
    assert.ok(guide.answer.length >= 80);
    assert.ok(guide.description.length >= 50 && guide.description.length <= 180);
    assert.ok(guide.decisionRows.length >= 3);
    assert.ok(guide.checklist.length >= 4);
    assert.ok(guide.stopConditions.length >= 2);
    assert.ok(guide.mistakes.length >= 3);
    const page = fs.readFileSync(path.join(root, "pages", `${guide.slug}.html`), "utf8");
    assert.match(page, /<meta name="robots" content="index,follow"/);
    assert.ok(page.includes(`Reviewed ${baseline.reviewedAt}`));
    assert.equal(/data-live-commerce|Get a verified answer|Buy credits/i.test(page), false);
  }
}

assert.deepEqual(
  registry.games.filter((game) => game.paidAnswers === "enabled").map((game) => game.id),
  ["rust", "palworld"],
);

console.log("Multi-game baseline content tests passed.");
