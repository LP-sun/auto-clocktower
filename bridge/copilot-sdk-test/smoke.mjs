import { CopilotClient } from '@github/copilot-sdk';

const client = new CopilotClient({ useLoggedInUser: true });
try {
  await client.start();
  let models = [];
  try {
    const quota = await client.rpc.account.getQuota({});
    const modelsResult = await client.rpc.models.list({});
    models = modelsResult.models ?? [];
    const snapshots = quota.quotaSnapshots ?? {};
    console.log(JSON.stringify({
      authenticated: true,
      quotas: Object.fromEntries(Object.entries(snapshots).map(([name, value]) => [name, {
        entitlementRequests: value.entitlementRequests,
        usedRequests: value.usedRequests,
        remainingPercentage: value.remainingPercentage,
        resetDate: value.resetDate
      }])),
      models: models.slice(0, 20).map(model => ({
        id: model.id,
        multiplier: model.billing?.multiplier
      }))
    }, null, 2));
  } catch (error) {
    console.log(JSON.stringify({ introspectionError: error.message }));
  }

  if (process.argv.includes('--generate')) {
    const selected = process.env.COPILOT_TEST_MODEL || models[0]?.id || 'auto';
    if (!selected) throw new Error('No Copilot models are available for this account.');
    const session = await client.createSession({
      model: selected,
      streaming: true,
      systemMessage: {
        mode: 'replace',
        content: 'Return only the JSON requested by the user.'
      },
      availableTools: [],
      enableSessionStore: false,
      infiniteSessions: { enabled: false }
    });
    let usage;
    session.on('assistant.usage', event => {
      const { model, inputTokens, outputTokens, cost } = event.data;
      usage = { model, inputTokens, outputTokens, cost };
    });
    const startedAt = performance.now();
    const response = await session.sendAndWait({
      prompt: 'Return exactly this compact JSON object and no markdown: {"action":"idle","reasoning":"SDK test passed","message":"","players":[]}'
    });
    const elapsedMs = Math.round(performance.now() - startedAt);
    console.log(JSON.stringify({
      requestedModel: selected,
      elapsedMs,
      usage,
      response: response?.data?.content ?? response
    }, null, 2));
    await session.disconnect();

    try {
      const afterQuota = await client.rpc.account.getQuota({});
      const premium = afterQuota.quotaSnapshots?.premium_interactions;
      console.log(JSON.stringify({
        premiumAfter: premium && {
          entitlementRequests: premium.entitlementRequests,
          usedRequests: premium.usedRequests,
          remainingPercentage: premium.remainingPercentage,
          resetDate: premium.resetDate
        }
      }, null, 2));
    } catch (error) {
      console.log(JSON.stringify({ quotaAfterError: error.message }));
    }
  }
} finally {
  await client.stop();
}
