import assert from "node:assert/strict";
import test from "node:test";
import {
  DecisionDomainError,
  MathRuleKernel,
  RuleEventBus,
  StatusTokenStore,
  TruthDomain,
  applyEffects,
  clockwiseDistance,
  createRuleState,
  nextPlayer,
  resolveDecisionDomain,
} from "./index";
import type { EnginePlayer } from "./types";
import type { StatusToken } from "./roles";

const players: EnginePlayer[] = [
  { id: "a", seat: 10, role: "monk", category: "Townsfolk", team: "good", alive: true },
  { id: "b", seat: 20, role: "imp", category: "Demon", team: "evil", alive: true },
  { id: "c", seat: 30, role: "soldier", category: "Townsfolk", team: "good", alive: true },
  { id: "d", seat: 40, role: "poisoner", category: "Minion", team: "evil", alive: true },
];

test("decision domains validate independent multi-target slots", () => {
  const domain = {
    id: "monk-choice", actorId: "a", phase: "night" as const,
    slots: [
      { id: "protect", kind: "target" as const, options: [{ value: "b" }, { value: "c" }], minSelections: 1, maxSelections: 1 },
      { id: "inspect", kind: "target" as const, options: ["b", "c", "d"], minSelections: 2, maxSelections: 2 },
    ],
  };
  const resolved = resolveDecisionDomain(domain, { protect: "c", inspect: ["b", "d"] });
  assert.deepEqual(resolved.selections.inspect, ["b", "d"]);
  assert.throws(() => resolveDecisionDomain(domain, { protect: "a", inspect: ["b", "d"] }), DecisionDomainError);
  assert.throws(() => resolveDecisionDomain(domain, { protect: "c", inspect: ["b", "b"] }), DecisionDomainError);
});

test("status tokens expire only at their declared boundary", () => {
  const token = (id: string, expiresAt: StatusToken["expiresAt"]): StatusToken => ({
    id, kind: "poisoned", targetId: "a", createdAt: { day: 1, night: 2, phase: "night" }, expiresAt,
  });
  const store = new StatusTokenStore([token("dusk", "dusk"), token("end", "game_end")]);
  assert.equal(store.expire("dawn").length, 0);
  assert.equal(store.expire("dusk").length, 1);
  assert.equal(store.has("poisoned", "a"), true);
  assert.equal(store.expire("game_end").length, 1);
  assert.equal(store.has("poisoned", "a"), false);
});

test("effect application is atomic, records truth claims, and creates a legal role-change domain", () => {
  const bus = new RuleEventBus();
  const observed: string[] = [];
  bus.on("*", (event) => observed.push(event.type));
  const result = applyEffects(createRuleState(players), [
    { type: "add_status", token: { id: "protect:b", kind: "protected", targetId: "b", sourceId: "a", createdAt: { day: 0, night: 1, phase: "night" }, expiresAt: "dawn" } },
    { type: "private_information", recipientId: "a", key: "neighbor_count", value: 1 },
    { type: "choose_role_change", sourceId: "b", legalTargets: ["d"], role: "imp", category: "Demon", team: "evil" },
  ], bus);
  assert.equal(result.state.statuses.length, 1);
  assert.equal(result.state.truth.claimsFor("a", "neighbor_count")[0]?.value, 1);
  assert.deepEqual(result.pendingDecisions[0]?.slots[0]?.options, [{ value: "d" }]);
  assert.ok(observed.includes("status_added"));
  assert.ok(observed.includes("decision_created"));
});

test("truth facts remain separate from player-facing claims", () => {
  const truth = new TruthDomain([{ key: "demon", subjectId: "b", value: "b" }]);
  truth.recordClaim({ id: "claim-1", recipientId: "a", key: "demon", value: "c", truthful: false });
  assert.equal(truth.fact("demon")?.value, "b");
  assert.equal(truth.claimsFor("a", "demon")[0]?.truthful, false);
});

test("ring helpers are seat-ordered and skip dead players when requested", () => {
  assert.equal(clockwiseDistance(players, "d", "a"), 1);
  const dead = players.map((player) => player.id === "b" ? { ...player, alive: false } : player);
  assert.equal(nextPlayer(dead, "a")?.id, "c");
});

test("kernel resolves Imp-style role transfer through the same effect path", () => {
  const kernel = new MathRuleKernel(createRuleState(players));
  const result = kernel.apply([{ type: "choose_role_change", sourceId: "b", legalTargets: ["d"], role: "imp", category: "Demon", team: "evil" }]);
  const domain = result.pendingDecisions[0]!;
  kernel.resolveDecision(domain.id, { target: "d" });
  assert.equal(kernel.state.players.find((player) => player.id === "d")?.role, "imp");
  assert.equal(kernel.state.pendingDecisions.length, 0);
});
