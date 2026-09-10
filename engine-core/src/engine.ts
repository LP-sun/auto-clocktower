import {
  DecisionPolicy,
  DecisionRequest,
  DecisionResult,
  EngineEvent,
  EngineOptions,
  EnginePlayer,
  EngineState,
  EventType,
  Phase,
  Team,
} from "./types";
import { EngineError, IllegalDecisionError, InvalidTransitionError, StaleDecisionError } from "./errors";

type Scalar = string | number | boolean;
type Pending<T extends Scalar = Scalar> = {
  request: DecisionRequest<T>;
  resolved?: T;
};

/**
 * Small, transport-agnostic state machine. It owns authoritative state and
 * legal domains; a model is only a DecisionPolicy and cannot mutate state.
 * Every mutating operation is serialized through the same queue.
 */
export class HeadlessEngine {
  private readonly policy?: DecisionPolicy;
  private readonly onEvent?: (event: EngineEvent) => void;
  private stateValue: EngineState;
  private eventSeq = 0;
  private requestSeq = 0;
  private rngState: number;
  private queue: Promise<unknown> = Promise.resolve();
  private readonly pending = new Map<string, Pending>();
  private readonly completedDecisions = new Map<string, Scalar>();
  private readonly completedTransitions = new Map<string, EngineState>();
  private readonly eventsValue: EngineEvent[] = [];

  constructor(options: EngineOptions) {
    if (!options.gameId.trim()) throw new EngineError("gameId is required");
    if (options.players.length < 5) throw new EngineError("At least five players are required");
    const ids = new Set<string>();
    const players: EnginePlayer[] = options.players.map((player, index) => {
      if (ids.has(player.id)) throw new EngineError(`Duplicate player id: ${player.id}`);
      ids.add(player.id);
      return {
        ...player,
        seat: player.seat ?? index,
        alive: true,
      };
    }).sort((a, b) => a.seat - b.seat);
    this.policy = options.policy;
    this.onEvent = options.onEvent;
    this.rngState = (options.seed ?? 0) >>> 0;
    if (this.rngState === 0) this.rngState = 0x9e3779b9;
    this.stateValue = {
      gameId: options.gameId,
      seed: options.seed ?? 0,
      phase: "setup",
      day: 0,
      night: 0,
      stateVersion: 0,
      phaseToken: `${options.gameId}:setup:0`,
      players,
      nominations: [],
    };
  }

  get state(): Readonly<EngineState> {
    return this.snapshot();
  }

  get events(): readonly EngineEvent[] {
    return this.eventsValue.map((event) => ({ ...event, data: { ...event.data } }));
  }

  private snapshot(): EngineState {
    return {
      ...this.stateValue,
      players: this.stateValue.players.map((p) => ({ ...p, death: p.death ? { ...p.death } : undefined })),
      nominations: this.stateValue.nominations.map((n) => ({ ...n, votes: [...n.votes], eligibleVoters: [...n.eligibleVoters] })),
    };
  }

  private enqueue<T>(operation: () => Promise<T> | T): Promise<T> {
    const result = this.queue.then(operation, operation);
    this.queue = result.then(() => undefined, () => undefined);
    return result;
  }

  private emit<T extends Record<string, unknown>>(type: EventType, data: T, requestId?: string): void {
    const event: EngineEvent<T> = {
      seq: ++this.eventSeq,
      type,
      stateVersion: this.stateValue.stateVersion,
      phaseToken: this.stateValue.phaseToken,
      ...(requestId ? { requestId } : {}),
      data,
    };
    this.eventsValue.push(event);
    this.onEvent?.(event);
  }

  /** Start the first night. Repeating the same transition is idempotent. */
  start(transitionId = "start"): Promise<Readonly<EngineState>> {
    return this.transition("night", transitionId);
  }

  transition(next: Phase, transitionId: string): Promise<Readonly<EngineState>> {
    return this.enqueue(() => {
      const completed = this.completedTransitions.get(transitionId);
      if (completed) return this.cloneState(completed);
      const current = this.stateValue.phase;
      const valid = (current === "setup" && next === "night") ||
        (current === "night" && next === "day") ||
        (current === "day" && (next === "night" || next === "ended"));
      if (!valid) throw new InvalidTransitionError(current, next);
      this.stateValue.phase = next;
      if (next === "night") this.stateValue.night += 1;
      if (next === "day") this.stateValue.day += 1;
      this.stateValue.stateVersion += 1;
      this.stateValue.phaseToken = `${this.stateValue.gameId}:${next}:${this.stateValue.stateVersion}`;
      this.pending.clear();
      const snapshot = this.snapshot();
      this.completedTransitions.set(transitionId, snapshot);
      this.emit("phase_started", { phase: next, day: this.stateValue.day, night: this.stateValue.night });
      return this.cloneState(snapshot);
    });
  }

