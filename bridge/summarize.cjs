const fs = require('node:fs');
const path = require('node:path');
const dir = path.resolve(process.argv[2]);
const events = fs.readFileSync(path.join(dir, 'events.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
const result = JSON.parse(fs.readFileSync(path.join(dir, 'result.json'), 'utf8'));
const names = require('./role-names.zh.json');
const assignment = events.find(e => e.type === 'assignment');
let text = `# ${result.mode === 'LLM' ? '模型对局记录' : '脚本联调记录（不是 AI 对局）'}\n\n完成：${result.completed}；种子：${result.seed}；胜方：${result.verdict?.team || '无'}；原因：${result.verdict?.kind || result.error}。\n\n执行门槛：标准至少半数，12 人至少 6 票。\n\n`;
if (assignment) text += '| 座位 | 真实角色 | 展示角色 |\n|---|---|---|\n' + assignment.players.map(p => `| ${p.player} | ${names[p.role] || p.role} | ${names[p.shown] || p.shown} |`).join('\n') + '\n\n';
text += '## 完整消息及行动记录\n\n';
for (const event of events) {
  if (event.type === 'public') text += `**${event.seq} · 公开**\n\n${event.message}\n\n`;
  if (event.type === 'private') text += `**${event.seq} · 私信 → ${event.recipient}**\n\n${event.message}\n\n`;
  if (event.type === 'player_decision') text += `**${event.seq} · ${event.actor} · ${event.kind}**\n\n\`\`\`json\n${JSON.stringify(event.response, null, 2)}\n\`\`\`\n\n`;
  if (event.type === 'storyteller_decision' || event.type === 'storyteller_info') text += `**${event.seq} · 说书人决策**\n\n\`\`\`json\n${JSON.stringify(event, null, 2)}\n\`\`\`\n\n`;
}
text=text.replaceAll('屠魔者','猎手').replaceAll('隐士','陌客').replaceAll('市长','镇长');
text+='\n译名说明：本可读记录将上游旧译名统一为集石译名；原始 events.jsonl 保留当时文字。\n';
fs.writeFileSync(path.join(dir, 'transcript.md'), text);
console.log(path.join(dir, 'transcript.md'));
