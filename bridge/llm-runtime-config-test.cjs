const test=require('node:test');
const assert=require('node:assert/strict');
const {loadRuntimeConfig,createPlayerProfiles,validate}=require('./llm-runtime-config.cjs');

test('runtime config validates and environment overrides file-independent defaults',()=>{
 const c=loadRuntimeConfig({BOTC_PLAYER_MODEL:'test-player',BOTC_MODEL_ATTEMPTS:'4'});
 assert.equal(c.models.player,'test-player');assert.equal(c.limits.maxAttempts,4);assert.equal(c.protocolVersion,'semantic-v3');
});
test('player profiles are reproducible, isolated, and use mathematical model dimensions',()=>{
 const c=loadRuntimeConfig({});const a=createPlayerProfiles(c,['P01','P02'],42),b=createPlayerProfiles(c,['P01','P02'],42);
 assert.deepEqual(a,b);assert.notDeepEqual(a.P01,a.P02);assert.equal(Object.keys(a.P01.personality).length,10);
 assert.equal(typeof a.P01.skill.beliefAccuracy,'number');assert.equal(typeof a.P01.skill.bluffConsistency,'number');
});
test('per-seat overrides are exact and invalid configuration fails early',()=>{
 const c=loadRuntimeConfig({});c.players={P01:{skillLevel:'expert',personality:{openness:.123}}};validate(c);
 const p=createPlayerProfiles(c,['P01'],7).P01;assert.equal(p.skill.level,'expert');assert.equal(p.personality.openness,.123);
 assert.throws(()=>validate({...c,players:{seat_one:{skillLevel:'expert'}}}),/invalid player override/);
});
