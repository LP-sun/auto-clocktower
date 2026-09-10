// Local transport bridge: the actual discord-botc Automated Mode remains the referee.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
require('../clocktower-ai/node_modules/dotenv').config({ path: path.join(__dirname, '.env') });
const fixture = process.argv.includes('--fixture');
if (!fixture && !process.argv.includes('--allow-live-models') && process.env.BOTC_REPLAY_ONLY !== '1') throw new Error('Live model calls require human confirmation. After approval use --allow-live-models; --fixture is offline.');
const seed = process.env.BOTC_SEED === undefined
  ? crypto.randomInt(0, 0x100000000)
  : Number(process.env.BOTC_SEED);
const runDir = require('./run-directory.cjs').createRunDirectory(path.join(__dirname,'runs'),fixture?'fixture':'llm');
let runTagWritten=false;
function writeRunTag(tag, details={}){if(runTagWritten)return;runTagWritten=true;const current=typeof state==='undefined'?null:state;fs.writeFileSync(path.join(runDir,tag),JSON.stringify({tag,time:new Date().toISOString(),phase:current?.phase||'initializing',night:current?.runtime?.nightNumber||0,day:current?.runtime?.daySession?.dayNumber||0,...details},null,2));}
process.once('SIGINT',()=>{writeRunTag('INTERRUPTED',{reason:'SIGINT'});process.exitCode=130;});
process.once('SIGTERM',()=>{writeRunTag('INTERRUPTED',{reason:'SIGTERM'});process.exitCode=143;});
fs.mkdirSync(path.join(runDir, 'data/generated'), { recursive: true });
process.chdir(runDir); // clocktower-ai's original CSV files remain per-run.
let serial = 0;
let lastActivityAt = Date.now();
function log(type, data) {
  lastActivityAt = Date.now();
  if(type==='semantic_event')data={event:data};
  fs.appendFileSync(path.join(runDir, 'events.jsonl'), JSON.stringify({ seq: ++serial, time: new Date().toISOString(), type, ...data }, (_, v) => v instanceof Map ? Object.fromEntries(v) : v instanceof Set ? [...v] : typeof v === 'function' ? undefined : v) + '\n');
}
const watchdogMs = Math.max(30_000, Number(process.env.BOTC_IDLE_TIMEOUT_MS || 300_000));
const watchdog = setInterval(() => {
  const idleMs = Date.now() - lastActivityAt;
  if (idleMs >= watchdogMs) {
    writeRunTag('INTERRUPTED', { reason:'idle-timeout', idleMs, watchdogMs, lastActivityAt:new Date(lastActivityAt).toISOString() });
    clearInterval(watchdog);
    process.exitCode = 124;
    process.exit();
  }
}, Math.min(10_000, Math.max(1_000, Math.floor(watchdogMs / 10))));
watchdog.unref();
const { makeProvider } = require('./provider.cjs');
const selectedProvider = fixture ? 'fixture' : (process.env.BOTC_PROVIDER || 'codex');
if (!['fixture','codex','copilot'].includes(selectedProvider)) throw new Error(`Unsupported BOTC_PROVIDER: ${selectedProvider}`);
const {SemanticStore}=require('./semantic-memory.cjs');
const {ViewProjector}=require('./player-view.cjs');
const semanticStore=new SemanticStore(), projector=new ViewProjector();
const runtimeConfig=require('./llm-runtime-config.cjs').loadRuntimeConfig();
const playerCount = Math.max(5, Number(process.env.BOTC_PLAYERS || 12));
const playerProfiles=require('./llm-runtime-config.cjs').createPlayerProfiles(runtimeConfig,Array.from({length:playerCount},(_,i)=>`P${String(i+1).padStart(2,'0')}`),seed);
const fixtureProvider=fixture?makeProvider({log:(type,data)=>log('fixture_'+type,data),runDir,fixture:true}):null;
const copilotPlayers=selectedProvider==='copilot';
const provider=require('./semantic-provider.cjs').makeSemanticProvider({store:semanticStore,projector,getState:()=>state,log,runDir,fixtureProvider,runtimeConfig,playerProfiles,providerKind:copilotPlayers?'copilot-sdk-players+codex-storyteller':undefined,playerModel:copilotPlayers?(process.env.BOTC_COPILOT_MODEL||'auto'):undefined,clientFactory:copilotPlayers?()=>new (require('./copilot-client.cjs').CopilotDecisionClient)(log):undefined,storytellerClientFactory:copilotPlayers?()=>new (require('./codex-client.cjs').CodexClient)(log):undefined});
const db = p => require(path.join(root, 'discord-botc/dist', p));
const { createGame, setUpdateHook } = db('game/state');
const { handleYouare } = db('handlers/youare');
const { handleNightPlayerDM, resolveEmptyNight, setAutomatedInfoReview, applyInfoDraftFieldForUI } = db('game/night');
const { handleNominate, handleYe, closeNominationWindow, cancelNominationTimer } = db('game/nominations');
const { processEndOfDay } = db('game/dayFlow');
const { handleRoleCommand } = db('game/roleCommands');
const { updateGuildSettings } = db('guildSettings');
const { getScript } = db('game/roles');
const { evaluateWinCondition } = db('game/winConditions');
const { executionThreshold } = db('game/voteThreshold');
const { setAdjudicationPolicy } = db('game/adjudication');
let randomState = seed >>> 0;
Math.random = () => { randomState = (Math.imul(1664525, randomState) + 1013904223) >>> 0; return randomState / 4294967296; };
const players = Array.from({ length: playerCount }, (_, index) => ({ userId: `P${String(index + 1).padStart(2, '0')}`, username: `P${String(index + 1).padStart(2, '0')}`, displayName: `P${String(index + 1).padStart(2, '0')}`, seatIndex: index }));
const aiPlayers = players.map(p => ({ name: p.displayName, actualRole: '', ephemeralControl:true, behaviorParameters:playerProfiles[p.displayName], chatHistory: [], actionHistory: [], status: 'alive' }));
const state = { gameId: `bridge-${playerCount}`, gameNumber: 1, guildId: 'local', channelId: 'local-game', players, storytellerId: null, mode: 'pending', phase: 'pending_storyteller', draft: null, runtime: null };
const {BASE_PLAYER_SYSTEM_EN,BASE_PLAYER_SYSTEM_ZH,renderTerminologyPrompt}=require('./prompt-terminology.cjs');
const system = `${BASE_PLAYER_SYSTEM_EN}\n${BASE_PLAYER_SYSTEM_ZH}\n${renderTerminologyPrompt({language:'bilingual'})}`;
const st = { name: 'Storyteller', actualRole: '', ephemeralControl:true, chatHistory: [], actionHistory: [], status: 'alive' };
if(provider.register) { for(const p of [...aiPlayers,st]) provider.register(p.chatHistory,p.name); }
function broadcastTo(recipients,message){
 for(const player of recipients){
  player.chatHistory.push({role:'user',parts:[{text:message}]});
  player.actionHistory.push('hear_message');
 }
}
const stSystem = 'You are the AI Storyteller for Blood on the Clocktower, Trouble Brewing. Act as a ReAct-style decision agent: inspect the supplied authoritative grimoire/state, choose exactly one legal action, and let the deterministic engine execute it. The engine is the sole authority for role rules, legal choices, targets, deaths, votes, and victory; never invent or mutate state and never disclose hidden information. Protocol: return one JSON object only, with keys reasoning (short), action, message, players. For a storyteller_decision request, evaluate its parameterized objectives, set action to choose_info, and return exactly one legal choice ID in players; reasoning remains your own assessment. For information selection, action must be choose_info. If the engine asks for a pair, players must contain exactly two seat IDs and message must be a JSON object containing the requested fields, for example {"action":"choose_info","message":"{\\"role\\":\\"virgin\\"}","players":["P02","P04"]}. For Fortune Teller, targets are already fixed by the engine: return players:[] and message {"yes":true} or {"yes":false}. For fixed-result roles, return players:[] and only the requested result fields. For pacing, action is continue_discussion or open_nominations. Do not return prose in place of JSON, markdown fences, indices, or fields not requested. If a prior response was rejected, read correction and repair the exact missing or illegal field. Never force players to make a statement or reveal a character; use open_nominations when discussion is repetitive or no longer productive.';
const {StorytellerAgent,socialView}=require('./storyteller-agent/index.cjs');
const stView=current=>({...projector.storyteller(current),social:socialView(semanticStore)});
const storytellerAgent=new StorytellerAgent({log,timeoutMs:runtimeConfig.limits.timeoutMs,parameters:runtimeConfig.storyteller,model:fixture?undefined:async request=>{
 const night=state.runtime?.nightNumber||0,phase=night===1?'first_night':'other_night';
 const task={...request,phase,night,responseProtocol:{action:'choose_info',choiceIdInPlayers:true}};
 const response=await provider.generate(stSystem,st.chatHistory,JSON.stringify(task),['choose_info']);
 const choiceId=Array.isArray(response.players)&&response.players.length===1?response.players[0]:undefined;
 const index=Number(choiceId);
 if((response.players!==undefined&&response.players.length!==1)||!Number.isInteger(index)||index<0||index>=request.decision.choices.length)throw Error('Invalid legal choice ID');
 return {choiceId:String(index),reasoning:response.reasoning,reasonCodes:response.reasonCodes};
}});
// All engine discretion — registration (Recluse/Spy), misinformation, and
// death redirection — crosses one asynchronous policy boundary.  Live model
// failures propagate and stop the run; rules-only mode has no policy.
setAdjudicationPolicy(async (current, decision) => storytellerAgent.decide(stView(current || state), {
  ...decision,
  actor: decision.actor || decision.player || decision.role,
}));
setAutomatedInfoReview(async current => {
 for(const [recipient,draft] of current.runtime.nightSession.infoOutcomeDrafts){
  // Rebuild the engine's legal domain after each field change (pair targets must differ).
  const fields=db('game/discretion').informationDecisions(current,recipient,draft).map(d=>d.field);
  for(const field of fields){
   const decision=db('game/discretion').informationDecisions(current,recipient,draft).find(d=>d.field===field);
   if(!decision)continue;
   const value=await storytellerAgent.decide(stView(current),decision);
   const outcome=applyInfoDraftFieldForUI(current,recipient,field,value);
   if(outcome.error)throw Error('Engine rejected legal information choice: '+outcome.error);
   log('storyteller_info',{recipient,field,value,policy:'legal-decision'});
  }
 }
});
db('game/informationGenerator').setInformationGenerator(async (ctx,choices)=>{
 const recipient=ctx.night.player.userId;
 if(fixture){log('information_generation',{recipient,source:'offline-policy',choice:choices[0]});return 0;}
 const actorState=ctx.state.runtime.playerStates.find(p=>p.player.userId===recipient);
 const roleEntry=getScript().roles.find(r=>r.id===actorState.effectiveRole.id);
 const fortune=actorState.effectiveRole.id==='fortune_teller'; const pairRequired=choices.some(c=>c.p1!==undefined&&c.p2!==undefined);
 let response, correction='';
 const keys=[...new Set(choices.flatMap(Object.keys))];
 const protocol={fields:keys,types:Object.fromEntries(keys.map(k=>[k,typeof choices.find(c=>k in c)[k]])),example:{reasoning:'简短理由',action:'choose_info',message:JSON.stringify(pairRequired?{role:'virgin'}:Object.fromEntries(Object.entries(choices[0]).map(([k,v])=>[k,typeof v==='boolean'?true:typeof v==='number'?0:v]))),players:pairRequired?['P02','P04']:[],memoryUpdate:null},note:'示例仅演示格式，不是推荐选择。role 使用剧本英文 ID；两人座位由 players 提供。固定 target/seat 字段必须原样返回。'};
 for(let attempt=0;attempt<3;attempt++){
 response=await provider.generate(stSystem,st.chatHistory,JSON.stringify({kind:'storyteller_info',protocol,recipient,night:ctx.night.nightNumber,grimoire:stView(state).grimoire,requestingRole:{id:actorState.effectiveRole.id,name:roleEntry?.name?.zh,rules:roleEntry?.guide?.zh},legalDecision:{type:'generate_information',actor:recipient,ability:actorState.effectiveRole.id,instruction:fortune?'只返回占卜结果 yes 为 true 或 false，players 必须为空。':pairRequired?'返回两个座位和当前角色所需的全部信息字段。':'只返回当前角色要求的结果字段（例如 count），players 必须为空。'},correction}),['choose_info']);
 let requested={};
 try { requested=JSON.parse(response.message||'{}'); } catch {
  const text=response.message||'';
  const responseSeats=Array.isArray(response.players)?[...new Set(response.players.filter(x=>/^P\d{2}$/.test(x)))]:[];
  const seats=responseSeats.length===2?responseSeats:[...new Set(text.match(/P\d{2}/g)||[])];
  // Natural-language fallback: identify one legal tuple by unordered seat pair
  // and the role name (English id or 集石 Chinese translation).  Do not rely
  // on the model returning players[] or on seat ordering.
  const directMatches=pairRequired&&seats.length===2?choices.map((c,i)=>({c,i})).filter(({c})=>{
   if(typeof c.role!=='string'||new Set([c.p1,c.p2]).size!==2)return false;
   if(!seats.every(s=>[c.p1,c.p2].includes(s)))return false;
   const role=getScript().roles.find(r=>r.id===c.role);
   const labels=[c.role,role?.name?.zh,role?.name,role?.displayName].filter(Boolean);
   return labels.some(label=>typeof label==='string'&&text.includes(label));
  }):[];
  const directIndex=directMatches.length===1?directMatches[0].i:-1;
  if(directIndex>=0){requested=choices[directIndex];log('action_normalization',{actor:'Storyteller',kind:'storyteller_info',from:response.message,to:requested,reason:'unique legal tuple extracted from Chinese role text'});return directIndex;}
  const roleIds=[...new Set(choices.flatMap(c=>typeof c.role==='string'?[c.role]:[]).filter(role=>text.includes(role)||text.includes(getScript().roles.find(r=>r.id===role)?.name?.zh||'')))];
  const countMatch=text.match(/(?:邪恶|恶魔|evil|count|数量|为)\D{0,8}([0-2])/i);
  if(pairRequired&&seats.length===2&&roleIds.length===1){requested={p1:seats[0],p2:seats[1],role:roleIds[0]};log('action_normalization',{actor:'Storyteller',kind:'storyteller_info',from:response.message,to:requested,reason:'unique legal seats and role extracted'});}
  else if(!pairRequired&&countMatch){requested={count:Number(countMatch[1])};log('action_normalization',{actor:'Storyteller',kind:'storyteller_info',from:response.message,to:requested,reason:'unique numeric result extracted'});}
  else {requested={}; correction='上一次返回的 message 不是合法 JSON，且无法唯一提取合法字段；请只返回接口要求的 JSON。'; continue;}
 }
 if (fortune && response.players?.length === 0 && typeof requested.yes === 'boolean') {
  const index=choices.findIndex(choice=>choice.yes===requested.yes);
  if(index<0){correction='占卜师结果必须是 message 中的 JSON {"yes":true} 或 {"yes":false}，且 players 必须为空。';continue;}
  log('information_generation',{recipient,source:'storyteller-model',choice:choices[index],reason:'ST selected only the result for the already-recorded targets',modelReason:response.reasoning});
  return index;
 }
 if (!fortune && !pairRequired && response.players?.length === 0) { const fixedIndex=choices.findIndex(choice=>Object.keys(choice).every(k=>choice[k]===requested[k])); if(fixedIndex>=0){log('information_generation',{recipient,source:'storyteller-model',choice:choices[fixedIndex],reason:'ST selected result fields for fixed targets',modelReason:response.reasoning});return fixedIndex;} correction='该角色不需要返回 players；请只返回合法结果字段，message 必须是 JSON。'; continue; }
 if (Array.isArray(response.players) && response.players.length === 2) {
  requested = { p1: response.players[0], p2: response.players[1], ...requested };
 }
 const index=choices.findIndex(choice=>Object.keys(choice).every(k=>choice[k]===requested[k]));
 let normalizedIndex=index;
 if(normalizedIndex<0 && pairRequired && typeof requested.p1==='string' && typeof requested.p2==='string'){
  normalizedIndex=choices.findIndex(choice=>choice.p1!==undefined&&choice.p2!==undefined&&choice.p1!==choice.p2&&new Set([choice.p1,choice.p2]).size===2&&new Set([choice.p1,choice.p2]).size===new Set([requested.p1,requested.p2]).size&&[choice.p1,choice.p2].every(seat=>[requested.p1,requested.p2].includes(seat))&&Object.keys(choice).filter(k=>k!=='p1'&&k!=='p2').every(k=>choice[k]===requested[k]));
  if(normalizedIndex>=0){requested=choices[normalizedIndex];log('action_normalization',{actor:'Storyteller',kind:'storyteller_info',from:{players:response.players,message:response.message},to:requested,reason:'unordered legal seat pair canonicalized'});}
 }
 const noOutsiders=requested.noOutsiders===true;
 if((pairRequired&&!noOutsiders&&response.players?.length!==2)||(noOutsiders&&response.players?.length!==0)||(!pairRequired&&response.players?.length!==0)||normalizedIndex<0){correction=JSON.stringify({error:'非法信息，尚未发送给玩家',submitted:requested,requiredFields:noOutsiders?['noOutsiders']:keys.filter(k=>k!=='noOutsiders'),missingFields:keys.filter(k=>k!=='noOutsiders'&&requested[k]===undefined),constraints:'两个不同座位，不能包含接收者；role 使用对应类别英文 ID；清醒健康信息必须符合魔典及登记规则。无外来者声明仅在引擎允许时合法。',protocol});continue;}
 const resolvedReason = "模型提交的信息已通过引擎合法性校验；内容以 choice 为准。";
 log('information_generation',{recipient,source:'storyteller-model',choice:choices[normalizedIndex],reason:resolvedReason,modelReason:response.reasoning,reasonMismatch:false});
 return normalizedIndex;
 }
 throw Error('Invalid ST information tuple after three attempts');
});

