'use strict';

const data = require('./prompt-terminology.json');

const ROLE_GLOSSARY = Object.freeze(data.roles);
const TERM_GLOSSARY = Object.freeze(data.terms);

const BASE_PLAYER_SYSTEM_EN = `You are one player in Blood on the Clocktower: Trouble Brewing. Make your own deductions, bluffs, and strategic choices from the information visible to you. The authoritative structured state controls characters, alignment, alive/dead status, legal actions, votes, executions, deaths, and victory. Chat and character claims are statements by players, not mechanical facts. Private information can be wrong because of drunkenness, poisoning, or registration. Do not invent hidden information or treat a character on the script as necessarily in play. Dead players may talk and have one dead vote token for the rest of the game. A nomination and a vote are different actions; the execution threshold and current player on the block come from state. If game_over is false, do not announce a completed victory. Use only an allowed action and exact seat IDs.`;

const BASE_PLAYER_SYSTEM_ZH = `你只扮演一名《染·钟楼谜团：暗流涌动》玩家。根据你能看到的信息自行推理、伪装并作出策略选择。结构化权威状态决定角色、阵营、生死、合法动作、票数、处决、死亡和胜负。聊天与角色自称只是玩家陈述，不是机械事实。私人信息也可能因酒醉、中毒或登记规则而错误。不得虚构未收到的隐藏信息，也不得因角色出现在剧本上就推断其在场。死者仍可发言，并在余下游戏中共有一张亡灵票。提名与投票是不同动作；处决门槛和当前最高票玩家以状态为准。game_over 为 false 时不得宣告已经获胜。只选择允许的动作，并使用准确座位号。角色和规则术语采用集石《钟楼百科》译名。`;

const OUTPUT_PROTOCOL = Object.freeze({
  instruction: 'Return one JSON object only. Give a brief decision summary, not hidden chain-of-thought.',
  fields: Object.freeze({reasoning: 'brief decision summary', action: 'one allowed action', message: 'message content or empty string', players: 'array of exact seat IDs'})
});

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

module.exports = {data, ROLE_GLOSSARY, TERM_GLOSSARY, BASE_PLAYER_SYSTEM_EN, BASE_PLAYER_SYSTEM_ZH, OUTPUT_PROTOCOL, canonicalRoleId, roleTerm, roleNameZh, roleNameEn, renderTerminologyPrompt, validateCanonicalTerminology};
