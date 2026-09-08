const names=require('./role-names.zh.json');
const {executionThreshold}=require('../discord-botc/dist/game/voteThreshold');
const clone=x=>JSON.parse(JSON.stringify(x));
class ViewProjector {
 constructor(){this.roster=[];this.deaths=[];}
 publicState(state){
  const r=state.runtime,d=r?.daySession;
  const phase=state.phase==='ended'?'ended':d?.status==='open'?'day':'night';
  // Night deaths are not public until dawn; never expose the ground-truth roster early.
  if(!this.roster.length || phase!=='night'){
   this.roster=(r?.playerStates||[]).map(p=>({seat:p.player.userId,alive:p.alive,ghost_vote_available:!!p.death&&!p.death.ghostVoteUsed}));
   this.deaths=(r?.playerStates||[]).filter(p=>p.death).map(p=>({seat:p.player.userId,phase:p.death.phase,day:p.death.dayNumber,night:p.death.nightNumber,byExecution:p.death.byExecution}));
  }
  const alive=this.roster.filter(p=>p.alive).map(p=>p.seat),dead=this.roster.filter(p=>!p.alive).map(p=>({seat:p.seat,ghost:p.ghost_vote_available}));
  const n=d?.activeNomination;
  return {game_over:state.phase==='ended',phase,day:d?.dayNumber||0,night:r?.nightNumber||0,alive,dead,deaths:clone(this.deaths),executionThreshold:alive.length?executionThreshold(alive.length):0,
   nominations:(d?.nominations||[]).map(n=>({nominator:n.nominatorId,nominee:n.nomineeId,votes:n.finalVoteCount,status:n.status})),
   nominatedBy:[...(d?.nominatorIds||[])],nominated:[...(d?.nomineeIds||[])],
   current_nomination:n?{nominator:n.nominatorId,nominee:n.nomineeId,votes:[...n.votes]}:null};
 }
 player(state,seat,memory){
  const publicState=this.publicState(state),p=state.runtime.playerStates.find(p=>p.player.userId===seat);
  if(!p)throw Error('Unknown player');
  const role=p.effectiveRole.id;
  const own={seat,role,roleName:names[role],alignment:['Minion','Demon'].includes(p.effectiveRole.category)?'evil':'good',alive:p.alive,ghost_vote_available:!!p.death&&!p.death.ghostVoteUsed};
  // These are perceived choices and uses, not hidden drunk/poisoned reminder tokens.
  own.ability=clone(memory?.ability||{});
  own.canNominate=own.alive&&!publicState.nominatedBy.includes(seat);
  if(role==='butler'){own.ability.master=memory?.ability?.lastNightChoice?.targets?.[0]||null;own.ability.master_has_voted=!!publicState.current_nomination?.votes.includes(own.ability.master);}
  return {...publicState,self:own};
 }
 storyteller(state){return {public:this.publicState(state),grimoire:state.runtime.playerStates.map(p=>({seat:p.player.userId,seatIndex:p.player.seatIndex,role:p.role.id,shown:p.effectiveRole.id,alignment:['Demon','Minion'].includes(p.role.category)?'evil':'good',alive:p.alive,tags:[...p.tags],death:clone(p.death)})),nightActions:[...(state.runtime.nightSession?.responses||[])],redHerring:state.draft?.redHerring,bluffs:state.draft?.impBluffs?.map(r=>r.id),script:require('../discord-botc/dist/game/roles').getScript().roles.map(r=>({id:r.id,name:r.name.zh,category:r.category,rules:r.guide.zh}))};}
}
module.exports={ViewProjector};
