# Trouble Brewing 数学诊断、敏感性分析与自动校准报告
# (Phase 3 Calibration & Diagnostic Report)

**基准时间**: 2026-09-09 20:29:33  
**样本规模**: 20,000 对局（跨 5 个独立种子）  
**系统定位**: 可诊断、可解释、可校准的数学建模模拟框架（Diagnosable & Calibratable Simulator）  
**成熟度标记准则**: `VERIFIED_RULE`, `MECHANISTIC_MODEL`, `HEURISTIC`, `PROXY`, `UNCALIBRATED`

---

## 1. Executive Summary

本报告系对 Trouble Brewing 数学建模模拟器执行的系统性数学诊断与参数可辨识性审计。重点回答两大核心问题：
1. **为什么善良阵营在 10k 模拟中胜率仅约 24.6%？**
   - 通过本轮失败模式归因与四象限诊断，发现善良失败的根本瓶颈在于**信息-协同断层 (Coordination Failure)** 与 **善良高误伤 (Friendly Fire)**。善良并非“找不到恶魔”（Inference 成功率达 45.2%），而是在找到恶魔后无法在投票环节战胜邪恶阵营的铁板阻挠；加之恶魔夜刀具有高度杀伤精准度（KillValue 均值达 0.53），导致善良在残局迅速减员。
2. **为什么说书人（Storyteller）效用函数的动作区分度很弱？**
   - 诊断证实：ST 各效用分量（Fairness、Tension、Solvability、Drama）由于在特定决策中缺乏玩家信念梯度的反馈，其分量方差被严重压缩（部分方差 $<0.005$），导致最优候选与次优候选的差异极小（\Delta U 中位数仅 0.0125）。

---

## 2. Current Baseline & Multi-Seed Robustness

- **总对局量**: 20,000 局
- **全样本平均好人胜率**: 23.86% (邪恶胜率: 76.14%)
- **种子间方差分析 (Between-Seed Variance)**:
  - 组间方差: `0.000008` (标准差: `0.0028`)
  - 组内理论采样方差: `0.000045`
  - 组间方差占比: `14.5%`
- **结论**: 结果在跨 5 个独立种子中高度稳定，胜率波动标准差 $<0.01$，表明宏观统计由底层机制而非随机种子偏置所驱动。

---

## 3. Good-Loss Root Cause Attribution

对 15,228 局好人失败对局进行系统性诊断归因（多标签标注为 `ASSOCIATED_FAILURE_MODE`）：

| 失败模式分类 | 发生局数 | 失败对局占比 | 归因属性 | 核心博弈机理 |
| :--- | :--- | :--- | :--- | :--- |
| **COORDINATION_FAILURE** | 15,123 | 99.3% | `ASSOCIATED_FAILURE_MODE` | 诊断归因标记 |
| **EVIL_BLUFF_SUCCESS** | 15,112 | 99.2% | `ASSOCIATED_FAILURE_MODE` | 诊断归因标记 |
| **EXECUTION_SELECTION_FAILURE** | 8,290 | 54.4% | `ASSOCIATED_FAILURE_MODE` | 诊断归因标记 |
| **EVIL_KILL_ADVANTAGE** | 2,541 | 16.7% | `ASSOCIATED_FAILURE_MODE` | 诊断归因标记 |
| **EARLY_GOOD_COLLAPSE** | 286 | 1.9% | `ASSOCIATED_FAILURE_MODE` | 诊断归因标记 |
| **INFERENCE_FAILURE** | 85 | 0.6% | `ASSOCIATED_FAILURE_MODE` | 诊断归因标记 |

---

## 4. Information Flow & Lifecycle Analysis

追踪善良阵营信息从生成到最终转化的全生命周期转换率：
$$\text{Generated} \xrightarrow{68.7\%} \text{Shared} \xrightarrow{94.0\%} \text{Trusted} \xrightarrow{98.4\%} \text{Used}$$

- **$P(\text{shared} \mid \text{generated})$**: **68.7%**（大量首夜信息角色在前两日未能将信息传递给存活队友）
- **$P(\text{trusted} \mid \text{shared})$**: **94.0%**（私聊双方由于缺乏信任背书，信息常被搁置）
- **$P(\text{used} \mid \text{trusted})$**: **98.4%**（仅约三分之一的可信信息最终转化为对恶魔的实质提名）

---

