import type { RoleCategory, Team } from "./types";
import { IMPLEMENTED_TB_ROLES, type RolePlugin } from "./roles";
import type { ScriptManifest } from "./script";

type CatalogEntry = {
  id: string;
  category: RoleCategory;
  team: Team;
  en: string;
  zh: string;
};

/** Canonical Trouble Brewing role roster. Rules are filled in by RolePlugins. */
const CATALOG: readonly CatalogEntry[] = [
  { id: "washerwoman", category: "Townsfolk", team: "good", en: "You learn that 1 of 2 players is a particular Townsfolk.", zh: "首夜，你会得知两名玩家中的一人是某个镇民。" },
  { id: "librarian", category: "Townsfolk", team: "good", en: "You learn that 1 of 2 players is a particular Outsider, or that there are no Outsiders in play.", zh: "首夜，你会得知两名玩家中的一人是某个外来者，或得知没有外来者在场。" },
  { id: "investigator", category: "Townsfolk", team: "good", en: "You learn that 1 of 2 players is a particular Minion.", zh: "首夜，你会得知两名玩家中的一人是某个爪牙。" },
  { id: "chef", category: "Townsfolk", team: "good", en: "You learn how many pairs of neighbouring players are evil.", zh: "首夜，你会得知有多少对相邻的邪恶玩家。" },
  { id: "empath", category: "Townsfolk", team: "good", en: "Each night, you learn how many of your 2 alive neighbours are evil.", zh: "每晚，你会得知与你相邻的两名存活玩家中有几名邪恶。" },
  { id: "fortune_teller", category: "Townsfolk", team: "good", en: "Each night, choose 2 players: you learn if either is the Demon. There is a good player who registers as the Demon to you.", zh: "每晚，选择两名玩家：你会得知他们之中是否有恶魔。有一名善良玩家会被你当成恶魔。" },
  { id: "undertaker", category: "Townsfolk", team: "good", en: "Each night*, you learn which character died by execution today.", zh: "每晚*，你会得知今天白天死于处决的玩家的角色。" },
  { id: "monk", category: "Townsfolk", team: "good", en: "Each night*, choose a player (not yourself): they are safe from the Demon tonight.", zh: "每晚*，选择一名玩家（不能是你自己）：他今晚不会被恶魔杀死。" },
  { id: "ravenkeeper", category: "Townsfolk", team: "good", en: "If you die at night, you are woken to choose a player: you learn their character.", zh: "如果你在夜间死亡，你会醒来并选择一名玩家，得知其角色。" },
  { id: "virgin", category: "Townsfolk", team: "good", en: "The 1st time you are nominated, if the nominator is a Townsfolk, they are executed immediately.", zh: "当你第一次被提名时，如果提名者是镇民，提名者立即被处决。" },
  { id: "slayer", category: "Townsfolk", team: "good", en: "Once per game, during the day, publicly choose a player: if they are the Demon, they die.", zh: "每局一次，在白天公开选择一名玩家：如果他是恶魔，他死亡。" },
  { id: "soldier", category: "Townsfolk", team: "good", en: "You are safe from the Demon.", zh: "你不会被恶魔杀死。" },
  { id: "mayor", category: "Townsfolk", team: "good", en: "If only 3 players live and no execution occurs, your team wins. If you are attacked at night, another player might die instead.", zh: "如果只有3名玩家存活且白天无人被处决，你的阵营获胜。你在夜间将死时，可能会有其他玩家代你死亡。" },
  { id: "butler", category: "Outsider", team: "good", en: "Each night, choose a player (not yourself) to be your master. You may only vote if they are voting too.", zh: "每晚，选择一名玩家（不能是你自己）作为主人。只有主人投票时你才能投票。" },
  { id: "drunk", category: "Outsider", team: "good", en: "You do not know that you are the Drunk. You think you are a Townsfolk, but you are not.", zh: "你不知道自己是酒鬼。你以为自己是镇民，但其实不是。" },
  { id: "recluse", category: "Outsider", team: "good", en: "You might register as evil and as a Minion or Demon, even if dead.", zh: "你可能登记为邪恶、爪牙或恶魔，即使你已经死亡。" },
  { id: "saint", category: "Outsider", team: "good", en: "If you die by execution, your team loses.", zh: "如果你死于处决，你的阵营失败。" },
  { id: "poisoner", category: "Minion", team: "evil", en: "Each night, choose a player: they are poisoned tonight and tomorrow day.", zh: "每晚，选择一名玩家：他在今夜和明天白天中毒。" },
  { id: "spy", category: "Minion", team: "evil", en: "Each night, you see the Grimoire. You might register as good, Townsfolk, or Outsider, even if dead.", zh: "每晚，你可以查看魔典。你可能登记为善良、镇民或外来者，即使你已经死亡。" },
  { id: "scarlet_woman", category: "Minion", team: "evil", en: "If the Demon dies and there are 5 or more players alive, you become the Demon.", zh: "当恶魔死亡时，若存活玩家不少于5人，你成为恶魔。" },
  { id: "baron", category: "Minion", team: "evil", en: "There are extra Outsiders in play. [+2 Outsiders]", zh: "有额外的外来者在场。[+2外来者]" },
  { id: "imp", category: "Demon", team: "evil", en: "Each night*, choose a player: they die. If you choose yourself, a living Minion becomes the Imp.", zh: "每晚*，选择一名玩家：他死亡。若你以此法选择自己，一名存活的爪牙成为小恶魔。" },
] as const;

