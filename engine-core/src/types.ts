export type Team = "good" | "evil";
export type RoleCategory = "Townsfolk" | "Outsider" | "Minion" | "Demon";
export type Phase = "setup" | "night" | "day" | "ended";
export type EventType =
  | "phase_started"
  | "random_draw"
  | "decision_requested"
  | "decision_resolved"
  | "player_killed"
  | "nomination_opened"
  | "vote_cast"
  | "nomination_resolved"
  | "game_ended";

export interface EnginePlayer {
  id: string;
  name?: string;
  seat: number;
  role: string;
  category?: RoleCategory;
  team?: Team;
  alive: boolean;
  death?: { byExecution: boolean; day: number; night: number };
}

export interface Nomination {
  id: string;
  day: number;
  nominatorId: string;
  nomineeId: string;
  votes: string[];
  eligibleVoters: string[];
  resolved?: boolean;
  passed?: boolean;
  executed?: boolean;
}

export interface EngineState {
  gameId: string;
  seed: number;
  phase: Phase;
  day: number;
  night: number;
  stateVersion: number;
  phaseToken: string;
  players: EnginePlayer[];
  nominations: Nomination[];
  winner?: Team;
  endReason?: string;
}

export interface EngineEvent<T = Record<string, unknown>> {
  seq: number;
  type: EventType;
  stateVersion: number;
  phaseToken: string;
  requestId?: string;
  data: T;
}

export interface DecisionRequest<T = string | number | boolean> {
  requestId: string;
  type: string;
  actor: string;
  legalOptions: readonly T[];
  stateVersion: number;
  phaseToken: string;
  metadata?: Record<string, unknown>;
}

export interface DecisionResult<T = string | number | boolean> {
  request: DecisionRequest<T>;
  value: T;
  duplicate: boolean;
}

export type DecisionPolicy = (
  request: DecisionRequest,
  state: Readonly<EngineState>,
) => Promise<string | number | boolean> | string | number | boolean;

export interface GameSetupPlayer {
  id: string;
  name?: string;
  seat?: number;
  role: string;
  category?: RoleCategory;
  team?: Team;
}

export interface EngineOptions {
  gameId: string;
  seed?: number;
  players: readonly GameSetupPlayer[];
  policy?: DecisionPolicy;
  onEvent?: (event: EngineEvent) => void;
}
