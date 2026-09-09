const path = require('node:path');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');

function defaultGameBudget(players) {
  if (players <= 8) return 16;
  if (players <= 12) return 25;
  return 32;
}

function buildQuotaPlan(snapshot, { players, model = 'auto', plannedCredits = defaultGameBudget(players), reserveCredits = 10 }) {
  if (!snapshot || !Number.isFinite(snapshot.entitlementRequests) || !Number.isFinite(snapshot.remainingPercentage)) return null;
  const remainingCredits = snapshot.entitlementRequests * snapshot.remainingPercentage / 100;
  return { allowed: remainingCredits >= plannedCredits + reserveCredits, quotaKnown: true, players, model, entitlementCredits: snapshot.entitlementRequests, remainingPercentage: snapshot.remainingPercentage, remainingCredits, plannedCredits, reserveCredits, resetDate: snapshot.resetDate };
}

class CopilotDecisionClient {
  constructor(log = () => {}) {
    this.log = log;
    this.sessions = new Map();
    this.model = process.env.BOTC_COPILOT_MODEL || 'auto';
  }

  async initialize() {
    const sdkRequire = createRequire(path.join(__dirname, 'copilot-sdk-test', 'package.json'));
    let sdkEntry;
    try { sdkEntry = sdkRequire.resolve('@github/copilot-sdk'); }
    catch { throw new Error('Copilot SDK is not installed. Run npm install --prefix bridge/copilot-sdk-test'); }
    const { CopilotClient } = await import(pathToFileURL(sdkEntry).href);
    this.client = new CopilotClient({ useLoggedInUser: true });
    await this.client.start();
    this.quota = await this.retryRead(() => this.client.rpc.account.getQuota({}), 'quota');
    this.models = (await this.retryRead(() => this.client.rpc.models.list({}), 'models')).models || [];
    if (!this.models.some(model => model.id === this.model)) {
      throw new Error(`Copilot model ${this.model} is unavailable; available: ${this.models.map(m => m.id).join(', ') || '(none)'}`);
    }
  }

  async retryRead(operation, label) {
    let last;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try { return await operation(); }
      catch (error) {
        last = error;
        this.log('copilot_preflight_retry', { label, attempt, category: error.name || 'Error' });
      }
    }
    throw new Error(`Copilot ${label} preflight failed after 3 attempts: ${last?.message || 'unknown error'}`);
  }

  async validateModels() { return true; }

  async planGame({ players }) {
    const snapshot = this.quota.quotaSnapshots?.premium_interactions;
    if (!snapshot || !Number.isFinite(snapshot.entitlementRequests) || !Number.isFinite(snapshot.remainingPercentage)) {
      if (process.env.BOTC_COPILOT_ALLOW_UNKNOWN_QUOTA === '1') return { allowed: true, quotaKnown: false };
      throw new Error('Copilot remaining quota is unavailable; refusing to start without a safe budget');
    }
    const plannedCredits = Number(process.env.BOTC_COPILOT_GAME_BUDGET_CREDITS || defaultGameBudget(players));
    const reserveCredits = Number(process.env.BOTC_COPILOT_RESERVE_CREDITS || 10);
    if (!Number.isFinite(plannedCredits) || plannedCredits <= 0 || !Number.isFinite(reserveCredits) || reserveCredits < 0) throw new Error('Copilot game and reserve credit budgets must be finite positive numbers');
    const plan = buildQuotaPlan(snapshot, { players, model: this.model, plannedCredits, reserveCredits });
    this.log('copilot_quota_plan', plan);
    if (!plan.allowed) {
      throw new Error(`Copilot quota safety check failed: ${plan.remainingCredits.toFixed(2)} credits remain, but ${plannedCredits.toFixed(2)} planned + ${reserveCredits.toFixed(2)} reserve are required`);
    }
    return plan;
  }

  async start(_model, _cwd, system) {
    const session = await this.client.createSession({
      model: this.model,
      streaming: true,
      systemMessage: { mode: 'replace', content: system },
      availableTools: [],
      enableSessionStore: false,
      infiniteSessions: { enabled: false }
    });
    this.sessions.set(session.sessionId, session);
    return { thread: { id: session.sessionId }, instructionSources: [] };
  }

  async run(threadId, input) {
    const session = this.sessions.get(threadId);
    if (!session) throw new Error('Unknown Copilot session');
    let rawUsage;
    session.on('assistant.usage', event => { rawUsage = event.data; });
    let response;
    try { response = await session.sendAndWait({ prompt: input }, 120000); }
    catch (error) { await session.abort(); throw error; }
    const last = rawUsage ? {
      totalTokens: (rawUsage.inputTokens || 0) + (rawUsage.outputTokens || 0),
      inputTokens: rawUsage.inputTokens || 0,
      cachedInputTokens: rawUsage.cacheReadTokens || 0,
      cacheWriteInputTokens: rawUsage.cacheWriteTokens || 0,
      outputTokens: rawUsage.outputTokens || 0,
      reasoningOutputTokens: rawUsage.reasoningTokens || 0,
      aiCreditCost: rawUsage.copilotUsage?.totalNanoAiu ? rawUsage.copilotUsage.totalNanoAiu / 1e9 : null,
      routedModel: rawUsage.model,
      timeToFirstTokenMs: rawUsage.timeToFirstTokenMs
    } : null;
    return { text: response?.data?.content ?? String(response), usage: last && { total: last, last } };
  }

  async rpc(method, params = {}) {
    if (method !== 'thread/unsubscribe') throw new Error(`Unsupported Copilot client RPC: ${method}`);
    const session = this.sessions.get(params.threadId);
    if (session) {
      await session.disconnect();
      this.sessions.delete(params.threadId);
    }
    return {};
  }

  close() {
    for (const session of this.sessions.values()) session.disconnect().catch(() => {});
    this.sessions.clear();
    this.client?.stop().catch(() => {});
  }
}

module.exports = { CopilotDecisionClient, defaultGameBudget, buildQuotaPlan };
