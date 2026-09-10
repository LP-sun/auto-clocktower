import { Content } from '@google/generative-ai';

export type GameStatus = 'evil-wins' | 'good-wins' | 'ongoing';

export type PlayerStatus = 'alive' | 'dead-with-vote' | 'dead-without-vote';

export type Role = {
  name: string;
  type: 'townsfolk' | 'outsider' | 'minion' | 'demon';
  ability: string;
  detailed_description: string;
  player_tips: string[];
  bluffing_tips?: string[];
  fighting_tips?: string[];
  examples?: string[];
};

export type Player = {
  ephemeralControl?: boolean;
  name: string;
  actualRole: string;
  // The token shown to the player, if it is different to their actual role
  tokenShown?: string;
  chatHistory: Content[];
  actionHistory: string[];
  status: PlayerStatus;
  /** Stable simulation parameters. They shape reasoning but never grant state. */
  behaviorParameters?: PlayerBehaviorParameters;
};

export type PlayerBehaviorParameters = {
  personality: Record<string, number>;
  skill: { level: string; decisionTemperature: number; [key: string]: string | number };
};

export type PlayerResponse = {
  memoryUpdate?: { beliefs: Array<{player:string; summary:string}>; plan:string[]; worlds:string[] } | null;
  reasoning: string;
  action: string;
  message?: string;
  players?: string[];
  communication?: {
    intent: string;
    identityClaims: { subject: string; claimedRole: string }[];
    evidenceRefs: number[];
  } | null;
};

export type PlayerResponseWithPlayer = PlayerResponse & { player: Player };

export type NominationResult = {
  result: 'on-the-block' | 'tie' | 'insufficient-votes';
  votes: number;
  nominator: Player;
  nominee: Player;
};

export type PlayerDiscussionResult = {
  action: string;
  nomination?: NominationResult;
};
