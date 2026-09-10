const test=require('node:test'),assert=require('node:assert/strict');
const {DEFAULT_STORYTELLER_PARAMETERS,StorytellerAgent,socialView,storytellerParameters}=require('./storyteller-agent/index.cjs');
const view={grimoire:[{seat:'P12',role:'imp',alive:true},{seat:'P03',role:'empath',alive:true},{seat:'P04',role:'chef',alive:true}],social:{claims:{P12:{role:'monk'}},suspicion:{}},balance:{goodAdvantage:.65,evilAdvantage:.35,confidence:.3}};
const cases=[{type:'registration',role:'recluse',actor:'P10',legalOptions:['good_outsider','evil_minion','evil_demon']},{type:'misinformation',actor:'P03',template:'empath_count',legalOptions:[0,1,2]},{type:'death_redirect',actor:'P08',legalOptions:['P08','P01','P03']}];

test('defaults transparently mirror mathematical storyteller settings',()=>{
 assert.deepEqual(DEFAULT_STORYTELLER_PARAMETERS.objectives,{fairness:.25,tension:.25,solvability:.25,drama:.25});
 assert.equal(DEFAULT_STORYTELLER_PARAMETERS.temperature,.5);
});

test('relative objective weights normalize and invalid parameters fail early',()=>{
 assert.deepEqual(storytellerParameters({objectives:{fairness:2,tension:1,solvability:1,drama:0}}).objectives,{fairness:.5,tension:.25,solvability:.25,drama:0});
 assert.throws(()=>storytellerParameters({temperature:3}),/temperature/);
 assert.throws(()=>storytellerParameters({objectives:{mystery:1}}),/unknown storyteller objective/);
 assert.throws(()=>storytellerParameters({objectives:{fairness:0,tension:0,solvability:0,drama:0}}),/positive weight/);
});

for(const d of cases)test('model receives a structured, parameterized legal decision: '+d.type,async()=>{
 let request;const logs=[];
 const agent=new StorytellerAgent({parameters:{temperature:.7},log:(type,data)=>logs.push({type,...data}),model:async value=>{request=value;return {choiceId:'1',reasoning:'LLM evaluated the supplied objectives',reasonCodes:['PRESERVE_SOLVABILITY']};}});
 assert.equal(await agent.decide(view,d),d.legalOptions[1]);
 assert.equal(request.kind,'storyteller_decision');assert.equal(request.schemaVersion,1);assert.equal(request.parameters.temperature,.7);
 assert.deepEqual(request.decision.choices,d.legalOptions.map((value,index)=>({id:String(index),value})));
 assert(!Object.hasOwn(request.decision,'legalOptions'));assert.deepEqual(request.constraints.legalChoiceIds,request.decision.choices.map(x=>x.id));
 assert.equal(logs[0].modelDriven,true);assert.deepEqual(logs[0].reasonCodes,['PRESERVE_SOLVABILITY']);
});

test('live model failures fail closed by default',async()=>{
 for(const model of [async()=>({choiceId:'99',reasoning:'bad'}),async()=>'{invalid',async()=>{throw Error('network');},()=>new Promise(()=>{})]){
  const logs=[];const agent=new StorytellerAgent({model,timeoutMs:5,log:(type,data)=>logs.push({type,...data})});
  await assert.rejects(()=>agent.decide(view,cases[1]));assert.equal(logs[0].type,'storyteller_model_failure');assert.equal(logs[0].failureMode,'throw');
 }
});

test('an explicitly configured offline fallback is labelled and historyWindow zero stays empty',async()=>{
 const logs=[];const agent=new StorytellerAgent({model:async()=>{throw Error('offline')},failureMode:'first_legal',parameters:{historyWindow:0},log:(type,data)=>logs.push({type,...data})});
 assert.equal(await agent.decide(view,cases[1]),0);assert.deepEqual(agent.recent,[]);assert.equal(logs.at(-1).modelDriven,false);
});

test('SocialState does not inspect player strategic memory or reasoning',()=>{
 const {SemanticStore}=require('./semantic-memory.cjs');const store=new SemanticStore();store.register('P01');store.register('Storyteller');store.players.get('P01').plan=['PRIVATE_INNER_PLAN'];
 assert(!JSON.stringify(socialView(store)).includes('PRIVATE_INNER_PLAN'));
});
