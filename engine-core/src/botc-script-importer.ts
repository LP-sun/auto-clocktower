import type { RolePlugin, ScriptRoleMetadata } from "./roles";
import type { ScriptManifest } from "./script";
import type { RoleCategory, Team } from "./types";

export class ScriptImportError extends Error { override name = "ScriptImportError"; }

type JsonObject = Record<string, unknown>;
const TEAM: Record<string, { category: RoleCategory; team: Team }> = {
  townsfolk: { category: "Townsfolk", team: "good" },
  outsider: { category: "Outsider", team: "good" },
  minion: { category: "Minion", team: "evil" },
  demon: { category: "Demon", team: "evil" },
  fabled: { category: "Fabled", team: "neutral" },
  traveller: { category: "Traveller", team: "neutral" },
};

function object(value: unknown, label: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ScriptImportError(`${label} must be an object`);
  return value as JsonObject;
}
function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new ScriptImportError(`${label} must be a non-empty string`);
  return value;
}
function number(value: unknown, label: string): number {
  if (value === undefined) return 0;
  if (typeof value !== "number" || value < 0 || !Number.isInteger(value)) throw new ScriptImportError(`${label} must be a non-negative integer`);
  return value;
}
function strings(value: unknown, label: string): readonly string[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) throw new ScriptImportError(`${label} must be a string array`);
  return [...value] as string[];
}
export function normalizeBotcRoleId(sourceId: string): string {
  const id = sourceId.trim().replace(/button$/i, "");
  if (!/^[a-z0-9_]+$/i.test(id)) throw new ScriptImportError(`Invalid role id: ${sourceId}`);
  return id.toLowerCase();
}

export interface ImportedScript extends ScriptManifest {
  readonly firstNightOrder: readonly string[];
  readonly otherNightOrder: readonly string[];
}

export function importBotcScript(input: unknown, id: string): ImportedScript {
  if (!Array.isArray(input) || input.length < 2) throw new ScriptImportError("Script JSON must contain metadata and roles");
  const entries = input.map((item, index) => object(item, `entry[${index}]`));
  const meta = entries.find((entry) => entry.id === "_meta");
  if (!meta) throw new ScriptImportError("Script metadata entry is required");
  const roles: RolePlugin[] = [];
  const seen = new Set<string>();
  for (const [index, entry] of entries.entries()) {
    if (entry.id === "_meta") continue;
    const sourceId = text(entry.id, `entry[${index}].id`);
    const roleId = normalizeBotcRoleId(sourceId);
    if (seen.has(roleId)) throw new ScriptImportError(`Duplicate role id: ${roleId}`);
    seen.add(roleId);
    const mapping = TEAM[text(entry.team, `${roleId}.team`).toLowerCase()];
    if (!mapping) throw new ScriptImportError(`Unknown team for ${roleId}: ${String(entry.team)}`);
    const firstNight = number(entry.firstNight, `${roleId}.firstNight`);
    const otherNight = number(entry.otherNight, `${roleId}.otherNight`);
    const metadata: ScriptRoleMetadata = {
      edition: typeof entry.edition === "string" ? entry.edition : undefined,
      firstNight, firstNightReminder: typeof entry.firstNightReminder === "string" ? entry.firstNightReminder : undefined,
      otherNight, otherNightReminder: typeof entry.otherNightReminder === "string" ? entry.otherNightReminder : undefined,
      reminders: strings(entry.reminders, `${roleId}.reminders`),
      remindersGlobal: strings(entry.remindersGlobal, `${roleId}.remindersGlobal`),
      setup: typeof entry.setup === "boolean" || typeof entry.setup === "number" ? entry.setup : undefined,
      flavor: typeof entry.flavor === "string" ? entry.flavor : undefined,
      image: typeof entry.image === "string" ? entry.image : undefined,
      nameEng: typeof entry.name_eng === "string" ? entry.name_eng : undefined,
      raw: { ...entry },
    };
    roles.push({
      id: roleId,
      name: { en: metadata.nameEng || "", zh: text(entry.name, `${roleId}.name`) },
      category: mapping.category, team: mapping.team,
      ability: { en: "", zh: text(entry.ability, `${roleId}.ability`) },
      script: metadata, firstNight, otherNight,
      firstNightReminder: metadata.firstNightReminder, otherNightReminder: metadata.otherNightReminder,
      reminders: metadata.reminders, remindersGlobal: metadata.remindersGlobal, setup: metadata.setup,
      implemented: false,
    });
  }
  const order = (key: "firstNight" | "otherNight") => roles.filter((role) => (role[key] ?? 0) > 0)
    .sort((a, b) => (a[key] ?? 0) - (b[key] ?? 0)).map((role) => role.id);
  return {
    id, name: { en: typeof meta.name_eng === "string" ? meta.name_eng : "", zh: text(meta.name, "meta.name") },
    version: 1, roles, roleIds: roles.map((role) => role.id), implementedRoleIds: [],
    meta: { ...meta }, metadata: { ...meta }, firstNightOrder: order("firstNight"), otherNightOrder: order("otherNight"),
  };
}