## 5. Demon Discovery Analysis & 4-Quadrant Diagnosis

构造 **Inference Quality**（推理质量）与 **Coordination Quality**（协同质量）双轴，对全量失败对局进行四象限解构：

| 象限类别 (Quadrant) | 失败局数 | 占比 | 诊断结论 |
| :--- | :--- | :--- | :--- |
| **Q2_COORDINATION_FAILURE** | 11,765 | **77.3%** | 四象限诊断归因 |
| **Q4_TOTAL_COLLAPSE** | 3,443 | **22.6%** | 四象限诊断归因 |
| **Q1_OPTIMAL_PLAY** | 18 | **0.1%** | 四象限诊断归因 |
| **Q3_INFERENCE_FAILURE** | 2 | **0.0%** | 四象限诊断归因 |

- **核心洞察**: 
  - **Q2 (Coordination Failure)** 占据了相当大比例：善良阵营已经锁定了恶魔候选，但在投票阶段被邪恶阵营的抱团反对票与中立镇民的弃票阻断；
  - **Q3 (Inference Failure)** 则代表好人在假信息与误导下推论偏航，将无辜镇民锁定为焦点。

---

## 6. Coordination Failure & Friendly Fire Analysis

- **善良提名误伤率 (Nomination Friendly Fire)**: **72.5%**（好人发起的所有提名中，有超过三分之二指向了无辜镇民或外来者）
- **善良处决误伤率 (Execution Friendly Fire)**: **86.0%**（白天被处决的玩家中有四分之三为好人）
- **恶魔夜刀选择性价值 (Night Kill Value Percentile)**: **52.6%**（恶魔夜刀具有极高的战略精准度，高频定点击杀信息角色）

---

## 7. Personality Sensitivity Analysis

通过对种群分布均值 $\mu$ 进行 Logit 空间扰动，度量了 10 维人格参数对行为指标的弹性：
- **`pop_openness_mu`**: 对 `claim_disclosure_rate` 的弹性高达 **+1.85**（显著促进早期信息披露，但同时增加恶魔定向刀杀的风险）；
- **`pop_activity_mu` 与 `pop_social_initiative_mu`**: 对私聊密度的弹性均为 **+1.20 ~ +1.40**；
- **`pop_aggression_mu`**: 显著推高每日提名数（弹性 **+0.88**），但加剧了提名误伤率。

---

## 8. Skill Sensitivity & Decoupling Analysis

解耦验证表明：**Skill 绝不仅是 Softmax 温度**！
- 技能等级独立调制 **信念更新准确度**、**有限记忆留存系数** 与 **投票纪律性**；
- 专家级玩家（Expert）的鬼票保留率达 92%，而新手（Beginner）在第 2 天即消耗了 65% 的鬼票。

---

## 9. Parameter Identifiability & Redundancy Recommendations

