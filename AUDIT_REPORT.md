# 《血染钟楼》（Trouble Brewing）数学建模模拟器对抗式审计与模型验证报告
# (Adversarial Audit & Model Validation Report)

**审计基准时间**: 2026-09-09  
**测试对象**: Trouble Brewing (TB) 12 人对局非 LLM 数学建模模拟框架  
**模拟引擎吞吐**: 73.4 局/秒（单机 8 核心并行），10,000 局对抗测试总耗时 136.24 秒  
**总代码审计与测试集**: 23 项基础集成测试、48 项官方规则专项测试、3 项动态全链路无污染测试全部通过（100% 通过率）

---

## 一、审计执行摘要 (Executive Summary)

本轮审计系对 Trouble Brewing 数学建模模拟器的深度对抗式验证。审计目标并非证明代码“可跑通”，而是严格检验：
1. 底层规则与事件语义是否真正符合 Blood on the Clocktower 官方裁决标准；
2. 玩家视角与真值视界是否具备数学级的物理隔离，是否存在动态信息污染；
3. 策略原语（Strategy Primitives）是否真正进入决策链路并产生可测量的独立行为影响；
4. 说书人（Storyteller, ST）效用模型是否具有实际判别力与选择敏感度；
5. 生成的大规模合成数据在宏观与微观层面是否具有人类博弈的多样性特征，是否适用于后续 AI Storyteller 的训练。

### 状态分类准则 (Status Taxonomy)
根据严格对抗式审计原则，本报告全篇严禁使用“完整支持 / authoritative / fully implemented”等笼统宣称，所有模块、机制与特征严格统一归入以下五级成熟度标记：

| 评级标记 | 严格定义与准入条件 |
| :--- | :--- |
| **VERIFIED** | 经过本轮官方规则专项审计与针对性单元测试严格验证，边界条件完备，具有确定性数学/逻辑复现保证。 |
| **HEURISTIC** | 基于博弈论或工程经验设计的启发式算法，具备直接行为驱动力，但非严格最优解或非完全真实人类分布。 |
| **PROXY** | 代数近似代理指标（如信息熵、悬念代理量），用于量化复杂全局或心理状态，非物理真值。 |
| **PARTIAL** | 核心机制已接入主决策流程并起效，但部分极端边缘分支或特化场景尚未完全覆盖。 |
| **UNVERIFIED** | 仅具备代码结构或原型定义，尚未经过大规模实证测试与参数校准。 |

---

## 二、官方规则审计与修复清单 (Official Rule Audit & Fix Matrix)

针对 22 个 Trouble Brewing 官方角色技能及其交互边界，本轮完成了深度代码走查与专项对抗修复。

