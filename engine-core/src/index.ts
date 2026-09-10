export * from "./types";
export * from "./errors";
export * from "./engine";
export * from "./roles";
export * from "./script";
export * from "./trouble-brewing";

import { ScriptRegistry } from "./script";
import { TROUBLE_BREWING_MANIFEST } from "./trouble-brewing";

/** Default registry used by headless callers that do not need a custom script. */
export const scriptRegistry = new ScriptRegistry([TROUBLE_BREWING_MANIFEST]);

export function getScript(id = "trouble_brewing") {
  return scriptRegistry.get(id);
}
