function prematureVictory(message,gameOver){
 if(gameOver||!message)return false;
 // Reject unqualified declarations; preserve conditional rules and quoted disagreement.
 if(/如果|若|假如|有人说|误以为|并未|尚未|并不|if |would |might |not over|not won/i.test(message))return false;
 return /(?:善良|邪恶)(?:阵营)?(?:已经|已)?获胜|游戏(?:已经|已)结束|\b(?:good|evil)(?: team)? (?:has )?won\b|\bgame (?:is |has )?(?:over|ended)\b/i.test(message);
}
module.exports={prematureVictory};
