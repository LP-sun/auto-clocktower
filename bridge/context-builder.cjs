const names=require('./role-names.zh.json');
const strategies=require('./role-strategy.zh.json');
const abilities={washerwoman:'首夜得知两人中一人的镇民角色。',librarian:'首夜得知两人中一人的外来者角色，或没有外来者。',investigator:'首夜得知两人中一人的爪牙角色。',chef:'首夜得知相邻邪恶玩家对数。',empath:'每夜得知存活邻居中邪恶人数。',fortune_teller:'每夜选两人，得知是否包含恶魔；有一善良玩家误报为恶魔。',undertaker:'每夜除首夜，得知当天被处决而死的角色。',monk:'每夜除首夜，选其他玩家免受恶魔能力影响直到黎明。',ravenkeeper:'夜间死亡时选一人得知其角色。',virgin:'首次被提名，若提名者登记为镇民，提名者立即被处决。',slayer:'每局一次白天公开选一人，若其登记为恶魔则死亡；中毒使用仍消耗。',soldier:'免受恶魔能力影响。',mayor:'三人存活且白天无人被处决则善良胜；夜间将死时可有他人代死。',butler:'每夜选其他玩家为主人；白天只有主人举手时才能举手。',drunk:'以为自己是镇民，但没有该能力。',recluse:'可能登记为邪恶、爪牙或恶魔，即使已死亡。',saint:'若被处决且死亡，邪恶获胜。',poisoner:'每夜选一人中毒至下一夜；自身死亡或失去能力则效果结束。',spy:'每夜看魔典；可登记为善良、镇民或外来者，即使已死亡。',scarlet_woman:'至少五人存活时恶魔死亡，你成为恶魔。',baron:'配置外来者+2，镇民-2。',imp:'每夜除首夜选一人死亡；自杀可由存活爪牙接任。'};
const stable='你只扮演一个钟楼玩家。结构化 state 的生死、票数、game_over 是权威；聊天不是机械事实。game_over=false 时不得宣告已经终局。claim 只是自称，belief 是推断；私人信息也可能因规则而错误。绝不推测自己拥有未收到的隐藏信息。只选合法行动，输出 JSON 和简短决策依据，不输出详细思维过程。中文名用集石译名。死者可发言且仅有一张亡灵票；同票最高不处决。按 state.executionThreshold 决定门槛。策略权衡信息收益、生存价值、暴露成本、未来能力、团队协调、目标威胁、伪装一致性及私聊网络暴露；不固定强迫首日亮身份。';
function getCharacterStrategy(role){return {role,name:names[role],rules:abilities[role],strategy:{core:['根据当前证据和行动收益权衡，而非固定首日行动。'],...strategies[role]},pitfalls:'自己的信息可能受规则干扰；他人宣称不是确认身份。',claimingGuidance:'权衡公开信息价值与暴露能力带来的风险。'};}
function estimateTokens(text){let nonAscii=0;for(const c of text)if(c.charCodeAt(0)>127)nonAscii++;return Math.ceil((text.length-nonAscii)/4+nonAscii);}
function buildContext({actor,task,actions,view,memory,store}){
 const light=['vote','nomination'].includes(task.kind),st=actor==='Storyteller';
 const system=st?'你是受约束的说书人。仅选引擎列出的合法选项；不能改生死、角色、胜负。不得读取玩家内心推理。不要绝对帮助某阵营，保护玩家决定胜负的空间。白天讨论若已重复、信息饱和或出现明确提名机会，可选择 open_nominations 立即打断讨论并进入提名阶段。只返回 JSON 与简短理由。':stable+' 公聊发言必须增加新事实、指出具体矛盾、回应具体玩家或提出可验证的投票建议；若最近发言没有新增内容，选择 idle，不要重复泛化句式。任何存活玩家在公聊中发现明确目标时可直接选择 nominate。善良玩家不要默认公开全部身份和首夜信息；先判断是否保密、私聊、部分公开或全桌公开。强能力角色在没有明确收益时保留身份。whisper 必须有具体 communicationIntent，不能只为活跃而私聊。';
 const script=st?undefined:Object.entries(abilities).map(([id,text])=>`${names[id]}:${text}`).join('\n');
 const control={kind:task.kind,actions};
 if(actions.includes('lookup'))control.retrieval='Optional action lookup. REQUIRED JSON example: {"action":"lookup","message":"lookup_public_chat","players":["P03"]}. message MUST be exactly one of lookup_claim_history, lookup_vote_history, lookup_public_chat, lookup_private_chat, lookup_ability_history; do not write natural-language text. players MUST contain exactly one legal seat. Read-only visible events; at most two lookups per decision.';
 if(task.retrievedFacts)control.retrievedFacts=task.retrievedFacts;
 for(const k of ['day','night','round','nominee','count','ravenkeeper','correction','field','choices','template','recipient'])if(task[k]!==undefined)control[k]=task[k];
 if(task.kind==='night')control.prompt=task.prompt;
 if(task.kind==='whisper_reply')control.instruction=task.instruction;
 if(task.kind==='discussion')control.communicationSchema={intent:['role_exchange','info_verification','trust_building','info_escrow','deception_test','nomination_coordination','vote_coordination','claim_conflict_check','protection_request','other'],secrecyLevel:[0,1,2,3,4],whisperRule:'If action=whisper, include communicationIntent:{intent,secrecyLevel,reason}. If no concrete intent, choose idle or announcement.'};
 if(task.kind==='storyteller_info')control.legalDecision=task.legalDecision||{field:task.field,choices:task.choices};
 const all=view?.alive?.concat((view.dead||[]).map(p=>p.seat))||[];
 if(task.candidates){control.targetDomain=task.candidates.length===all.length&&task.candidates.every(x=>all.includes(x))?'all seats':task.candidates;}
 const m=memory;
 const semantic={privateFacts:m.privateFacts,claims:Object.fromEntries(Object.entries(m.publicClaims).map(([seat,c])=>[seat,{role:c.role,kind:'claim',confirmed:false,source:c.source,day:c.day}])),privateClaims:m.privateClaims,sharedInformation:m.sharedInformation,whisperHistory:m.whisperHistory.slice(-8),trust:m.trust,beliefs:m.beliefs,contradictions:m.contradictions,plan:m.plan,worlds:m.worlds,ownCommitments:m.bluff.public_commitments.slice(-3),bluff:m.identity.alignment==='evil'?m.bluff:undefined,daySummaries:m.summaries.map(s=>({day:s.day,deaths:s.deaths,nominations:s.nominations}))};
 const recent={public:m.recent.slice(light?-4:-12),private:m.privateConversations.slice(light?-3:-5)};
 const sections={script,character:st?undefined:getCharacterStrategy(view.self.role),roleStrategyNotice:st?undefined:'以下 Role-Specific Strategic Guidance 是策略启发，不是规则或强制动作；根据当前局面自行判断。',state:view,memory:semantic,recent,control};
 const budget=Number(process.env.BOTC_CONTEXT_BUDGET || (st?10000:light?4000:8000));
 let input=JSON.stringify(sections),estimated=estimateTokens(system+input);
 while(estimated>budget&&(recent.public.length||recent.private.length)){
  if(recent.public.length)recent.public.shift();else recent.private.shift();input=JSON.stringify(sections);estimated=estimateTokens(system+input);
 }
 if(estimated>budget)throw Error(`Protected memory exceeds context budget for ${actor}; no private facts silently removed`);
 return {system,input,sections,metrics:{actor,kind:task.kind,day:task.day||view.day||0,contextChars:system.length+input.length,estimatedInputTokens:estimated,estimateMethod:'ASCII/4 + non-ASCII characters; excludes native harness',semanticMemoryChars:JSON.stringify(semantic).length,ephemeralContextChars:JSON.stringify(control).length,historyLength:store.events.length,sections:Object.fromEntries(Object.entries(sections).filter(([,v])=>v!==undefined).map(([k,v])=>[k,estimateTokens(JSON.stringify(v))]))}};
}
module.exports={buildContext,estimateTokens,getCharacterStrategy};
