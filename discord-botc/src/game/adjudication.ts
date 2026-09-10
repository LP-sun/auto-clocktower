/**
 * The only boundary at which an automated storyteller may influence a rules
 * decision.  The rules engine constructs a finite legal domain; a policy may
 * select one member of that domain asynchronously.  The engine never parses
 * prose and never silently replaces an invalid model result with a different
 * model result.
 */
import type { GameState } from "./types";

export type LegalValue = string | number | boolean;
export type RegistrationValue = "good_townsfolk" | "good_outsider" | "evil_minion" | "evil_demon";

export interface AdjudicationRequestContext {
  sourceAbility?: string;
  interactionId?: string;
  phase?: string;
  stateVersion?: number;
  requestId?: string;
}

export interface LegalDecision extends AdjudicationRequestContext {
  type: "misinformation" | "death_redirect";
  actor: string;
  field?: string;
  template?: string;
  legalOptions: readonly LegalValue[];
}

export interface AuthoritativeLegalDecision extends LegalDecision {
  sourceAbility: string;
  interactionId: string;
  phase: string;
  stateVersion: number;
  requestId: string;
  schemaVersion: 1;
  informationStatus: "authoritative_state";
}

export interface RegistrationDecision extends AdjudicationRequestContext {
  type: "registration";
  actor: string;
  role: string;
  player?: string;
  target: "Townsfolk" | "Outsider" | "Minion" | "Demon" | "Evil";
  legalOptions: readonly RegistrationValue[];
}

export interface AuthoritativeRegistrationDecision extends RegistrationDecision {
  sourceAbility: string;
  interactionId: string;
  phase: string;
  stateVersion: number;
  requestId: string;
  schemaVersion: 1;
  informationStatus: "authoritative_state";
}

export type AdjudicationDecision = LegalDecision | RegistrationDecision;
export type AuthoritativeDecision = AuthoritativeLegalDecision | AuthoritativeRegistrationDecision;

export type LegalPolicy = (
  state: GameState | null,
  decision: AuthoritativeDecision,
) => Promise<LegalValue | RegistrationValue>;
export type AdjudicationMode = "rules_only" | "storyteller_policy";

export class InvalidAdjudicationResult extends Error {
  constructor(
    public readonly decisionType: string,
    public readonly value: unknown,
    public readonly legalOptions: readonly (LegalValue | RegistrationValue)[],
  ) {
    super(
      `Adjudication policy returned an illegal ${decisionType} value: ${String(value)}`,
    );
    this.name = "InvalidAdjudicationResult";
  }
}

/** Small, stateless asynchronous kernel shared by the Discord and headless engines. */
export class AsyncAdjudicationKernel {
  readonly mode: AdjudicationMode;
  private sequence = 0;
  private readonly registrationCache = new Map<string, RegistrationValue>();

  constructor(private readonly policy?: LegalPolicy) {
    this.mode = policy ? "storyteller_policy" : "rules_only";
  }

  async choose<T extends LegalValue | RegistrationValue>(state: GameState | null, decision: AdjudicationDecision): Promise<T> {
    if (decision.legalOptions.length === 0) {
      throw new Error(`No legal options for ${decision.type}`);
    }
    const sourceAbility = decision.sourceAbility ?? ("template" in decision ? decision.template : undefined) ?? decision.type;
    const interactionId = decision.interactionId ?? `${sourceAbility}:${decision.actor}`;
    const phase = decision.phase ?? state?.phase ?? "unknown";
    const stateVersion = decision.stateVersion ?? state?.runtime?.stateVersion ?? 0;
    const requestId = decision.requestId ?? `${state?.gameId ?? "rules"}:${++this.sequence}`;
    if (decision.type === "registration") {
      const cached = this.registrationCache.get(interactionId);
      if (cached && decision.legalOptions.includes(cached)) return cached as T;
    }
    if (!this.policy) return decision.legalOptions[0] as T;
    const authoritative: AuthoritativeDecision = decision.type === "registration"
      ? {
          ...decision,
          sourceAbility,
          interactionId,
          phase,
          stateVersion,
          requestId,
          legalOptions: [...decision.legalOptions] as RegistrationValue[],
          schemaVersion: 1,
          informationStatus: "authoritative_state",
        }
      : {
          ...decision,
          sourceAbility,
          interactionId,
          phase,
          stateVersion,
          requestId,
          legalOptions: [...decision.legalOptions],
          schemaVersion: 1,
          informationStatus: "authoritative_state",
        };
    const result = await this.policy(state, authoritative);
    if (!(decision.legalOptions as readonly (LegalValue | RegistrationValue)[]).includes(result)) {
      throw new InvalidAdjudicationResult(
        decision.type,
        result,
        decision.legalOptions,
      );
    }
    if (decision.type === "registration") this.registrationCache.set(interactionId, result as RegistrationValue);
    return result as T;
  }
}

let kernel = new AsyncAdjudicationKernel();

/** Configure one policy for a headless run; pass undefined to restore rules-only mode. */
export function setAdjudicationPolicy(policy?: LegalPolicy): void {
  kernel = new AsyncAdjudicationKernel(policy);
}

/** Explicitly select deterministic rules-only mode for tests/replay. */
export function setRulesOnlyAdjudication(): void {
  kernel = new AsyncAdjudicationKernel();
}

export function getAdjudicationKernel(): AsyncAdjudicationKernel {
  return kernel;
}
