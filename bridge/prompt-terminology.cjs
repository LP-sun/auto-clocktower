'use strict';

const data = require('./prompt-terminology.json');

const ROLE_GLOSSARY = Object.freeze(data.roles);
const TERM_GLOSSARY = Object.freeze(data.terms);

const roleAliases = new Map();
for (const [id, role] of Object.entries(ROLE_GLOSSARY)) {
  roleAliases.set(id, id);
  for (const alias of role.aliases || []) roleAliases.set(alias, id);
}

function canonicalRoleId(roleId) {
  const id = roleAliases.get(roleId);
  if (!id) throw new RangeError(`Unknown Trouble Brewing character id: ${roleId}`);
  return id;
}

function roleTerm(roleId) {
  const id = canonicalRoleId(roleId);
  return Object.freeze({id, ...ROLE_GLOSSARY[id]});
}

function roleNameZh(roleId) { return roleTerm(roleId).zh; }
function roleNameEn(roleId) { return roleTerm(roleId).en; }

function renderTerminologyPrompt({language = 'zh'} = {}) {
  if (!['zh', 'en', 'bilingual'].includes(language)) throw new RangeError(`Unsupported prompt language: ${language}`);
  const role = ([id, value]) => language === 'zh' ? `${id}=${value.zh}` : language === 'en' ? `${id}=${value.en}` : `${id}=${value.en}/${value.zh}`;
  const term = ([id, value]) => language === 'zh' ? `${id}=${value.zh}` : language === 'en' ? `${id}=${value.en}` : `${id}=${value.en}/${value.zh}`;
  return [
    `Canonical terminology (${data.script.en}/${data.script.zh}). Use character IDs exactly as written.`,
    `Characters: ${Object.entries(ROLE_GLOSSARY).map(role).join('; ')}`,
    `Game terms: ${Object.entries(TERM_GLOSSARY).map(term).join('; ')}`,
    'A character claim is a player statement, not authoritative state. Registration is how a character may be treated by an ability; it does not change that character or alignment.'
  ].join('\n');
}

function validateCanonicalTerminology() {
  const errors = [];
  const expectedCategories = new Set(Object.keys(data.categories));
  const seenEn = new Set(), seenZh = new Set();
  for (const [id, role] of Object.entries(ROLE_GLOSSARY)) {
    if (!/^[a-z]+(?:_[a-z]+)*$/.test(id)) errors.push(`invalid role id: ${id}`);
    if (!expectedCategories.has(role.category)) errors.push(`invalid category for ${id}: ${role.category}`);
    if (!role.en || seenEn.has(role.en)) errors.push(`missing or duplicate English name: ${id}`); else seenEn.add(role.en);
    if (!role.zh || seenZh.has(role.zh)) errors.push(`missing or duplicate Chinese name: ${id}`); else seenZh.add(role.zh);
  }
  if (Object.keys(ROLE_GLOSSARY).length !== 22) errors.push('Trouble Brewing must contain 22 characters');
  return errors;
}

module.exports = {data, ROLE_GLOSSARY, TERM_GLOSSARY, canonicalRoleId, roleTerm, roleNameZh, roleNameEn, renderTerminologyPrompt, validateCanonicalTerminology};
