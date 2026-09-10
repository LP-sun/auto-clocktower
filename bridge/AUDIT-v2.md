# 修改前数据流审计（2026-09-08）

已先阅读两份需求及当前代码，未采用完整重写。工作区 sources 保持只读。

```text
discord-botc rules engine / role handlers
 → bridge/run.cjs publicMessage / privateMessage
 → bridge broadcastTo → 各自 isolated chatHistory
 → bridge ask / discussionRound / playDay / playNight（构造参数化 JSON）
 → semantic-provider.generate（单一模型边界）
 → codex-provider sessions Map → codex-client thread/start + turn/start
 → 校验 response → 引擎行动

Storyteller 的登记、误导信息、死亡转移和信息选择均走同一异步裁决边界；
engine 只提供 legalOptions，LLM 只能选择其中一个。实时模型异常直接终止
运行；first_legal 仅由无模型的 fixture/replay 路径显式启用。
```

| 动作 | 构造位置 | 原持久化行为 |
|---|---|---|
| discussion / whisper / whisper_reply | run.cjs discussionRound → ask | 控制 JSON、回复及 reasoning 全部写回；公开发言再广播 |
| nomination / defense / vote | run.cjs playDay → ask | 候选人、旧票决、publicStatus 等快照反复写回 |
| night / death | run.cjs playNight → ask | 夜间请求、行动 JSON 写回；目标私信单独保存 |
| storyteller pacing / preflight | run.cjs main / playDay → semantic-provider.generate | ST 独立 history，控制请求不写入其他玩家上下文 |
| information review | run.cjs setAutomatedInfoReview | ST 可见真实魔典；不向玩家投递魔典 |

会话创建：codex-client.cjs `start()`。绑定：semantic-provider 的 `register()` WeakMap 与 sessions Map，按 actor 维护 threadId。每次决策使用新的原生会话；玩家和说书人历史仅保留其可见游戏事件。

原 delta 是 history.slice(cursor)，cursor 在一次回复后增加两个元素（请求、回复）。这样避免同一调用重复发送，但原生会话依然保留此前所有控制回合。公开动作再次成为广播是实际游戏事件；不能因此保留旧控制响应。replay 直接返回保存的结果，不进行推理；恢复时创建新会话，cursor=0，因此重发完整 API transcript。不存在刻意重复 append 同一控制回合，但事实广播与机器协议存在大量语义重复。

修复顺序：规则/信息边界 → 无 LLM 完整测试 → 控制协议隔离 → 轻量决策视图 → 语义记忆与压缩/恢复 → telemetry → 人工确认后才可真模型测试。

当前规则为标准至少半数：`ceil(存活人数/2)`，12 人存活时 6 票即可处决。真实模型 overhead/质量/多档 benchmark 本轮均不调用模型；用现有用量证据与 mock 测量，不将字符估算冒充实际 token。
