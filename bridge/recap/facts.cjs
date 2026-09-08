const fs=require('node:fs'),path=require('node:path');
const names=require('../role-names.zh.json');
function extract(dir){
 const events=fs.readFileSync(path.join(dir,'events.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
 const result=JSON.parse(fs.readFileSync(path.join(dir,'result.json'),'utf8'));
 const assignment=events.find(e=>e.type==='assignment');
 if(!assignment)throw Error('Missing assignment');
 const sections=[], byId=new Map();let current=null,previous=new Map();
 const section=id=>{if(!byId.has(id)){const s={id,events:[],facts:[]};sections.push(s);byId.set(id,s);}return byId.get(id);};
 for(const e of events){
  const m=e.type==='public'&&e.message.match(/\*\*第 (\d+) ([夜天])\*\*/);
  if(m)current=section(`${m[2]==='夜'?'night':'day'}-${m[1]}`);
  if(e.type==='state'){
   for(const p of e.players){const before=previous.get(p.name);
    if(before&&current){
     if(before.alive&&!p.alive)current.facts.push({seq:e.seq,kind:'death',player:p.name,role:p.role,execution:p.death.byExecution});
     if(before.role!==p.role)current.facts.push({seq:e.seq,kind:'role_change',player:p.name,from:before.role,to:p.role});
    }
    previous.set(p.name,p);
   }
  }
  if(!current)continue;
  if(e.type==='player_decision'&&e.kind==='night')current.facts.push({seq:e.seq,kind:'choice',player:e.actor,targets:e.response.players});
  if(e.type==='private'&&e.message.startsWith('你得知'))current.facts.push({seq:e.seq,kind:'information',player:e.recipient,text:e.message});
  if(e.type==='nomination_complete'){const n=e.nomination;section(`day-${e.day}`).facts.push({seq:e.seq,kind:'nomination',from:n.nominatorId,to:n.nomineeId,votes:n.finalVoteCount,alive:n.aliveThenCount,threshold:Math.floor(n.aliveThenCount/2)+1});}
  if(e.type==='public'&&(/^P\d{2}:/.test(e.message)||m||/获胜|被处决|死亡|击杀/.test(e.message)))current.events.push({seq:e.seq,visibility:'public',text:e.message});
  if(e.type==='private'&&e.message.startsWith('Private from'))current.events.push({seq:e.seq,visibility:'private',recipient:e.recipient,text:e.message});
 }
 return {version:1,run:path.basename(dir),mode:result.mode,completed:result.completed,verdict:result.verdict,seed:result.seed,players:assignment.players.map(p=>({...p,name:names[p.role],shownName:names[p.shown]})),bluffs:assignment.bluffs,sections};
}
module.exports={extract};
if(require.main===module){const dir=path.resolve(process.argv[2]);const data=extract(dir);fs.writeFileSync(path.join(dir,'recap-facts.json'),JSON.stringify(data,null,2));console.log('Extracted '+data.sections.length+' phases');}