  private cloneState(state: EngineState): Readonly<EngineState> {
    return {
      ...state,
      players: state.players.map((p) => ({ ...p, death: p.death ? { ...p.death } : undefined })),
      nominations: state.nominations.map((n) => ({ ...n, votes: [...n.votes], eligibleVoters: [...n.eligibleVoters] })),
    };
  }

  requestDecision<T extends Scalar>(spec: Omit<DecisionRequest<T>, "requestId" | "stateVersion" | "phaseToken">): Promise<DecisionRequest<T>> {
    return this.enqueue(() => {
      if (this.stateValue.phase === "ended") throw new EngineError("Cannot request a decision after the game ended");
      if (!spec.legalOptions.length) throw new EngineError(`No legal options for ${spec.type}`);
      const request: DecisionRequest<T> = {
        ...spec,
        requestId: `${this.stateValue.gameId}:r${++this.requestSeq}`,
        stateVersion: this.stateValue.stateVersion,
        phaseToken: this.stateValue.phaseToken,
        legalOptions: [...spec.legalOptions],
      };
      this.pending.set(request.requestId, { request });
      this.emit("decision_requested", { type: request.type, actor: request.actor, legalOptions: [...request.legalOptions] }, request.requestId);
      return { ...request, legalOptions: [...request.legalOptions] };
    });
  }

  /** Deterministic per-instance PRNG. It never uses Math.random or global state. */
  nextRandom(): Promise<number> {
    return this.enqueue(() => {
      let x = this.rngState;
      x ^= x << 13;
      x ^= x >>> 17;
      x ^= x << 5;
      this.rngState = x >>> 0;
      const value = this.rngState / 0x100000000;
      this.stateValue.stateVersion += 1;
      this.emit("random_draw", { value });
      return value;
    });
  }

  async pick<T>(values: readonly T[]): Promise<T> {
    if (!values.length) throw new EngineError("Cannot pick from an empty list");
    const index = Math.floor((await this.nextRandom()) * values.length);
    return values[index];
  }

  resolveDecision<T extends Scalar>(request: DecisionRequest<T>, value?: T): Promise<DecisionResult<T>> {
    return this.enqueue(async () => {
      const prior = this.completedDecisions.get(request.requestId);
      if (prior !== undefined) return { request, value: prior as T, duplicate: true };
      const pending = this.pending.get(request.requestId) as Pending<T> | undefined;
      if (!pending) throw new StaleDecisionError(request.requestId, request.stateVersion, this.stateValue.stateVersion, request.phaseToken, this.stateValue.phaseToken);
      if (pending.request.stateVersion !== this.stateValue.stateVersion || pending.request.phaseToken !== this.stateValue.phaseToken) {
        this.pending.delete(request.requestId);
        throw new StaleDecisionError(request.requestId, pending.request.stateVersion, this.stateValue.stateVersion, pending.request.phaseToken, this.stateValue.phaseToken);
      }
      const chosen = value === undefined ? await this.policy?.(pending.request, this.snapshot()) : value;
      const result = (chosen === undefined ? pending.request.legalOptions[0] : chosen) as T;
      if (!pending.request.legalOptions.includes(result)) throw new IllegalDecisionError(result, pending.request.legalOptions);
      this.pending.delete(request.requestId);
      this.completedDecisions.set(request.requestId, result);
      this.emit("decision_resolved", { type: request.type, actor: request.actor, value: result }, request.requestId);
      return { request, value: result, duplicate: false };
    });
  }

  killPlayer(playerId: string, byExecution = false): Promise<Readonly<EngineState>> {
    return this.enqueue(() => {
      const player = this.player(playerId);
      if (!player.alive) return this.snapshot();
      player.alive = false;
      player.death = { byExecution, day: this.stateValue.day, night: this.stateValue.night };
      this.stateValue.stateVersion += 1;
      this.emit("player_killed", { playerId, byExecution });
      this.checkWinInternal();
      return this.snapshot();
    });
  }

  nominate(nominatorId: string, nomineeId: string): Promise<Readonly<EngineState>> {
    return this.enqueue(() => {
      if (this.stateValue.phase !== "day") throw new EngineError("Nominations are only allowed during the day");
      const nominator = this.player(nominatorId);
      const nominee = this.player(nomineeId);
      if (!nominator.alive || !nominee.alive) throw new EngineError("Only living players may nominate or be nominated");
      if (this.stateValue.nominations.some((n) => n.nominatorId === nominatorId && n.day === this.stateValue.day)) throw new EngineError("Player has already nominated today");
      const id = `${this.stateValue.gameId}:n${this.stateValue.nominations.length + 1}`;
      const eligibleVoters = this.stateValue.players.filter((p) => p.alive).map((p) => p.id);
      this.stateValue.nominations.push({ id, day: this.stateValue.day, nominatorId, nomineeId, votes: [], eligibleVoters });
      this.stateValue.stateVersion += 1;
      this.emit("nomination_opened", { id, nominatorId, nomineeId });
      return this.snapshot();
    });
  }

