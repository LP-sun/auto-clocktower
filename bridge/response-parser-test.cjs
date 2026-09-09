const assert = require('node:assert/strict');
const { parseModelJson, normalizeModelResponse } = require('./semantic-provider.cjs');

assert.deepEqual(parseModelJson('{"action":"idle"}'), { action: 'idle' });
assert.deepEqual(parseModelJson('```json\n{"action":"choose","players":["P03"]}\n```'), { action: 'choose', players: ['P03'] });
assert.throws(() => parseModelJson('I choose P03'), /Unexpected token/);
assert.throws(() => parseModelJson('prefix {"action":"idle"} suffix'));
assert.deepEqual(normalizeModelResponse({ action: 'choose', players: ['P02'], message: '' }), {
  action: 'choose', players: ['P02'], message: '', reasoning: '模型返回了行动，但未提供简短决策摘要。'
});
assert.deepEqual(normalizeModelResponse({ action: 'idle', reasoning: '等待更多信息。' }), {
  action: 'idle', reasoning: '等待更多信息。', message: '', players: []
});
assert.deepEqual(normalizeModelResponse({ action: 'choose', target: 'P03', reason: '选择合法目标。' }, { candidates: ['P02', 'P03'] }), {
  action: 'choose', players: ['P03'], message: '', reasoning: '选择合法目标。'
});
assert.throws(() => normalizeModelResponse({ action: 'choose', target: 'P09' }, { candidates: ['P02', 'P03'] }), /legal candidate/);
assert.throws(() => normalizeModelResponse([]), /JSON object/);
console.log('response-parser tests passed');
