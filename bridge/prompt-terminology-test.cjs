const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const names = require('./role-names.zh.json');
const terminology = require('./prompt-terminology.cjs');

test('canonical Trouble Brewing glossary is complete and internally valid', () => {
  assert.deepEqual(terminology.validateCanonicalTerminology(), []);
  assert.equal(Object.keys(terminology.ROLE_GLOSSARY).length, 22);
});

test('legacy Chinese role-name lookup agrees with canonical glossary', () => {
  assert.deepEqual(names, Object.fromEntries(Object.entries(terminology.ROLE_GLOSSARY).map(([id, role]) => [id, role.zh])));
});

test('hyphenated upstream ids normalize without changing prompt ids', () => {
  assert.equal(terminology.canonicalRoleId('fortune-teller'), 'fortune_teller');
  assert.equal(terminology.roleNameZh('scarlet-woman'), '红唇女郎');
  assert.throws(() => terminology.roleTerm('clockmaker'), /Unknown Trouble Brewing/);
});

test('rendered prompt distinguishes claims, registration, and character identity', () => {
  const prompt = terminology.renderTerminologyPrompt({language: 'bilingual'});
  assert.match(prompt, /washerwoman=Washerwoman\/洗衣妇/);
  assert.match(prompt, /character=character\/角色/);
  assert.match(prompt, /claim is a player statement/);
  assert.match(prompt, /Registration/);
});

test('shared player clauses preserve reasoning while requesting only a short summary', () => {
  assert.match(terminology.BASE_PLAYER_SYSTEM_EN, /Make your own deductions, bluffs, and strategic choices/);
  assert.match(terminology.BASE_PLAYER_SYSTEM_ZH, /自行推理、伪装并作出策略选择/);
  assert.match(terminology.OUTPUT_PROTOCOL.instruction, /brief decision summary/);
  assert.doesNotMatch(terminology.OUTPUT_PROTOCOL.instruction, /internal train of thought/i);
});

test('base prompt does not retain the former rule contradictions', () => {
  const promptRoot = path.join(__dirname, '..', 'clocktower-ai', 'data', 'prompts');
  const introduction = fs.readFileSync(path.join(promptRoot, 'introduction.txt'), 'utf8');
  const conclusion = fs.readFileSync(path.join(promptRoot, 'conclusion.txt'), 'utf8');
  assert.match(introduction, /nomination opens a vote; it is not itself a vote/i);
  assert.match(introduction, /five- or six-player games/);
  assert.doesNotMatch(introduction, /8 player game.*2 Minions/i);
  assert.doesNotMatch(introduction, /cannot use their special abilities during the nomination phase/i);
  assert.match(conclusion, /Duplicate claims can occur/);
  assert.doesNotMatch(conclusion, /internal train of thought/i);
});
