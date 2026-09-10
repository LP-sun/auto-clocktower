import assert from "node:assert/strict";
import test from "node:test";
import { createTroubleBrewingGame, HeadlessEngine, StaleDecisionError } from "./index";

const players = [
  { id: "p1", role: "chef", category: "Townsfolk" as const, team: "good" as const },
  { id: "p2", role: "empath", category: "Townsfolk" as const, team: "good" as const },
  { id: "p3", role: "soldier", category: "Townsfolk" as const, team: "good" as const },
  { id: "p4", role: "baron", category: "Minion" as const, team: "evil" as const },
  { id: "p5", role: "imp", category: "Demon" as const, team: "evil" as const },
];

test("core imports and runs without discord.js", async () => {
  const game = createTroubleBrewingGame({ gameId: "import-test", players });
  assert.equal((await game.start()).phase, "night");
  assert.equal(game.events[0].type, "phase_started");
});

test("two engine instances have isolated policies and state", async () => {
  const a = new HeadlessEngine({ gameId: "a", players, policy: async () => "a" });
  const b = new HeadlessEngine({ gameId: "b", players, policy: async () => "b" });
  await Promise.all([a.start(), b.start()]);
  const [ra, rb] = await Promise.all([
    a.requestDecision({ type: "target", actor: "p1", legalOptions: ["a", "b"] }),
    b.requestDecision({ type: "target", actor: "p1", legalOptions: ["a", "b"] }),
  ]);
  assert.equal((await a.resolveDecision(ra)).value, "a");
  assert.equal((await b.resolveDecision(rb)).value, "b");
  assert.equal(a.state.gameId, "a");
  assert.equal(b.state.gameId, "b");
});

test("stale decision is rejected after phase transition", async () => {
  const game = new HeadlessEngine({ gameId: "stale", players });
  await game.start();
  const request = await game.requestDecision({ type: "night_action", actor: "p1", legalOptions: ["p2"] });
  await game.transition("day", "night-complete");
  await assert.rejects(game.resolveDecision(request, "p2"), (error: unknown) => error instanceof StaleDecisionError);
});

test("duplicate transition and decision are idempotent", async () => {
  const game = new HeadlessEngine({ gameId: "idempotent", players });
  const first = await game.start("boot");
  const second = await game.start("boot");
  assert.deepEqual(second, first);
  assert.equal(game.events.filter((event) => event.type === "phase_started").length, 1);
  const request = await game.requestDecision({ type: "target", actor: "p1", legalOptions: ["p2"] });
  const resolved = await game.resolveDecision(request, "p2");
  const duplicate = await game.resolveDecision(request, "p2");
  assert.equal(resolved.duplicate, false);
  assert.equal(duplicate.duplicate, true);
  assert.equal(game.events.filter((event) => event.type === "decision_resolved").length, 1);
});

test("randomness is deterministic per instance and does not leak", async () => {
  const a = new HeadlessEngine({ gameId: "a", seed: 42, players });
  const b = new HeadlessEngine({ gameId: "b", seed: 42, players });
  assert.equal(await a.nextRandom(), await b.nextRandom());
  assert.equal(await a.pick(["x", "y", "z"]), await b.pick(["x", "y", "z"]));
});

test("day end executes only a unique highest nomination at the half threshold", async () => {
  const game = new HeadlessEngine({ gameId: "votes", players });
  await game.start();
  await game.transition("day", "day-1");
  await game.nominate("p1", "p5");
  const nomination = game.state.nominations[0];
  await game.castVote(nomination.id, "p1");
  await game.castVote(nomination.id, "p2");
  await game.castVote(nomination.id, "p3");
  await game.resolveDayNominations();
  assert.equal(game.state.players.find((p) => p.id === "p5")?.alive, false);
});

test("a tie between highest passing nominations causes no execution", async () => {
  const game = new HeadlessEngine({ gameId: "tie", players });
  await game.start();
  await game.transition("day", "day-1");
  await game.nominate("p1", "p2");
  await game.nominate("p3", "p3");
  const [first, second] = game.state.nominations;
  await game.castVote(first.id, "p1");
  await game.castVote(first.id, "p2");
  await game.castVote(first.id, "p4");
  await game.castVote(second.id, "p3");
  await game.castVote(second.id, "p2");
  await game.castVote(second.id, "p4");
  await game.resolveDayNominations();
  assert.equal(game.state.players.find((p) => p.id === "p2")?.alive, true);
  assert.equal(game.state.players.find((p) => p.id === "p3")?.alive, true);
});