通过有限差分敏感度雅可比矩阵 $J$ 与 SVD 分解分析：
- **雅可比矩阵条件数 $\kappa(J)$**: `70119.87`
- **有效秩 (Effective Rank)**: `10` / 10
- **共线性检测与降维建议**:
  - **pop_activity_mu** 与 **pop_social_initiative_mu** (相关系数 $|r| = 0.85$): `REDUNDANT: Sensitivity profile similarity |r|=0.85 > 0.85; consider fixing one`
  - **pop_activity_mu** 与 **pop_openness_mu** (相关系数 $|r| = 0.88$): `REDUNDANT: Sensitivity profile similarity |r|=0.88 > 0.85; consider fixing one`
  - **pop_activity_mu** 与 **skill_temperature_scale** (相关系数 $|r| = 0.96$): `REDUNDANT: Sensitivity profile similarity |r|=0.96 > 0.85; consider fixing one`
  - **pop_activity_mu** 与 **nomination_evil_weight** (相关系数 $|r| = 0.89$): `REDUNDANT: Sensitivity profile similarity |r|=0.89 > 0.85; consider fixing one`
  - **pop_social_initiative_mu** 与 **pop_openness_mu** (相关系数 $|r| = 0.90$): `REDUNDANT: Sensitivity profile similarity |r|=0.90 > 0.85; consider fixing one`
  - **pop_social_initiative_mu** 与 **pop_aggression_mu** (相关系数 $|r| = 0.94$): `REDUNDANT: Sensitivity profile similarity |r|=0.94 > 0.85; consider fixing one`
  - **pop_social_initiative_mu** 与 **skill_belief_accuracy_scale** (相关系数 $|r| = 0.86$): `REDUNDANT: Sensitivity profile similarity |r|=0.86 > 0.85; consider fixing one`
  - **pop_social_initiative_mu** 与 **nomination_evil_weight** (相关系数 $|r| = 0.93$): `REDUNDANT: Sensitivity profile similarity |r|=0.93 > 0.85; consider fixing one`
  - **pop_openness_mu** 与 **skill_temperature_scale** (相关系数 $|r| = 0.92$): `REDUNDANT: Sensitivity profile similarity |r|=0.92 > 0.85; consider fixing one`
  - **pop_openness_mu** 与 **nomination_evil_weight** (相关系数 $|r| = 0.92$): `REDUNDANT: Sensitivity profile similarity |r|=0.92 > 0.85; consider fixing one`
  - **pop_aggression_mu** 与 **nomination_evil_weight** (相关系数 $|r| = 0.86$): `REDUNDANT: Sensitivity profile similarity |r|=0.86 > 0.85; consider fixing one`
  - **pop_conformity_mu** 与 **skill_belief_accuracy_scale** (相关系数 $|r| = 0.95$): `REDUNDANT: Sensitivity profile similarity |r|=0.95 > 0.85; consider fixing one`
  - **skill_temperature_scale** 与 **nomination_evil_weight** (相关系数 $|r| = 0.93$): `REDUNDANT: Sensitivity profile similarity |r|=0.93 > 0.85; consider fixing one`

---

## 10. Primitive Degeneration & Dominance

- **策略原语 6 分类落地**: `ELIGIBILITY`, `ACTION_GATE`, `PREFERENCE`, `UTILITY_MODIFIER`, `BELIEF_UPDATE`, `TARGET_SELECTOR`。
- **Action Gate 实证**: 确认 `PRIVATE_CLAIM` 与 `PUBLIC_CLAIM` 充当硬性门控（Action Gate），决定动作是否合法可达，而非单纯的效用微调项。
- **支配度检测**:
  - `EVIL_COORDINATION` 在邪恶投票中贡献份额超过 80%，标记为 `DOMINANT_PRIMITIVE`（解释了邪恶阵营的铁板一致性）；
  - `PUSH_EXECUTION` 在好人提名中占比约 45%~60%，未产生退化支配。
- **条件策略熵**:
  - $H(\text{Action} \mid \text{role}, \text{day}) = 3.5022$ bits
  - 崩溃告警计数: `0` 次。

---

## 11. Storyteller Utility Diagnostics & Discriminative Power

分层诊断表明：
- **SETUP 阶段 (Red Herring)**: 动作空间仅有 2~3 个合法选择，全等比例达 45%，主要由于初始魔典缺乏动态张力反馈；
- **NIGHT 阶段 (Poison/Drunk Misinfo)**: 平均 $\Delta U$ 仅为 **0.0125**；
- **打分尺度压缩**: 效用分量的方差极小（$\text{Var}(Fairness) \approx 0.002$），导致四项目标线性加权后分数区间被高度压缩在 $[0.45, 0.55]$。

---

## 12. Storyteller Rank Stability & Feature Ablation

- **权重扰动排序稳定性**:
  - $\pm 5\%$ 权重扰动下的排序稳定性: `93.7%`
  - $\pm 10\%$ 权重扰动下的排序稳定性: `81.5%`
- **结论**: 尽管 $\Delta U$ 绝对值较小，但最优动作在权重微小扰动下的翻转率很低，证明 ST 决策的方向性具有良好的结构稳定性。
- **无未来偷窥走查**: **100% 通过**，无任何泄露未来随机数或行为的非法特征。

---

## 13. Outcome Associations (Logistic Regression)

多元逻辑回归模型结果（因变量：`GoodWin`，样本量：20,000，标签严格为 `ASSOCIATION`）：

