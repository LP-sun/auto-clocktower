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
function log(type, data) {
  if(type==='semantic_event')data={event:data};
  fs.appendFileSync(path.join(runDir, 'events.jsonl'), JSON.stringify({ seq: ++serial, time: new Date().toISOString(), type, ...data }, (_, v) => v instanceof Map ? Object.fromEntries(v) : v instanceof Set ? [...v] : typeof v === 'function' ? undefined : v) + '\n');
}
const { makeProvider } = require('./provider.cjs');
const useCodex = !fixture && (process.env.BOTC_PROVIDER || 'codex') === 'codex';
const {SemanticStore}=require('./semantic-memory.cjs');
const {ViewProjector}=require('./player-view.cjs');
const semanticStore=new SemanticStore(), projector=new ViewProjector();
const fixtureProvider=fixture?makeProvider({log:(type,data)=>log('fixture_'+type,data),runDir,fixture:true}):null;
const provider=require('./semantic-provider.cjs').makeSemanticProvider({store:semanticStore,projector,getState:()=>state,log,runDir,fixtureProvider});
const db = p => require(path.join(root, 'discord-botc/dist', p));
const ca = p => require(path.join(root, 'clocktower-ai/dist', p));
const { createGame, setUpdateHook } = db('game/state');
const { handleYouare } = db('handlers/youare');
const { handleNightPlayerDM, setAutomatedInfoReview, applyInfoDraftFieldForUI } = db('game/night');
const { handleNominate, handleYe, closeNominationWindow, cancelNominationTimer } = db('game/nominations');
const { processEndOfDay } = db('game/dayFlow');
const { handleRoleCommand } = db('game/roleCommands');
const { updateGuildSettings } = db('guildSettings');
const { getScript } = db('game/roles');
const { evaluateWinCondition } = db('game/winConditions');
const { executionThreshold } = db('game/voteThreshold');
const { broadcastMessage, sendMessageToPlayer } = ca('clocktower/players');
ca('services/vertex-ai').setResponseProvider(provider.generate);
let randomState = seed >>> 0;
Math.random = () => { randomState = (Math.imul(1664525, randomState) + 1013904223) >>> 0; return randomState / 4294967296; };
const playerCount = Math.max(5, Number(process.env.BOTC_PLAYERS || 12));
const players = Array.from({ length: playerCount }, (_, index) => ({ userId: `P${String(index + 1).padStart(2, '0')}`, username: `P${String(index + 1).padStart(2, '0')}`, displayName: `P${String(index + 1).padStart(2, '0')}`, seatIndex: index }));
const aiPlayers = players.map(p => ({ name: p.displayName, actualRole: '', ephemeralControl:true, chatHistory: [], actionHistory: [], status: 'alive' }));
const state = { gameId: `bridge-${playerCount}`, gameNumber: 1, guildId: 'local', channelId: 'local-game', players, storytellerId: null, mode: 'pending', phase: 'pending_storyteller', draft: null, runtime: null };
const system = fs.readFileSync(path.join(root, 'clocktower-ai/data/prompts/introduction.txt'), 'utf8') + '\n暗流涌动（Trouble Brewing）：角色中文名严格采用集石钟楼百科，禁止另译。角色规则与当前角色策略只从本次决策上下文读取；不要自行补充或改写角色说明。执行门槛由权威 state.executionThreshold 决定，严格过半：票数必须大于存活人数的一半（12 名存活玩家需要 7 票）。提名本身不等于投票。死者可以发言，并保留一张亡灵票。善良阵营在没有存活恶魔时获胜。只相信收到的私信和公开观察，不要声称拥有未收到的隐藏信息。座位为 P01 至 P12。只执行当前允许的动作。中文公聊每条不超过 150 字。可以为自己的阵营进行合理伪装与协作，避免在已有足够票数后重复发起相同提名。';
const st = { name: 'Storyteller', actualRole: '', ephemeralControl:true, chatHistory: [], actionHistory: [], status: 'alive' };
if(provider.register) { for(const p of [...aiPlayers,st]) provider.register(p.chatHistory,p.name); }
const stSystem = 'You are the AI Storyteller facilitator for a 12-player Trouble Brewing game. The deterministic engine owns all rules, secret information delivery, deaths and victory. You choose whether to allow one extra public discussion round before nominations. Choose only continue_discussion or open_nominations. Never disclose hidden state. Give one brief decision summary. Use the execution threshold from authoritative state.';
const {StorytellerAgent,socialView}=require('./storyteller-agent/index.cjs');
const stView=current=>({...projector.storyteller(current),social:socialView(semanticStore)});
const storytellerAgent=new StorytellerAgent({log,model:fixture?undefined:async(view,decision)=>{
 const task={kind:'storyteller_info',night:state.runtime.nightNumber,recipient:decision.actor,template:decision.template,field:decision.field,choices:decision.legalOptions.map((value,index)=>({id:String(index),value})),legalDecision:decision,social:view.social};
 const response=await sendMessageToPlayer(stSystem,st,JSON.stringify(task),['choose_info']);
 const index=Number(response.players?.[0]);
 if(response.players?.length!==1||!Number.isInteger(index)||index<0||index>=decision.legalOptions.length)throw Error('Invalid legal choice ID');
 return {choice:decision.legalOptions[index],reason:response.reasoning};
}});
db('utils/roleDetection').setRegistrationPolicy(decision=>storytellerAgent.chooseSync(stView(state),{...decision,actor:decision.player}));
db('game/discretion').setDiscretionPolicy((current,decision)=>storytellerAgent.decide(stView(current),decision));
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
 const columns=[...new Set(choices.flatMap(c=>Object.keys(c)))];
 const response=await sendMessageToPlayer(stSystem,st,JSON.stringify({kind:'storyteller_info',recipient,night:ctx.night.nightNumber,legalDecision:{type:'generate_information',actor:recipient,ability:ctx.state.runtime.playerStates.find(p=>p.player.userId===recipient).effectiveRole.id,columns,choices:choices.map(value=>columns.map(k=>value[k])),instruction:'Choose one complete information row by its zero-based index using players:["index"]. Each row follows columns. Consider current grimoire and information utility. Avoid self-confirming pairs where alternatives exist; do not always select the first option. Return action choose_info, message empty, and a short reason.'}}),['choose_info']);
 const index=Number(response.players?.[0]);
 if(response.players?.length!==1||!Number.isInteger(index)||index<0||index>=choices.length)throw Error('Invalid ST information tuple');
 log('information_generation',{recipient,source:'storyteller-model',choice:choices[index],reason:response.reasoning});
 return index;
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
  log('public', { message });
  const speaker=message.match(/^(P\d{2}):/);
  const type=speaker?'chat':/死亡|dies|died/.test(message)?'death':/第 \d+ [天夜]|Dawn|night .*begin/i.test(message)?'phase':'announcement';
  const e=semanticStore.observe({visibility:'public',type,text:message,actor:speaker?.[1],day:state.runtime?.daySession?.dayNumber||0,night:state.runtime?.nightNumber||0});log('semantic_event',e);
  await broadcastMessage(aiPlayers, message);
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
  await broadcastMessage([recipient], message);
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
  for (let retry = 0; retry < 3; retry++) {
    const response = await sendMessageToPlayer(system, player, JSON.stringify({ ...task, actor: id, publicStatus: publicStatus(), ...(retry ? { correction: 'Your previous response was invalid. Follow candidates/count and authoritative game_over; do not declare victory while game_over is false.' } : {}) }), actions);
    if(task.kind==='night'&&response.action==='choose'&&(!Array.isArray(response.players)||response.players.length===0)&&typeof response.message==='string'){
      const found=[...new Set((task.candidates||[]).filter(p=>new RegExp(`(?:^|[^A-Za-z0-9])${p}(?:$|[^A-Za-z0-9])`).test(response.message)))];
      if(found.length===1){response.players=found;log('action_normalization',{actor:id,kind:task.kind,field:'players',from:response.message,to:found,reason:'unique legal target in message'});}
    }
    log('player_decision', { actor: id, kind: task.kind, response });
    const premature=require('./action-validation.cjs').prematureVictory(response.message,state.phase==='ended');
    if (validate(response) && !premature) return response;
  }
  throw new Error(`Invalid target/action after three attempts for ${id}; refusing to substitute a fake LLM choice`);
}
const flush = () => new Promise(resolve => setTimeout(resolve, 10));
async function playNight() {
  const session = state.runtime.nightSession;
  const night = session.nightNumber;
  if (session.status === 'awaiting_players') {
    for (const id of [...session.pendingPlayerIds]) {
      const spec = session.prompts.get(id);
      const candidates = players.filter(p => spec.inputs.every(i => i.allowSelf) || p.userId !== id).map(p => p.userId);
      const count = spec.inputs.filter(i => !i.optional).length;
      const response = await ask(id, { kind: 'night', night, count, candidates, prompt: session.actionMessages.get(id) }, ['choose'], r => Array.isArray(r.players) && r.players.length >= count && r.players.length <= spec.inputs.length && new Set(r.players).size === r.players.length && r.players.every(p => candidates.includes(p)));
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
      const ci=response.communicationIntent;
      const intent=ci?.intent||'unspecified';
      log('communication_plan',{player:player.name,day,action:'whisper',communication_intent:intent,target:peer,reason:ci?.reason||'player chose to open private conversation',information_disclosed:response.message||'',secrecy_level_before:ci?.secrecyLevel??null,secrecy_level_after:ci?.secrecyLevel??null});
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
  await publicMessage('Execution uses the authoritative threshold. Standard rule: at least half alive; twelve alive require six votes. Dead players may speak.');
  await discussionRound(day, 1);
  if (state.phase === 'ended' || daySession.status !== 'open') return;
  const pacing = await sendMessageToPlayer(stSystem, st, JSON.stringify({ kind: 'pacing', day, publicStatus: publicStatus() }), ['open_nominations', 'continue_discussion']);
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
  log('run_config', { protocol:'semantic-v2', mode: fixture ? 'SCRIPTED_FIXTURE_NOT_AI' : 'LLM', seed, players: playerCount, provider: provider.kind, model: provider.model, storytellerModel:provider.storytellerModel, executionThreshold: process.env.BOTC_EXECUTION_RULE || 'standard-half', storyteller: 'discord-botc Automated Mode plus isolated LLM decisions', source: { discordBotc: '55afc19b063995176696a587ed939019d3773e36', clocktowerAi: '91cc58819f0d949ef505e166ec7ed3f5602db05a' } });
  // Fail before pretending to start an AI game when no endpoint/model is configured.
  if (!fixture && provider.kind !== 'gemini' && !provider.model) throw new Error('OPENAI_MODEL is missing; no configured model endpoint was found');
  if (useCodex) await sendMessageToPlayer(stSystem,st,'{"kind":"preflight","instruction":"请确认你是独立说书人上下文，只返回 action idle。"}',['idle']);
  else if (!fixture) await provider.generate('Connectivity check. Respond with action idle and a brief reasoning summary.', [], '{"kind":"preflight"}', ['idle']);
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
  const result = { completed: true, mode: fixture ? 'SCRIPTED_FIXTURE_NOT_AI' : useCodex && provider.liveCalls === 0 ? 'LLM_DECISION_REPLAY' : 'LLM', seed, verdict, night: state.runtime.nightNumber, initialAssignment, finalPlayers: state.runtime.playerStates, modelCalls: provider.calls, liveModelCalls:provider.liveCalls, sessions:provider.sessions };
  fs.writeFileSync(path.join(runDir, 'result.json'), JSON.stringify(result, (_, v) => v instanceof Set ? [...v] : v, 2));
  writeRunTag('COMPLETED',{verdict:verdict?.team||null});
  log('result', result);
  console.log(`Completed ${result.mode}: ${verdict?.team}, night ${state.runtime.nightNumber}, ${provider.calls} decisions (${provider.liveCalls ?? 0} live subscription calls)\n${runDir}`);
}
main().catch(error => {
  const result = { completed: false, mode: fixture ? 'SCRIPTED_FIXTURE_NOT_AI' : 'LLM', error: error.message, night: state.runtime?.nightNumber || 0, modelCalls: provider.calls };
  fs.writeFileSync(path.join(runDir, 'result.json'), JSON.stringify(result, null, 2)); writeRunTag('INTERRUPTED',{reason:error.message,modelCalls:provider.calls}); log('failure', result); console.error(error.message); console.error(runDir); process.exitCode = 1;
}).finally(() => { cancelNominationTimer(state.channelId); provider.close?.(); });
