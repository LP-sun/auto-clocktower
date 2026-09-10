'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {defaults}=require('./llm-runtime-config.cjs');
const {SemanticStore}=require('./semantic-memory.cjs');
const {buildContext}=require('./context-builder.cjs');

const clone=value=>JSON.parse(JSON.stringify(value));
function config(overrides={}){
 const value=clone(defaults);
 for(const [section,fields] of Object.entries(overrides))value[section]={...value[section],...fields};
 return value;
}
function projectedPlayer(){return {self:{seat:'P01',role:'chef',alignment:'good'},alive:['P01','P02','P03','P04','P05'],dead:[],game_over:false,phase:'day',day:1,executionThreshold:3};}
function temporaryRun(){return fs.mkdtempSync(path.join(os.tmpdir(),'botc-parameterized-'));
}

test('semantic route exposes the selected profile and passes model, effort, timeout, and attempts to the client',async()=>{
 const store=new SemanticStore(),logs=[],starts=[],runs=[];let attempt=0;
 const runtime=config({models:{player:'player-custom',storyteller:'story-custom'},reasoningEffort:{player:'xhigh',storyteller:'low'},limits:{...defaults.limits,maxAttempts:2,timeoutMs:4321}});
 const profile={personality:{openness:.123},skill:{level:'expert',decisionTemperature:.5}};
 const fake={async initialize(){},async validateModels(models){assert.deepEqual(models,['player-custom']);},async start(model,_cwd){starts.push(model);return {thread:{id:'turn-'+starts.length},instructionSources:[]};},async run(id,input,actions,effort,timeoutMs){runs.push({id,input,actions,effort,timeoutMs});attempt++;return {text:attempt===1?'not json':JSON.stringify({action:'idle',reasoning:'ok',message:'',players:[],memoryUpdate:null})};},async rpc(){return{};},close(){}};
 const provider=require('./semantic-provider.cjs').makeSemanticProvider({store,projector:{player:projectedPlayer},getState:()=>({runtime:{}}),log:(type,data)=>logs.push({type,data}),runDir:temporaryRun(),runtimeConfig:runtime,playerProfiles:{P01:profile},clientFactory:()=>fake});
 const history=[];provider.register(history,'P01');
 const response=await provider.generate('',history,JSON.stringify({kind:'vote',day:1}),['idle']);
 assert.equal(response.action,'idle');assert.deepEqual(starts,['player-custom','player-custom']);
 assert.deepEqual(runs.map(x=>[x.effort,x.timeoutMs]),[['xhigh',4321],['xhigh',4321]]);
 const visibleProfile=JSON.parse(runs[0].input).agentParameters;
 assert.deepEqual(visibleProfile.personality,profile.personality);assert.deepEqual(visibleProfile.skill,profile.skill);assert.match(visibleProfile.interpretation,/稳定行为倾向/);
 const request=logs.find(x=>x.type==='model_request').data;
 assert.equal(request.protocol,runtime.protocolVersion);assert.equal(request.model,'player-custom');assert.deepEqual(request.agentParameters,profile);
 provider.close();
});

test('structured claim evidence references resolve only to public, ACL-visible events',()=>{
 const store=new SemanticStore();for(const seat of ['P01','P02','P03','Storyteller'])store.register(seat);
 const secret=store.observe({visibility:'private',audience:['P01','P02'],type:'whisper',actor:'P02',day:1,text:'ACL_SECRET'});
 const claim=store.observe({visibility:'public',type:'chat',actor:'P02',day:1,text:'我是厨师'});
 for(const seat of ['P01','P02','P03']){
  const memory=store.players.get(seat),structured=memory.publicClaims.P02;
  assert.equal(structured.kind,'claim');assert.equal(structured.confirmed,false);assert.equal(structured.source,claim.id);
  const evidence=store.lookup(seat).find(event=>event.id===structured.source);
  assert(evidence);assert.equal(evidence.visibility,'public');
  const context=buildContext({actor:seat,task:{kind:'discussion',day:1},actions:['idle'],view:{...projectedPlayer(),self:{...projectedPlayer().self,seat}},memory,store,profile:{personality:{},skill:{}}});
  assert.equal(JSON.parse(context.input).memory.claims.P02.source,claim.id);
  if(seat==='P03'){assert(!context.input.includes('ACL_SECRET'));assert(!store.lookup(seat).some(event=>event.id===secret.id));}
 }
 assert(!JSON.stringify(require('./storyteller-agent/index.cjs').socialView(store)).includes('ACL_SECRET'));
});

test('direct OpenAI route applies generation, retry, timeout, and call-budget configuration',async()=>{
 const dir=temporaryRun(),file=path.join(dir,'config.json'),runtime=config({generation:{temperature:.31,topP:.72,topK:17,maxOutputTokens:333},limits:{...defaults.limits,maxCalls:1,maxAttempts:2,timeoutMs:7654}});
 fs.writeFileSync(file,JSON.stringify(runtime));
 const saved={...process.env},oldFetch=global.fetch,oldTimeout=AbortSignal.timeout,calls=[],timeoutMarker={configuredTimeout:true};
 try{
  Object.assign(process.env,{BOTC_LLM_CONFIG:file,BOTC_PROVIDER:'openai',OPENAI_MODEL:'route-model'});delete process.env.OPENAI_API_KEY;
  AbortSignal.timeout=milliseconds=>{assert.equal(milliseconds,7654);return timeoutMarker;};
  global.fetch=async(url,options)=>{calls.push({url,options,body:JSON.parse(options.body)});return calls.length===1?{ok:false,status:503}:{ok:true,json:async()=>({choices:[{message:{content:'{"action":"idle","reasoning":"ok"}'}}],usage:{}})};};
  const provider=require('./provider.cjs').makeProvider({log(){},runDir:dir});
  assert.equal((await provider.generate('system',[],'{"kind":"vote"}',['idle'])).action,'idle');
  assert.equal(calls.length,2);assert.deepEqual(calls[1].body,{model:'route-model',messages:calls[1].body.messages,max_tokens:333,temperature:.31,top_p:.72,response_format:{type:'json_object'}});
  assert.equal(calls[1].options.signal,timeoutMarker);
  await assert.rejects(()=>provider.generate('system',[],'{"kind":"vote"}',['idle']),/budget/);
 }finally{
  global.fetch=oldFetch;AbortSignal.timeout=oldTimeout;for(const key of Object.keys(process.env))if(!(key in saved))delete process.env[key];Object.assign(process.env,saved);
 }
});

test('replay refuses the same protocol when archived runtime parameters differ',()=>{
 const dir=temporaryRun(),runtime=config({generation:{...defaults.generation,temperature:.19}}),archived=config({generation:{...defaults.generation,temperature:1.4}});
 fs.writeFileSync(path.join(dir,'events.jsonl'),JSON.stringify({type:'run_config',protocol:runtime.protocolVersion,runtimeConfig:archived})+'\n');
 const previous=process.env.BOTC_REPLAY_FROM;process.env.BOTC_REPLAY_FROM=dir;
 try{
  assert.throws(()=>require('./semantic-provider.cjs').makeSemanticProvider({store:new SemanticStore(),projector:{},getState(){},log(){},runDir:temporaryRun(),runtimeConfig:runtime}),/replay.*config|config.*mismatch|parameters.*differ/i);
 }finally{if(previous===undefined)delete process.env.BOTC_REPLAY_FROM;else process.env.BOTC_REPLAY_FROM=previous;}
});