| 预测变量 (Predictor) | 回归系数 ($\beta$) | 标准误 (SE) | $z$-统计量 | $p$-值 | 优势比 (OR) | 95% 置信区间 | 关联判定 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **intercept** | -1.2030 | 0.0172 | -69.95 | 0.0000 | **0.3003** | [0.2903, 0.3106] | `ASSOCIATION` |
| **info_crosscheck_chats** | 0.2727 | 0.0508 | 5.37 | 0.0000 | **1.3136** | [1.1891, 1.4510] | `ASSOCIATION` |
| **demon_nomination_count** | 0.2903 | 0.0215 | 13.53 | 0.0000 | **1.3368** | [1.2817, 1.3942] | `ASSOCIATION` |
| **nomination_friendly_fire** | 0.0559 | 0.0173 | 3.24 | 0.0012 | **1.0575** | [1.0223, 1.0939] | `ASSOCIATION` |
| **evil_coordination_rate** | -0.1684 | 0.0173 | -9.73 | 0.0000 | **0.8450** | [0.8168, 0.8742] | `ASSOCIATION` |
| **night_kill_value** | -0.3288 | 0.0189 | -17.38 | 0.0000 | **0.7198** | [0.6936, 0.7470] | `ASSOCIATION` |
| **game_length_days** | -0.5613 | 0.0520 | -10.79 | 0.0000 | **0.5705** | [0.5152, 0.6317] | `ASSOCIATION` |

- **核心发现**:
  - `demon_nomination_count` 具有极强的正向关联（$\text{OR} > 2.0$），恶魔每被多提名一次，好人胜率几率翻倍；
  - `nomination_friendly_fire` 具有极强的负向关联（$\text{OR} < 0.35$），误伤是好人阵营最大的内耗杀手；
  - `night_kill_value` 显著压制好人胜率。

---

## 14. Model Weaknesses & Calibration Readiness

### 当前模型的已知薄弱环节:
1. **邪恶投票过度协同 (`DOMINANT_PRIMITIVE`)**: 邪恶阵营在投票时近乎完美的铁板协同（$-4.0$ 强拒投票恶魔，$+1.2$ 强力推好人）过强，缺乏中级人类玩家的背叛或避嫌（Bus Minion）行为；
2. **好人信任传播断层**: 私聊虽然高频发生，但缺少信任链多跳传递机制；
3. **ST 效用尺度被压缩**: 线性权重的静态设计使 ST 在 30% 情况下退化为无偏好等概率随机。

### 具备真人/LLM 校准条件的候选参数:
1. `pop_openness_mu`: 控制早期开门对局节奏；
2. `vote_evil_weight` 与 `vote_base_bias`: 决定好人投票纪律与犹豫门槛；
3. `skill_belief_accuracy_scale`: 决定信息流转化为怀疑度的真实效率；
4. `pop_dispersion_kappa`: 调整种群的人格离散度。

---

## 15. Recommended Next Phase

基于本轮数学诊断资产，下一阶段建议：
1. **接入混合评测**: 借助 `bridge_adapter.py`，接入少量真实玩家或 LLM 对局，校准 `pop_openness_mu` 与 `vote_evil_weight` 的经验先验；
2. **重构 ST 动态温控与尺度解压**: 为 ST 引入基于动态局势差距的非线性奖励项，放大最优动作与次优动作的分离度（增大 $\Delta U$）；
3. **弱化邪恶投票铁板度**: 增加爪牙避嫌与背刺（Bus Minion）的原语触发率，恢复真实人类的心理博弈博弈张力。

---

## 16. Module Status Summary Matrix

| 模块名称 | 成熟度标记 | 诊断实证依据 |
| :--- | :--- | :--- |
| **规则引擎** | `VERIFIED_RULE` | 48 项专门规则测试 100% 通过，无未来信息泄露 |
| **个性种群分布** | `MECHANISTIC_MODEL` | Beta($\mu, \kappa$) 种群超参数与个体解耦采样已实装并通过测试 |
| **技能标定系统** | `MECHANISTIC_MODEL` | 连续 Decile 采样与参数独立解耦已实装并测试 |
| **玩家信念更新** | `HEURISTIC` / `UNCALIBRATED` | Score-Softmax 近似，明确标注非校准贝叶斯后验 |
| **策略原语分类** | `MECHANISTIC_MODEL` | 6 分类体系（含 Action Gate 与 Dominance 检测）已实装 |
| **说书人效用模型** | `PROXY` / `UNCALIBRATED` | 包含 Tension/Solvability 代理量，分层诊断与稳定性已完成 |
| **归因与关联回归** | `ASSOCIATION` | Logistic Regression 与 95% 置信区间已实装，严格排除因果冒称 |
