import type { Effect, StatusToken } from "./roles";
import type { EnginePlayer, Phase, RoleCategory, Team } from "./types";

/** Values which can be selected by an LLM or another deterministic policy. */
export type DecisionValue = string | number | boolean;

export interface DecisionOption<T extends DecisionValue = DecisionValue> {
  readonly value: T;
  readonly label?: string;
  readonly metadata?: Readonly<Record<string, DecisionValue>>;
}

/** One independently constrained selection in a multi-target decision. */
export interface DecisionSlot<T extends DecisionValue = DecisionValue> {
  readonly id: string;
  readonly kind: "target" | "role" | "player" | "choice" | "number" | "boolean";
  readonly options: readonly (DecisionOption<T> | T)[];
  readonly minSelections?: number;
  readonly maxSelections?: number;
  readonly allowDuplicates?: boolean;
  readonly metadata?: Readonly<Record<string, DecisionValue>>;
}

/** A complete legal domain. The model chooses values; the kernel owns legality. */
export interface DecisionDomain {
  readonly id: string;
  readonly actorId: string;
  readonly phase: Exclude<Phase, "setup" | "ended">;
  readonly slots: readonly DecisionSlot[];
  readonly metadata?: Readonly<Record<string, DecisionValue>>;
}

export type DecisionInput = Readonly<Record<string, DecisionValue | readonly DecisionValue[]>>;
export interface DecisionResolution {
  readonly domain: DecisionDomain;
  readonly selections: Readonly<Record<string, readonly DecisionValue[]>>;
}

export class DecisionDomainError extends Error {
  override name = "DecisionDomainError";
}

function optionValue(option: DecisionOption | DecisionValue): DecisionValue {
  return typeof option === "object" && option !== null && "value" in option
    ? option.value
    : option;
}

function sameValue(a: DecisionValue, b: DecisionValue): boolean {
  return Object.is(a, b);
}

/** Validate a domain before giving it to a model or UI. */
export function validateDecisionDomain(domain: DecisionDomain): void {
  if (!domain.id.trim()) throw new DecisionDomainError("Decision domain id is required");
  if (!domain.actorId.trim()) throw new DecisionDomainError("Decision actor is required");
  if (domain.phase !== "day" && domain.phase !== "night") throw new DecisionDomainError("Decision phase must be day or night");
  if (!domain.slots.length) throw new DecisionDomainError("Decision domain must contain at least one slot");
  const ids = new Set<string>();
  for (const slot of domain.slots) {
    if (!slot.id.trim() || ids.has(slot.id)) throw new DecisionDomainError(`Duplicate or empty decision slot: ${slot.id}`);
    ids.add(slot.id);
    const min = slot.minSelections ?? 1;
    const max = slot.maxSelections ?? min;
    if (!Number.isInteger(min) || min < 0 || !Number.isInteger(max) || max < min) {
      throw new DecisionDomainError(`Invalid selection bounds for ${slot.id}`);
    }
    const values = slot.options.map(optionValue);
    if (!values.length && min > 0) throw new DecisionDomainError(`Slot ${slot.id} has no legal options`);
    for (let index = 0; index < values.length; index += 1) {
      if (values.slice(index + 1).some((value) => sameValue(value, values[index]))) {
        throw new DecisionDomainError(`Duplicate legal option in ${slot.id}`);
      }
    }
  }
}

/** Check and normalise an LLM/UI response against every slot's legal domain. */
export function resolveDecisionDomain(domain: DecisionDomain, input: DecisionInput): DecisionResolution {
  validateDecisionDomain(domain);
  const known = new Set(domain.slots.map((slot) => slot.id));
  for (const id of Object.keys(input)) if (!known.has(id)) throw new DecisionDomainError(`Unknown decision slot: ${id}`);
  const selections: Record<string, readonly DecisionValue[]> = {};
  for (const slot of domain.slots) {
    const raw = input[slot.id];
    const values = raw === undefined ? [] : Array.isArray(raw) ? [...raw] : [raw];
    const min = slot.minSelections ?? 1;
    const max = slot.maxSelections ?? min;
    if (values.length < min || values.length > max) throw new DecisionDomainError(`Invalid number of selections for ${slot.id}`);
    if (!slot.allowDuplicates && new Set(values).size !== values.length) throw new DecisionDomainError(`Duplicate selections for ${slot.id}`);
    const legal = slot.options.map(optionValue);
    for (const value of values) if (!legal.some((candidate) => sameValue(candidate, value))) {
      throw new DecisionDomainError(`Illegal selection ${String(value)} for ${slot.id}`);
    }
    selections[slot.id] = values;
  }
  return { domain, selections };
}