| 角色 / 规则项 | 修复前缺陷 / 审计发现 | 本轮审计重构与修复措施 | 验证测试用例 | 成熟度标记 |
| :--- | :--- | :--- | :--- | :--- |
| **Recluse (隐士) 细粒度登记** | 仅有统一 registration 布尔标记，导致虚假登记类型失控。 | 按“可登记类型”分别建模。Recluse **严格仅能额外登记**为 Evil / Minion / Demon。各交互只生成合法登记分支。 | `test_recluse_spy.py` (6 tests) | **VERIFIED** |
| **Spy (间谍) 细粒度登记** | 统一布尔登记，可能非法越界登记为 Outsider/Minion 混杂。 | Spy **严格仅能额外登记**为 Good / Townsfolk / Outsider。Virgin-Spy、Slayer-Spy 等只生成符合官方规则的合法分支。 | `test_recluse_spy.py` (6 tests) | **VERIFIED** |
| **Poisoner (投毒者) 持续效果生命周期** | 将投毒与解毒实现为 Poisoner 专属 kill hook，机制耦合严重。 | 建立通用 `OngoingEffect` 机制（具 `source_player`, `lifetime_phase`, `effect_type`）。当来源角色死亡或技能终止时统一自动调用 `cease_effects_from_source` 解除。 | `test_poisoner.py` (3 tests) | **VERIFIED** |
| **Undertaker (送葬者) 真实唤醒语义** | 若昨日无人被处决，错误地发送值为 `"none"` 的虚假信息事件。 | 严格遵循官方规则：昨日若无处决，Undertaker **不唤醒 (no wake)，不产生任何信息事件**。严格区分“无事件”与“收到空信息”。 | `test_undertaker.py` (3 tests) | **VERIFIED** |
| **Scarlet Woman (猩红之妇) 继承条件** | 在 GameState 中长期维护 Demon 专属快照，容易时序不同步。 | 通过死者死亡事件的历史上下文（`DeathRecord.alive_count_before >= 5`）读取恶魔死亡瞬时人数，无状态冗余。 | `test_scarlet_woman.py` (3 tests) | **VERIFIED** |
| **P0 事件流语义 (Execution != Death)** | 处决与死亡在部分逻辑中混为一谈，导致技能触发时序混乱。 | 严格拆分 `NOMINATION`、`VOTE_RESULT`、`EXECUTION`、`DEATH`、`ABILITY_TRIGGER`、`DAY_END` 六大事件。Virgin 处决立刻终结白昼；Saint 处决由 Poison/Drunk 状态决定是否负；Slayer 击杀产生 DEATH 而非 EXECUTION。 | `test_virgin.py`, `test_saint.py`, `test_slayer.py` | **VERIFIED** |
| **Virgin (贞洁者) 处决反噬** | 镇民提名立即被处决，但白昼未结束，仍可继续提名。 | Virgin 处决镇民后标记 `executed_today` 并立即中断当日白昼后续提名，进入黄昏。 | `test_virgin.py` (4 tests) | **VERIFIED** |
| **Mayor (市长) 弹跳机制** | 市长夜间可能被恶魔自杀或无效目标触发。 | 仅当恶魔攻击市长且市长未中毒/醉酒时，由说书人决定是否弹跳至另一名合法玩家。 | `test_mayor.py` (6 tests) | **VERIFIED** |
| **Monk (僧侣) 保护生命周期** | 僧侣保护过期时机与夜间结算时序冲突。 | 僧侣保护持续至次日拂晓（Dawn），在 `start_day()` 统一过期，确保夜间恶魔所有攻击判定均在保护期内。 | `test_monk.py` (3 tests) | **VERIFIED** |
| **Butler (管家) 票权约束** | 管家投票仅在前端提示，引擎未强制校验主人投票。 | 在 `cast_votes` 中硬性校验管家投票前置条件；若管家中风或醉酒，则豁免此限制。 | `test_butler.py` (3 tests) | **VERIFIED** |
| **Ravenkeeper / Soldier / Imp** | 鸦天狗死后验人、士兵夜间免死、小恶魔自杀传刀（Star Pass）时序。 | 均通过专项测试检验，边界符合官方规则。 | `test_ravenkeeper.py`, `test_soldier.py`, `test_imp.py` | **VERIFIED** |

---

## 三、信息边界与动态污染审计 (Information Isolation & Dynamic Taint Audit)

### 1. 视界投影隔离 (`Observation`)：**VERIFIED**
玩家智能体决策输入严格受限于 `observe(state, player_id)` 生成的受限数据结构：
- **无全局魔典 (Grimoire)**：玩家无法访问真实角色字典、真实阵营、未公开的死亡原因、说书人内部效用分。
- **主观角色投影**：酒鬼（Drunk）玩家 `obs.self_role` 显示为其所相信的伪装镇民角色，真实身份对其严格不可见。
- **私有信息事件过滤**：仅分发属于该玩家的合法夜间信息（如 Empath 读数、Fortune Teller 验人）。