let initialAssignment;
let mutationSnapshot = '';
setUpdateHook(s => {
  if (!s.runtime) return;
  for (const ps of s.runtime.playerStates) assert.equal(ps.alive, ps.death === null);
  const snapshot = JSON.stringify(s.runtime.playerStates.map(ps => ({ name: ps.player.userId, role: ps.role.id, shown: ps.effectiveRole.id, alive: ps.alive, death: ps.death, tags: [...ps.tags] })));
  if (snapshot !== mutationSnapshot) { log('state', { night: s.runtime.nightNumber, day: s.runtime.daySession?.dayNumber, players: JSON.parse(snapshot) }); mutationSnapshot = snapshot; }
});
const contentOf = x => typeof x === 'string' ? x : x.content || '';
async function publicMessage(value) {
  const message = contentOf(value);
  // Discord's command menu is not an action interface for isolated AI players.
  if(message.includes('自由讨论开始。可用指令：') || message.includes('Free discussion is open. Commands available:'))return {};
  log('public', { message });
  const speaker=message.match(/^(P\d{2}):/);
  const type=speaker?'chat':/无人死亡|no deaths|nobody died/i.test(message)?'phase':/死亡|dies|died/.test(message)?'death':/第\s*\d+\s*[天夜]|Dawn|night .*begin/i.test(message)?'phase':'announcement';
  const e=semanticStore.observe({visibility:'public',type,text:message,actor:speaker?.[1],day:state.runtime?.daySession?.dayNumber||0,night:state.runtime?.nightNumber||0});log('semantic_event',e);
  broadcastTo(aiPlayers, message);
  st.chatHistory.push({ role: 'user', parts: [{ text: message }] });
  for(const p of [...aiPlayers,st])p.chatHistory.splice(0,Math.max(0,p.chatHistory.length-15));
  return {};
}
async function privateMessage(id, value) {
  const message = contentOf(value);
  log('private', { recipient: id, message });
  const from=message.match(/^Private from (P\d{2}):/);
  const e=semanticStore.observe({visibility:'private',audience:from?[id,from[1]]:[id],type:from?'whisper':'private_info',text:message,actor:from?.[1],day:state.runtime?.daySession?.dayNumber||0,night:state.runtime?.nightNumber||0});log('semantic_event',e);
  const recipient = aiPlayers.find(p => p.name === id);
  if (!recipient) throw new Error('Unknown private-message recipient');
  broadcastTo([recipient], message);
  recipient.chatHistory.splice(0,Math.max(0,recipient.chatHistory.length-15));
  return {};
}
const channel = { send: publicMessage, isDMBased: () => false };
const client = { channels: { fetch: async () => channel }, users: { fetch: async id => ({ send: value => privateMessage(id, value) }) } };
function interaction(id, target, commandName) {
  return { user: { id }, guildId: state.guildId, channelId: state.channelId, channel, commandName,
    options: { getString: () => target },
    reply: async value => value?.ephemeral ? privateMessage(id, value) : publicMessage(value) };
}
function publicStatus() {
  return state.runtime.playerStates.map(ps => ({ name: ps.player.userId, alive: ps.alive, ghostVoteUsed: ps.death?.ghostVoteUsed || false }));
}
async function ask(id, task, actions, validate = () => true) {
  const player = aiPlayers.find(p => p.name === id);
  let correction = '';
  for (let retry = 0; retry < 3; retry++) {
    // The bridge talks to the provider's compact request boundary directly;
    // no clocktower-ai Player/CSV adapter is needed for isolated decisions.
    const response = await provider.generate(system, player.chatHistory, JSON.stringify({ ...task, actor: id, publicStatus: publicStatus(), ...(correction ? { correction } : {}) }), actions);
    if(task.kind==='night'&&response.action==='choose'&&(!Array.isArray(response.players)||response.players.length===0)&&typeof response.message==='string'){
      const found=[...new Set((task.candidates||[]).filter(p=>new RegExp(`(?:^|[^A-Za-z0-9])${p}(?:$|[^A-Za-z0-9])`).test(response.message)))];
      if(found.length===1){response.players=found;log('action_normalization',{actor:id,kind:task.kind,field:'players',from:response.message,to:found,reason:'unique legal target in message'});}
    }
    log('player_decision', { actor: id, kind: task.kind, response });
    const premature=require('./action-validation.cjs').prematureVictory(response.message,state.phase==='ended');
    if (validate(response) && !premature) return response;
    const targetText = Array.isArray(response.players) ? response.players.join(', ') : '(none)';
    const legalText = Array.isArray(task.candidates) ? task.candidates.join(', ') : '(see current request constraints)';
    const illegalTargets = Array.isArray(task.candidates) && Array.isArray(response.players)
      ? response.players.filter(p => !task.candidates.includes(p)) : [];
    const targetReason = illegalTargets.length
      ? ` These targets are not legal in the current phase: ${illegalTargets.join(', ')}.` : '';
    const prematureText = premature ? ' The response also made an unsupported game-over claim.' : '';
    correction = `Your previous response was rejected as illegal. You returned action=${response.action || '(missing)'}, players=[${targetText}]. ` +
      `Reason: the selected action or target does not satisfy the current engine rules or candidate list.${targetReason}${prematureText} ` +
      `For this request, legal actions are ${actions.join(', ')}; legal target candidates are ${legalText}. ` +
      `Choose again using only the current request and return the required JSON fields.`;
    log('action_rejection', { actor: id, kind: task.kind, response, correction });
  }
  throw new Error(`Invalid target/action after three attempts for ${id}; refusing to substitute a fake LLM choice`);
}
const flush = () => new Promise(resolve => setTimeout(resolve, 10));
async function playNight() {
  const session = state.runtime.nightSession;
  const night = session.nightNumber;
  if (session.status === 'awaiting_players') {
    const pending=[...session.pendingPlayerIds];
    if(pending.length===0){ await resolveEmptyNight(client,state); return; }
    log('night_action_batch',{night,actors:pending,stage:'request'});
    const decisions=await Promise.all(pending.map(async id => {
      const spec = session.prompts.get(id);
      const candidates = players.filter(p => spec.inputs.every(i => i.allowSelf) || p.userId !== id).map(p => p.userId);
      const count = spec.inputs.filter(i => !i.optional).length;
      const response = await ask(id, { kind: 'night', night, count, candidates, prompt: session.actionMessages.get(id) }, ['choose'], r => Array.isArray(r.players) && r.players.length >= count && r.players.length <= spec.inputs.length && new Set(r.players).size === r.players.length && r.players.every(p => candidates.includes(p)));
      return {id,response};
    }));
    // No engine mutation or information delivery until every independent
    // player has answered. Only the engine resolves effects, in night order.
    if(state.runtime.nightSession!==session)throw Error('Night changed during action batch');
    log('night_action_batch',{night,actors:pending,stage:'commit'});
    for (const {id,response} of decisions) {
      await handleNightPlayerDM({ author: { id }, content: response.players.join(', '), reply: text => privateMessage(id, text) }, client, state);
    }
  } else if (session.status === 'awaiting_death_narrative') {
    for (const id of [...session.deathNarrativePendingIds]) {
      const ravenkeeper = session.deathNarrativePlayers.get(id) === 'ravenkeeper';
      const candidates = players.map(p => p.userId);
      const response = await ask(id, { kind: 'death', night, ravenkeeper, candidates, instruction: ravenkeeper ? 'Choose one player to learn their character and give a short death description.' : 'Acknowledge your death with a short description.' }, ['acknowledge'], r => !ravenkeeper || r.players?.length === 1 && candidates.includes(r.players[0]));
      const content = (ravenkeeper ? response.players[0] + ', ' : '') + (response.message || 'I acknowledge my death.');
      await handleNightPlayerDM({ author: { id }, content, reply: text => privateMessage(id, text) }, client, state);
    }
  }
  await flush();
  if (session.status === 'completed') log('night_complete', { night, responses: session.responses, info: session.infoMessages, drafts: session.infoOutcomeDrafts, deaths: session.deathNarrativePlayers });
}
async function discussionRound(day, round) {
  for (const player of aiPlayers) {
    if (state.phase === 'ended' || state.runtime.daySession.status !== 'open') break;
    const alive = state.runtime.playerStates.find(p => p.player.userId === player.name).alive;
    const candidates = players.map(p => p.userId);
    const actions = alive ? ['announcement', 'idle', 'slay', 'whisper', 'nominate'] : ['announcement', 'idle', 'whisper'];
    const response = await ask(player.name, { kind: 'discussion', day, round, candidates, instruction: 'Share a concise public claim or deduction, idle, whisper to exactly one other player, or slay one player. Use message for speech and players for targets.' }, actions, r => !['slay', 'whisper'].includes(r.action) || r.players?.length === 1 && candidates.includes(r.players[0]) && (r.action !== 'whisper' || r.players[0] !== player.name));
    if (response.action === 'announcement' && response.message) await publicMessage(`${player.name}: ${response.message}`);
    if (response.action === 'slay') { log('semantic_event',semanticStore.observe({visibility:'public',type:'ability',actor:player.name,day,text:`D${day}: ${player.name} publicly used Slayer on ${response.players[0]}`})); await publicMessage(`${player.name}: ${response.message || 'I claim Slayer.'}`); await handleRoleCommand(interaction(player.name, response.players[0], 'slay'), client); }
    if (response.action === 'whisper') {
      const peer = response.players[0];
      const intent='private_conversation';
      log('communication_plan',{player:player.name,day,action:'whisper',target:peer,reason:'player chose to open private conversation',information_disclosed:response.message||''});
      log('semantic_event',semanticStore.observe({visibility:'public',type:'whisper_contact',actor:player.name,peer,topic:intent,day,text:`${player.name} privately spoke with ${peer}`}));
      await publicMessage(`${player.name} has a private conversation with ${peer}.`);
      await privateMessage(peer, `Private from ${player.name}: ${response.message || ''}`);
      const answer = await ask(peer, { kind: 'whisper_reply', day, instruction: `Privately reply to ${player.name}; use message.` }, ['reply', 'idle']);
      if (answer.message) await privateMessage(player.name, `Private from ${peer}: ${answer.message}`);
      log('semantic_event',semanticStore.observe({visibility:'public',type:'trust_update',actor:player.name,target:peer,score:intent==='trust_building'?0.1:0,reason:`whisper intent ${intent}`,day,text:`${player.name} updated trust context for ${peer}`}));
    }
    if (response.action === 'nominate') {
      const daySession = state.runtime.daySession;
      const candidates = players.filter(p => !daySession.nomineeIds.has(p.userId)).map(p => p.userId);
      if (!response.players?.length || !candidates.includes(response.players[0])) continue;
      if (response.message) await publicMessage(`${player.name}: ${response.message}`);
      await handleNominate(interaction(player.name, response.players[0], 'nominate'), client, state);
      if (daySession.nominatorIds.has(player.name) && daySession.activeNomination) {
        await resolveNomination(daySession.activeNomination, day, client);
      }
      if (state.phase === 'ended' || daySession.status !== 'open') break;
    }
  }
}
async function resolveNomination(nomination, day, client) {
  const daySession = state.runtime.daySession;
  const defense = await ask(nomination.nomineeId, { kind: 'defense', day, instruction: 'Give your public defense before the vote.' }, ['announcement', 'idle']);
  if (defense.message) await publicMessage(`${nomination.nomineeId}: ${defense.message}`);
  const index = players.findIndex(p => p.userId === nomination.nomineeId);
  const votingOrder = [...players.slice(index + 1), ...players.slice(0, index + 1)];
  for (const voter of votingOrder) {
    const rt = state.runtime.playerStates.find(p => p.player.userId === voter.userId);
    if (!rt.alive && rt.death.ghostVoteUsed) continue;
    const vote = await ask(voter.userId, { kind: 'vote', day, nominee: nomination.nomineeId, votesSoFar: [...nomination.votes], instruction: 'Choose vote_yes or vote_no. Dead yes uses your only ghost vote; a living sober Butler may only vote if their master has voted; follow your private ability instructions.' }, ['vote_yes', 'vote_no']);
    if (vote.action === 'vote_yes') await handleYe(interaction(voter.userId, null, 'ye'), client);
    const accepted=nomination.votes.has(voter.userId);
    log('semantic_event',semanticStore.observe({visibility:'public',type:'vote',actor:voter.userId,target:nomination.nomineeId,accepted,day,text:`D${day}: ${voter.userId} voted ${accepted?'YES':'NO'} on ${nomination.nomineeId}`}));
    await publicMessage(`${voter.userId} votes ${accepted?'YES':'NO'} on ${nomination.nomineeId}.`);
  }
  await closeNominationWindow(client, state.channelId);
  log('nomination_complete', { day, nomination });
}
async function playDay() {
  const daySession = state.runtime.daySession;
  const day = daySession.dayNumber;
  console.log(`Day ${day}: ${publicStatus().filter(p => p.alive).length} alive (${provider.kind})`);
  await publicMessage(`自由讨论开始。当前 ${publicStatus().filter(p=>p.alive).length} 人存活，处决至少需要 ${Math.ceil(publicStatus().filter(p=>p.alive).length/2)} 票；同票最高不处决。死者可发言。请使用本次请求允许的动作。`);
  await discussionRound(day, 1);
  if (state.phase === 'ended' || daySession.status !== 'open') return;
  const pacing = await provider.generate(stSystem, st.chatHistory, JSON.stringify({ kind: 'pacing', day, publicStatus: publicStatus() }), ['open_nominations', 'continue_discussion']);
  log('storyteller_decision', { day, response: pacing });
  if (pacing.action === 'continue_discussion') await discussionRound(day, 2);
  await publicMessage('Nominations are now open. Every living player gets one opportunity in seating order.');
  for (const ps of state.runtime.playerStates) {
    if (state.phase === 'ended' || daySession.status !== 'open') break;
    if (!ps.alive || daySession.nominatorIds.has(ps.player.userId)) continue;
    const candidates = players.filter(p => !daySession.nomineeIds.has(p.userId)).map(p => p.userId);
    const response = await ask(ps.player.userId, { kind: 'nomination', day, candidates, previous: daySession.nominations.map(n => ({ nominee: n.nomineeId, votes: n.finalVoteCount, status: n.status })), instruction: 'Nominate one listed player, or idle. Use message for your public accusation.' }, ['nominate', 'idle'], r => r.action === 'idle' || r.players?.length === 1 && candidates.includes(r.players[0]));
    if (response.action === 'idle') continue;
    if (response.message) await publicMessage(`${ps.player.userId}: ${response.message}`);
    await handleNominate(interaction(ps.player.userId, response.players[0], 'nominate'), client);
    if(daySession.nominatorIds.has(ps.player.userId))log('semantic_event',semanticStore.observe({visibility:'public',type:'nomination',actor:ps.player.userId,target:response.players[0],day,text:`D${day}: ${ps.player.userId} nominated ${response.players[0]}`}));
    cancelNominationTimer(state.channelId); // Close after all agents decide, not wall-clock time.
    const nomination = daySession.activeNomination;
    if (!nomination) continue; // Virgin may have ended the day.
    await resolveNomination(nomination, day, client);
  }
  if (state.phase !== 'ended' && daySession.status === 'open') {
    log('storyteller_schedule', { day, decision: 'End day after all living players had a nomination opportunity' });
    await processEndOfDay(client, state, channel);
  }
  log('day_complete', { day, nominations: daySession.nominations });
  semanticStore.compact(day);
  await flush();
}
async function main() {
  log('run_config', { protocol:runtimeConfig.protocolVersion, mode: fixture ? 'SCRIPTED_FIXTURE_NOT_AI' : 'LLM', seed, players: playerCount, provider: provider.kind, model: provider.model, storytellerModel:provider.storytellerModel, runtimeConfig, playerProfiles, executionThreshold: 'standard-half', storyteller: 'discord-botc Automated Mode plus isolated LLM decisions', source: { discordBotc: '55afc19b063995176696a587ed939019d3773e36', clocktowerAi: '91cc58819f0d949ef505e166ec7ed3f5602db05a' } });
  if (!fixture) await provider.prepareGame({ players: playerCount });
  // Fail before pretending to start an AI game when no endpoint/model is configured.
  if (!fixture && provider.kind !== 'gemini' && !provider.model) throw new Error('OPENAI_MODEL is missing; no configured model endpoint was found');
  if (!fixture) await provider.generate(stSystem,st.chatHistory,'{"kind":"preflight","instruction":"请确认你是独立说书人上下文，只返回 action idle。"}',['idle']);
  updateGuildSettings(state.guildId, { onlineMode: true, defaultLang:'zh' });
  createGame(state);
  await handleYouare(interaction('P01', null, 'youare'), client);
  initialAssignment = players.map(p => ({ player: p.userId, role: state.draft.assignments.get(p.userId).id, shown: state.runtime.playerStates.find(ps => ps.player.userId === p.userId).effectiveRole.id }));
  log('assignment', { players: initialAssignment, redHerring: state.draft.redHerring, bluffs: state.draft.impBluffs?.map(r => r.id) });
  await flush();
  let stalls = 0;
  while (state.phase !== 'ended') {
    if (state.runtime.nightNumber > Number(process.env.BOTC_MAX_DAYS || 20)) throw new Error('Maximum days reached; game is incomplete');
    const night = state.runtime.nightSession;
    if (night && ['awaiting_players', 'awaiting_death_narrative'].includes(night.status)) { await playNight(); stalls = 0; }
    else if (state.runtime.daySession?.status === 'open') { await playDay(); stalls = 0; }
    else { await flush(); if (++stalls > 1000) throw new Error('Engine stalled with no actionable phase'); }
  }
  const verdict = evaluateWinCondition(state, { trigger: 'day_end_no_execution' });
  const result = { completed: true, mode: fixture ? 'SCRIPTED_FIXTURE_NOT_AI' : provider.liveCalls === 0 ? 'LLM_DECISION_REPLAY' : 'LLM', seed, verdict, night: state.runtime.nightNumber, initialAssignment, finalPlayers: state.runtime.playerStates, modelCalls: provider.calls, liveModelCalls:provider.liveCalls, sessions:provider.sessions };
  fs.writeFileSync(path.join(runDir, 'result.json'), JSON.stringify(result, (_, v) => v instanceof Set ? [...v] : v, 2));
  writeRunTag('COMPLETED',{verdict:verdict?.team||null});
  log('result', result);
  console.log(`Completed ${result.mode}: ${verdict?.team}, night ${state.runtime.nightNumber}, ${provider.calls} decisions (${provider.liveCalls ?? 0} live subscription calls)\n${runDir}`);
}
main().catch(error => {
  const result = { completed: false, mode: fixture ? 'SCRIPTED_FIXTURE_NOT_AI' : 'LLM', error: error.message, night: state.runtime?.nightNumber || 0, modelCalls: provider.calls };
  fs.writeFileSync(path.join(runDir, 'result.json'), JSON.stringify(result, null, 2)); writeRunTag('INTERRUPTED',{reason:error.message,modelCalls:provider.calls}); log('failure', result); console.error(error.message); console.error(runDir); process.exitCode = 1;
}).finally(() => { cancelNominationTimer(state.channelId); provider.close?.(); });
