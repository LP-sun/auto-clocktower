import { readFileSync } from "node:fs";
import { join } from "node:path";
import { importBotcScript } from "./botc-script-importer";

const source = JSON.parse(readFileSync(join(__dirname, "../scripts/feng-ya-ji.json"), "utf8")) as unknown;
export const FENG_YA_JI_MANIFEST = importBotcScript(source, "feng_ya_ji");
