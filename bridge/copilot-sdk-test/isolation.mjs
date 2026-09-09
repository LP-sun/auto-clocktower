import { CopilotClient } from '@github/copilot-sdk';

const client = new CopilotClient({ useLoggedInUser: true });
const markers = ['PLAYER_ALPHA_4F2C', 'PLAYER_BETA_9A71'];

function config(marker) {
  return {
    model: 'auto',
    streaming: true,
    systemMessage: {
      mode: 'replace',
      content: `You are one isolated game player. Your private marker is ${marker}. Return only JSON.`
    },
    availableTools: [],
    enableSessionStore: false,
    infiniteSessions: { enabled: false }
  };
}

try {
  await client.start();
  const currentAuth = await client.rpc.account.getCurrentAuth();
  console.log(JSON.stringify({
    auth: currentAuth.authInfo && {
      type: currentAuth.authInfo.type,
      host: currentAuth.authInfo.host,
      login: currentAuth.authInfo.login
    },
    authErrors: currentAuth.authErrors
  }));
  await client.rpc.account.getQuota({});
  const models = (await client.rpc.models.list({})).models ?? [];
  const selectedModel = models[0]?.id ?? 'auto';
  const sessions = [];
  for (const marker of markers) {
    sessions.push(await client.createSession({ ...config(marker), model: selectedModel }));
  }
  const usages = new Map();
  sessions.forEach((session, index) => {
    session.on('assistant.usage', event => {
      const data = event.data;
      usages.set(index, {
        model: data.model,
        inputTokens: data.inputTokens,
        outputTokens: data.outputTokens,
        reasoningTokens: data.reasoningTokens,
        cost: data.cost,
        duration: data.duration,
        timeToFirstTokenMs: data.timeToFirstTokenMs,
        availableToolCount: data.availableToolCount
      });
    });
  });

  const wallStarted = performance.now();
  const results = await Promise.all(sessions.map(async (session, index) => {
    const started = performance.now();
    const response = await session.sendAndWait({
      prompt: 'Return {"marker":"YOUR_PRIVATE_MARKER","otherMarkerSeen":false}. Never invent another player marker.'
    });
    return {
      player: index + 1,
      elapsedMs: Math.round(performance.now() - started),
      usage: usages.get(index),
      response: response?.data?.content ?? response
    };
  }));
  const wallElapsedMs = Math.round(performance.now() - wallStarted);

  const parsed = results.map(result => JSON.parse(result.response));
  const isolated = parsed.every((value, index) =>
    value.marker === markers[index] &&
    value.otherMarkerSeen === false &&
    !results[index].response.includes(markers[1 - index])
  );

  console.log(JSON.stringify({ selectedModel, isolated, wallElapsedMs, results }, null, 2));
  await Promise.all(sessions.map(session => session.disconnect()));
  if (!isolated) process.exitCode = 1;
} finally {
  await client.stop();
}
