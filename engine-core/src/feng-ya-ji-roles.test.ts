import assert from "node:assert/strict";
import test from "node:test";
import { empath, fortuneTeller, innkeeper, librarian, physician, resolveDecisionDomain, shugenja, type RolePluginContext, type StatusToken } from "./index";
import type { EnginePlayer } from "./types";

function ctx(selfId: string, players: EnginePlayer[], statuses: StatusToken[] = [], night = 1): RolePluginContext {
  return { self: players.find((p) => p.id === selfId)!, statuses, state: { gameId: "fy", seed: 1, phase: "night", day: night - 1, night, stateVersion: 1, phaseToken: `fy:n${night}`, players, nominations: [] } };
}
const base: EnginePlayer[] = [
  { id: "a", seat: 0, role: "shugenja", category: "Townsfolk", team: "good", alive: true },
  { id: "b", seat: 1, role: "drunk", category: "Outsider", team: "good", alive: true },
  { id: "c", seat: 2, role: "imp", category: "Demon", team: "evil", alive: true },
  { id: "d", seat: 3, role: "empath", category: "Townsfolk", team: "good", alive: true },
  { id: "e", seat: 4, role: "langzhong", category: "Townsfolk", team: "good", alive: true },
];

test("Shugenja computes the closest evil direction on the seat ring", () => {
  const info = shugenja.computeInformation!(ctx("a", base))!;
  assert.deepEqual(info.domain.truthValues, ["clockwise"]);
  assert.equal(info.reportedValue, "clockwise");
});

test("Empath skips dead neighbours and poisoned information is necessarily false", () => {
  const players = base.map((p) => p.id === "c" ? { ...p, alive: false } : p);
  const truthful = empath.computeInformation!(ctx("d", players))!;
  assert.deepEqual(truthful.domain.truthValues, [0]);
  const poison: StatusToken = { id: "p", kind: "poisoned", targetId: "d", createdAt: { day: 0, night: 1, phase: "night" }, expiresAt: "dusk" };
  const falseInfo = empath.computeInformation!(ctx("d", players, [poison]))!;
  assert.equal(falseInfo.domain.falseValues.includes(falseInfo.reportedValue), true);
});

test("Fortune Teller validates two distinct targets and computes Demon truth", () => {
  const context = ctx("a", base);
  const domain = fortuneTeller.buildDecisionDomain!(context)!;
  assert.throws(() => resolveDecisionDomain(domain, { targets: ["c", "c"] }));
  const result = resolveDecisionDomain(domain, { targets: ["b", "c"] });
  assert.equal(fortuneTeller.resolveInformation!(context, result)!.reportedValue, true);
});

test("Librarian domain contains only claims with a real Outsider as a truthful member", () => {
  const info = librarian.computeInformation!(ctx("a", base))!;
  assert.ok(info.domain.truthValues.length > 0);
  for (const value of info.domain.truthValues) assert.match(String(value), /"role":"drunk"/);
});

test("Innkeeper reports two good players with the drunk inside the pair", () => {
  const drunk: StatusToken = { id: "drunk", kind: "drunk", targetId: "b", createdAt: { day: 0, night: 1, phase: "setup" }, expiresAt: "game_end" };
  const info = innkeeper.computeInformation!(ctx("a", base, [drunk]))!;
  const claim = JSON.parse(String(info.reportedValue)) as { players: string[]; drunk: string };
  assert.equal(claim.drunk, "b");
  assert.equal(claim.players.includes("b"), true);
});

test("Physician target is model-selected but keyword truth comes from a static catalog", () => {
  const context = ctx("e", base);
  const domain = physician.buildDecisionDomain!(context)!;
  const resolution = resolveDecisionDomain(domain, { target: "c" });
  const info = physician.resolveInformation!(context, resolution)!;
  assert.deepEqual(info.domain.truthValues, ["自杀"]);
});