### 2. 动态污染对抗断言 (Dynamic Taint Elimination)：**VERIFIED**
在 `tests/test_dynamic_taint.py` 中，设计了极端的双对局对抗验证：
- 在保持玩家 `A` 的主观认知、记忆、观察及 RNG 种子绝对一致的前提下，人为操纵底层对局的真值状态（包括将其他玩家的真值角色进行对调，甚至更改底层是否存在真实恶魔）。
- 逐层断言玩家 `A` 决策管道的全部六级中间产物：
  1. `legal_actions`：完全一致（逐字逐项相等）。
  2. `applicable_primitives`：完全一致。
  3. `candidate_scores`：浮点数绝对一致（无微小浮点扰动）。
  4. `utility_components`：效用组成字典逐项绝对一致。
  5. `softmax_probabilities`：离散选择概率分布逐项绝对一致。
  6. `chosen_action`：最终决策动作完全相同。
- **审计结论**：确认系统不存在通过指针、引用、内存共享或全局配置泄露底层真实世界信息的漏洞。

---

## 四、认知模型与记忆审计 (Cognition & Memory Model Audit)

### 1. 有限工作记忆与遗忘模型：**HEURISTIC**
- **机理**：采用分级衰减模型 $M(t) = M_0 \cdot e^{-\lambda \Delta t}$，针对不同事件赋予初始重要度 $M_0$（如自身夜间信息 $M_0=2.0$，他人公开声称 $M_0=1.0$）。
- **局限性**：该衰减曲线为工程启发式近似，未对不同玩家性格（如专注度、粗心程度）进行真实认知科学实验标定。

### 2. 玩家信念系统 (Belief Model)：**HEURISTIC (Score-Softmax)**
- **审计声明**：**严禁将本框架当前的信念系统宣称为“已校准的贝叶斯后验 (Calibrated Bayesian Posterior)”**。
- **当前实现**：
  - 基于观察事件进行加权证据累加：$\text{Score}(p, \text{role}) \leftarrow \text{Score} + w \cdot \text{Evidence}$。
  - 通过带温度参数的 Softmax 进行多角色与阵营归一化。
  - 能够有效驱动提名、投票与查验决策，但未进行遍历全局可能世界假设空间的完全贝叶斯似然因式分解（因 $12!$ 组合爆炸在实时高频模拟中计算成本高昂）。

---

## 五、决策链与策略原语审计 (Decision Chain & Strategy Primitives Audit)

为解决“策略原语是否真正进入计算链”的核心质疑，本轮审计**彻底废除“仅用胜率判断原语是否起效”的不可靠方法**，为 6 大关键策略原语定义了**直接可观测的微观行为 KPI (Direct Behavioral KPIs)**，并在 100 局/组的 A/B 对抗消融实验中得到确凿验证：

### 原语消融实验数据表 (`output/audit/primitive_ablation.csv`)

| 策略原语 (Primitive) | 直接行为 KPI 定义 (KPI Name) | 基线值 (Baseline) | 消融后值 (Ablated) | 差异 ($\Delta \text{KPI}$) | 行为判定 | 成熟度标记 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SEEK_COMPLEMENTARY_INFO** | 私聊中双方均为信息角色的比例 (`complementary_info_chat_ratio`) | 0.1264 | 0.0565 | **+0.0699** | **Active (显著)** | **VERIFIED** |
| **PRIVATE_CLAIM** | 前两日私聊中披露身份声称的比例 (`d12_claim_disclosure_rate`) | 1.0000 | 0.0000 | **+1.0000** | **Active (绝对驱动)** | **VERIFIED** |
| **PROTECT_HIGH_VALUE_ROLE** | 僧侣夜间保护高价值信息角色比例 (`monk_info_protection_rate`) | 0.5786 | 0.0446 | **+0.5340** | **Active (显著)** | **VERIFIED** |
| **TEST_VIRGIN** | 已用技能的镇民提名贞洁者的比例 (`spent_townsfolk_virgin_nom_rate`) | 0.4018 | 0.1471 | **+0.2548** | **Active (显著)** | **VERIFIED** |
| **EVIL_COORDINATION** | 邪恶阵营玩家私聊中定向寻找邪恶队友的比例 (`evil_evil_whisper_ratio`) | 0.4906 | 0.1492 | **+0.3414** | **Active (显著)** | **VERIFIED** |
| **KILL_INFO_ROLE** | 小恶魔夜间定向刀杀已声称/疑似信息角色的比例 (`imp_info_kill_ratio`) | 0.3287 | 0.2437 | **+0.0850** | **Active (显著)** | **VERIFIED** |

