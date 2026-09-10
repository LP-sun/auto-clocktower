import type { GameState, Role, PlayerRuntimeState } from "../game/types";
import { getAdjudicationKernel, type RegistrationDecision, type AdjudicationRequestContext } from "../game/adjudication";

export type DetectionTarget = "Townsfolk" | "Outsider" | "Minion" | "Demon" | "Evil";
export type Registration = "good_townsfolk" | "good_outsider" | "evil_minion" | "evil_demon";

export type { RegistrationDecision } from "../game/adjudication";

export function legalRegistrations(role: Role, poisoned = false): Registration[] {
  const natural = ({ Townsfolk: "good_townsfolk", Outsider: "good_outsider", Minion: "evil_minion", Demon: "evil_demon" } as const)[role.category];
  if (poisoned) return [natural];
  if (role.id === "recluse") return ["good_outsider", "evil_minion", "evil_demon"];
  if (role.id === "spy") return ["evil_minion", "good_townsfolk", "good_outsider"];
  return [natural];
}

function matches(chosen: Registration, target: DetectionTarget): boolean {
  return target === "Evil"
    ? chosen.startsWith("evil_")
    : chosen.split("_")[1] === target.toLowerCase();
}

/**
 * Resolve a registration against a finite legal domain. Ambiguous Recluse and
 * Spy registrations cross the async policy boundary; invalid policy output is
 * surfaced to the caller and is never replaced by a truthful fallback.
 */
export async function registersAs(
  role: Role,
  target: DetectionTarget,
  subject?: PlayerRuntimeState,
  state?: GameState | null,
  context?: AdjudicationRequestContext,
): Promise<boolean> {
  const legalOptions = legalRegistrations(role, subject?.tags.has("poisoned"));
  let chosen = legalOptions[0];
  if (legalOptions.length > 1) {
    const result = await getAdjudicationKernel().choose<Registration>(state ?? null, {
      type: "registration",
      actor: subject?.player.userId ?? role.id,
      role: role.id,
      player: subject?.player.userId,
      target,
      legalOptions: [...legalOptions],
      ...context,
    }) as Registration;
    chosen = result;
  }
  return matches(chosen, target);
}

/** Pure predicate for domains where every legal registration agrees. */
export function registrationMatchesAll(role: Role, target: DetectionTarget, subject?: PlayerRuntimeState): boolean {
  return legalRegistrations(role, subject?.tags.has("poisoned")).every((value) => matches(value, target));
}
