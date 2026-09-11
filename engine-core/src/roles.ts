import type {
  EnginePlayer,
  EngineState,
  Phase,
  RoleCategory,
  Team,
} from "./types";
import type { DecisionDomain, DecisionResolution, InformationOutcome } from "./math-rules";

/** A serialisable status carried by the authoritative game state. */
export interface StatusToken {
  /** Stable, deterministic identifier (never generated with Math.random). */
  id: string;
  kind: "poisoned" | "protected" | (string & {});
  targetId: string;
  sourceId?: string;
  createdAt: { day: number; night: number; phase: Phase };
  /** The phase boundary at which this token is removed. */
  expiresAt: "dawn" | "dusk" | "game_end";
  /** Optional structured details for future script rules. */
  metadata?: Readonly<Record<string, string | number | boolean>>;
}

/**
 * Effects are the only output of a role rule.  A storyteller/adapter applies
 * them to an EngineState; role rules themselves never mutate state or access a
 * transport such as Discord.
 */
export type Effect =
  | {
      type: "add_status";
      token: StatusToken;
    }
  | {
      type: "remove_status";
      tokenId: string;
    }
  | {
      type: "kill";
      targetId: string;
      sourceId: string;
      cause: "demon" | "ability" | "execution";
      byExecution: boolean;
    }
  | {
      type: "change_role";
      targetId: string;
      role: string;
      category: RoleCategory;
      team: Team;
    }
  | {
      type: "choose_role_change";
      sourceId: string;
      legalTargets: readonly string[];
      role: string;
      category: RoleCategory;
      team: Team;
    }
  | {
      type: "private_information";
      recipientId: string;
      key: string;
      value: unknown;
    }
  | {
      type: "declare_win";
      winner: Team;
      reason: string;
    };

export interface RolePluginContext {
  readonly state: Readonly<EngineState>;
  readonly self: Readonly<EnginePlayer>;
  /** Active status tokens, supplied by the state adapter. */
  readonly statuses: readonly StatusToken[];
}

export interface TargetRule {
  aliveOnly: boolean;
  allowSelf: boolean;
  minTargets: 1;
  maxTargets: 1;
}

/** A fully parameterised action request for a model or UI. */
export interface RoleAction {
  id: string;
  actorId: string;
  phase: "night" | "day";
  legalTargets: readonly string[];
  targetRule: TargetRule;
  metadata?: Readonly<Record<string, string | number | boolean>>;
}

export interface NightKillContext extends RolePluginContext {
  sourceId: string;
  targetId: string;
}

export interface NightKillResolution {
  prevented: boolean;
  reason?: "soldier" | "monk_protection" | "other";
  effects: readonly Effect[];
}

/** A transport-free description of one script character. */
export interface RolePlugin {
  readonly id: string;
  readonly name: { en: string; zh: string };
  readonly category: RoleCategory;
  readonly team: Team;
  readonly ability: { en: string; zh: string };
  /** Original BotC script fields retained by an importer. */
  readonly script?: ScriptRoleMetadata;
  readonly firstNight?: number;
  readonly firstNightReminder?: string;
  readonly otherNight?: number;
  readonly otherNightReminder?: string;
  readonly reminders?: readonly string[];
  readonly remindersGlobal?: readonly string[];
  readonly setup?: boolean | number;
  /** True for rules that have been migrated to this engine. */
  readonly implemented?: boolean;
  buildNightAction?: (context: RolePluginContext) => RoleAction | undefined;
  resolveNightAction?: (context: RolePluginContext, targetId: string) => readonly Effect[];
  /** Finite target/choice domain. The model may select only from this domain. */
  buildDecisionDomain?: (context: RolePluginContext) => DecisionDomain | undefined;
  /** Resolve an already validated decision into authoritative information. */
  resolveInformation?: (context: RolePluginContext, resolution: DecisionResolution) => InformationOutcome | undefined;
  /** Compute information-only roles without asking a model for a fact. */
  computeInformation?: (context: RolePluginContext) => InformationOutcome | undefined;
  /** Called by a kill resolver when this role is the target of a Demon attack. */
  preventsDemonKill?: (context: RolePluginContext) => boolean;
}

/** Lossless, normalized view of the fields supplied by a BotC script JSON entry. */
export interface ScriptRoleMetadata {
  readonly edition?: string;
  readonly firstNight?: number;
  readonly firstNightReminder?: string;
  readonly otherNight?: number;
  readonly otherNightReminder?: string;
  readonly reminders: readonly string[];
  readonly remindersGlobal: readonly string[];
  readonly setup?: boolean | number;
  readonly flavor?: string;
  readonly image?: string;
  readonly nameEng?: string;
  readonly raw: Readonly<Record<string, unknown>>;
}

export class RoleRuleError extends Error {
  override name = "RoleRuleError";
}

export function isPoisoned(context: RolePluginContext, playerId = context.self.id): boolean {
  return context.statuses.some((token) => token.kind === "poisoned" && token.targetId === playerId);
}

function livingPlayers(context: RolePluginContext, allowSelf: boolean): readonly EnginePlayer[] {
  return context.state.players.filter((player) => player.alive && (allowSelf || player.id !== context.self.id));
}

function targetAction(
  context: RolePluginContext,
  id: string,
  allowSelf: boolean,
  metadata?: Readonly<Record<string, string | number | boolean>>,
): RoleAction | undefined {
  // A poisoned character still wakes and makes a normal-looking choice. The
  // rule resolver suppresses the effect without revealing the poison.
  if (!context.self.alive) return undefined;
  return {
    id,
    actorId: context.self.id,
    phase: "night",
    legalTargets: livingPlayers(context, allowSelf).map((player) => player.id),
    targetRule: { aliveOnly: true, allowSelf, minTargets: 1, maxTargets: 1 },
    metadata,
  };
}

