import assert from "node:assert/strict";
import test from "node:test";
import {
  TROUBLE_BREWING_MANIFEST,
  getScript,
  imp,
  monk,
  poisoner,
  resolveNightKill,
  soldier,
  type RolePluginContext,
  type StatusToken,
} from "./index";

function context(role: string, night: number, statuses: readonly StatusToken[] = []): RolePluginContext {
  const players = [
    { id: "soldier", seat: 0, role: "soldier", category: "Townsfolk" as const, team: "good" as const, alive: true },
    { id: "monk", seat: 1, role: "monk", category: "Townsfolk" as const, team: "good" as const, alive: true },
    { id: "poisoner", seat: 2, role: "poisoner", category: "Minion" as const, team: "evil" as const, alive: true },
    { id: "imp", seat: 3, role: "imp", category: "Demon" as const, team: "evil" as const, alive: true },
    { id: "minion", seat: 4, role: "baron", category: "Minion" as const, team: "evil" as const, alive: true },
  ];
  const self = players.find((player) => player.role === role)!;
  return {
    self,
    statuses,
    state: {
      gameId: "roles",
      seed: 1,
      phase: "night",
      day: Math.max(0, night - 1),
      night,
      stateVersion: 1,
      phaseToken: `roles:night:${night}`,
      players,
      nominations: [],
    },
  };
}

test("Trouble Brewing manifest exposes the full 22-role script and migration status", () => {
  assert.equal(TROUBLE_BREWING_MANIFEST.roles.length, 22);
  assert.deepEqual([...TROUBLE_BREWING_MANIFEST.implementedRoleIds].sort(), ["imp", "monk", "poisoner", "soldier"]);
  assert.equal(getScript().name.zh, "暗流涌动");
  assert.equal(getScript().roleIds.includes("baron"), true);
});

test("Soldier prevents an unpoisoned Demon attack but not when poisoned", () => {
  const clean = context("imp", 2);
  const cleanResult = resolveNightKill({ ...clean, sourceId: "imp", targetId: "soldier" });
  assert.equal(cleanResult.prevented, true);
  assert.equal(cleanResult.reason, "soldier");

  const poisoned: StatusToken = {
    id: "poisoner:poisoner:soldier:n2",
    kind: "poisoned",
    targetId: "soldier",
    sourceId: "poisoner",
    createdAt: { day: 1, night: 2, phase: "night" },
    expiresAt: "dusk",
  };
  const poisonedResult = resolveNightKill({ ...clean, statuses: [poisoned], sourceId: "imp", targetId: "soldier" });
  assert.equal(poisonedResult.prevented, false);
  assert.equal(poisonedResult.effects[0]?.type, "kill");
});

test("Monk has no first-night action and creates one-night protection thereafter", () => {
  assert.equal(monk.buildNightAction?.(context("monk", 1)), undefined);
  const action = monk.buildNightAction!(context("monk", 2))!;
  assert.equal(action.targetRule.allowSelf, false);
  assert.equal(action.legalTargets.includes("monk"), false);
  const [effect] = monk.resolveNightAction!(context("monk", 2), "soldier");
  assert.equal(effect.type, "add_status");
  if (effect.type === "add_status") {
    assert.equal(effect.token.kind, "protected");
    assert.equal(effect.token.targetId, "soldier");
    assert.equal(effect.token.expiresAt, "dawn");
  }
});

test("Poisoner may target itself and poisoned Poisoner still chooses without an effect", () => {
  const action = poisoner.buildNightAction!(context("poisoner", 1))!;
  assert.equal(action.targetRule.allowSelf, true);
  assert.equal(action.legalTargets.includes("poisoner"), true);
  const [effect] = poisoner.resolveNightAction!(context("poisoner", 1), "soldier");
  assert.equal(effect.type, "add_status");
  if (effect.type === "add_status") {
    assert.equal(effect.token.kind, "poisoned");
    assert.equal(effect.token.expiresAt, "dusk");
  }
  const poisonedSelf: StatusToken = {
    id: "self-poison",
    kind: "poisoned",
    targetId: "poisoner",
    createdAt: { day: 0, night: 1, phase: "night" },
    expiresAt: "dusk",
  };
  assert.ok(poisoner.buildNightAction?.(context("poisoner", 2, [poisonedSelf])));
  assert.deepEqual(poisoner.resolveNightAction?.(context("poisoner", 2, [poisonedSelf]), "soldier"), []);
});

test("Imp acts after the first night and self-targeting transfers to a living Minion", () => {
  assert.equal(imp.buildNightAction?.(context("imp", 1)), undefined);
  const action = imp.buildNightAction!(context("imp", 2))!;
  assert.equal(action.targetRule.allowSelf, true);
  const kill = imp.resolveNightAction!(context("imp", 2), "soldier");
  assert.deepEqual(kill, [{ type: "kill", targetId: "soldier", sourceId: "imp", cause: "demon", byExecution: false }]);
  const selfKill = imp.resolveNightAction!(context("imp", 2), "imp");
  assert.equal(selfKill.some((effect) => effect.type === "kill" && effect.targetId === "imp"), true);
  const transfer = selfKill.find((effect) => effect.type === "choose_role_change");
  assert.equal(transfer?.type, "choose_role_change");
  if (transfer?.type === "choose_role_change") {
    assert.deepEqual(transfer.legalTargets, ["poisoner", "minion"]);
    assert.equal(transfer.role, "imp");
    assert.equal(transfer.category, "Demon");
  }
});