function placeholder(entry: CatalogEntry): RolePlugin {
  const englishNames: Record<string, string> = {
    washerwoman: "Washerwoman",
    librarian: "Librarian",
    investigator: "Investigator",
    chef: "Chef",
    empath: "Empath",
    fortune_teller: "Fortune Teller",
    undertaker: "Undertaker",
    monk: "Monk",
    ravenkeeper: "Ravenkeeper",
    virgin: "Virgin",
    slayer: "Slayer",
    soldier: "Soldier",
    mayor: "Mayor",
    butler: "Butler",
    drunk: "Drunk",
    recluse: "Recluse",
    saint: "Saint",
    poisoner: "Poisoner",
    spy: "Spy",
    scarlet_woman: "Scarlet Woman",
    baron: "Baron",
    imp: "Imp",
  };
  const chineseNames: Record<string, string> = {
    washerwoman: "洗衣妇",
    librarian: "图书管理员",
    investigator: "调查员",
    chef: "厨师",
    empath: "共情者",
    fortune_teller: "占卜师",
    undertaker: "送葬者",
    monk: "僧侣",
    ravenkeeper: "守鸦人",
    virgin: "贞洁者",
    slayer: "猎手",
    soldier: "士兵",
    mayor: "镇长",
    butler: "管家",
    drunk: "酒鬼",
    recluse: "陌客",
    saint: "圣徒",
    poisoner: "投毒者",
    spy: "间谍",
    scarlet_woman: "红唇女郎",
    baron: "男爵",
    imp: "小恶魔",
  };
  return {
    id: entry.id,
    name: { en: englishNames[entry.id] ?? entry.id.replace(/_/g, " "), zh: chineseNames[entry.id] ?? entry.id },
    category: entry.category,
    team: entry.team,
    ability: { en: entry.en, zh: entry.zh },
    implemented: false,
  };
}

const migrated = new Map(IMPLEMENTED_TB_ROLES.map((role) => [role.id, role]));

/** Trouble Brewing manifest with all 22 script roles and explicit migration status. */
export const TROUBLE_BREWING_MANIFEST: ScriptManifest = (() => {
  const roles = CATALOG.map((entry) => migrated.get(entry.id) ?? placeholder(entry));
  return {
    id: "trouble_brewing",
    name: { en: "Trouble Brewing", zh: "暗流涌动" },
    version: 1,
    roles,
    roleIds: roles.map((role) => role.id),
    implementedRoleIds: roles.filter((role) => role.implemented).map((role) => role.id),
  };
})();
