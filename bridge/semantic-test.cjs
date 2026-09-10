const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
test('ephemeral control and reasoning never append to persistent chatHistory',async()=>{
 const dir=path.join(__dirname,'runs','semantic-unit');fs.mkdirSync(path.join(dir,'data/generated'),{recursive:true});const cwd=process.cwd();process.chdir(dir);
 try{
 const {setResponseProvider}=require('../clocktower-ai/dist/services/vertex-ai');const {sendMessageToPlayer}=require('../clocktower-ai/dist/clocktower/players');
 setResponseProvider(async()=>({reasoning:'AUDIT_ONLY_CANARY',action:'idle',message:'',players:[]}));
 const p={name:'P01',actualRole:'',chatHistory:[{role:'user',parts:[{text:'N1 private information'}]}],actionHistory:[],status:'alive',ephemeralControl:true};
 for(let i=0;i<30;i++)await sendMessageToPlayer('rules',p,JSON.stringify({kind:i%2?'vote':'nomination',publicStatus:['CONTROL_CANARY']}),['idle']);
 assert.equal(p.chatHistory.length,1);assert(!JSON.stringify(p.chatHistory).includes('CANARY'));
 }finally{process.chdir(cwd);}
});
const {SemanticStore}=require('./semantic-memory.cjs');const {ViewProjector}=require('./player-view.cjs');const {buildContext}=require('./context-builder.cjs');
function sampleState(){const roles=require('../discord-botc/dist/game/roles').getScript().roles;const role=id=>roles.find(r=>r.id===id);return {phase:'in_progress',runtime:{nightNumber:1,daySession:{status:'open',dayNumber:1,nominations:[],nominatorIds:new Set(),nomineeIds:new Set()},playerStates:Array.from({length:12},(_,i)=>({player:{userId:'P'+String(i+1).padStart(2,'0')},role:role(i===0?'drunk':i===11?'imp':'chef'),effectiveRole:role(i===0?'librarian':i===11?'imp':'chef'),alive:true,death:null,tags:new Set()}))}};}
function memoryStore(){const s=new SemanticStore();for(let i=1;i<=12;i++)s.register('P'+String(i).padStart(2,'0'));s.register('Storyteller');return s;}
test('private facts and whispers isolate recipients, including retrieval and restored snapshots',()=>{
 const s=memoryStore();s.observe({visibility:'private',audience:['P01'],type:'private_info',text:'N1 PRIVATE_A'});s.observe({visibility:'private',audience:['P02','P03'],type:'whisper',text:'PRIVATE_B'});
 assert(!JSON.stringify(s.players.get('P02')).includes('PRIVATE_A'));assert(!JSON.stringify(s.lookup('P04')).includes('PRIVATE_B'));
 const restored=new SemanticStore();restored.restore(s.snapshot());assert.deepEqual(restored.lookup('P01'),s.lookup('P01'));assert(!JSON.stringify(restored.lookup('Storyteller')).includes('PRIVATE_A'));
});
test('claims stay claims; belief updates never import reasoning or another actor memory',()=>{
 const s=memoryStore();s.observe({visibility:'public',actor:'P01',type:'chat',day:1,text:'我是图书管理员。'});
 assert.equal(s.players.get('P02').publicClaims.P01.confirmed,false);
 s.recordChoice('P02',{kind:'vote'},{action:'vote_no',reasoning:'SECRET_COT',memoryUpdate:{beliefs:[{player:'P01',summary:'Possible Drunk'}],plan:['recheck'],worlds:[]}});
 assert.equal(s.players.get('P02').beliefs.P01.kind,'belief');assert(!JSON.stringify(s.snapshot()).includes('SECRET_COT'));assert(!s.players.get('Storyteller').beliefs.P01);
});
test('structured state masks drunk, poison, other roles and unannounced night deaths',()=>{
 const state=sampleState(),v=new ViewProjector(),s=memoryStore();state.runtime.playerStates[0].tags.add('poisoned');
 let p=v.player(state,'P01',s.players.get('P01'));assert.equal(p.self.role,'librarian');assert.equal(p.self.poisoned,undefined);assert.equal(p.grimoire,undefined);assert.equal(p.game_over,false);
 state.runtime.daySession.status='ended';state.runtime.playerStates[5].alive=false;state.runtime.playerStates[5].death={phase:'night',nightNumber:2,ghostVoteUsed:false};
 p=v.player(state,'P01',s.players.get('P01'));assert(p.alive.includes('P06'));
 state.runtime.daySession.status='open';p=v.player(state,'P01',s.players.get('P01'));assert(!p.alive.includes('P06'));assert.equal(p.executionThreshold,6);
 state.phase='ended';assert.equal(v.player(state,'P01',s.players.get('P01')).game_over,true);
});
test('six days of compaction retain private information, current claims, bluff commitments and retrieval',()=>{
 const s=memoryStore();s.observe({visibility:'private',audience:['P01'],type:'private_info',night:1,text:'N1 number=2'});
 for(let day=1;day<=6;day++){for(let i=0;i<40;i++)s.observe({visibility:'public',actor:'P01',type:'chat',day,text:i===0?'我是图书管理员。':`D${day} claim item ${i}`});s.compact(day);}
 const m=s.players.get('P01');assert.equal(m.privateFacts[0].text,'N1 number=2');assert.equal(m.publicClaims.P01.role,'librarian');assert(m.recent.length<=15);assert(m.bluff.public_commitments.length<=8);assert(s.lookup('P01',{day:1}).length>=40);
});
test('vote/nomination contexts bounded independently of full transcript; critical data survives',()=>{
 const s=memoryStore(),state=sampleState(),v=new ViewProjector();s.observe({visibility:'private',audience:['P01'],type:'private_info',text:'UNIQUE_NIGHT_FACT'});
 for(let i=0;i<500;i++)s.observe({visibility:'public',type:'chat',actor:'P02',day:1,text:'old transcript '+i});
 const m=s.players.get('P01'),view=v.player(state,'P01',m);
 for(const kind of ['vote','nomination']){const c=buildContext({actor:'P01',task:{kind,day:1,publicStatus:['REDUNDANT_CONTROL']},actions:['idle'],view,memory:m,store:s});assert(c.metrics.estimatedInputTokens<4000);assert(c.input.includes('UNIQUE_NIGHT_FACT'));assert(!c.input.includes('old transcript 0'));assert(!c.input.includes('REDUNDANT_CONTROL'));}
});
test('over-budget protected private memory fails rather than silently truncating',()=>{
 const s=memoryStore(),state=sampleState(),v=new ViewProjector();s.observe({visibility:'private',audience:['P01'],type:'private_info',text:'秘'.repeat(10000)});
 assert.throws(()=>buildContext({actor:'P01',task:{kind:'vote'},actions:['vote_no'],view:v.player(state,'P01',s.players.get('P01')),memory:s.players.get('P01'),store:s}),/Protected memory/);
});
test('single-turn native sessions never reuse previous control or private response',async()=>{
 const s=memoryStore(),state=sampleState(),v=new ViewProjector(),inputs=[],starts=[];
 const fake={async initialize(){},async rpc(method){return method==='account/read'?{account:{type:'chatgpt'}}:{data:[{model:'gpt-5.6-luna'},{model:'gpt-6-astra'}]};},async start(model,cwd,system){const id='fresh'+starts.length;starts.push(id);return {thread:{id},instructionSources:[]};},async run(id,input){inputs.push(input);return {text:JSON.stringify({action:'idle',reasoning:'RESPONSE_CANARY',players:[],message:''})};},close(){}};
 const dir=path.join(__dirname,'runs','semantic-provider-unit');fs.mkdirSync(dir,{recursive:true});
 // Provider register owns memory creation.
 const store=new SemanticStore();const p=require('./semantic-provider.cjs').makeSemanticProvider({store,projector:v,getState:()=>state,log(){},runDir:dir,clientFactory:()=>fake});const a=[],b=[];p.register(a,'P01');p.register(b,'P02');
 store.observe({visibility:'private',audience:['P01'],type:'private_info',text:'A_ONLY'});
 await p.generate('ignored',a,JSON.stringify({kind:'vote',day:1}),['idle']);await p.generate('ignored',a,JSON.stringify({kind:'nomination',day:1}),['idle']);await p.generate('ignored',b,JSON.stringify({kind:'vote',day:1}),['idle']);
 assert.equal(new Set(starts).size,3);assert(!inputs[1].includes('RESPONSE_CANARY'));assert(!inputs[2].includes('A_ONLY'));p.close();
});
test('Butler receives explicit current master vote even when master used a ghost vote',()=>{
 const s=memoryStore(),state=sampleState(),v=new ViewProjector();const roles=require('../discord-botc/dist/game/roles').getScript().roles;state.runtime.playerStates[0].effectiveRole=roles.find(r=>r.id==='butler');s.players.get('P01').ability.lastNightChoice={night:2,targets:['P04']};state.runtime.daySession.activeNomination={nominatorId:'P02',nomineeId:'P03',votes:new Set(['P04'])};state.runtime.playerStates[3].alive=false;state.runtime.playerStates[3].death={phase:'night',nightNumber:2,ghostVoteUsed:true};
 const p=v.player(state,'P01',s.players.get('P01'));assert.equal(p.self.ability.master_has_voted,true);assert.equal(p.self.ability.master,'P04');
});
test('bridge rejects premature victory without treating conditional rules as victory',()=>{
 const {prematureVictory}=require('./action-validation.cjs');assert(prematureVictory('善良阵营获胜！',false));assert(!prematureVictory('如果恶魔死亡则善良获胜。',false));assert(!prematureVictory('善良阵营获胜！',true));
});
test('internal retrieval can fetch older visible whispers without another pair private contents',async()=>{
 const state=sampleState(),store=new SemanticStore(),projector=new ViewProjector(),inputs=[];let turn=0;
 const fake={async initialize(){},async rpc(m){return m==='account/read'?{account:{type:'chatgpt'}}:{data:[{model:'gpt-5.6-luna'},{model:'gpt-6-astra'}]};},async start(){return {thread:{id:'retrieve-'+turn},instructionSources:[]};},async run(id,input){inputs.push(input);return {text:JSON.stringify(turn++===0?{reasoning:'lookup needed',action:'lookup',message:'lookup_private_chat',players:['P02']}:{reasoning:'enough',action:'idle',message:'',players:[]})};},close(){}};
 const dir=path.join(__dirname,'runs','retrieval-unit');fs.mkdirSync(dir,{recursive:true});const provider=require('./semantic-provider.cjs').makeSemanticProvider({store,projector,getState:()=>state,log(){},runDir:dir,clientFactory:()=>fake});const history=[];provider.register(history,'P01');store.register('P02');store.register('P03');
 store.observe({visibility:'private',audience:['P01','P02'],type:'whisper',actor:'P02',text:'OLD_VISIBLE_SECRET'});store.observe({visibility:'private',audience:['P02','P03'],type:'whisper',actor:'P02',text:'FORBIDDEN_SECRET'});
 for(let i=0;i<50;i++)store.observe({visibility:'private',audience:['P01','P03'],type:'whisper',actor:'P03',text:'recent '+i});store.compact(1);
 const r=await provider.generate('',history,JSON.stringify({kind:'vote',day:1}),['idle']);assert.equal(r.action,'idle');assert(inputs[1].includes('OLD_VISIBLE_SECRET'));assert(!inputs[1].includes('FORBIDDEN_SECRET'));provider.close();
});
test('new evidence updates belief and preserves a changed claim as contradiction, never proof',()=>{
 const s=memoryStore();s.observe({visibility:'public',type:'chat',actor:'P02',day:1,text:'我是厨师'});s.observe({visibility:'public',type:'chat',actor:'P02',day:2,text:'我是镇长'});
 assert.equal(s.players.get('P01').contradictions[0].kind,'claim_change_not_proof');
 for(const summary of ['trusted','now suspicious'])s.recordChoice('P01',{kind:'discussion'},{action:'idle',memoryUpdate:{beliefs:[{player:'P02',summary}],plan:[],worlds:[]}});
 assert.equal(s.players.get('P01').beliefs.P02.summary,'now suspicious');assert(!s.players.get('P03').beliefs.P02);
});
test('run directories are atomic and unique even for identical timestamps',()=>{
 const {createRunDirectory}=require('./run-directory.cjs');const base=path.join(__dirname,'runs','directory-unit');const paths=Array.from({length:10},()=>createRunDirectory(base,'fixture','same-instant'));assert.equal(new Set(paths).size,10);
});
test('structured communication records public claims and rejects hidden evidence references',()=>{
 const s=new SemanticStore();for(const seat of ['P01','P02','P03'])s.register(seat);
 const secret=s.observe({visibility:'private',audience:['P01'],type:'private_info',actor:'Storyteller',day:1,text:'secret'});
 s.recordChoice('P01',{kind:'discussion',day:1},{action:'announcement',message:'我是厨师',players:[],communication:{intent:'role_claim',identityClaims:[{subject:'P01',claimedRole:'chef'}],evidenceRefs:[secret.id]}});
 assert.equal(s.players.get('P03').publicClaims.P01.role,'chef');assert.equal(s.players.get('P03').publicClaims.P01.structured,true);
 assert.throws(()=>s.recordChoice('P02',{kind:'discussion',day:1},{action:'announcement',message:'引用秘密',players:[],communication:{intent:'claim',identityClaims:[],evidenceRefs:[secret.id]}}),/non-visible evidence/);
});