  castVote(nominationId: string, voterId: string, yes = true): Promise<Readonly<EngineState>> {
    return this.enqueue(() => {
      const nomination = this.stateValue.nominations.find((n) => n.id === nominationId);
      if (!nomination) throw new EngineError(`Unknown nomination: ${nominationId}`);
      if (!nomination.eligibleVoters.includes(voterId)) throw new EngineError("Player is not eligible to vote");
      if (yes && !nomination.votes.includes(voterId)) nomination.votes.push(voterId);
      this.stateValue.stateVersion += 1;
      this.emit("vote_cast", { nominationId, voterId, yes });
      return this.snapshot();
    });
  }

  resolveNomination(nominationId: string): Promise<Readonly<EngineState>> {
    return this.enqueue(() => {
      const nomination = this.stateValue.nominations.find((n) => n.id === nominationId);
      if (!nomination) throw new EngineError(`Unknown nomination: ${nominationId}`);
      if (nomination.resolved) return this.snapshot();
      // A nomination passes its vote at half of the living voters, rounded up.
      // Passing the vote does not itself execute the nominee: at day end the
      // highest unique passing nomination is selected across the whole day.
      nomination.resolved = true;
      nomination.passed = nomination.votes.length >= Math.ceil(nomination.eligibleVoters.length / 2);
      this.stateValue.stateVersion += 1;
      this.emit("nomination_resolved", { nominationId, passed: nomination.passed, votes: nomination.votes.length });
      return this.snapshot();
    });
  }

  /** Resolve the day's nominations and execute only a unique highest candidate. */
  resolveDayNominations(): Promise<Readonly<EngineState>> {
    return this.enqueue(() => {
      if (this.stateValue.phase !== "day") throw new EngineError("Day nominations can only resolve during the day");
      const todays = this.stateValue.nominations.filter((n) => n.day === this.stateValue.day);
      for (const nomination of todays) {
        if (nomination.resolved) continue;
        nomination.resolved = true;
        nomination.passed = nomination.votes.length >= Math.ceil(nomination.eligibleVoters.length / 2);
        this.stateValue.stateVersion += 1;
        this.emit("nomination_resolved", { nominationId: nomination.id, passed: nomination.passed, votes: nomination.votes.length });
      }
      const passing = todays.filter((n) => n.passed && !n.executed);
      const highest = Math.max(0, ...passing.map((n) => n.votes.length));
      const leaders = passing.filter((n) => n.votes.length === highest);
      if (highest > 0 && leaders.length === 1) {
        const nominee = this.player(leaders[0].nomineeId);
        if (nominee.alive) {
          nominee.alive = false;
          nominee.death = { byExecution: true, day: this.stateValue.day, night: this.stateValue.night };
          leaders[0].executed = true;
          this.stateValue.stateVersion += 1;
          this.emit("player_killed", { playerId: nominee.id, byExecution: true });
          this.checkWinInternal();
        }
      }
      return this.snapshot();
    });
  }

  end(reason = "ended", winner?: Team): Promise<Readonly<EngineState>> {
    return this.enqueue(() => {
      if (this.stateValue.phase === "ended") return this.snapshot();
      this.stateValue.phase = "ended";
      this.stateValue.winner = winner;
      this.stateValue.endReason = reason;
      this.stateValue.stateVersion += 1;
      this.stateValue.phaseToken = `${this.stateValue.gameId}:ended:${this.stateValue.stateVersion}`;
      this.pending.clear();
      this.emit("game_ended", { reason, winner: winner ?? null });
      return this.snapshot();
    });
  }

  private checkWinInternal(): void {
    const alive = this.stateValue.players.filter((p) => p.alive);
    const demon = alive.find((p) => p.category === "Demon" || p.role === "imp");
    if (!demon) {
      this.finishGame("demon_dead", "good");
      return;
    }
    if (alive.length <= 2) {
      this.finishGame("final_two", "evil");
    }
  }

  private finishGame(reason: string, winner: Team): void {
    this.stateValue.phase = "ended";
    this.stateValue.winner = winner;
    this.stateValue.endReason = reason;
    this.stateValue.stateVersion += 1;
    this.stateValue.phaseToken = `${this.stateValue.gameId}:ended:${this.stateValue.stateVersion}`;
    this.pending.clear();
    this.emit("game_ended", { reason, winner });
  }

  private player(id: string): EnginePlayer {
    const player = this.stateValue.players.find((candidate) => candidate.id === id);
    if (!player) throw new EngineError(`Unknown player: ${id}`);
    return player;
  }
}

export function createTroubleBrewingGame(options: EngineOptions): HeadlessEngine {
  return new HeadlessEngine(options);
}
