# Trouble Brewing 模拟器已知局限与模型边界 (Known Limitations & Model Boundaries)

本文档系统性梳理当前《血染钟楼》（Trouble Brewing 剧本）数学建模模拟框架的理论边界、工程局限与近似假设。

---

## 一、系统模块状态分类标准 (Status Taxonomy)

根据严格的对抗式审计与模型验证准则，本项目对所有模块与特性的成熟度采用以下五级标记，杜绝夸大宣称：

| 标记 | 含义 |
| :--- | :--- |
| **VERIFIED** | 经过本轮官方规则审计和专项单元测试严格验证，边界条件完备，确定性复现。 |
| **HEURISTIC** | 基于工程或博弈规则设计的启发式算法，能达成直接行为目标，但非最优解或非完全人类分布。 |
| **PROXY** | 代数近似代理指标（如信息熵、悬念代理量），用于量化复杂心理或全局状态，非物理真值。 |
| **PARTIAL** | 核心机制已实现并连通主流程，但仍有边缘分支或特化场景尚未完全覆盖。 |
| **UNVERIFIED** | 仅有代码原型或结构定义，尚未经过大规模对抗测试与实证校准。 |

---

## 二、各子系统成熟度与局限性清单

### 1. 规则引擎与事件语义 (Engine & Rules)
- **TB 22 角色官方技能实现**: `VERIFIED`
  - 经由 `tests/rules/` 48 项专属规则测试验证，覆盖 Scarlet Woman 5 人前置判定、Virgin 反噬处决终结白昼、Undertaker 严格无处决无信息语义、Poisoner 通用持续效果生命周期（`OngoingEffect`）、Mayor 弹杀、Slayer 射击、Butler 随从投票、Soldier 夜间免死、Saint 处决判负等。
- **Recluse / Spy 细粒度登记**: `VERIFIED`
  - Recluse 严格仅登记为 Evil / Minion / Demon；Spy 严格仅登记为 Good / Townsfolk / Outsider。针对 Slayer、Virgin、FT、Chef、Empath、Undertaker 生成合法分支。
- **事件流语义严格区分 (Execution != Death)**: `VERIFIED`
  - 明确划分 `NOMINATION`, `VOTE_RESULT`, `EXECUTION`, `DEATH`, `ABILITY_TRIGGER`, `DAY_END`。
- **其他剧本扩展支持 (BMR / S&V / 自定义剧本)**: `UNVERIFIED`
  - 当前架构虽然设计了解耦的效果机制，但目前仅实现 Trouble Brewing 官方角色库。

### 2. 玩家认知与观察隔离 (Cognition & Perception)
- **真值状态与观察投影视界隔离**: `VERIFIED`
  - 经由 `test_isolation.py` 与 `test_dynamic_taint.py` 严格验证。观察投影视界仅暴露公开事实与合法私有信息，酒鬼视角仅见虚假镇民角色，决无魔典与全局真值泄漏。
- **动态全链路无污染 (Dynamic Taint Elimination)**: `VERIFIED`
  - 经由六层决策断言（`legal_actions`, `applicable_primitives`, `candidate_scores`, `utility_components`, `softmax_probabilities`, `chosen_action`），证明底层世界扰动对相同认知状态下的决策链零污染。
- **有限工作记忆与遗忘曲线**: `HEURISTIC`
  - 采用指数衰减模型 $m(t) = m_0 e^{-\lambda \Delta t}$，模拟人类玩家注意力遗忘。属于工程近似，非真实神经认知模型。
- **玩家信念模型 (Belief Model)**: `HEURISTIC` (非校准贝叶斯后验)
  - **重要说明**：当前信念更新采用证据驱动的打分累加与 Softmax 归一化近似（Score-Softmax Approximation）。**严禁将当前系统宣称为“已校准的贝叶斯后验（Calibrated Bayesian Posterior）”**。它能够有效驱动决策，但未进行世界假设空间的完全贝叶斯后验因式分解计算。

### 3. 策略原语与决策链 (Strategy & Policy)
- **策略原语行为驱动**: `VERIFIED`
  - 经由 `src/analytics/ablation.py` 消融实验验证，`SEEK_COMPLEMENTARY_INFO`, `PRIVATE_CLAIM`, `PROTECT_HIGH_VALUE_ROLE`, `TEST_VIRGIN`, `EVIL_COORDINATION`, `KILL_INFO_ROLE` 均能直接影响专属行为 KPI，证实原语进入核心计算链。
- **性格与技能调制**: `HEURISTIC`
  - 10-D Beta 分布性格向量与 4 级技能预设通过线性权重与温度参数调制效用打分。虽然能显著拉开决策行为分布，但尚未经过真实人类对局微观轨迹的拟合校准。
- **博弈树前瞻与高阶欺骗**: `PARTIAL`
  - 当前玩家策略基于即时效用与有限记忆，缺乏深度 Minimax 或 MCTS 多步树搜索能力，主要模拟中级人类玩家的直觉式博弈。

### 4. 说书人决策与效用模型 (Storyteller Policy)
- **平衡性与悬念裁决**: `HEURISTIC` / `PROXY`
  - 引入 `tension`（双方存活人数与票权差距）与 `solvability_proxy`（恶魔候选怀疑度香农熵），作为说书人权衡好恶阵营天平的代理指标。
- **反事实候选打分与敏感度度量**: `VERIFIED`
  - 每次裁决记录所有合法候选分支的效用与理由，并计算敏感度差值 $\Delta U = U_{\text{best}} - U_{\text{second}}$，支持离线 AI ST 模仿学习与强化学习训练。

---

## 三、合成数据训练 AI ST 的适用性评估

1. **可用场景 (Ready for Use)**:
   - 作为预训练（Pre-training）与行为克隆（Behavioral Cloning）数据源，学习说书人基础规则合法性、醉酒中毒给假信息的合理范围以及维持对局张力的基本模式。
   - 用于反事实策略评估（Off-policy Evaluation），对比不同 ST 策略下的对局时长与悬念走向。

2. **限制与注意事项 (Cautionary Advice)**:
   - 由于玩家信念目前是 Score-Softmax 启发式近似，AI ST 模型若过度拟合当前合成数据中的玩家心理读数，可能在面对真实人类的高阶心理战时产生偏差。建议后续通过接入真实或 LLM 驱动的标定数据开展参数校准。
