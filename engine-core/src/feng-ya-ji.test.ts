import assert from "node:assert/strict";
import test from "node:test";
import { FENG_YA_JI_MANIFEST, ScriptImportError, importBotcScript } from "./index";

test("imports the attached Feng Ya Ji definition without losing script metadata", () => {
  assert.equal(FENG_YA_JI_MANIFEST.name.zh, "风雅集");
  assert.equal(FENG_YA_JI_MANIFEST.meta?.author, "苏通染");
  assert.equal(FENG_YA_JI_MANIFEST.roles.length, 26);
  assert.equal(FENG_YA_JI_MANIFEST.roles.filter((r) => r.category === "Fabled").length, 1);
  assert.equal(FENG_YA_JI_MANIFEST.roleIds.includes("librarian"), true);
  assert.equal(FENG_YA_JI_MANIFEST.roleIds.includes("librarianbutton"), false);
  assert.deepEqual(FENG_YA_JI_MANIFEST.firstNightOrder.slice(0, 3), ["marionette", "witch", "cerenovus"]);
  assert.deepEqual(FENG_YA_JI_MANIFEST.otherNightOrder.slice(0, 3), ["hatter", "monk", "witch"]);
  const hundun = FENG_YA_JI_MANIFEST.roles.find((r) => r.id === "hundun")!;
  assert.match(hundun.ability.zh, /互相不认识/);
  assert.equal(hundun.setup, true);
});

test("rejects duplicate normalized ids and unknown teams", () => {
  const meta = { id: "_meta", name: "x" };
  const role = { id: "foobutton", name: "甲", team: "townsfolk", ability: "a" };
  assert.throws(() => importBotcScript([meta, role, { ...role, id: "foo" }], "x"), ScriptImportError);
  assert.throws(() => importBotcScript([meta, { ...role, team: "unknown" }], "x"), ScriptImportError);
});
