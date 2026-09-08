// Reconstruct visibility from message routing, independently of provider snapshots.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const dir=path.resolve(process.argv[2]);
const events=fs.readFileSync(path.join(dir,'events.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
const actors=[...Array.from({length:12},(_,i)=>'P'+String(i+1).padStart(2,'0')),'Storyteller'];
const histories=new Map(actors.map(a=>[a,[]])),requests=new Map(),threads=new Map();
const entry=(text,role='user')=>({role,parts:[{text}]});
let auditedRequests=0,replayedResponses=0,liveResponses=0;
for(const [i,e] of events.entries()) {
  assert.equal(e.seq,i+1,'Event sequence gap');
  if(e.type==='public')for(const history of histories.values())history.push(entry(e.message));
  if(e.type==='private') {assert(histories.has(e.recipient));histories.get(e.recipient).push(entry(e.message));}
  if(e.type==='codex_session') {
    assert(!threads.has(e.threadId),'Session shared between actors');threads.set(e.threadId,e.actor);
    assert.deepEqual(e.instructionSources,[]);assert.equal(e.environmentAccess,false);
  }
  if(e.type==='model_request') {
    requests.set(e.requestId,e);const history=histories.get(e.actor);assert(history);
    assert.equal(history.length,e.historyLength,`History length ${e.actor} request ${e.requestId}`);
    if(!e.replayed) {
      assert.equal(threads.get(e.threadId),e.actor);
      assert.deepEqual(e.delta,history.slice(e.deltaStart),`Private routing mismatch ${e.actor}`);
      assert.equal(e.historySha256,crypto.createHash('sha256').update(JSON.stringify(history)).digest('hex'));
      auditedRequests++;
    }
  }
  if(e.type==='model_response') {
    const request=requests.get(e.requestId);assert(request);
    const r=e.response, normalized={reasoning:r.reasoning,action:r.action};
    if(r.message!==undefined)normalized.message=r.message;
    if(r.players!==undefined)normalized.players=r.players;
    histories.get(request.actor).push(entry(request.prompt),entry(JSON.stringify(normalized),'model'));
    e.replayed?replayedResponses++:liveResponses++;
  }
  assert(!['codex_tool_denied','codex_unexpected_item'].includes(e.type),'Unexpected tool attempt');
}
const result={passed:true,events:events.length,auditedRequests,liveResponses,replayedResponses,independentSessions:threads.size,scope:'Public/private routing reconstruction, request hashes, session separation, absent tools. Does not certify all game rules.'};
fs.writeFileSync(path.join(dir,'audit.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
