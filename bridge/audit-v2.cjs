const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');const {SemanticStore}=require('./semantic-memory.cjs');
const norm=x=>JSON.parse(JSON.stringify(x));
function audit(dir){
 dir=path.resolve(dir);if(fs.existsSync(path.join(dir,'INVALID-MIXED-RUN.txt')))throw Error('Known mixed-run evidence');
 const events=fs.readFileSync(path.join(dir,'events.jsonl'),'utf8').trim().split('\n').map(JSON.parse);const store=new SemanticStore();for(let i=1;i<=12;i++)store.register('P'+String(i).padStart(2,'0'));store.register('Storyteller');const requests=new Map();let checked=0;
 for(const [i,e]of events.entries()){
  assert.equal(e.seq,i+1,'Event sequence gap or collision');
  const semantic=e.type==='semantic_event'?e.event:e.visibility&&e.id?Object.fromEntries(Object.entries(e).filter(([k])=>!['seq','time'].includes(k))):null;
  if(semantic){if(semantic.id<store.nextId)assert.deepEqual(norm(store.events[semantic.id-1]),semantic);else{assert.equal(semantic.id,store.nextId);store.observe(semantic);}}
  if(e.type==='model_request'&&e.protocol==='semantic-v2'){
   requests.set(e.requestId,e);const input=JSON.parse(e.input),m=store.players.get(e.actor);assert(m);
   assert.equal(e.contextSha256,crypto.createHash('sha256').update(e.system+e.input).digest('hex'));
   assert.deepEqual(input.memory.privateFacts,norm(m.privateFacts),`Private routing mismatch ${e.actor}`);
   assert.deepEqual(input.memory.beliefs,m.beliefs);assert.deepEqual(input.memory.plan,m.plan);
   for(const f of input.recent.private){const original=store.events.find(x=>x.id===f.id);assert(original?.visibility==='private'&&original.audience.includes(e.actor));}
   for(const f of input.control.retrievedFacts||[]){const original=store.events.find(x=>x.id===f.id);assert(original&&(original.visibility==='public'||original.audience.includes(e.actor)));}
   assert.deepEqual(input.state,e.structuredState);if(e.actor!=='Storyteller'){assert(!input.state.grimoire);assert.equal(input.state.self.poisoned,undefined);assert.equal(input.state.self.drunk,undefined);assert.equal(input.state.self.seat,e.actor);}
   checked++;
  }
  if(e.type==='model_response'&&e.actor){const request=requests.get(e.requestId);assert(request);store.recordChoice(e.actor,JSON.parse(request.prompt),e.response);}
  if(e.type==='day_complete')store.compact(e.day);
  assert(!['codex_tool_denied','codex_unexpected_item'].includes(e.type),'Unexpected native tool attempt');
 }
 const report={passed:true,events:events.length,checkedRequests:checked,scope:'Independent semantic private-fact routing, belief ownership, retrieved event ACL, native input hashes and public-view schema; not exhaustive game-rule certification'};fs.writeFileSync(path.join(dir,'audit-v2.json'),JSON.stringify(report,null,2));return report;
}
module.exports={audit};if(require.main===module)console.log(JSON.stringify(audit(process.argv[2])));