/** Deterministic, serialisable status-token store with explicit expiry boundaries. */
export class StatusTokenStore {
  private readonly values = new Map<string, StatusToken>();

  constructor(tokens: readonly StatusToken[] = []) {
    for (const token of tokens) this.add(token);
  }

  add(token: StatusToken): this {
    if (!token.id.trim()) throw new Error("Status token id is required");
    if (!token.targetId.trim()) throw new Error("Status token target is required");
    this.values.set(token.id, { ...token, metadata: token.metadata ? { ...token.metadata } : undefined });
    return this;
  }

  remove(tokenId: string): StatusToken | undefined {
    const token = this.values.get(tokenId);
    this.values.delete(tokenId);
    return token;
  }

  get(tokenId: string): StatusToken | undefined {
    const token = this.values.get(tokenId);
    return token ? { ...token, metadata: token.metadata ? { ...token.metadata } : undefined } : undefined;
  }

  has(kind: string, targetId?: string): boolean {
    return [...this.values.values()].some((token) => token.kind === kind && (targetId === undefined || token.targetId === targetId));
  }

  forTarget(targetId: string, kind?: string): readonly StatusToken[] {
    return this.list().filter((token) => token.targetId === targetId && (kind === undefined || token.kind === kind));
  }

  list(): readonly StatusToken[] {
    return [...this.values.values()].map((token) => ({ ...token, metadata: token.metadata ? { ...token.metadata } : undefined }));
  }

  /** Remove tokens whose expiry boundary is reached, returning removed tokens. */
  expire(boundary: StatusToken["expiresAt"]): readonly StatusToken[] {
    const removed: StatusToken[] = [];
    for (const token of this.list()) if (token.expiresAt === boundary) {
      this.values.delete(token.id);
      removed.push(token);
    }
    return removed;
  }

  clone(): StatusTokenStore {
    return new StatusTokenStore(this.list());
  }
}

export interface TruthFact {
  readonly key: string;
  readonly value: unknown;
  readonly subjectId?: string;
  readonly source?: string;
}

export interface InformationClaim {
  readonly id: string;
  readonly recipientId: string;
  readonly key: string;
  readonly value: unknown;
  readonly factKey?: string;
  readonly truthful?: boolean;
}

/**
 * A finite domain for a piece of player-facing information.  `truthValues`
 * are calculated from authoritative state; `falseValues` are the only values
 * a poisoned/drunk information channel may use.  Neither list is model input.
 */
export interface InformationValueDomain {
  readonly id: string;
  readonly key: string;
  readonly recipientId: string;
  readonly subjectId?: string;
  readonly legalValues: readonly DecisionValue[];
  readonly truthValues: readonly DecisionValue[];
  readonly falseValues: readonly DecisionValue[];
  readonly truthful: boolean;
}

export interface InformationOutcome {
  readonly domain: InformationValueDomain;
  readonly reportedValue: DecisionValue;
  readonly truth: TruthFact;
  readonly claim: InformationClaim;
}

function uniqueValues(values: readonly DecisionValue[]): readonly DecisionValue[] {
  return values.filter((value, index) => values.findIndex((candidate) => Object.is(candidate, value)) === index);
}