function assertTarget(action: RoleAction, targetId: string): void {
  if (!action.legalTargets.includes(targetId)) {
    throw new RoleRuleError(`Illegal target ${targetId} for ${action.id}`);
  }
}

function tokenId(kind: string, sourceId: string, targetId: string, night: number): string {
  return `${kind}:${sourceId}:${targetId}:n${night}`;
}

export const soldier: RolePlugin = {
  id: "soldier",
  name: { en: "Soldier", zh: "士兵" },
  category: "Townsfolk",
  team: "good",
  ability: {
    en: "You are safe from the Demon.",
    zh: "你不会被恶魔杀死。",
  },
  implemented: true,
  preventsDemonKill: (context) => !isPoisoned(context),
};

export const monk: RolePlugin = {
  id: "monk",
  name: { en: "Monk", zh: "僧侣" },
  category: "Townsfolk",
  team: "good",
  ability: {
    en: "Each night*, choose a player (not yourself): they are safe from the Demon tonight.",
    zh: "每晚*，选择一名玩家（不能是你自己）：他今晚不会被恶魔杀死。",
  },
  implemented: true,
  buildNightAction: (context) => {
    if (context.state.night < 2) return undefined;
    return targetAction(context, "monk_protect", false, { expiresAt: "dawn" });
  },
  resolveNightAction: (context, targetId) => {
    const action = monk.buildNightAction?.(context);
    if (!action) throw new RoleRuleError("Monk has no action this night");
    assertTarget(action, targetId);
    if (isPoisoned(context)) return [];
    return [
      {
        type: "add_status",
        token: {
          id: tokenId("protected", context.self.id, targetId, context.state.night),
          kind: "protected",
          targetId,
          sourceId: context.self.id,
          createdAt: {
            day: context.state.day,
            night: context.state.night,
            phase: context.state.phase,
          },
          expiresAt: "dawn",
        },
      },
    ];
  },
};

export const poisoner: RolePlugin = {
  id: "poisoner",
  name: { en: "Poisoner", zh: "投毒者" },
  category: "Minion",
  team: "evil",
  ability: {
    en: "Each night, choose a player: they are poisoned tonight and tomorrow day.",
    zh: "每晚，选择一名玩家：他在今夜和明天白天中毒。",
  },
  implemented: true,
  buildNightAction: (context) => targetAction(context, "poisoner_poison", true, { expiresAt: "dusk" }),
  resolveNightAction: (context, targetId) => {
    const action = poisoner.buildNightAction?.(context);
    if (!action) throw new RoleRuleError("Dead Poisoner cannot act");
    assertTarget(action, targetId);
    if (isPoisoned(context)) return [];
    return [
      {
        type: "add_status",
        token: {
          id: tokenId("poisoned", context.self.id, targetId, context.state.night),
          kind: "poisoned",
          targetId,
          sourceId: context.self.id,
          createdAt: {
            day: context.state.day,
            night: context.state.night,
            phase: context.state.phase,
          },
          expiresAt: "dusk",
        },
      },
    ];
  },
};

export const imp: RolePlugin = {
  id: "imp",
  name: { en: "Imp", zh: "小恶魔" },
  category: "Demon",
  team: "evil",
  ability: {
    en: "Each night*, choose a player: they die. If you choose yourself, a living Minion becomes the Imp.",
    zh: "每晚*，选择一名玩家：他死亡。若你以此法选择自己，一名存活的爪牙成为小恶魔。",
  },
  implemented: true,
  buildNightAction: (context) => {
    if (context.state.night < 2) return undefined;
    return targetAction(context, "imp_kill", true, {
      selfTarget: true,
    });
  },
  resolveNightAction: (context, targetId) => {
    const action = imp.buildNightAction?.(context);
    if (!action) throw new RoleRuleError("Imp has no action this night");
    assertTarget(action, targetId);
    if (isPoisoned(context)) return [];
    const effects: Effect[] = [
      {
        type: "kill",
        targetId,
        sourceId: context.self.id,
        cause: "demon",
        byExecution: false,
      },
    ];
    if (targetId === context.self.id) {
      const livingMinions = context.state.players.filter(
        (player) => player.alive && player.category === "Minion" && player.id !== context.self.id,
      );
      if (livingMinions.length) {
        effects.push({
          type: "choose_role_change",
          sourceId: context.self.id,
          legalTargets: livingMinions.map((player) => player.id),
          role: "imp",
          category: "Demon",
          team: "evil",
        });
      }
    }
    return effects;
  },
};

/** Resolves the two Trouble Brewing forms of protection without mutating state. */
export function resolveNightKill(context: NightKillContext): NightKillResolution {
  const target = context.state.players.find((player) => player.id === context.targetId);
  if (!target || !target.alive) {
    return { prevented: true, reason: "other", effects: [] };
  }
  if (context.statuses.some((token) => token.kind === "protected" && token.targetId === target.id)) {
    return { prevented: true, reason: "monk_protection", effects: [] };
  }
  if (target.role.toLowerCase() === "soldier" && !isPoisoned(context, target.id)) {
    return { prevented: true, reason: "soldier", effects: [] };
  }
  return {
    prevented: false,
    effects: [
      {
        type: "kill",
        targetId: target.id,
        sourceId: context.sourceId,
        cause: "demon",
        byExecution: false,
      },
    ],
  };
}

export const IMPLEMENTED_TB_ROLES = [soldier, poisoner, monk, imp] as const;
