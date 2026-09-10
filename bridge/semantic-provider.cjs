const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
 const {buildContext,getCharacterStrategy}=require('./context-builder.cjs');const {Telemetry}=require('./telemetry.cjs');
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
function parseModelJson(text){
 const raw=String(text||'').trim();
 const fenced=raw.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
 return JSON.parse(fenced?fenced[1]:raw);
}
function normalizeModelResponse(response,task={}){
 assert(response&&typeof response==='object'&&!Array.isArray(response),'Model response must be a JSON object');
 const normalized={...response};
 if(normalized.target!==undefined&&Array.isArray(normalized.players)&&normalized.players.length)assert(normalized.players.length===1&&normalized.players[0]===normalized.target,'Conflicting target and players');
 if((!Array.isArray(normalized.players)||normalized.players.length===0)&&typeof normalized.target==='string'){
  assert(Array.isArray(task.candidates)&&task.candidates.includes(normalized.target),'Legacy target is not a legal candidate');
  normalized.players=[normalized.target];
 }
 if(typeof normalized.reasoning!=='string'||!normalized.reasoning.trim())normalized.reasoning=typeof normalized.reason==='string'&&normalized.reason.trim()?normalized.reason:'模型返回了行动，但未提供简短决策摘要。';
 if(normalized.message===undefined)normalized.message='';
 if(normalized.players===undefined)normalized.players=[];
 delete normalized.target;delete normalized.reason;
 return normalized;
}
function makeSemanticProvider({store,projector,getState,log,runDir,fixtureProvider,clientFactory,storytellerClientFactory,providerKind,playerModel,runtimeConfig,playerProfiles={}}){
 const ids=new WeakMap(),sessions=[],replay=[];let client,storytellerClient,ready,calls=0,liveCalls=0;
 runtimeConfig=runtimeConfig||require('./llm-runtime-config.cjs').loadRuntimeConfig();
 const model=playerModel||runtimeConfig.models.player,storytellerModel=runtimeConfig.models.storyteller;
 const telemetry=new Telemetry(log);
 const lookupTypes={lookup_claim_history:'chat',lookup_vote_history:'vote',lookup_public_chat:'chat',lookup_private_chat:'whisper',lookup_ability_history:'choice',lookup_role_rules:'role_rules'};
 function normalizeLookupMessage(value){
  if(lookupTypes[value])return {value,method:'exact'};
  const s=String(value||'').toLowerCase();
  if(/公开|public/.test(s)&&/聊天|chat/.test(s))return {value:'lookup_public_chat',method:'safe-normalization'};
  if(/私聊|private|whisper/.test(s))return {value:'lookup_private_chat',method:'safe-normalization'};
  if(/投票|vote/.test(s))return {value:'lookup_vote_history',method:'safe-normalization'};
  if(/能力|ability|行动|choice/.test(s))return {value:'lookup_ability_history',method:'safe-normalization'};
  if(/自称|claim/.test(s))return {value:'lookup_claim_history',method:'safe-normalization'};
  if(/角色规则|技能规则|role.?rules|character.?rules/.test(s))return {value:'lookup_role_rules',method:'safe-normalization'};
  return null;
 }
 if(process.env.BOTC_REPLAY_FROM){
  const source=path.resolve(process.env.BOTC_REPLAY_FROM),ev=fs.readFileSync(path.join(source,'events.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
  const archivedConfig=ev.find(e=>e.type==='run_config'&&e.protocol===runtimeConfig.protocolVersion);
  if(!archivedConfig)throw Error(`Replay protocol mismatch: ${runtimeConfig.protocolVersion} refuses silent migration`);
  assert.deepEqual(archivedConfig.runtimeConfig,runtimeConfig,'Replay runtime configuration mismatch');
  const requests=new Map(ev.filter(e=>e.type==='model_request'&&e.protocol===runtimeConfig.protocolVersion).map(e=>[e.requestId,e]));
  for(const e of ev.filter(e=>e.type==='model_response'&&e.actor))replay.push({request:requests.get(e.requestId),response:e.response});
  log('replay_source',{source,decisions:replay.length,protocol:runtimeConfig.protocolVersion});
 }
 async function initialize(){
  client=clientFactory?clientFactory():new (require('./codex-client.cjs').CodexClient)(log);
  storytellerClient=storytellerClientFactory?storytellerClientFactory():client;
  await client.initialize();if(storytellerClient!==client)await storytellerClient.initialize();
  if(client.validateModels)await client.validateModels([model]);
  else {const account=await client.rpc('account/read',{refreshToken:false});assert.equal(account.account?.type,'chatgpt');const catalog=await client.rpc('model/list',{limit:100});assert(catalog.data.some(m=>m.model===model),'Configured player model unavailable');}
  if(storytellerClient!==client){const account=await storytellerClient.rpc('account/read',{refreshToken:false});assert.equal(account.account?.type,'chatgpt');const catalog=await storytellerClient.rpc('model/list',{limit:100});assert(catalog.data.some(m=>m.model===storytellerModel),'Configured storyteller model unavailable');}
  else if(!client.validateModels){const catalog=await client.rpc('model/list',{limit:100});assert(catalog.data.some(m=>m.model===storytellerModel),'Configured storyteller model unavailable');}
  log('provider_auth',{provider:providerKind||'codex-subscription',players:model,storyteller:storytellerModel});
 }
 function register(history,actor){assert(!ids.has(history));ids.set(history,actor);store.register(actor);}
 async function generate(_system,history,message,actions){
  const actor=ids.get(history);assert(actor,'Unknown actor history');const task=JSON.parse(message);const memory=store.players.get(actor),state=getState();
  const view=actor==='Storyteller'?(state.runtime?{...projector.storyteller(state),social:require('./storyteller-agent/index.cjs').socialView(store)}:{game_over:false,phase:'setup'}):projector.player(state,actor,memory);
  if(actor!=='Storyteller')memory.identity={...view.self};
  else if(state.runtime?.nightSession){
   view.resolvedInformation=[...state.runtime.nightSession.infoOutcomeDrafts].map(([recipient,draft])=>({recipient,template:draft.templateId,fields:draft.fields}));
  }
  const allowed=(!fixtureProvider&&actor!=='Storyteller'&&(task.lookupDepth||0)<2)?[...actions,'lookup']:actions;
  const context=buildContext({actor,task,actions:allowed,view,memory,store,profile:playerProfiles[actor],runtimeConfig});const requestId=++calls;
  if(calls>runtimeConfig.limits.maxCalls)throw Error('Decision budget reached');
  const request={requestId,protocol:runtimeConfig.protocolVersion,actor,prompt:message,actions:allowed,contextSha256:hash(context.system+context.input),system:context.system,input:context.input,structuredState:view,agentParameters:playerProfiles[actor],model:actor==='Storyteller'?storytellerModel:model};
  log('model_request',request);
  let response,usage;
  if(requestId<=replay.length){const saved=replay[requestId-1];assert.equal(saved.request.actor,actor);assert.equal(saved.request.prompt,message,'Replay control state mismatch');assert.equal(saved.request.contextSha256,request.contextSha256,'Replay semantic state mismatch');assert.deepEqual(saved.request.actions,allowed);response=saved.response;}
  else if(process.env.BOTC_REPLAY_ONLY==='1')throw Error('Replay exhausted: live generation forbidden');
  else if(fixtureProvider)response=await fixtureProvider.generate(context.system,[],message,actions);
  else{
   if(!ready)ready=initialize();await ready;
   const cwd=path.join(runDir,'isolated',actor);fs.mkdirSync(cwd,{recursive:true});
   const activeClient=actor==='Storyteller'?storytellerClient:client;
   const maxAttempts=runtimeConfig.limits.maxAttempts;
   let lastError, correction='';
   for(let attempt=1;attempt<=maxAttempts;attempt++){
    let threadId;
    try{
     const session=await activeClient.start(request.model,cwd,context.system);assert(!session.instructionSources?.length);
     threadId=session.thread.id;assert(!sessions.some(s=>s.threadId===threadId),'Reused native context');
     sessions.push({actor,threadId,requestId,model:request.model,attempt});log('model_session',{actor,threadId,requestId,attempt,model:request.model,provider:actor==='Storyteller'?'codex-subscription':providerKind||'codex-subscription',ephemeral:true,singleTurn:true,instructionSources:[],environmentAccess:false});
     liveCalls++;
     const retryInput=correction?JSON.stringify({...JSON.parse(context.input),responseCorrection:correction}):context.input;
     const result=await activeClient.run(threadId,retryInput,allowed,actor==='Storyteller'?runtimeConfig.reasoningEffort.storyteller:runtimeConfig.reasoningEffort.player,runtimeConfig.limits.timeoutMs);
     log('model_raw_response',{requestId,actor,attempt,text:result.text,usage:result.usage});
     response=parseModelJson(result.text);usage=result.usage;
     const candidate=normalizeModelResponse(response,task);
     assert(allowed.includes(candidate.action),'Invalid action; choose one of '+allowed.join(', '));
     assert(Object.keys(candidate).every(k=>['action','message','players','reasoning','memoryUpdate'].includes(k)),'Unknown response fields; use action,message,players,reasoning only');
     assert(typeof candidate.message==='string'&&Array.isArray(candidate.players)&&candidate.players.every(p=>typeof p==='string'),'message must be string; players must be array of strings');
     if(candidate.action==='choose'&&task.kind==='night')assert(candidate.players.length===task.count&&new Set(candidate.players).size===task.count&&candidate.players.every(p=>task.candidates.includes(p)),'Night choose requires exactly '+task.count+' distinct legal players');
     lastError=null;break;
    }catch(error){
     lastError=error;
     correction='上一响应未被执行。错误：'+error.message+'。仅返回一个 JSON 对象，完整填写 action,message,players,reasoning；不得在 JSON 前后补充文字。请依据原局面重新选择。';
     if(attempt<maxAttempts)log('model_call_retry',{requestId,actor,attempt,nextAttempt:attempt+1,category:error.name||'Error',message:error.message});
    }finally{if(threadId){try{await activeClient.rpc('thread/unsubscribe',{threadId});}catch{ /* client.close releases remaining sessions */ }}}
   }
   if(lastError)throw lastError;
  }
  const missingReasoning=typeof response?.reasoning!=='string'||!response.reasoning.trim();
  const legacyTarget=typeof response?.target==='string';
  response=normalizeModelResponse(response,task);
  if(missingReasoning)log('response_normalization',{requestId,actor,field:'reasoning',reason:'mapped legacy reason or inserted neutral audit text'});
  if(legacyTarget)log('response_normalization',{requestId,actor,field:'target',reason:'mapped exact legal legacy target to players'});
  assert(allowed.includes(response.action),'Invalid action');
  log('model_response',{requestId,actor,response,replayed:requestId<=replay.length,source:fixtureProvider?'deterministic-fixture':actor==='Storyteller'?'codex-subscription':providerKind||'codex-subscription'});
  if(usage)log('model_usage',{requestId,actor,usage});
  const before=store.events.length;store.recordChoice(actor,task,response);for(const e of store.events.slice(before))log('semantic_event',e);telemetry.record({...context.metrics,requestId},usage);
  store.save(path.join(runDir,'semantic-checkpoint.json'));
  if(response.action==='lookup'){
   const normalized=normalizeLookupMessage(response.message); if(normalized&&normalized.method!=='exact')log('lookup_normalization',{requestId,actor,from:response.message,to:normalized.value});
   const type=normalized&&lookupTypes[normalized.value]; if(normalized)response.message=normalized.value;
   const target=response.players?.[0];
   if(type==='role_rules'){
    const rule=getCharacterStrategy(target);
    assert(rule&&rule.rules,'Invalid role-rules lookup');
    log('retrieval',{actor,target,type,eventIds:[]});
    return generate(_system,history,JSON.stringify({...task,lookupDepth:(task.lookupDepth||0)+1,retrievedFacts:[{type:'role_rules',role:target,name:rule.name,rules:rule.rules}]}),actions);
   }
   assert(type&&store.players.has(target),'Invalid internal retrieval request');
   let found=store.lookup(actor,{type}).filter(e=>type==='whisper'?e.audience.includes(target):e.actor===target).slice(-8);
   log('retrieval',{actor,target,type,eventIds:found.map(e=>e.id)});
   return generate(_system,history,JSON.stringify({...task,lookupDepth:(task.lookupDepth||0)+1,retrievedFacts:found}),actions);
  }
  return response;
 }
 async function prepareGame(config){if(!ready)ready=initialize();await ready;return client.planGame?client.planGame(config):null;}
 return {kind:fixtureProvider?'fixture':providerKind||'codex-subscription',model,storytellerModel,runtimeConfig,playerProfiles,register,generate,prepareGame,telemetry,get calls(){return calls;},get liveCalls(){return liveCalls;},get sessions(){return sessions;},close(){telemetry.save(path.join(runDir,'telemetry.json'));store.save(path.join(runDir,'semantic-checkpoint.json'));client?.close();if(storytellerClient&&storytellerClient!==client)storytellerClient.close();}};
}
module.exports={makeSemanticProvider,parseModelJson,normalizeModelResponse};
