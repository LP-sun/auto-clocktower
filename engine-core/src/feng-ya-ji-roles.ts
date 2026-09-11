import { createInformationOutcome, nextPlayer, type DecisionDomain, type DecisionResolution, type InformationOutcome } from "./math-rules";
import { isPoisoned, imp, monk, type RolePlugin, type RolePluginContext } from "./roles";
import type { EnginePlayer } from "./types";

function isTruthful(context: RolePluginContext): boolean {
  const vortox = context.state.players.some((p) => p.alive && p.role === "vortox" && !isPoisoned(context, p.id));
  const drunk = context.statuses.some((s) => s.kind === "drunk" && s.targetId === context.self.id);
  return !isPoisoned(context) && !drunk && !(context.self.category === "Townsfolk" && vortox);
}

function outcome(context: RolePluginContext, key: string, legalValues: readonly (string | number | boolean)[], truthValues: readonly (string | number | boolean)[]): InformationOutcome {
  return createInformationOutcome({ id: `${context.self.id}:n${context.state.night}:${key}`, key, recipientId: context.self.id, legalValues, truthValues, truthful: isTruthful(context), source: context.self.role });
}

function pairs<T>(values: readonly T[]): readonly [T, T][] {
  const result: [T, T][] = [];
  for (let a = 0; a < values.length; a += 1) for (let b = a + 1; b < values.length; b += 1) result.push([values[a], values[b]]);
  return result;
}

function roleBase(id: string, en: string, zh: string, ability: string): RolePlugin {
  return { id, name: { en, zh }, category: "Townsfolk", team: "good", ability: { en: "", zh: ability }, implemented: true };
}

export const shugenja: RolePlugin = {
  ...roleBase("shugenja", "Shugenja", "修行者", "在你的首个夜晚，你会得知距离最近的邪恶玩家位于你的顺时针还是逆时针方向。"),
  computeInformation(context) {
    if (context.state.night !== 1) return undefined;
    const evil = (p: EnginePlayer) => p.alive && p.team === "evil";
    const cw = nextPlayer(context.state.players, context.self.id, evil, "clockwise");
    const ccw = nextPlayer(context.state.players, context.self.id, evil, "counterclockwise");
    if (!cw || !ccw) return undefined;
    const ring = [...context.state.players].sort((a, b) => a.seat - b.seat);
    const at = (id: string) => ring.findIndex((p) => p.id === id);
    const origin = at(context.self.id);
    const cwDistance = (at(cw.id) - origin + ring.length) % ring.length;
    const ccwDistance = (origin - at(ccw.id) + ring.length) % ring.length;
    const truth = cwDistance === ccwDistance ? ["clockwise", "counterclockwise"] : [cwDistance < ccwDistance ? "clockwise" : "counterclockwise"];
    return outcome(context, "shugenja.direction", ["clockwise", "counterclockwise"], truth);
  },
};

export const empath: RolePlugin = {
  ...roleBase("empath", "Empath", "共情者", "每个夜晚，你会得知与你邻近的两名存活的玩家中邪恶玩家的数量。"),
  computeInformation(context) {
    const alive = (p: EnginePlayer) => p.alive;
    const neighbours = [nextPlayer(context.state.players, context.self.id, alive, "clockwise"), nextPlayer(context.state.players, context.self.id, alive, "counterclockwise")]
      .filter((p): p is EnginePlayer => Boolean(p));
    const count = new Set(neighbours.map((p) => p.id)).size === 1 ? Number(neighbours[0]?.team === "evil") : neighbours.filter((p) => p.team === "evil").length;
    return outcome(context, "empath.evil_neighbours", [0, 1, 2], [count]);
  },
};

function chooseTwoDomain(context: RolePluginContext, id: string): DecisionDomain {
  return { id: `${context.self.id}:n${context.state.night}:${id}`, actorId: context.self.id, phase: "night", slots: [{ id: "targets", kind: "target", options: context.state.players.map((p) => p.id), minSelections: 2, maxSelections: 2, allowDuplicates: false }] };
}

export const fortuneTeller: RolePlugin = {
  ...roleBase("fortune_teller", "Fortune Teller", "占卜师", "每个夜晚，选择两名玩家：你会得知其中是否有恶魔。"),
  buildDecisionDomain: (context) => chooseTwoDomain(context, "fortune_teller.targets"),
  resolveInformation(context, resolution) {
    const targets = resolution.selections.targets ?? [];
    const yes = targets.some((id) => context.state.players.some((p) => p.id === id && p.category === "Demon")) || targets.some((id) => context.statuses.some((s) => s.kind === "red_herring" && s.targetId === id));
    return outcome(context, "fortune_teller.demon", [false, true], [yes]);
  },
};

