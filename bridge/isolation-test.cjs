const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {makeCodexProvider}=require('./codex-provider.cjs');
test('13 independent subscription sessions, per-role model strength, no cross-player private history',async()=>{
  const starts=[],requests=[],logs=[];
  const fake={async initialize(){},async rpc(method){return method==='account/read'?{account:{type:'chatgpt'}}:{data:[{model:'gpt-5.6-luna'},{model:'gpt-6-astra'}]};},async start(model,cwd,instructions){const id='T'+starts.length;starts.push({id,model,cwd,instructions});return {thread:{id},instructionSources:[]};},async run(threadId,input,actions,effort){requests.push({threadId,input:JSON.parse(input),effort});return {text:JSON.stringify({action:actions[0],reasoning:'test',message:'',players:[]})};},close(){}};
  const provider=makeCodexProvider({log:(type,data)=>logs.push({type,...data}),runDir:path.join(__dirname,'runs','isolation-test'),clientFactory:()=>fake});
  const histories=Array.from({length:13},()=>[]);
  for(let i=0;i<13;i++)provider.register(histories[i],i===12?'Storyteller':'P'+String(i+1).padStart(2,'0'));
  for(let i=0;i<13;i++) {
    histories[i].push({role:'user',parts:[{text:'PRIVATE_CANARY_'+i}]});
    const res=await provider.generate('common_rules',histories[i],'act',['idle']);
    histories[i].push({role:'user',parts:[{text:'act'}]},{role:'model',parts:[{text:JSON.stringify(res)}]});
  }
  assert.equal(new Set(starts.map(s=>s.id)).size,13);
  assert.equal(starts[12].model,'gpt-6-astra');
  assert.equal(starts.slice(0,12).every(s=>s.model==='gpt-5.6-luna'),true);
  for(let i=0;i<13;i++)assert.deepEqual(requests[i].input.newVisibleEvents,[{role:'user',parts:[{text:'PRIVATE_CANARY_'+i}]}]);
  histories[0].push({role:'user',parts:[{text:'PUBLIC_NEXT'}]});
  await provider.generate('common_rules',histories[0],'act2',['idle']);
  assert.equal(requests[13].threadId,requests[0].threadId);
  assert.deepEqual(requests[13].input.newVisibleEvents,[{role:'user',parts:[{text:'PUBLIC_NEXT'}]}]);
  await assert.rejects(provider.generate('rules',[],'act',['idle']),/Unregistered/);
  assert.throws(()=>provider.register(histories[0],'SomeoneElse'),/already assigned/);
  provider.close();
});
test('all 22 in-engine Chinese names match the fixed 集石钟楼百科 mapping',()=>{
  const names=require('./role-names.zh.json');
  const roles=require('../discord-botc/dist/game/roles').getScript().roles;
  assert.equal(Object.keys(names).length,22);
  for(const role of roles)assert.equal(role.name.zh,names[role.id]);
});
test('recovery replays only successful decisions and refuses divergent game prompts',async()=>{
  const dir=path.join(__dirname,'runs','replay-test');fs.mkdirSync(dir,{recursive:true});
  const response={action:'idle',reasoning:'saved',message:'',players:[]};
  fs.writeFileSync(path.join(dir,'events.jsonl'),[
    {type:'model_request',requestId:1,actor:'P01',prompt:'same state',actions:['idle']},
    {type:'model_response',requestId:1,response},
    {type:'model_request',requestId:2,actor:'P02',prompt:'failed request',actions:['idle']}
  ].map(JSON.stringify).join('\n'));
  const previous=process.env.BOTC_REPLAY_FROM;process.env.BOTC_REPLAY_FROM=dir;
  try {
    const options={log(){},runDir:dir,clientFactory(){throw Error('Replay must not call model');}};
    const provider=makeCodexProvider(options),history=[];provider.register(history,'P01');
    assert.deepEqual(await provider.generate('rules',history,'same state',['idle']),response);
    assert.equal(provider.liveCalls,0);
    const divergent=makeCodexProvider(options),other=[];divergent.register(other,'P01');
    await assert.rejects(divergent.generate('rules',other,'different state',['idle']),/Replay game state diverged/);
  } finally { if(previous===undefined)delete process.env.BOTC_REPLAY_FROM;else process.env.BOTC_REPLAY_FROM=previous; }
});
