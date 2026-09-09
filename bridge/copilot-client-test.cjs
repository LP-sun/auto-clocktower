const assert = require('node:assert/strict');
const { defaultGameBudget, buildQuotaPlan } = require('./copilot-client.cjs');

assert.equal(defaultGameBudget(8), 16);
assert.equal(defaultGameBudget(12), 25);
assert.equal(defaultGameBudget(13), 32);

const safe = buildQuotaPlan({ entitlementRequests: 200, remainingPercentage: 99.4, resetDate: 'reset' }, { players: 12, plannedCredits: 25, reserveCredits: 10 });
assert.equal(safe.remainingCredits, 198.8);
assert.equal(safe.allowed, true);

const blocked = buildQuotaPlan({ entitlementRequests: 200, remainingPercentage: 15 }, { players: 12, plannedCredits: 25, reserveCredits: 10 });
assert.equal(blocked.remainingCredits, 30);
assert.equal(blocked.allowed, false);
assert.equal(buildQuotaPlan(null, { players: 8 }), null);

console.log('copilot-client tests passed');
