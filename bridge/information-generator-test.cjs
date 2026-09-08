const {test}=require('node:test'),assert=require('node:assert/strict');
const {setInformationGenerator,generatePair,generateRoleInformation}=require('../discord-botc/dist/game/informationGenerator');
const {getScript}=require('../discord-botc/dist/game/roles');
function ctx(ids,actor=0){const roles=getScript().roles;const roster=ids.map((id,i)=>({player:{userId:`P${i}`,seatIndex:i,displayName:`P${i}`},role:roles.find(r=>r.id===id),effectiveRole:roles.find(r=>r.id===id),alive:true,tags:new Set(),death:null}));return {state:{runtime:{playerStates:roster,daySession:{dayNumber:1}}},night:{player:roster[actor].player,scriptRoles:roles,responses:new Map(),nightNumber:1}};}
test('pair generation uses ST tuple, no random draft; offers other true Townsfolk',async()=>{
 const c=ctx(['washerwoman','soldier','imp']);let called=0;
 setInformationGenerator(async(current,choices)=>{assert.equal(current,c);called++;return choices.findIndex(x=>x.p1==='P1'&&x.p2==='P2'&&x.role==='soldier');});
 const random=Math.random;Math.random=()=>{throw Error('Random information forbidden');};
 try{assert.deepEqual((await generatePair(c)).fields,{p1:'P1',p2:'P2',role:'soldier'});assert.equal(called,1);}finally{Math.random=random;}
});
test('invalid ST choices fail closed',async()=>{setInformationGenerator(async()=>-1);await assert.rejects(generatePair(ctx(['washerwoman','soldier','imp'])),/invalid information/);});
test('fixed chef result does not call model; poisoned count does',async()=>{
 const c=ctx(['chef','imp','poisoner','soldier']);let called=0;setInformationGenerator(async(c,choices)=>{called++;return choices.findIndex(x=>x.count===0);});
 assert.equal((await generatePair(c)).fields.count,1);assert.equal(called,0);
 c.state.runtime.playerStates[0].tags.add('poisoned');assert.equal((await generatePair(c)).fields.count,0);assert.equal(called,1);
});
test('Recluse registration creates ST choices; poison removes the choice',async()=>{
 const c=ctx(['fortune_teller','recluse','soldier']);c.night.responses.set('P0',['P1','P2']);let called=0;setInformationGenerator(async(c,choices)=>{called++;return choices.findIndex(x=>x.yes===true);});
 assert.equal((await generatePair(c)).fields.yes,true);c.state.runtime.playerStates[1].tags.add('poisoned');assert.equal((await generatePair(c)).fields.yes,false);assert.equal(called,1);
});
test('poisoned Undertaker and Ravenkeeper role information is chosen by ST',async()=>{
 const c=ctx(['undertaker','soldier','imp']);c.state.runtime.playerStates[0].tags.add('poisoned');c.state.runtime.playerStates[1].death={byExecution:true,dayNumber:1};
 setInformationGenerator(async(c,choices)=>choices.findIndex(x=>x.role==='monk'));
 assert.equal((await generatePair(c)).fields.role,'monk');assert.equal(await generateRoleInformation(c,'P1'),'monk');
});
