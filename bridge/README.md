# discord-botc × clocktower-ai：12 人本地桥接

已完成源码获取、适配、编译和脚本联调，并通过已登录的 Codex 订阅运行真实模型对局。最新完成状态和结果见 `REPORT.md`。`--fixture` 仅为脚本测试，不能作为模型表现评估。

默认规则：处决需要至少半数存活玩家，即 `ceil(alive / 2)`；12 人存活时至少 6 票。

## 当前目录直接运行

在本项目根目录执行：

```powershell
./bridge/build.ps1
node bridge/test.cjs
node bridge/isolation-test.cjs
node bridge/semantic-test.cjs
node bridge/storyteller-test.cjs
$env:BOTC_SEED = '42'
node bridge/run.cjs --fixture
```

`node bridge/test.cjs` 直接运行 Node 内置测试，避免受限环境中 `node --test` 启动子进程遭拒。无需 Discord token，不连接真实 Discord 服务器。

## 配置真实模型

默认使用官方 Codex app-server 和现有 ChatGPT 登录，无需 API key。先安装 Codex CLI 并通过 `codex login` 登录；本适配不会自行提取凭据或兑换额度重置。会检查登录类型与账户实际提供的模型列表，不静默更换模型。

```powershell
$env:BOTC_PROVIDER = 'codex'
$env:BOTC_CODEX_HTTP = '1'
$env:BOTC_PLAYER_MODEL = 'gpt-5.6-luna'
$env:BOTC_PLAYER_EFFORT = 'medium'
$env:BOTC_ST_MODEL = 'gpt-6-astra'
$env:BOTC_ST_EFFORT = 'high'
$env:BOTC_SEED = '42'
node bridge/run.cjs
```

真实模型运行必须显式加入 `--allow-live-models`；没有该参数时 bridge 会拒绝模型推理。本轮使用 `semantic-v2`：权威引擎状态、独立玩家可见语义记忆、最近相关事件和一次性控制上下文分离。完整 request/response/reasoning 仍写入审计日志，但不会进入玩家长期记忆。投票和提名使用轻量视图；旧事件只能通过受 ACL 限制的 lookup 检索。说书人只读取魔典、公开状态和公共社交信号，不读取玩家 memory 或 reasoning。

也可将 `bridge/.env.example` 复制为 `bridge/.env`。`BOTC_CODEX_BIN` 可指定原生 Codex 可执行文件。HTTP 开关配置官方 Responses 传输及 `requires_openai_auth=true`，继续使用同一订阅认证；本机默认 WebSocket 连接每次约等待两分钟，HTTP 实测约 5–10 秒。

玩家默认较轻的 `gpt-5.6-luna / medium`，说书人使用 `gpt-6-astra / high`。每个角色分别创建独立临时会话，只增量投递该席位可见历史；禁用工具、外部环境、记忆与额外指令来源。这里的会话不会创建用户侧的新任务。

中断后保留原始目录，使用相同种子并指向最近一次日志恢复：

```powershell
$env:BOTC_REPLAY_FROM = (Resolve-Path bridge/runs/此前运行目录).Path
node bridge/run.cjs
```

恢复会重放已成功记录的模型决策，逐项校验席位、请求状态和可用行动；然后把重建的各自可见历史送入新的独立会话，继续未完成的决策。不会重抽此前选择。种子或代码行为变化导致不一致时立即停止。新开一局需移除 `BOTC_REPLAY_FROM`。

模型错误、额度不足或持续非法目标会保存失败状态并停止，不以脚本决策替代。默认上限为 1000 次逻辑请求、20 天。备用 OpenAI 兼容和 Gemini 适配保留，但本次真实运行使用 Codex 订阅。额度由账户共享，适配层不会自动兑换重置。

## 原项目如何进入自动模式

Discord 部署的原始流程是 `!clocktower @玩家...` → 私有游戏频道 → `/youare`。自动模式接受 5–15 人，16 人分支会拒绝；12 人无需扩容。本桥接直接调用同一个 `handleYouare()`，使用本地 client/channel/user 对象承接消息，随后仍由上游 `runGameLoop()` 推进。

clocktower-ai 保留 `Player`、`chatHistory`、`sendMessageToPlayer()` 和 `broadcastMessage()`；没有调用需要真人输入的 CLI 循环。引擎负责角色、夜晚结算、提名和胜负，桥接负责调度 AI 玩家及消息路由。全部 22 个 Trouble Brewing 角色说明由 discord-botc 的角色定义进入模型系统提示。

说书人有独立上下文。LLM 可以决定是否多给一轮讨论，并在限定范围内选择酒鬼/中毒玩家的占卜师、共情者、厨师、送葬者信息。其余随机裁量保留上游策略；这不是完整的人类说书人能力复刻。

## 新机器复现

```powershell
git clone https://github.com/ShuzhaoFeng/discord-botc.git
git clone https://github.com/raphydaphy/clocktower-ai.git
git -C discord-botc checkout 55afc19b063995176696a587ed939019d3773e36
git -C clocktower-ai checkout 91cc58819f0d949ef505e166ec7ed3f5602db05a
# 将本次 bridge 文件夹放到两仓库旁边
git -C discord-botc apply ../bridge/patches/discord-botc.patch
git -C clocktower-ai apply ../bridge/patches/clocktower-ai.patch
Copy-Item bridge/patches/discord-botc.package-lock.json discord-botc/package-lock.json
Copy-Item bridge/patches/clocktower-ai.package-lock.json clocktower-ai/package-lock.json
Push-Location discord-botc
npm.cmd ci --ignore-scripts --no-audit --no-fund
Pop-Location
Push-Location clocktower-ai
npm.cmd ci --ignore-scripts --no-audit --no-fund
Pop-Location
./bridge/build.ps1
node bridge/test.cjs
node bridge/isolation-test.cjs
$env:BOTC_SEED = '42'
node bridge/run.cjs --fixture
```

运行需求：Node.js 22+、npm、Git。测试时不需要 Next.js 页面构建；本次验证的是两个后端 TypeScript 编译，而非 Discord 网关或 Web UI 部署。

## 产物

每次运行保存到 `bridge/runs/<模式>-<UTC时间>/`：

- `events.jsonl`：配置、角色分配、公开发言、逐人私信、行动、提名/投票、夜晚结果、状态变化及终局。真实模型模式还记录完整请求上下文与响应；脚本模式只记请求长度及可重建的路由事件。
- `result.json`：是否完成、模式、种子、胜方、角色与死亡状态；失败时包含失败原因。
- `data/generated/*.csv`：继承 clocktower-ai 的逐人记录。已修正引号转义；这些文件没有额外表头。
- `audit.json`：运行 `node bridge/audit.cjs <运行目录>` 独立重建消息可见性、核对历史哈希及会话隔离。
- `transcript.md`：运行 `node bridge/summarize.cjs <运行目录>` 生成可读全文。

完整日志含全知角色与私信，是复盘材料，不应在对局进行时给玩家模型读取。固定种子复现规则层随机选择；真实模型输出不保证确定性。断点恢复按上文设置 `BOTC_REPLAY_FROM`；未设置时另起一局。

请先阅读 `REPORT.md` 中的剩余规则缺陷。当前适配是可运行原型，不代表已通过完整 Trouble Brewing 规则认证。
