import type { GameState, NightOutcomeDraft } from "./types";
import { getScript } from "./roles";
import {
  getAdjudicationKernel,
  type LegalDecision,
  type LegalValue,
} from "./adjudication";

export type { LegalDecision, LegalValue, AuthoritativeLegalDecision } from "./adjudication";
export { setAdjudicationPolicy } from "./adjudication";

/** Invalid policy output is an error; there is no synchronous storyteller fallback. */
export function decideLegal(state: GameState, decision: LegalDecision): Promise<LegalValue> {
  return getAdjudicationKernel().choose(state, decision);
}

/** Only fields explicitly marked editable by the authoritative engine enter this domain. */
export function informationDecisions(state: GameState, actor: string, draft: NightOutcomeDraft): LegalDecision[] {
  const p = state.runtime?.playerStates.find((candidate) => candidate.player.userId === actor);
  if (!p || !(p.role.id === "drunk" || p.tags.has("poisoned")) || !draft.allowArbitraryOverride) return [];
  const out: LegalDecision[] = [];
  for (const [field, type] of Object.entries(draft.fieldTypes)) {
    let options: LegalValue[] = [];
    if (type === "boolean") options = [false, true];
    if (type === "number") options = draft.templateId === "empath_count" ? [0, 1, 2] : Array.from({ length: state.players.length + 1 }, (_, i) => i);
    if (type === "role") options = getScript().roles.filter((role) => !draft.constraints?.pairCategory || role.category === draft.constraints.pairCategory).map((role) => role.id);
    if (type === "player") options = state.players.filter((candidate) => !(field === "p1" || field === "p2") || candidate.userId !== draft.fields[field === "p1" ? "p2" : "p1"]).map((candidate) => candidate.userId);
    if (options.length) out.push({
      type: "misinformation",
      actor,
      field,
      template: draft.templateId,
      sourceAbility: draft.templateId,
      interactionId: `${draft.templateId}:${actor}:${field}`,
      phase: state.phase,
      stateVersion: state.runtime?.stateVersion ?? 0,
      requestId: `${state.gameId}:${draft.templateId}:${actor}:${field}`,
      legalOptions: options,
    });
  }
  return out;
}
