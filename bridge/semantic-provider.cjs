const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {buildContext}=require('./context-builder.cjs');const {Telemetry}=require('./telemetry.cjs');
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
function makeSemanticProvider({store,projector,getState,log,runDir,fixtureProvider,clientFactory}){
 const ids=new WeakMap(),sessions=[],replay=[];let client,ready,calls=0,liveCalls=0;
 const model=process.env.BOTC_PLAYER_MODEL||'gpt-5.6-luna',storytellerModel=process.env.BOTC_ST_MODEL||'gpt-6-astra';
 const telemetry=new Telemetry(log);
 const lookupTypes={lookup_claim_history:'chat',lookup_vote_history:'vote',lookup_public_chat:'chat',lookup_private_chat:'whisper',lookup_ability_history:'choice'};
 function normalizeLookupMessage(value){
  if(lookupTypes[value])return {value,method:'exact'};
  const s=String(value||'').toLowerCase();
  if(/公开|public/.test(s)&&/聊天|chat/.test(s))return {value:'lookup_public_chat',method:'safe-normalization'};
  if(/私聊|private|whisper/.test(s))return {value:'lookup_private_chat',method:'safe-normalization'};
  if(/投票|vote/.test(s))return {value:'lookup_vote_history',method:'safe-normalization'};
  if(/能力|ability|行动|choice/.test(s))return {value:'lookup_ability_history',method:'safe-normalization'};
  if(/自称|claim/.test(s))return {value:'lookup_claim_history',method:'safe-normalization'};
  return null;
 }
 if(process.env.BOTC_REPLAY_FROM){
  const source=path.resolve(process.env.BOTC_REPLAY_FROM),ev=fs.readFileSync(path.join(source,'events.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
  if(!ev.some(e=>e.type==='run_config'&&e.protocol==='semantic-v2'))throw Error('Legacy transcript replay requires archived v1 adapter; semantic-v2 refuses silent migration');
  const requests=new Map(ev.filter(e=>e.type==='model_request'&&e.protocol==='semantic-v2').map(e=>[e.requestId,e]));
  for(const e of ev.filter(e=>e.type==='model_response'&&e.actor))replay.push({request:requests.get(e.requestId),response:e.response});
  log('replay_source',{source,decisions:replay.length,protocol:'semantic-v2'});
 }
 async function initialize(){
  client=clientFactory?clientFactory():new (require('./codex-client.cjs').CodexClient)(log);await client.initialize();
  const account=await client.rpc('account/read',{refreshToken:false});assert.equal(account.account?.type,'chatgpt');
  const catalog=await client.rpc('model/list',{limit:100});for(const selected of [model,storytellerModel])assert(catalog.data.some(m=>m.model===selected),'Configured model unavailable');
  log('codex_auth',{type:'chatgpt',players:model,storyteller:storytellerModel});
 }
 function register(history,actor){assert(!ids.has(history));ids.set(history,actor);store.register(actor);}
 async function generate(_system,history,message,actions){
  const actor=ids.get(history);assert(actor,'Unknown actor history');const task=JSON.parse(message);const memory=store.players.get(actor),state=getState();
  const view=actor==='Storyteller'?(state.runtime?{...projector.storyteller(state),social:require('./storyteller-agent/index.cjs').socialView(store)}:{game_over:false,phase:'setup'}):projector.player(state,actor,memory);
  if(actor!=='Storyteller')memory.identity={...view.self};
  const allowed=(!fixtureProvider&&actor!=='Storyteller'&&(task.lookupDepth||0)<2)?[...actions,'lookup']:actions;
  const context=buildContext({actor,task,actions:allowed,view,memory,store});const requestId=++calls;
  if(calls>Number(process.env.BOTC_MAX_CALLS||1000))throw Error('Decision budget reached');
  const request={requestId,protocol:'semantic-v2',actor,prompt:message,actions:allowed,contextSha256:hash(context.system+context.input),system:context.system,input:context.input,structuredState:view,model:actor==='Storyteller'?storytellerModel:model};
  log('model_request',request);
  let response,usage;
  if(requestId<=replay.length){const saved=replay[requestId-1];assert.equal(saved.request.actor,actor);assert.equal(saved.request.prompt,message,'Replay control state mismatch');assert.equal(saved.request.contextSha256,request.contextSha256,'Replay semantic state mismatch');assert.deepEqual(saved.request.actions,allowed);response=saved.response;}
  else if(process.env.BOTC_REPLAY_ONLY==='1')throw Error('Replay exhausted: live generation forbidden');
  else if(fixtureProvider)response=await fixtureProvider.generate(context.system,[],message,actions);
  else{
   if(!ready)ready=initialize();await ready;
   const cwd=path.join(runDir,'isolated',actor);fs.mkdirSync(cwd,{recursive:true});
   const session=await client.start(request.model,cwd,context.system);assert(!session.instructionSources?.length);
   const threadId=session.thread.id;assert(!sessions.some(s=>s.threadId===threadId),'Reused native context');
   sessions.push({actor,threadId,requestId,model:request.model});log('codex_session',{actor,threadId,requestId,model:request.model,ephemeral:true,singleTurn:true,instructionSources:[],environmentAccess:false});
   liveCalls++;
   try{const result=await client.run(threadId,context.input,allowed,process.env[actor==='Storyteller'?'BOTC_ST_EFFORT':'BOTC_PLAYER_EFFORT']||(actor==='Storyteller'?'high':'medium'));response=JSON.parse(result.text);usage=result.usage;}
   finally{try{await client.rpc('thread/unsubscribe',{threadId});}catch{ /* client.close releases remaining sessions */ }}
  }
  assert(allowed.includes(response.action),'Invalid action');
  log('model_response',{requestId,actor,response,replayed:requestId<=replay.length,source:fixtureProvider?'deterministic-fixture':'codex-subscription'});
  if(usage)log('model_usage',{requestId,actor,usage});
  const before=store.events.length;store.recordChoice(actor,task,response);for(const e of store.events.slice(before))log('semantic_event',e);telemetry.record({...context.metrics,requestId},usage);
  store.save(path.join(runDir,'semantic-checkpoint.json'));
  if(response.action==='lookup'){
   const normalized=normalizeLookupMessage(response.message); if(normalized&&normalized.method!=='exact')log('lookup_normalization',{requestId,actor,from:response.message,to:normalized.value});
   const type=normalized&&lookupTypes[normalized.value]; if(normalized)response.message=normalized.value;
   const target=response.players?.[0];
   assert(type&&store.players.has(target),'Invalid internal retrieval request');
   let found=store.lookup(actor,{type}).filter(e=>type==='whisper'?e.audience.includes(target):e.actor===target).slice(-8);
   log('retrieval',{actor,target,type,eventIds:found.map(e=>e.id)});
   return generate(_system,history,JSON.stringify({...task,lookupDepth:(task.lookupDepth||0)+1,retrievedFacts:found}),actions);
  }
  return response;
 }
 return {kind:fixtureProvider?'fixture':'codex-subscription',model,storytellerModel,register,generate,telemetry,get calls(){return calls;},get liveCalls(){return liveCalls;},get sessions(){return sessions;},close(){telemetry.save(path.join(runDir,'telemetry.json'));store.save(path.join(runDir,'semantic-checkpoint.json'));client?.close();}};
}
module.exports={makeSemanticProvider};
