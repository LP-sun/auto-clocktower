const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const db = p => require('../discord-botc/dist/' + p);
const { getScript } = db('game/roles');
const { createGame } = db('game/state');
const { ensureRuntime } = db('game/utils');
const { runDayPhase, processEndOfDay } = db('game/dayFlow');
const { handleNominate, handleYe, closeNominationWindow, cancelNominationTimer } = db('game/nominations');
const { runNightPhase, handleNightPlayerDM } = db('game/night');
const { killPlayer } = db('game/death');
const { evaluateWinCondition } = db('game/winConditions');
const { updateGuildSettings } = db('guildSettings');
let counter = 0;
function game(roles = ['washerwoman','chef','empath','fortune_teller','undertaker','monk','soldier','drunk','saint','poisoner','scarlet_woman','imp']) {
  const id = 'test-' + ++counter;
  const players = roles.map((_, i) => ({ userId: 'P' + i, displayName: 'P' + i, username: 'P' + i, seatIndex: i }));
  const assignments = new Map(players.map((p, i) => [p.userId, getScript().roles.find(r => r.id === roles[i])]));
  const state = { gameId: id, gameNumber: counter, guildId: id, channelId: id, players, storytellerId: null, mode: 'automated', phase: 'in_progress', draft: { assignments, drunkFakeRole: getScript().roles.find(r => r.id === 'librarian'), redHerring: null, impBluffs: null }, runtime: null };
  const messages = [];
  const channel = { send: async m => messages.push({ public: true, m }) };
  const client = { channels: { fetch: async () => channel }, users: { fetch: async id => ({ send: async m => messages.push({ recipient: id, m }) }) } };
  const interaction = (id, target) => ({ user: { id }, channelId: state.channelId, guildId: id, options: { getString: () => target }, reply: async m => messages.push({ recipient: id, m }) });
  ensureRuntime(state); createGame(state); updateGuildSettings(id, { onlineMode: true });
  return { state, client, channel, interaction, messages };
}
const flush = () => new Promise(r => setImmediate(r));
async function day(g) { g.state.runtime.nightNumber = 1; runDayPhase(g.client, g.state); await flush(); }
async function nominate(g, a, b, voters) {
  await handleNominate(g.interaction(a, b), g.client); cancelNominationTimer(g.state.channelId);
  for (const voter of voters) await handleYe(g.interaction(voter), g.client);
  await closeNominationWindow(g.client, g.state.channelId);
}
async function night(g, choices) {
  g.state.runtime.nightNumber = 1; // exercise night 2
  const done = runNightPhase(g.client, g.state); await flush();
  const session = g.state.runtime.nightSession;
  for (const id of [...session.pendingPlayerIds].reverse()) {
    const content = choices[id] || 'P0';
    await handleNightPlayerDM({ author: { id }, content, reply: async () => {} }, g.client, g.state);
  }
  for (const id of [...session.deathNarrativePendingIds]) {
    await handleNightPlayerDM({ author: { id }, content: session.deathNarrativePlayers.get(id) === 'ravenkeeper' ? 'P0, dead' : 'dead', reply: async () => {} }, g.client, g.state);
  }
  await done;
}
test('12-player distribution exists and all 22 Trouble Brewing characters load', () => {
  assert.deepEqual(db('game/distribution').getDistribution(12), { townsfolk: 7, outsiders: 2, minions: 2, demon: 1 });
  assert.equal(getScript().roles.length, 22);
});
test('standard rule: five votes do not execute with twelve alive', async () => {
  const g = game(); await day(g); await nominate(g, 'P0', 'P1', ['P0','P1','P2','P3','P4']); await processEndOfDay(g.client, g.state, g.channel); assert.equal(g.state.runtime.playerStates[1].alive, true);
});
test('strict-majority rule: six votes do not execute with twelve alive; no automatic nominator vote', async () => {
  const g = game(); await day(g); await handleNominate(g.interaction('P0', 'P1'), g.client); cancelNominationTimer(g.state.channelId); assert.equal(g.state.runtime.daySession.activeNomination.votes.size, 0);
  for (let i=0;i<6;i++) await handleYe(g.interaction('P'+i),g.client);
  await closeNominationWindow(g.client,g.state.channelId); await processEndOfDay(g.client,g.state,g.channel); assert.equal(g.state.runtime.playerStates[1].alive,true);
});
test('tied highest qualifying votes mean no execution', async () => {
  const g=game(); await day(g); const voters=['P0','P1','P2','P3','P4','P5','P6']; await nominate(g,'P0','P1',voters); await nominate(g,'P2','P3',voters); await processEndOfDay(g.client,g.state,g.channel); assert.equal(g.state.runtime.playerStates.filter(p=>p.alive).length,12);
});
test('ghost vote can only be spent once', async () => {
  const g=game(); await day(g); await killPlayer(g.client,g.state,'P4',{phase:'day',byExecution:false,skipWinCheck:true}); await nominate(g,'P0','P1',['P4']); await nominate(g,'P2','P3',['P4']); assert.equal(g.state.runtime.daySession.nominations[0].votes.has('P4'),true); assert.equal(g.state.runtime.daySession.nominations[1].votes.has('P4'),false);
});
test('Virgin executes once and immediately ends the day', async () => {
  const g=game(['washerwoman','virgin','chef','saint','imp']); await day(g); await handleNominate(g.interaction('P0','P1'),g.client); assert.equal(g.state.runtime.playerStates[0].death.byExecution,true); assert.equal(g.state.runtime.daySession.status,'ended'); assert.equal(g.state.runtime.playerStates[1].tags.has('virgin_used'),true);
});
test('poisoned first nomination still consumes Virgin ability', async () => {
  const g=game(['washerwoman','virgin','chef','saint','imp']); await day(g); g.state.runtime.playerStates[1].tags.add('poisoned'); await nominate(g,'P0','P1',[]); assert.equal(g.state.runtime.playerStates[0].alive,true); assert.equal(g.state.runtime.playerStates[1].tags.has('virgin_used'),true);
});
test('Scarlet Woman takes over at exactly five alive before Demon death', async () => {
  const g=game(['washerwoman','chef','saint','scarlet_woman','imp']); await killPlayer(g.client,g.state,'P4',{phase:'day',byExecution:true,skipWinCheck:true}); assert.equal(g.state.runtime.playerStates[3].role.id,'imp');
});
test('poisoned Scarlet Woman does not take over', async () => {
  const g=game(['washerwoman','chef','saint','scarlet_woman','imp']); g.state.runtime.playerStates[3].tags.add('poisoned'); await killPlayer(g.client,g.state,'P4',{phase:'day',byExecution:true,skipWinCheck:true}); assert.equal(g.state.runtime.playerStates[3].role.id,'scarlet_woman');
});
test('poisoned Saint execution remains nonfatal after poison is later cleared', async () => {
  const g=game(); g.state.runtime.playerStates[8].tags.add('poisoned'); await killPlayer(g.client,g.state,'P8',{phase:'day',byExecution:true,skipWinCheck:true}); g.state.runtime.playerStates[8].tags.clear(); assert.equal(evaluateWinCondition(g.state,{trigger:'death'}),null);
});
test('poisoned Mayor cannot win with three alive', () => {
  const g=game(['mayor','chef','imp']); g.state.runtime.playerStates[0].tags.add('poisoned'); assert.equal(evaluateWinCondition(g.state,{trigger:'day_end_no_execution'}),null);
});
test('Poisoner suppresses Imp regardless of reply arrival order', async () => {
  const g=game(['washerwoman','chef','soldier','poisoner','imp']); await night(g,{P3:'P4',P4:'P0'}); assert.equal(g.state.runtime.playerStates[0].alive,true);
});
test('poisoned Soldier can die to Imp', async () => {
  const g=game(['washerwoman','chef','soldier','poisoner','imp']); await night(g,{P3:'P2',P4:'P2'}); assert.equal(g.state.runtime.playerStates[2].alive,false);
});
test('poisoned Monk does not protect the target', async () => {
  const g=game(['washerwoman','chef','monk','poisoner','imp']); await night(g,{P2:'P0',P3:'P2',P4:'P0'}); assert.equal(g.state.runtime.playerStates[0].alive,false);
});
test('sober Monk protects the target', async () => {
  const g=game(['washerwoman','chef','monk','poisoner','imp']); await night(g,{P2:'P0',P3:'P1',P4:'P0'}); assert.equal(g.state.runtime.playerStates[0].alive,true);
});
test('Imp self-kill transfers to a living Minion', async () => {
  const g=game(['washerwoman','chef','soldier','baron','imp']); await night(g,{P4:'P4'}); assert.equal(g.state.runtime.playerStates[4].alive,false); assert.equal(g.state.runtime.playerStates[3].role.id,'imp');
});
test('Storyteller review modifies permitted poisoned info before private delivery', async () => {
  const api=db('game/night'); const g=game(['fortune_teller','chef','soldier','poisoner','imp']); let reviewed=false;
  api.setAutomatedInfoReview(async state=>{
    const draft=state.runtime.nightSession.infoOutcomeDrafts.get('P0');
    assert.equal(draft.allowArbitraryOverride,true);
    assert.equal(api.applyInfoDraftFieldForUI(state,'P0','yes',true).error,undefined); reviewed=true;
  });
  try {
    await night(g,{P0:'P1, P2',P3:'P0',P4:'P1'});
    assert.equal(reviewed,true);
    assert.match(g.state.runtime.nightSession.infoMessages.get('P0'),/yes/i);
    assert.equal(g.messages.some(m=>m.recipient==='P0' && /yes/i.test(m.m)),true);
  } finally { api.setAutomatedInfoReview(async()=>{}); }
});
test('OpenAI-compatible HTTP transport preserves isolated history and rejects bad actions', async () => {
  const requests=[];
  const server=http.createServer((req,res)=>{ let raw=''; req.on('data',c=>raw+=c); req.on('end',()=>{requests.push(JSON.parse(raw));res.setHeader('Content-Type','application/json');res.end(JSON.stringify({choices:[{message:{content:JSON.stringify({action:'idle',reasoning:'Contract fixture.'})}}]}));}); });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const previous={...process.env};
  try {
    process.env.OPENAI_BASE_URL=`http://127.0.0.1:${server.address().port}/v1`; process.env.OPENAI_MODEL='local-contract-fixture'; process.env.BOTC_PROVIDER='openai';
    const {makeProvider}=require('./provider.cjs'); const provider=makeProvider({log:()=>{},fixture:false});
    await provider.generate('PLAYER_A', [{role:'user',parts:[{text:'A_SECRET'}]}], 'act', ['idle']);
    await provider.generate('PLAYER_B', [], 'act', ['idle']);
    assert.equal(JSON.stringify(requests[1]).includes('A_SECRET'),false); assert.equal(requests[0].messages[1].content,'A_SECRET');
    const {setResponseProvider,generateResponse}=require('../clocktower-ai/dist/services/vertex-ai'); setResponseProvider(async()=>({action:'illegal',reasoning:'fixture'})); await assert.rejects(generateResponse('system',[],'act',['idle']));
  } finally { process.env=previous; await new Promise(r=>server.close(r)); }
});

