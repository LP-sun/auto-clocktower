import type { Role, PlayerRuntimeState } from "../game/types";
export type DetectionTarget = "Townsfolk" | "Outsider" | "Minion" | "Demon" | "Evil";
export type Registration = "good_townsfolk" | "good_outsider" | "evil_minion" | "evil_demon";
export interface RegistrationDecision { type: "registration"; role: string; player?: string; target: DetectionTarget; legalOptions: Registration[]; }
/** DTO passed across the engine/policy boundary; values originate in authoritative state. */
export interface AuthoritativeRegistrationDecision extends RegistrationDecision { schemaVersion: 1; informationStatus: "authoritative_state"; }
let policy: ((decision: AuthoritativeRegistrationDecision) => Registration) | undefined;
export function setRegistrationPolicy(next?: typeof policy): void { policy = next; }
export function legalRegistrations(role: Role, poisoned = false): Registration[] {
  const natural = ({Townsfolk:"good_townsfolk",Outsider:"good_outsider",Minion:"evil_minion",Demon:"evil_demon"} as const)[role.category];
  if (poisoned) return [natural];
  if (role.id === "recluse") return ["good_outsider", "evil_minion", "evil_demon"];
  if (role.id === "spy") return ["evil_minion", "good_townsfolk", "good_outsider"];
  return [natural];
}
export function registersAs(role: Role, target: DetectionTarget, subject?: PlayerRuntimeState): boolean {
  const legalOptions = legalRegistrations(role, subject?.tags.has("poisoned"));
  let chosen = legalOptions[0];
  if (policy && legalOptions.length > 1) {
    try { const result = policy({ type:"registration",role:role.id,player:subject?.player.userId,target,legalOptions:[...legalOptions],schemaVersion:1,informationStatus:"authoritative_state" }); if (legalOptions.includes(result)) chosen=result; } catch { /* legal truthful fallback */ }
  }
  return target === "Evil" ? chosen.startsWith("evil_") : chosen.split("_")[1] === target.toLowerCase();
}