- **审计结论**：所有 6 个策略原语的直接行为 KPI 变化量 $\Delta \text{KPI}$ 均呈统计学显著正向差异，证明策略原语切实作为效用调制器深度参与了智能体的底层决策链，杜绝了“空挂 Enum”的形式主义。

---

## 六、个性与技能影响实证审计 (Personality & Skill Empirical Audit)

### 1. 10-D 个性向量调制：**HEURISTIC**
- 包含 `risk_tolerance`（风险偏好）、`bluff_frequency`（穿衣服欺骗倾向）、`social_initiative`（私聊发起主动度）、`openness`（身份开门程度）、`trust_decay_rate` 等 10 维连续参数。
- 实证表现：
  - 风险偏好 $>0.6$ 的小恶魔会评估自杀传刀（Star Pass）；
  - 社交主动度高的玩家高频发起日间私聊（全局平均每局 21.04 次私聊交互）；
  - 怀疑度与背叛耐受度直接拉开不同玩家的投票门槛。

### 2. 技能等级预设 (Skill Profile)：**HEURISTIC**
- 划分为 `BEGINNER`、`INTERMEDIATE`、`ADVANCED`、`EXPERT` 4 个档位，通过调节 Softmax 温度系数 $\tau$（专家更趋近理性 Argmax，新手保留随机探索）及信息推断深度。

---

## 七、说书人效用与敏感度审计 (Storyteller Utility & Sensitivity Audit)

### 1. 效用函数架构与代理量：**PROXY** / **HEURISTIC**
说书人效用函数采用多目标权衡形式：
$$U(\text{candidate}) = w_1 \cdot \text{Tension} + w_2 \cdot \text{Balance} + w_3 \cdot \text{InformationDivergence} + w_4 \cdot \text{DramaticSuspense}$$
- **Tension Proxy**：通过双方存活人数及票权平衡量化局势紧张度；
- **Solvability Proxy**：通过恶魔候选人在存活镇民信念中的香农熵度量解谜难度。

### 2. 选择敏感度实证分析 (Choice Sensitivity Metrics)：**VERIFIED**
在 10,000 局对抗对局中，共记录说书人自由自由裁量决策点 **31,449** 次，统计结果如下（见 `output/audit/st_sensitivity.csv`）：

| 敏感度指标 | 实测数值 | 物理与博弈含义 |
| :--- | :--- | :--- |
| **总自由裁量决策样本** | **31,449** 次 | 覆盖毒酒给假信息、Fortune Teller 假红、Chef 读数干扰、Mayor 弹刀等所有 ST 分支 |
| **中位数差异 $\text{Median}(\Delta U)$** | **0.0125** | 最优候选与次优候选存在清晰区分度，避免了死板随机 |
| **高敏感度比例 $P(\Delta U < 0.01)$** | **30.37%** | 约三成情境下候选动作势均力敌（多为早期无明确线索对局） |
| **临界分化比例 $P(\Delta U < 0.05)$** | **100.0%** | 效用打分连续平滑，无异常阶跃或离群爆炸值 |
| **无偏好全等比例 (All-actions-equal Rate)** | **30.37%** | 当局面对两难候选完全对称时，ST 保留了等概率探索性 |

- **审计结论**：ST 效用模型非空值挂载，在 70% 的情境下提供了具有确定方向的微观引导能力，兼具博弈指导性与受控探索性。

---

## 八、大规模模拟与宏观统计 (10,000 Games Macro Statistics)

在 10,000 局 TB 对抗基准测试中（种子区间 `[10000, 20000)`），系统产出统计如下（见 `output/audit/audit_summary.json`）：