function encodedPair(a: string, b: string, role?: string): string {
  const players = [a, b].sort();
  return JSON.stringify({ players, ...(role ? { role } : {}) });
}

export const librarian: RolePlugin = {
  ...roleBase("librarian", "Librarian", "图书管理员", "在你的首个夜晚，你会得知两名玩家和一个外来者角色。"),
  computeInformation(context) {
    if (context.state.night !== 1) return undefined;
    const allPairs = pairs(context.state.players).map(([a, b]) => encodedPair(a.id, b.id));
    const outsiders = context.state.players.filter((p) => p.category === "Outsider");
    if (!outsiders.length) return outcome(context, "librarian.pair", ["no_outsiders", ...allPairs], ["no_outsiders"]);
    const truth: string[] = [];
    const legal = new Set<string>();
    for (const outsider of outsiders) for (const other of context.state.players) if (other.id !== outsider.id) truth.push(encodedPair(outsider.id, other.id, outsider.role));
    for (const [a, b] of pairs(context.state.players)) for (const role of outsiders.map((p) => p.role)) legal.add(encodedPair(a.id, b.id, role));
    return outcome(context, "librarian.pair", [...legal], truth);
  },
};

export const innkeeper: RolePlugin = {
  ...roleBase("dianxiaoer", "", "店小二", "在你的首个夜晚，你会得知两名善良玩家。他们之中会有一人醉酒，即使你已死亡。"),
  computeInformation(context) {
    if (context.state.night !== 1) return undefined;
    const good = context.state.players.filter((p) => p.team === "good");
    const drunkIds = new Set(context.statuses.filter((s) => s.kind === "drunk").map((s) => s.targetId));
    const legal = pairs(good).flatMap(([a, b]) => [JSON.stringify({ players: [a.id, b.id], drunk: a.id }), JSON.stringify({ players: [a.id, b.id], drunk: b.id })]);
    const truth = legal.filter((value) => { const parsed = JSON.parse(value) as { drunk: string }; return drunkIds.has(parsed.drunk); });
    if (!truth.length) return undefined;
    return outcome(context, "dianxiaoer.guests", legal, truth);
  },
};

export const ABILITY_KEYWORDS: Readonly<Record<string, readonly string[]>> = {
  librarian: ["外来者"], shugenja: ["方向"], dianxiaoer: ["醉酒"], empath: ["相邻"], fortune_teller: ["恶魔"], langzhong: ["词语"], undertaker: ["处决"], monk: ["保护"], savant: ["真假"], bianlianshi: ["疯狂"], artist: ["问题"], wudaozhe: ["转变"], ravenkeeper: ["死亡"], hatter: ["换职"], barber: ["交换"], drunk: ["以为"], nichen: ["阵营"], cerenovus: ["疯狂"], witch: ["提名"], marionette: ["邻座"], scarlet_woman: ["接任"], hundun: ["互认"], no_dashii: ["中毒"], imp: ["自杀"], vortox: ["错误"], spirit_of_ivory: ["邪恶上限"],
};

export const physician: RolePlugin = {
  ...roleBase("langzhong", "", "郎中", "每个夜晚，选择一名玩家：你会得知一个与他能力相关的词语。"),
  buildDecisionDomain(context) { return { id: `${context.self.id}:n${context.state.night}:langzhong.target`, actorId: context.self.id, phase: "night", slots: [{ id: "target", kind: "target", options: context.state.players.filter((p) => p.id !== context.self.id).map((p) => p.id) }] }; },
  resolveInformation(context, resolution) {
    const targetId = resolution.selections.target?.[0];
    const target = context.state.players.find((p) => p.id === targetId);
    if (!target) return undefined;
    const truth = ABILITY_KEYWORDS[target.role] ?? [target.role];
    const legal = [...new Set(Object.values(ABILITY_KEYWORDS).flat())];
    return outcome(context, "langzhong.keyword", legal, truth);
  },
};

export const FENG_YA_JI_IMPLEMENTATIONS: Readonly<Record<string, RolePlugin>> = {
  librarian, shugenja, dianxiaoer: innkeeper, empath, fortune_teller: fortuneTeller, langzhong: physician, monk, imp,
};
