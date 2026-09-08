const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {StorytellerAgent,socialView}=require('./storyteller-agent/index.cjs');
const view={grimoire:[{seat:'P12',role:'imp',alive:true},{seat:'P03',role:'empath',alive:true},{seat:'P04',role:'chef',alive:true}],social:{claims:{P12:{role:'monk'}},suspicion:{}},balance:{goodAdvantage:.65,evilAdvantage:.35,confidence:.3}};
const cases=[{type:'registration',role:'recluse',actor:'P10',legalOptions:['good_outsider','evil_minion','evil_demon']},{type:'registration',role:'spy',actor:'P09',legalOptions:['evil_minion','good_townsfolk','good_outsider']},{type:'misinformation',actor:'P03',template:'empath_count',legalOptions:[0,1,2]},{type:'misinformation',actor:'P03',template:'fortune_result',legalOptions:[false,true]},{type:'death_redirect',actor:'P08',legalOptions:['P08','P01','P03']}];
for(const d of cases)test('legal choice and all failure fallbacks '+d.type+' '+(d.role||d.template||''),async()=>{
 for(const model of [async()=>({choice:d.legalOptions[0],reason:'valid'}),async()=>({choice:'ILLEGAL',reason:'bad'}),async()=>'{invalid',async()=>{throw Error('network');},()=>new Promise(()=>{})]){
  const a=new StorytellerAgent({model,timeoutMs:5});assert(d.legalOptions.includes(await a.decide(view,d)));
 }
});
test('poisoned Empath false zero may support public Demon Monk bluff without confirmation',()=>{
 const logs=[];const a=new StorytellerAgent({log:(type,data)=>logs.push({type,...data})});const d={...cases[2],trueResult:1};assert.equal(a.chooseSync(view,d),0);
 assert.deepEqual(logs[0].predictedEffect,{supports_demon_bluff:true,hard_confirmation:false,helps_weaker_team:true});
 fs.mkdirSync(path.join(__dirname,'validation-v2'),{recursive:true});fs.writeFileSync(path.join(__dirname,'validation-v2','storyteller-case.json'),JSON.stringify({mode:'DETERMINISTIC_TEST_NOT_LLM',view,decision:d,record:logs[0]},null,2));
});
test('SocialState does not inspect player strategic memory or reasoning',()=>{
 const {SemanticStore}=require('./semantic-memory.cjs');const store=new SemanticStore();store.register('P01');store.register('Storyteller');store.players.get('P01').plan=['PRIVATE_INNER_PLAN'];
 assert(!JSON.stringify(socialView(store)).includes('PRIVATE_INNER_PLAN'));
});