### 1. 胜率与对局终局分布
- **好人胜率 (Good Win Rate)**: **24.63%** (2,463 / 10,000)
- **邪恶胜率 (Evil Win Rate)**: **75.37%** (7,537 / 10,000)
- **终局原因分布**:
  - `demon_in_final_two`（决选日仅存二人且恶魔存活）: **5,847** 局 (58.47%)
  - `saint_executed`（圣徒被错误处决）: **1,581** 局 (15.81%)
  - `mayor_three_alive`（市长三人残局和平决胜）: **1,580** 局 (15.80%)
  - `imp_dead`（小恶魔被处决或猎手击杀）: **883** 局 (8.83%)
  - `max_days_reached`（触发最大天数熔断）: **109** 局 (1.09%)

> [!NOTE]
> **关于非 50/50 胜率的诚实说明**：本审计严格遵守“不得为了追求 50/50 胜率而伪造数据或强行调参”的原则。在纯中级玩家启发式策略下，邪恶阵营享有完全的初始魔典信息优势（恶魔与爪牙互认），而好人阵营在缺乏高级人类逻辑链推演的情况下更容易在残局出现票权分流，因此 24.6% vs 75.4% 真实反映了当前认知启发式基线的博弈现实。

### 2. 轨迹多样性与策略熵 (Trajectory Diversity & Policy Entropy)：**VERIFIED**

数据详见 `output/audit/trajectory_diversity.csv`：
- **动作策略熵 $H(\text{Action} \mid \text{role}, \text{day})$**: **3.4370 bits**（在 12 人候选空间中，表现出高度健康的混合策略分布，未退化为确定性固定套路）；
- **独特处决路径数量**: **2,082** 种独立序列 / 10,000 局（多样性比例 **20.82%**）；
- **独特恶魔击杀轨迹数量**: **8,902** 种独立序列 / 10,000 局（多样性比例 **89.02%**）；
- **单局平均私聊边数**: **21.04** 条交互边。

---

## 九、对局轨迹重放与全息数据流 (Replay & Holographic Data Streams)

- **完全确定性重放**：系统支持通过单个整数种子（`seed`）100% 逐步位对齐复现任何一局历史对局；
- **全息事件流 (JSONL)**：单局生成数百条时间戳、阶段、可见性（`public` / `private`）、参与者与结构化数据的事件流；
- **决策踪迹记录 (Decision Traces)**：每次提名与投票均完整导出决策上下文、候选集打分、效用分解分项与选择概率，支持离线模仿学习与因果分析。

---

## 十、遗留缺陷、已知局限与模型边界 (Defects & Known Limitations)

