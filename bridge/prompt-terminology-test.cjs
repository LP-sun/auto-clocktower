const {test} = require('node:test');
const assert = require('node:assert/strict');
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
