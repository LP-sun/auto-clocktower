const names=require('./role-names.zh.json');
const strategies=require('./role-strategy.zh.json');
const abilities={washerwoman:'首夜得知两人中一人的镇民角色。',librarian:'首夜得知两人中一人的外来者角色，或没有外来者。',investigator:'首夜得知两人中一人的爪牙角色。',chef:'首夜得知相邻邪恶玩家对数。',empath:'每夜得知存活邻居中邪恶人数。',fortune_teller:'每夜选两人，得知是否包含恶魔；有一善良玩家误报为恶魔。',undertaker:'每夜除首夜，得知当天被处决而死的角色。',monk:'每夜除首夜，选其他玩家免受恶魔能力影响直到黎明。',ravenkeeper:'夜间死亡时选一人得知其角色。',virgin:'首次被提名，若提名者登记为镇民，提名者立即被处决。',slayer:'每局一次白天公开选一人，若其登记为恶魔则死亡；中毒使用仍消耗。',soldier:'免受恶魔能力影响。',mayor:'三人存活且白天无人被处决则善良胜；夜间将死时可有他人代死。',butler:'每夜选其他玩家为主人；白天只有主人举手时才能举手。',drunk:'以为自己是镇民，但没有该能力。',recluse:'可能登记为邪恶、爪牙或恶魔，即使已死亡。',saint:'若被处决且死亡，邪恶获胜。',poisoner:'每夜选一人中毒至下一夜；自身死亡或失去能力则效果结束。',spy:'每夜看魔典；可登记为善良、镇民或外来者，即使已死亡。',scarlet_woman:'至少五人存活时恶魔死亡，你成为恶魔。',baron:'配置外来者+2，镇民-2。',imp:'每夜除首夜选一人死亡；自杀可由存活爪牙接任。'};
const stable='你只扮演一个钟楼玩家。结构化 state 的生死、票数、game_over 是权威；聊天不是机械事实。收到其他玩家的能力信息时，若直接与自己的真实角色或能力吻合，先承认相容并提供可验证细节，不要求对方重复解释规则；只有真正矛盾或规则不可能时才追问。game_over=false 时不得宣告已经终局。claim 只是自称，belief 是推断；私人信息也可能因规则而错误。绝不推测自己拥有未收到的隐藏信息。只选合法行动，输出 JSON 和简短决策依据，不输出详细思维过程。中文名用集石译名。死者可发言且仅有一张亡灵票；同票最高不处决。按 state.executionThreshold 决定门槛。策略权衡信息收益、暴露成本、生存价值和团队协调；不固定强迫首日行动。';
function getCharacterStrategy(role){return {role,name:names[role],rules:abilities[role],strategy:{core:['根据当前证据和行动收益权衡，而非固定首日行动。'],...strategies[role]},informationDecisionSequence:['先判断信息是否需要立即公开，以及公开会让谁获得什么收益。','若不必立即公开，优先选择一名或多名相关玩家进行私聊核验，交换身份主张、能力结果和可验证事实。','根据私聊回应判断信息是否相容、是否出现真正矛盾，再决定部分公开、全桌公开、继续保密或托管给可信玩家。','公开时明确区分已知事实、二选一范围和个人推断，不把策略建议或他人自称说成规则事实。'],pitfalls:'自己的信息可能受规则干扰；他人宣称不是确认身份。',claimingGuidance:'权衡公开信息价值与暴露能力带来的风险。'};}
function estimateTokens(text){let nonAscii=0;for(const c of text)if(c.charCodeAt(0)>127)nonAscii++;return Math.ceil((text.length-nonAscii)/4+nonAscii);}
function buildContext({actor,task,actions,view,memory,store}){
 const light=['vote','nomination'].includes(task.kind),st=actor==='Storyteller';
 const system=st?'你是受约束的说书人。根据权威魔典和角色规则生成接口字段，由引擎校验；若提供枚举选项则仅从中选择；不能改生死、角色、胜负。不得读取玩家内心推理。不要绝对帮助某阵营，保护玩家决定胜负的空间。白天讨论若已重复、信息饱和或出现明确提名机会，可选择 open_nominations 立即打断讨论并进入提名阶段。只返回 JSON 与简短理由。':stable+' 公聊发言必须增加新事实、指出具体矛盾、回应具体玩家或提出可验证的投票建议；若最近发言没有新增内容，选择 idle，不要重复泛化句式。任何存活玩家在公聊中发现明确目标时可直接选择 nominate。收到能力信息后按顺序判断：先评估是否必须公开，再评估暴露风险；若不必立即公开，优先与相关玩家私聊核验；根据回应再决定保密、托管、部分公开或全桌公开。公开时区分事实、候选范围和推断。私聊不需要额外意图字段，只要目标合法且消息具体。';
 const script=st?undefined:Object.entries(abilities).map(([id,text])=>`${names[id]}:${text}`).join('\n');
 const scriptIndex=st?undefined:Object.keys(abilities).map(id=>({id,name:names[id],category:['washerwoman','librarian','investigator','chef','empath','fortune_teller','undertaker','monk','ravenkeeper','virgin','slayer','soldier','mayor'].includes(id)?'镇民':['butler','drunk','recluse','saint'].includes(id)?'外来者':['poisoner','spy','scarlet_woman','baron'].includes(id)?'爪牙':'恶魔'}));
 const control={kind:task.kind,actions};
 control.responseProtocol={instruction:'只返回一个完整 JSON 对象；禁止附加文字、第二个对象或 Markdown。字段名严格使用 action,message,players,reasoning；不要用 target 或 reason。message 是发给其他人的话；reasoning 仅为私有简短摘要。',example:{action:actions[0],message:'',players:[],reasoning:'简短行动依据。'}};
 if(task.kind==='night')control.responseProtocol.example={action:'choose',message:'',players:(task.candidates||[]).slice(0,task.count||1),reasoning:'选择合法目标。'};
 if(!st)control.basicRules='暗流涌动首夜小恶魔和僧侣均不行动；首夜平安不能证明保护成功。slay 是白天公开自称猎手开枪，绝不是恶魔夜杀；非猎手可虚张声势，但没有杀人能力。slay/announcement 的 message 会公开，绝不把邪恶计划写进去。已用完首夜信息的角色未必是优先击杀目标，应权衡持续能力。5或6人局无初始恶魔/爪牙互认、无恶魔伪装角色；间谍仍正常看魔典。';
 if(st)control.pacingRule='只决定讨论继续或进入提名，不点名要求回应，不强迫自曝，不以玩家必须回应作为进入提名条件。';
 if(actions.includes('lookup'))control.retrieval='Optional action lookup. For public/private history use a seat ID. To read a public script role rule, use the role ID instead, e.g. {"action":"lookup","message":"lookup_role_rules","players":["butler"]}. message MUST be exactly one of lookup_claim_history, lookup_vote_history, lookup_public_chat, lookup_private_chat, lookup_ability_history, lookup_role_rules; do not write natural-language text. Use exactly one legal seat or role ID. Role-rule lookup returns only public script rules, never assignments or hidden state; at most two lookups per decision.';
 if(task.retrievedFacts)control.retrievedFacts=task.retrievedFacts;
 for(const k of ['day','night','round','nominee','count','ravenkeeper','correction','field','choices','template','recipient'])if(task[k]!==undefined)control[k]=task[k];
 if(task.kind==='night')control.prompt=task.prompt;
 if(task.kind==='whisper_reply')control.instruction=task.instruction;
 if(task.kind==='discussion')control.whisperRule='选择 whisper 时提供一名合法目标和具体私聊内容。';
 if(task.kind==='storyteller_info'){
  control.legalDecision=task.legalDecision||{field:task.field,choices:task.choices};
  control.requestingRole=task.requestingRole;
  control.protocol=task.protocol;
  control.workflow='读取 state 魔典和 requestingRole；提交 choose_info 动作；若 correction 报错，依据错误修正。message 是序列化的 JSON 字符串，不能是给玩家的口头消息。引擎负责校验与发送。只给简短决策依据。';
  control.strategy='二选一信息避免包含接收者自己；调查员的另一候选通常选善良玩家，避免直接圈出恶魔和爪牙。这是策略指导，合法性以引擎校验为准。';
 }
 const all=view?.alive?.concat((view.dead||[]).map(p=>p.seat))||[];
 if(task.candidates){control.targetDomain=task.candidates.length===all.length&&task.candidates.every(x=>all.includes(x))?'all seats':task.candidates;}
 const m=memory;
 const semantic={privateFacts:m.privateFacts,claims:Object.fromEntries(Object.entries(m.publicClaims).map(([seat,c])=>[seat,{role:c.role,kind:'claim',confirmed:false,source:c.source,day:c.day}])),privateClaims:m.privateClaims,sharedInformation:m.sharedInformation,whisperHistory:m.whisperHistory.slice(-8),trust:m.trust,beliefs:m.beliefs,contradictions:m.contradictions,plan:m.plan,worlds:m.worlds,ownCommitments:m.bluff.public_commitments.slice(-3),bluff:m.identity.alignment==='evil'?m.bluff:undefined,daySummaries:m.summaries.map(s=>({day:s.day,deaths:s.deaths,nominations:s.nominations}))};
 const recent={public:m.recent.slice(light?-4:-12),private:m.privateConversations.slice(light?-3:-5)};
 const sections={script:st?undefined:undefined,scriptIndex,character:st?undefined:getCharacterStrategy(view.self.role),roleStrategyNotice:st?undefined:'以下 Role-Specific Strategic Guidance 是策略启发，不是规则或强制动作；根据当前局面自行判断。当前上下文只展开你的角色规则；其他角色先通过 scriptIndex 判断类别，不能据此推断本局存在或玩家身份。',state:view,memory:semantic,recent,control};
 // Keep all protected private facts, while allowing the normal semantic context
 // to grow across a long game.  The previous 8k player ceiling could abort a
 // healthy game late at night even though the transport/model still had room.
 // Light vote/nomination turns remain compact; night/discussion turns get 12k.
 const budget=Number(process.env.BOTC_CONTEXT_BUDGET || (st?14000:light?4000:12000));
 let input=JSON.stringify(sections),estimated=estimateTokens(system+input);
 while(estimated>budget&&(recent.public.length||recent.private.length)){
  if(recent.public.length)recent.public.shift();else recent.private.shift();input=JSON.stringify(sections);estimated=estimateTokens(system+input);
 }
 if(estimated>budget)throw Error(`Protected memory exceeds context budget for ${actor}; no private facts silently removed`);
 return {system,input,sections,metrics:{actor,kind:task.kind,day:task.day||view.day||0,contextChars:system.length+input.length,estimatedInputTokens:estimated,estimateMethod:'ASCII/4 + non-ASCII characters; excludes native harness',semanticMemoryChars:JSON.stringify(semantic).length,ephemeralContextChars:JSON.stringify(control).length,historyLength:store.events.length,sections:Object.fromEntries(Object.entries(sections).filter(([,v])=>v!==undefined).map(([k,v])=>[k,estimateTokens(JSON.stringify(v))]))}};
}
module.exports={buildContext,estimateTokens,getCharacterStrategy};