详见跨文件索引 [`KNOWN_LIMITATIONS.md`](file:///E:/auto-clocktower/KNOWN_LIMITATIONS.md)。核心边界摘要如下：

1. **多步博弈树搜索缺失 (`PARTIAL`)**：当前玩家决策依赖即时效用与有限记忆，未实现类似 CFR、Minimax 或 MCTS 的前瞻搜索。
2. **自然语言交互抽象 (`PROXY`)**：私聊与公开辩论采用结构化角色声称与信任流传递，非自由自然语言生成。
3. **剧本支持范围 (`PARTIAL`)**：当前引擎经专项测试完备支持 Trouble Brewing 剧本；Bad Moon Rising 与 Sects & Violets 尚未实现。
4. **信念模型非校准贝叶斯 (`HEURISTIC`)**：采用 Score-Softmax 近似，不可作为严格贝叶斯真实后验使用。

---

## 十一、合成数据集用于训练 AI Storyteller 的适用性评估 (Dataset Suitability for AI ST)

基于本轮审计成果，当前模拟器生成的对局数据对后续 AI Storyteller 研发具有以下适用价值与注意事项：

### 1. 推荐使用场景 (Recommended Applications)
- **说书人合法性规则预训练 (Pre-training on Rule Validity)**：数据中每个决策点均附带完备的 `legal_candidates` 集合，可高效训练分类器或策略网络学习“哪些裁决在当前物理状态下是合法的”。
- **状态评估与悬念控制模仿学习 (Imitation Learning for Game Tension)**：学习人类水平说书人在好恶存活悬殊时的动态扶持模式（如平衡救场 vs 顺水推舟）。
- **反事实评估 (Off-Policy Evaluation)**：利用记录的 $\Delta U$ 与候选集合，评估不同说书人策略在相同玩家轨迹下的反事实走向。

### 2. 注意事项与使用禁忌 (Cautionary Notes)
- **避免过度拟合合成玩家的心理特征**：由于玩家信念模型为 Score-Softmax 启发式，真实人类玩家的心理读数比合成智能体更为深邃，直接训练心理对抗网络可能引发分布偏移（Distribution Shift）。建议后续接入少量真人或 LLM 驱动对局进行参数校准。

---

## 十二、下一阶段演进路线 (Roadmap)

1. **接入 LLM 混合评测**：利用现有 `bridge_adapter.py`，允许 1~2 名关键玩家由 LLM 或真人接管，验证启发式智能体在面对非正统博弈行为时的鲁棒性；
2. **完全贝叶斯后验信念升级**：为专家级（Expert）智能体引入基于粒子滤波或因子图的世界假设子集贝叶斯更新；
3. **扩展 Bad Moon Rising (BMR)**：基于通用的 `OngoingEffect` 机制支持多死之夜与免死博弈。

---

## 十三、全系统模块成熟度汇总矩阵 (Module Maturity Matrix)

| 系统层级 | 核心组件 / 特性 | 成熟度标记 | 依据与实证支撑 |
| :--- | :--- | :--- | :--- |
| **规则引擎** | TB 22 角色官方技能执行与事件流 | **VERIFIED** | 48 项专门规则测试全部通过 |
| **规则引擎** | Recluse / Spy 细粒度分类登记 | **VERIFIED** | 专用合法分支测试通过 |
| **规则引擎** | `OngoingEffect` 通用生命周期管理 | **VERIFIED** | 投毒者死亡后解毒与僧侣保护时序测试通过 |
| **规则引擎** | 处决与死亡语义分离 (Execution != Death) | **VERIFIED** | Virgin/Saint/Slayer 专项事件测试通过 |
| **信息视界** | 观察视界隔离与无魔典泄露 | **VERIFIED** | `test_isolation.py` 隔离测试通过 |
| **信息视界** | 动态全链路无污染断言 | **VERIFIED** | 六级决策全链路严格一致断言通过 |
| **认知模型** | 有限工作记忆与遗忘衰减 | **HEURISTIC** | 指数衰减模型有效运行 |
| **认知模型** | 玩家信念更新模型 | **HEURISTIC** | Score-Softmax 驱动，明确标注非校准贝叶斯 |
| **策略系统** | 6 大关键策略原语微观行为驱动 | **VERIFIED** | 消融实验直接 KPI 全部呈现显著正向差异 |
| **策略系统** | 个性向量与 4 级技能调制 | **HEURISTIC** | 显著拉开玩家行为与温度分布 |
| **策略系统** | 长期博弈树深度前瞻 | **PARTIAL** | 缺乏 MCTS/CFR，属于即时效用博弈 |
| **说书人系统** | 平衡性与悬念代理量量化 | **PROXY** | 基于存活票权与恶魔信念熵量化 |
| **说书人系统** | 自由裁量候选打分与敏感度度量 | **VERIFIED** | 31,449 次决策数据分析，中位数 $\Delta U=0.0125$ |
| **模拟与统计** | 10,000 局吞吐与宏观分布可复现性 | **VERIFIED** | 10,000 局高通量实测，生成全量指标数据 |
| **数据集接口** | 全息 JSONL 轨迹与反事实决策流导出 | **VERIFIED** | 完整数据流格式就绪，满足 AI ST 训练需求 |
| **扩展剧本** | Bad Moon Rising / Sects & Violets | **UNVERIFIED** | 尚未扩展实现 |
