export * from "./types";
export * from "./errors";
export * from "./engine";
export * from "./roles";
export * from "./script";
export * from "./trouble-brewing";
export * from "./botc-script-importer";
export * from "./feng-ya-ji";
export * from "./feng-ya-ji-roles";
export * from "./math-rules";

import { ScriptRegistry } from "./script";
import { TROUBLE_BREWING_MANIFEST } from "./trouble-brewing";
import { FENG_YA_JI_MANIFEST } from "./feng-ya-ji";

/** Default registry used by headless callers that do not need a custom script. */
export const scriptRegistry = new ScriptRegistry([TROUBLE_BREWING_MANIFEST, FENG_YA_JI_MANIFEST]);

export function getScript(id = "trouble_brewing") {
  return scriptRegistry.get(id);
}
