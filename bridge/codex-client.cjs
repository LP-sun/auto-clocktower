const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');

function binary() {
  if (process.env.BOTC_CODEX_BIN) return process.env.BOTC_CODEX_BIN;
  const installed = path.join(process.env.APPDATA || '', 'npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe');
  return fs.existsSync(installed) ? installed : 'codex';
}

class CodexClient {
  constructor(log = () => {}) {
    this.log = log; this.nextId = 0; this.pending = new Map(); this.turns = new Map();
    const args = ['app-server', '--stdio'];
    // No model-controlled filesystem/network/browser/plugin access is needed to play.
    for (const feature of ['shell_tool','apps','plugins','multi_agent','browser_use','computer_use','image_generation','view_image','memories','skill_search','goals','sleep_tool']) args.push('-c', `features.${feature}=false`);
    args.push('-c','web_search="disabled"','-c','mcp_servers={}');
    if (process.env.BOTC_CODEX_HTTP === '1') args.push('-c','model_providers.botc_openai={name="OpenAI",wire_api="responses",requires_openai_auth=true,supports_websockets=false}');
    this.child = spawn(binary(), args, { stdio: ['pipe','pipe','pipe'], windowsHide: true });
    this.child.stderr.on('data', chunk => {
      // Only classify transport diagnostics; never dump raw SDK/credential output.
      const text = chunk.toString();
      if (/websocket/i.test(text)) this.log('codex_transport',{category:'websocket',timeout:/timeout|timed out/i.test(text)});
    });
    this.child.on('error', e => this.failAll(new Error(`Codex process failed: ${e.code || 'spawn'}`)));
    this.child.on('exit', code => this.failAll(new Error(`Codex app-server exited: ${code}`)));
    readline.createInterface({ input: this.child.stdout }).on('line', line => {
      let msg; try { msg = JSON.parse(line); } catch { return; }
      if (msg.id !== undefined && !msg.method) {
        const pending = this.pending.get(msg.id); if (!pending) return;
        this.pending.delete(msg.id); clearTimeout(pending.timer);
        msg.error ? pending.reject(new Error(`Codex RPC: ${msg.error.message}`)) : pending.resolve(msg.result);
        return;
      }
      if (msg.id !== undefined && msg.method) {
        // Reject all server-initiated tool/approval requests. They are outside this game protocol.
        this.child.stdin.write(JSON.stringify({ id: msg.id, error: { code: -32601, message: 'Tools are disabled in the isolated game client' } })+'\n');
        this.log('codex_tool_denied', { method: msg.method }); return;
      }
      const params = msg.params || {};
      const turn = this.turns.get(params.threadId);
      if (!turn) return;
      if (msg.method === 'item/completed') {
        const item = params.item;
        if (item?.type === 'agentMessage') turn.text = item.text;
        else if (item && !['reasoning','userMessage','plan'].includes(item.type)) {
          this.log('codex_unexpected_item', { threadId: params.threadId, type: item.type });
          turn.toolUsed = true;
        }
      }
      if (msg.method === 'thread/tokenUsage/updated') turn.usage = params.tokenUsage;
      if (msg.method === 'turn/completed') {
        this.turns.delete(params.threadId); clearTimeout(turn.timer);
        if (turn.toolUsed) turn.reject(new Error('Unexpected tool use: refusing this game response'));
        else if (params.turn.status !== 'completed') turn.reject(new Error(`Codex turn ${params.turn.status}: ${params.turn.error?.message || 'no result'}`));
        else turn.resolve({ text: turn.text, usage: turn.usage });
      }
    });
  }
  failAll(error) { for (const item of [...this.pending.values(),...this.turns.values()]) { clearTimeout(item.timer); item.reject(error); } this.pending.clear(); this.turns.clear(); }
  rpc(method, params = {}, timeout = 60000) {
    return new Promise((resolve,reject) => {
      const id = ++this.nextId;
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error(`Codex RPC timeout: ${method}`)); }, timeout);
      this.pending.set(id, { resolve, reject, timer });
      this.child.stdin.write(JSON.stringify({ id, method, params })+'\n');
    });
  }
  async initialize() {
    await this.rpc('initialize', { clientInfo: { name: 'botc_isolated_game', version: '0.1.0' }, capabilities: { experimentalApi: true } });
    this.child.stdin.write(JSON.stringify({ method: 'initialized', params: {} })+'\n');
  }
  async start(model, cwd, instructions) {
    const response = await this.rpc('thread/start', { model, modelProvider: process.env.BOTC_CODEX_HTTP === '1' ? 'botc_openai' : 'openai', allowProviderModelFallback: false, cwd, runtimeWorkspaceRoots: [cwd], approvalPolicy: 'never', sandbox: 'read-only', ephemeral: true, environments: [], selectedCapabilityRoots: [], dynamicTools: [], baseInstructions: instructions, developerInstructions: 'This is a hidden-role game simulation. You have no filesystem, browser, plugin, or other-player access. Return only the requested JSON decision. Never call tools.', config: { 'web_search': 'disabled', 'memories.generate_memories': false, 'memories.use_memories': false } });
    return response;
  }
  async run(threadId, input, actions, effort) {
    const outputSchema = { type: 'object', additionalProperties: false, properties: { reasoning: { type: 'string' }, action: { type: 'string', enum: actions }, message: { type: 'string' }, players: { type: 'array', items: { type: 'string' } } }, required: ['reasoning','action','message','players'] };
    outputSchema.properties.memoryUpdate = { anyOf: [{type:'null'}, {type:'object',additionalProperties:false,properties:{beliefs:{type:'array',maxItems:12,items:{type:'object',additionalProperties:false,properties:{player:{type:'string'},summary:{type:'string',maxLength:240}},required:['player','summary']}},plan:{type:'array',maxItems:5,items:{type:'string',maxLength:240}},worlds:{type:'array',maxItems:5,items:{type:'string',maxLength:240}}},required:['beliefs','plan','worlds']}] };
    outputSchema.required.push('memoryUpdate');
    const completion = new Promise((resolve,reject) => {
      const timer = setTimeout(() => { this.turns.delete(threadId); reject(new Error('Codex model turn timed out')); }, Number(process.env.BOTC_CODEX_TIMEOUT_MS || 180000));
      this.turns.set(threadId, { resolve, reject, timer, text: '', toolUsed: false });
    });
    try { await this.rpc('turn/start', { threadId, input: [{ type: 'text', text: input, text_elements: [] }], environments: [], effort, outputSchema }); }
    catch(e) { const turn = this.turns.get(threadId); this.turns.delete(threadId); clearTimeout(turn?.timer); turn?.reject(e); }
    return completion;
  }
  close() { this.child.stdin.end(); this.child.kill(); }
}
module.exports = { CodexClient };

if (require.main === module) {
  (async () => {
    const client = new CodexClient();
    try {
      await client.initialize();
      const account = await client.rpc('account/read', { refreshToken: false });
      console.log(JSON.stringify({ accountType: account.account?.type, requiresOpenaiAuth: account.requiresOpenaiAuth }));
      const models = await client.rpc('model/list', { limit: 100 });
      console.log(JSON.stringify({ models: models.data.map(m => ({ id: m.id, model: m.model, efforts: m.supportedReasoningEfforts })) }));
      if (process.argv.includes('--smoke')) {
        const cwd = path.join(__dirname,'isolated-smoke'); fs.mkdirSync(cwd,{recursive:true});
        const thread = await client.start(process.env.BOTC_PLAYER_MODEL || 'gpt-5.6-luna', cwd, 'You are an isolated game player. Do not use tools.');
        console.log(JSON.stringify({ started: thread.thread.id, model: thread.model, instructionSources: thread.instructionSources }));
        const answer = await client.run(thread.thread.id, 'Return JSON with action idle, reasoning 测试通过, message 你好, players [].', ['idle'], 'low');
        console.log(JSON.stringify(answer));
      }
    } finally { client.close(); }
  })().catch(e=>{ console.error(e.message); process.exitCode=1; });
}
