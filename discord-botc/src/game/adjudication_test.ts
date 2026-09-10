import test from "node:test";
import assert from "node:assert/strict";
import {
  AsyncAdjudicationKernel,
  InvalidAdjudicationResult,
  setAdjudicationPolicy,
} from "./adjudication";
import { legalRegistrations, registersAs } from "../utils/roleDetection";
import type { GameState, PlayerRuntimeState, Role } from "./types";

const state = {} as GameState;
const recluse: Role = { id: "recluse", category: "Outsider" };
const subject: PlayerRuntimeState = {
  player: { userId: "P1", username: "P1", displayName: "P1", seatIndex: 1 },
  role: recluse,
  effectiveRole: recluse,
  alive: true,
  death: null,
  tags: new Set(),
};

test("adjudication kernel accepts only a legal asynchronous result", async () => {
  const seen: unknown[] = [];
  const kernel = new AsyncAdjudicationKernel(async (_state, decision) => {
    seen.push(decision);
    return "P2";
  });
  assert.equal(await kernel.choose(state, {
    type: "death_redirect",
    actor: "P0",
    legalOptions: ["P1", "P2"],
  }), "P2");
  assert.equal((seen[0] as { informationStatus: string }).informationStatus, "authoritative_state");
});

test("invalid asynchronous results fail closed", async () => {
  const kernel = new AsyncAdjudicationKernel(async () => "not-legal");
  await assert.rejects(
    kernel.choose(state, { type: "misinformation", actor: "P0", legalOptions: [0, 1] }),
    (error: unknown) => error instanceof InvalidAdjudicationResult,
  );
});

test("ambiguous registration awaits policy and propagates failures", async () => {
  assert.deepEqual(legalRegistrations(recluse), ["good_outsider", "evil_minion", "evil_demon"]);
  let calls = 0;
  setAdjudicationPolicy(async (_state, decision) => {
    calls += 1;
    assert.equal(decision.type, "registration");
    if (decision.type === "registration") assert.equal(decision.role, "recluse");
    return "evil_demon";
  });
  try {
    const interaction = { sourceAbility: "test_registration", interactionId: "test-registration-1" };
    assert.equal(await registersAs(recluse, "Demon", subject, state, interaction), true);
    assert.equal(calls, 1);
    assert.equal(await registersAs(recluse, "Demon", subject, state, interaction), true);
    assert.equal(calls, 1);
    setAdjudicationPolicy(async () => "invalid" as never);
    await assert.rejects(registersAs(recluse, "Demon", subject, state, {
      ...interaction,
      interactionId: "test-registration-2",
    }), /illegal registration value/);
  } finally {
    setAdjudicationPolicy();
  }
});