/** Build a deterministic information result from facts and a finite domain. */
export function createInformationOutcome(options: {
  readonly id: string;
  readonly key: string;
  readonly recipientId: string;
  readonly subjectId?: string;
  readonly legalValues: readonly DecisionValue[];
  readonly truthValues: readonly DecisionValue[];
  readonly truthful: boolean;
  readonly source?: string;
}): InformationOutcome {
  const legalValues = uniqueValues(options.legalValues);
  const truthValues = uniqueValues(options.truthValues);
  if (!legalValues.length) throw new DecisionDomainError(`Information domain ${options.id} has no legal values`);
  if (!truthValues.length || truthValues.some((value) => !legalValues.some((candidate) => Object.is(candidate, value)))) {
    throw new DecisionDomainError(`Information truth is outside legal domain: ${options.id}`);
  }
  const falseValues = legalValues.filter((value) => !truthValues.some((truth) => Object.is(truth, value)));
  const domain: InformationValueDomain = {
    id: options.id, key: options.key, recipientId: options.recipientId, subjectId: options.subjectId,
    legalValues, truthValues, falseValues, truthful: options.truthful,
  };
  const reportedValue = options.truthful ? truthValues[0]! : (falseValues[0] ?? truthValues[0]!);
  const truthValue: DecisionValue = truthValues.length === 1 ? truthValues[0]! : JSON.stringify(truthValues);
  return {
    domain,
    reportedValue,
    truth: { key: options.key, value: truthValue, subjectId: options.subjectId, source: options.source },
    claim: {
      id: `claim:${options.recipientId}:${options.key}:${options.id}`,
      recipientId: options.recipientId, key: options.key, value: reportedValue,
      factKey: options.key, truthful: options.truthful,
    },
  };
}

/** Authoritative truth and player-facing claims are deliberately separate. */
export class TruthDomain {
  private readonly factsValue = new Map<string, TruthFact>();
  private readonly claimsValue = new Map<string, InformationClaim>();

  constructor(facts: readonly TruthFact[] = [], claims: readonly InformationClaim[] = []) {
    for (const fact of facts) this.setFact(fact);
    for (const claim of claims) this.recordClaim(claim);
  }

  setFact(fact: TruthFact): this {
    if (!fact.key.trim()) throw new Error("Truth fact key is required");
    this.factsValue.set(fact.key, { ...fact });
    return this;
  }

  fact(key: string): TruthFact | undefined {
    const fact = this.factsValue.get(key);
    return fact ? { ...fact } : undefined;
  }

  facts(): readonly TruthFact[] { return [...this.factsValue.values()].map((fact) => ({ ...fact })); }

  recordClaim(claim: InformationClaim): this {
    if (!claim.id.trim() || !claim.recipientId.trim() || !claim.key.trim()) throw new Error("Information claim requires id, recipient and key");
    this.claimsValue.set(claim.id, { ...claim });
    return this;
  }

  claim(id: string): InformationClaim | undefined {
    const claim = this.claimsValue.get(id);
    return claim ? { ...claim } : undefined;
  }

  claimsFor(recipientId: string, key?: string): readonly InformationClaim[] {
    return [...this.claimsValue.values()]
      .filter((claim) => claim.recipientId === recipientId && (key === undefined || claim.key === key))
      .map((claim) => ({ ...claim }));
  }

  claims(): readonly InformationClaim[] { return [...this.claimsValue.values()].map((claim) => ({ ...claim })); }

  clone(): TruthDomain { return new TruthDomain(this.facts(), this.claims()); }
}

export interface RuleState {
  phase: Exclude<Phase, "setup">;
  day: number;
  night: number;
  players: EnginePlayer[];
  statuses: StatusToken[];
  truth: TruthDomain;
  pendingDecisions: DecisionDomain[];
  winner?: Team;
  endReason?: string;
}

export type RuleEventType =
  | "effect_applied" | "status_added" | "status_removed" | "status_expired"
  | "player_killed" | "role_changed" | "information_granted"
  | "decision_created" | "decision_resolved" | "win_declared";

export interface RuleEvent {
  readonly seq: number;
  readonly type: RuleEventType;
  readonly data: Readonly<Record<string, unknown>>;
}

export type RuleEventHandler = (event: RuleEvent) => void;

/** Small synchronous event bus; adapters can bridge these events to any transport. */
export class RuleEventBus {
  private sequence = 0;
  private readonly handlers = new Map<RuleEventType | "*", Set<RuleEventHandler>>();
  private readonly history: RuleEvent[] = [];

  on(type: RuleEventType | "*", handler: RuleEventHandler): () => void {
    const set = this.handlers.get(type) ?? new Set<RuleEventHandler>();
    set.add(handler);
    this.handlers.set(type, set);
    return () => set.delete(handler);
  }

  emit(type: RuleEventType, data: Readonly<Record<string, unknown>>): RuleEvent {
    const event: RuleEvent = { seq: ++this.sequence, type, data: { ...data } };
    this.history.push(event);
    for (const handler of this.handlers.get(type) ?? []) handler(event);
    for (const handler of this.handlers.get("*") ?? []) handler(event);
    return event;
  }

  get events(): readonly RuleEvent[] { return this.history.map((event) => ({ ...event, data: { ...event.data } })); }
}

