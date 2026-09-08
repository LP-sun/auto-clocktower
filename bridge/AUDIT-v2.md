# 修改前数据流审计（2026-09-08）

已先阅读两份需求及当前代码，未采用完整重写。工作区 sources 保持只读。

```text
discord-botc runGameLoop / role handlers
 → bridge/run.cjs publicMessage / privateMessage
 → clocktower-ai broadcastMessage → 各自 chatHistory
 → bridge ask / discussionRound / playDay / playNight（构造控制 JSON）
 → clocktower-ai sendMessageToPlayer
 → vertex-ai.generateResponse → injected provider.generate
 → codex-provider sessions Map → codex-client thread/start + turn/start
 → 校验 response → 引擎行动
 → sendMessageToPlayer 将整个请求及 response 再 append 至 chatHistory
```

| 动作 | 构造位置 | 原持久化行为 |
|---|---|---|
| discussion / whisper / whisper_reply | run.cjs discussionRound → ask | 控制 JSON、回复及 reasoning 全部写回；公开发言再广播 |
| nomination / defense / vote | run.cjs playDay → ask | 候选人、旧票决、publicStatus 等快照反复写回 |
| night / death | run.cjs playNight → ask | 夜间请求、行动 JSON 写回；目标私信单独保存 |
| storyteller pacing / preflight | run.cjs main / playDay → sendMessageToPlayer | ST 独立 history，包含旧控制请求及 response |
| information review | run.cjs setAutomatedInfoReview | ST 可见真实魔典；不向玩家投递魔典 |

会话创建：codex-client.cjs `start()`。绑定：codex-provider.cjs `register()` 的 WeakMap 与 sessions Map，按 actor 维护 threadId。原生 `ephemeral:true` 仅不持久写盘，不意味着旧 turn 不进入下一次上下文。

原 delta 是 history.slice(cursor)，cursor 在一次回复后增加两个元素（请求、回复）。这样避免同一调用重复发送，但原生会话依然保留此前所有控制回合。公开动作再次成为广播是实际游戏事件；不能因此保留旧控制响应。replay 直接返回保存的结果，不进行推理；恢复时创建新会话，cursor=0，因此重发完整 API transcript。不存在刻意重复 append 同一控制回合，但事实广播与机器协议存在大量语义重复。

修复顺序：规则/信息边界 → 无 LLM 完整测试 → 控制协议隔离 → 轻量决策视图 → 语义记忆与压缩/恢复 → telemetry → 人工确认后才可真模型测试。

新要求把默认处决门槛改为标准至少半数；原严格过半保留可选桌规。真实模型 overhead/质量/多档 benchmark 本轮均不调用模型；用现有用量证据与 mock 测量，不将字符估算冒充实际 token。
