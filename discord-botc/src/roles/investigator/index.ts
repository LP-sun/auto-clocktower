import type { RoleDefinition } from "../types";
import { Night } from "../types";
import { buildDecoyPairInfo } from "../../utils/nightInfo";
import { localize } from "../../utils/roleI18n";
import en from "./i18n/en.json";
import zh from "./i18n/zh.json";

const i18n = { en, zh };

export const definition: RoleDefinition = {
  id: "investigator",
  name: localize(i18n, "name"),
  guide: localize(i18n, "guide"),
  nightHandlers: {
    info: {
      active: Night.firstOnly,
      compute: async (ctx) =>
        buildDecoyPairInfo({
          runtime: ctx.state.runtime,
          state: ctx.state,
          sourceAbility: "investigator",
          interactionId: `investigator:${ctx.night.nightNumber}:${ctx.night.player.userId}`,
          playerId: ctx.night.player.userId,
          scriptRoles: ctx.night.scriptRoles,
          category: "Minion",
          reasonKey: "nightReasonDecoyPair",
        }),
    },
  },
};