export function cloneRuleState(state: RuleState): RuleState {
  return {
    ...state,
    players: state.players.map((player) => ({ ...player, death: player.death ? { ...player.death } : undefined })),
    statuses: new StatusTokenStore(state.statuses).list() as StatusToken[],
    truth: state.truth.clone(),
    pendingDecisions: state.pendingDecisions.map((domain) => ({
      ...domain,
      slots: domain.slots.map((slot) => ({ ...slot, options: [...slot.options] })),
      metadata: domain.metadata ? { ...domain.metadata } : undefined,
    })),
  };
}

export interface ApplyEffectsResult {
  readonly state: RuleState;
  readonly pendingDecisions: readonly DecisionDomain[];
  readonly events: readonly RuleEvent[];
}

function requirePlayer(state: RuleState, id: string): EnginePlayer {
  const player = state.players.find((candidate) => candidate.id === id);
  if (!player) throw new Error(`Unknown player: ${id}`);
  return player;
}

/** Apply role effects atomically and produce structured choices for unresolved effects. */
export function applyEffects(state: RuleState, effects: readonly Effect[], bus = new RuleEventBus()): ApplyEffectsResult {
  const next = cloneRuleState(state);
  const tokens = new StatusTokenStore(next.statuses);
  const pending: DecisionDomain[] = [];
  const events: RuleEvent[] = [];
  const publish = (type: RuleEventType, data: Readonly<Record<string, unknown>>) => events.push(bus.emit(type, data));
  effects.forEach((effect, index) => {
    publish("effect_applied", { effectType: effect.type, index });
    switch (effect.type) {
      case "add_status":
        requirePlayer(next, effect.token.targetId);
        tokens.add(effect.token);
        publish("status_added", { tokenId: effect.token.id, kind: effect.token.kind, targetId: effect.token.targetId });
        break;
      case "remove_status":
        if (tokens.remove(effect.tokenId)) publish("status_removed", { tokenId: effect.tokenId });
        break;
      case "kill": {
        const player = requirePlayer(next, effect.targetId);
        if (player.alive) {
          player.alive = false;
          player.death = { byExecution: effect.byExecution, day: next.day, night: next.night };
          publish("player_killed", { playerId: effect.targetId, sourceId: effect.sourceId, cause: effect.cause, byExecution: effect.byExecution });
        }
        break;
      }
      case "change_role": {
        const player = requirePlayer(next, effect.targetId);
        player.role = effect.role;
        player.category = effect.category;
        player.team = effect.team;
        publish("role_changed", { targetId: effect.targetId, role: effect.role, category: effect.category, team: effect.team });
        break;
      }
      case "choose_role_change": {
        const domain: DecisionDomain = {
          id: `role-change:${effect.sourceId}:${index}`,
          actorId: effect.sourceId,
          phase: "night",
          slots: [{
            id: "target", kind: "target", options: effect.legalTargets.map((value) => ({ value })),
            minSelections: 1, maxSelections: 1,
          }],
          metadata: { effectType: "change_role", role: effect.role, category: effect.category, team: effect.team },
        };
        validateDecisionDomain(domain);
        pending.push(domain);
        publish("decision_created", { domainId: domain.id, actorId: domain.actorId, slotIds: domain.slots.map((slot) => slot.id) });
        break;
      }
      case "private_information": {
        requirePlayer(next, effect.recipientId);
        const claim: InformationClaim = {
          id: `claim:${effect.recipientId}:${effect.key}:${index}`,
          recipientId: effect.recipientId, key: effect.key, value: effect.value,
        };
        next.truth.recordClaim(claim);
        publish("information_granted", { claimId: claim.id, recipientId: claim.recipientId, key: claim.key });
        break;
      }
      case "declare_win":
        next.winner = effect.winner;
        next.endReason = effect.reason;
        next.phase = "ended";
        publish("win_declared", { winner: effect.winner, reason: effect.reason });
        break;
    }
  });
  next.statuses = tokens.list() as StatusToken[];
  next.pendingDecisions.push(...pending);
  return { state: next, pendingDecisions: pending, events };
}

export interface RuleStateOptions {
  readonly phase?: Exclude<Phase, "setup">;
  readonly day?: number;
  readonly night?: number;
  readonly statuses?: readonly StatusToken[];
  readonly truth?: TruthDomain;
}