test('execution thresholds use strict majority',()=>{
 const threshold=db('game/voteThreshold').executionThreshold;
 for(const [n,expected] of [[12,7],[10,6],[8,5],[11,6],[9,5]]) assert.equal(threshold(n),expected);
});
test('registration legal domains, poisoned suppression and invalid policy fallback',()=>{
 const {legalRegistrations,registersAs,setRegistrationPolicy}=db('utils/roleDetection');
 const g=game(['recluse','spy','chef','saint','imp']);const [recluse,spy]=g.state.runtime.playerStates;
 assert.deepEqual(legalRegistrations(recluse.role),['good_outsider','evil_minion','evil_demon']);
 assert(!legalRegistrations(spy.role).includes('evil_demon'));
 setRegistrationPolicy(()=> 'evil_demon');assert.equal(registersAs(recluse.role,'Demon',recluse),true);
 recluse.tags.add('poisoned');assert.equal(registersAs(recluse.role,'Demon',recluse),false);
 setRegistrationPolicy(()=> 'good_townsfolk');spy.tags.add('poisoned');assert.equal(registersAs(spy.role,'Townsfolk',spy),false);
 setRegistrationPolicy(()=> 'INVALID');assert.equal(registersAs(recluse.role,'Outsider',recluse),true);setRegistrationPolicy();
});
test('Slayer kills Demon or registering Recluse without public role confirmation',async()=>{
 const {setRegistrationPolicy}=db('utils/roleDetection');setRegistrationPolicy(()=> 'evil_demon');
 try{for(const targetRole of ['imp','recluse']){
  const g=game(['slayer',targetRole,'chef','saint','scarlet_woman', 'imp']);await day(g);
  await db('game/roleCommands').handleRoleCommand({...g.interaction('P0','P1'),commandName:'slay'},g.client);
  assert.equal(g.state.runtime.playerStates[1].alive,false);
  const publicText=g.messages.filter(x=>x.public).map(x=>typeof x.m==='string'?x.m:x.m.content).join(' ');
  assert(!/is.*Demon|是.*恶魔|Recluse|陌客/.test(publicText));
 }}finally{setRegistrationPolicy();}
});
test('poisoned Slayer consumes shot and poisoned Recluse cannot be shot as Demon',async()=>{
 for(const poisonTarget of [0,1]){
  const g=game(['slayer','recluse','chef','saint','imp']);await day(g);g.state.runtime.playerStates[poisonTarget].tags.add('poisoned');
  await db('game/roleCommands').handleRoleCommand({...g.interaction('P0','P1'),commandName:'slay'},g.client);
  assert(g.state.runtime.playerStates[0].tags.has('slayer_used'));assert(g.state.runtime.playerStates[1].alive);
 }
});
test('poison immediately ends when its source dies',async()=>{
 const g=game(['washerwoman','chef','soldier','poisoner','imp']);await night(g,{P3:'P2',P4:'P0'});
 assert(g.state.runtime.playerStates[2].tags.has('poisoned'));await killPlayer(g.client,g.state,'P3',{phase:'day',byExecution:true,skipWinCheck:true});assert(!g.state.runtime.playerStates[2].tags.has('poisoned'));
});
test('day discussion templates render count and player names',async()=>{
 const g=game();updateGuildSettings(g.state.guildId,{onlineMode:true,defaultLang:'zh'});await day(g);
 const text=g.messages.filter(x=>x.public).map(x=>x.m).join(' ');assert(!/\{count\}|\{players\}/.test(text));assert(text.includes('12'));
});
test('evil startup DMs expose teammate seats but not their specific roles',async()=>{
 const g=game(['washerwoman','chef','soldier','saint','monk','butler','baron','scarlet_woman','imp']);
 await db('handlers/roleSender').distributeRoles(g.client,g.state);
 for(const id of ['P6','P7','P8']){
  const roleDM=g.messages.find(x=>x.recipient===id)?.m;assert(roleDM);
  if(id==='P8')assert(!/Baron|Scarlet Woman|男爵|红唇女郎/.test(roleDM));
  if(id==='P6')assert(!/Scarlet Woman|红唇女郎/.test(roleDM));
  if(id==='P7')assert(!/Baron|男爵/.test(roleDM));
 }
});
test('engine misinformation domains never expose truthful fixed information for override',()=>{
 const {informationDecisions}=db('game/discretion');const g=game(['empath','chef','soldier','poisoner','imp']);const draft={templateId:'empath_count',fields:{count:1},fieldTypes:{count:'number'},allowArbitraryOverride:true};
 assert.deepEqual(informationDecisions(g.state,'P0',draft),[]);g.state.runtime.playerStates[0].tags.add('poisoned');assert.deepEqual(informationDecisions(g.state,'P0',draft)[0].legalOptions,[0,1,2]);
 assert.deepEqual(informationDecisions(g.state,'P0',{...draft,allowArbitraryOverride:false}),[]);
});
test('Mayor redirect uses legal domain, retains protection and invalid output falls back',async()=>{
 const {setDiscretionPolicy,decideLegal}=db('game/discretion');const g=game(['mayor','soldier','monk','baron','imp']);
 setDiscretionPolicy(async()=> 'P1');try{await night(g,{P2:'P3',P4:'P0'});assert(g.state.runtime.playerStates[0].alive);assert(g.state.runtime.playerStates[1].alive);}finally{setDiscretionPolicy();}
 setDiscretionPolicy(async()=> 'NOT_A_PLAYER');try{assert.equal(await decideLegal(g.state,{type:'death_redirect',actor:'P0',legalOptions:['P0','P1']}),'P0');}finally{setDiscretionPolicy();}
});
test('Slayer may choose a dead player: nothing happens but the shot is consumed',async()=>{
 const g=game(['slayer','chef','soldier','baron','imp']);await day(g);await killPlayer(g.client,g.state,'P1',{phase:'day',byExecution:false,skipWinCheck:true});
 await db('game/roleCommands').handleRoleCommand({...g.interaction('P0','P1'),commandName:'slay'},g.client);assert(g.state.runtime.playerStates[0].tags.has('slayer_used'));
});