export function createRuleState(players: readonly EnginePlayer[], options: RuleStateOptions = {}): RuleState {
  return {
    phase: options.phase ?? "night", day: options.day ?? 0, night: options.night ?? 1,
    players: players.map((player) => ({ ...player, death: player.death ? { ...player.death } : undefined })),
    statuses: new StatusTokenStore(options.statuses).list() as StatusToken[],
    truth: options.truth?.clone() ?? new TruthDomain(), pendingDecisions: [],
  };
}

export function ringPlayers(players: readonly EnginePlayer[]): readonly EnginePlayer[] {
  return [...players].sort((a, b) => a.seat - b.seat || a.id.localeCompare(b.id));
}

export function ringIndex(players: readonly EnginePlayer[], playerId: string): number {
  const index = ringPlayers(players).findIndex((player) => player.id === playerId);
  if (index < 0) throw new Error(`Unknown player: ${playerId}`);
  return index;
}

export function clockwiseDistance(players: readonly EnginePlayer[], fromId: string, toId: string): number {
  const ring = ringPlayers(players);
  return (ringIndex(ring, toId) - ringIndex(ring, fromId) + ring.length) % ring.length;
}

export function playersInDirection(
  players: readonly EnginePlayer[], startId: string, direction: "clockwise" | "counterclockwise" = "clockwise", includeStart = false,
): readonly EnginePlayer[] {
  const ring = ringPlayers(players);
  const start = ringIndex(ring, startId);
  const step = direction === "clockwise" ? 1 : -1;
  const result: EnginePlayer[] = [];
  for (let offset = includeStart ? 0 : 1; offset < ring.length; offset += 1) result.push(ring[(start + step * offset + ring.length * 2) % ring.length]);
  return result;
}

export function nextPlayer(
  players: readonly EnginePlayer[], startId: string, predicate: (player: EnginePlayer) => boolean = (player) => player.alive,
  direction: "clockwise" | "counterclockwise" = "clockwise",
): EnginePlayer | undefined {
  return playersInDirection(players, startId, direction).find(predicate);
}

/** Stateful façade for adapters: effects, expiry, decisions and hooks share one state. */
export class MathRuleKernel {
  private stateValue: RuleState;
  readonly events: RuleEventBus;

  constructor(state: RuleState, events = new RuleEventBus()) {
    this.stateValue = cloneRuleState(state);
    this.events = events;
  }

  get state(): Readonly<RuleState> { return cloneRuleState(this.stateValue); }

  apply(effects: readonly Effect[]): ApplyEffectsResult {
    const result = applyEffects(this.stateValue, effects, this.events);
    this.stateValue = result.state;
    return { ...result, state: cloneRuleState(result.state) };
  }

  expire(boundary: StatusToken["expiresAt"]): readonly StatusToken[] {
    const next = cloneRuleState(this.stateValue);
    const store = new StatusTokenStore(next.statuses);
    const removed = store.expire(boundary);
    next.statuses = store.list() as StatusToken[];
    this.stateValue = next;
    if (removed.length) this.events.emit("status_expired", { boundary, tokenIds: removed.map((token) => token.id) });
    return removed;
  }

  resolveDecision(domainId: string, input: DecisionInput): DecisionResolution {
    const domain = this.stateValue.pendingDecisions.find((candidate) => candidate.id === domainId);
    if (!domain) throw new DecisionDomainError(`Unknown pending decision: ${domainId}`);
    const resolution = resolveDecisionDomain(domain, input);
    this.stateValue = cloneRuleState(this.stateValue);
    this.stateValue.pendingDecisions = this.stateValue.pendingDecisions.filter((candidate) => candidate.id !== domainId);
    this.events.emit("decision_resolved", { domainId, actorId: domain.actorId, selections: resolution.selections });
    const metadata = domain.metadata;
    if (metadata?.effectType === "change_role") {
      const targetId = resolution.selections.target?.[0];
      if (typeof targetId !== "string" || typeof metadata.role !== "string" || typeof metadata.category !== "string" || typeof metadata.team !== "string") {
        throw new DecisionDomainError(`Invalid role-change decision metadata: ${domainId}`);
      }
      this.apply([{ type: "change_role", targetId, role: metadata.role, category: metadata.category as RoleCategory, team: metadata.team as Team }]);
    }
    return resolution;
  }
}
