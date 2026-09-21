# 研究 Q4 —— 资源集大小

## 研究问题

当客观世界真值完全相同时，仅改变人物可见的个人 Resource Set，会如何影响：单步行为对齐、确定性规则可执行性、held-out 真人日记支持度、关键遗漏，以及上下文成本？

本阶段只测试四个预注册的嵌套条件：

`C8 = R8`、`C16 = R16`、`C32 = R32`、`C64 = R64`。

本阶段不重新测试 Q3 的对象实验臂，不启动 Q5 scaling，不启动本地 8B，也不运行全天连续性。

## Resource 的定义

Resource 是能够持续存在并影响后续动作选择的个人状态变量。Resource 值归一化到 `[0,1]`：0 表示低需求/低压力（或能量耗尽），1 表示高需求/高压力（或高能量）。

固定 schema 一共包含 64 个字段。R8、R16、R32、R64 都是同一个不可变 `ResourceTruth64` 的投影；不允许按实验臂修改底层真值。

meal、restaurant、office、target、object availability 以及 catalog 等世界事实不属于 Resource。它们在所有条件中都保持存在。

## 保持不变的内容

四个层级之间，以下内容完全相同：

* persona、时间、地点、客观世界事实、对象可用性以及 Catalog + Top-K 架构；
* 可用 action 与 target；
* previous activity、recent events 以及 R1 behavior-prior query；
* 完整 64 字段真值、场景 seed、确定性 RuleEngine 和 scorer；
* provider、请求契约、temperature、retry policy，以及 resource block 之外的 prompt 文本。

只有可见的 `r` block 发生变化。为了便于审计，artifact 同时记录 `truth_values` 与 `visible_resources`，以及 truth hash 和 fixed-context hash。acceptable actions、critical resources、scenario family、expected labels 从不进入 prompt。

Q3 保持为历史结果且不改动：Object 架构固定为 Catalog + Top-K。

## R8

八个粗粒度 Resource 为：

`hunger`、`energy`、`sleep_pressure`、`work_urgency`、`hygiene_need`、`chores_backlog`、`leisure_need`、`budget_pressure`。

## R16

R16 包含全部 R8 字段，并额外加入：

`stress`、`social_need`、`commute_pressure`、`discretionary_budget_remaining`、`work_progress`、`meal_recency`、`personal_care_recency`、`chores_recency`。

## R32

R32 包含全部 R16 字段，并额外加入：

`physical_fatigue`、`mental_fatigue`、`sleep_debt`、`sleep_quality`、`hunger_trend`、`food_security`、`cash_on_hand`、`checking_balance`、`credit_available`、`debt_pressure`、`work_minutes_today`、`work_deadline_pressure`、`commute_minutes_pressure`、`household_load`、`leisure_minutes_today`、`recent_spending_ratio`。

## R64

R64 包含全部 R32 字段，并额外加入：

`hydration_need`、`caffeine_level`、`physical_discomfort`、`temperature_discomfort`、`sickness_signal`、`exercise_fatigue`、`work_stress`、`financial_stress`、`social_stress`、`social_contact_recency`、`friend_availability`、`family_contact_recency`、`loneliness`、`shower_due`、`dental_care_due`、`clothing_cleanliness_need`、`laundry_load`、`dish_load`、`trash_load`、`kitchen_cleaning_need`、`bedroom_cleaning_need`、`cooking_prep_need`、`grocery_stock_pressure`、`appointment_urgency`、`transport_availability`、`mobility_friction`、`cash_reserve_pressure`、`savings_health`、`credit_pressure`、`currency_liquidity`、`entertainment_novelty_need`、`routine_disruption`。

## 场景设计

冻结 manifest 中包含 24 个确定性的固定状态决策：physiology、work、personal care、chores、leisure、finance、mobility、food/consumption 八类场景各 3 个。每个场景都包含客观世界事实、完整 ResourceTruth64、previous activity、recent events、BTRAIN_ALL/R1 prior query、acceptable action set 和 critical resource fields。

场景设计避免把问题压成单一主观“正确答案”，也避免同时叠加多个极端压力。acceptable sets 是只供 scorer 使用的确定性充分性契约，从不展示给 provider。

调度采用确定性的 Latin-style rotations 做平衡。每个 scenario × repetition × level 单元只请求一次。

## 离线验证

无网络能力探针已经通过：

* 标记：`RESOURCE_SET_OFFLINE_OK`；
* 说明：`SYSTEM_CAPABILITY_PROBE_NOT_MODEL_BEHAVIOR`；
* 24 个场景 × 4 个层级 × 2 次重复 = 192 行；
* nested projections、immutable truth、prompt isolation、deterministic scorer 和 192-cell schedule 全部通过。

离线输出不作为行为证据。

## 真实 Smoke

Artifact：`run/evaluation/resource_set_size/real_q4_attempt_1_smoke_20260918T081701224684Z/`。

smoke 使用四个不同 family（hunger、work、personal care、chores），重复 1 次，共 16 个请求。

```text
scheduled=16
success=16
timeout=0
http_error=0
parse_error=0
architecture_error=0
backend_model_counts={glm-5.3: 16}
smoke_gate=PASS
```

所有成功行都通过 strict parse，并且 resource projection 合法。smoke 指标只说明 pipeline/provider 正常，不用于选择 Resource 层级。

## 完整 Provider 运行

Artifact：`run/evaluation/resource_set_size/real_q4_attempt_1_full_20260918T081859853289Z/`。

完整调度为 24 个场景 × 4 个层级 × 2 次重复 = 192 个请求。

```text
scheduled=192
success=174
timeout=18
http_error=0
parse_error=0
architecture_error=0
backend_model_counts={glm-5.3: 174}
matched_quadruples=33/48
```

全部 174 个成功 response envelope 都通过 strict parse。没有发生 retry、repair、cosmetic rerun 或 automatic resume。

artifact 记录的 source base 为 `20f5f0c0e6f1aa830075981dc87f9852d356460d`；包含 Q4 实现与本报告的最终 Git commit 在验证后的 handoff 中记录。

## Provider 可靠性

成功响应的 HTTP status 计数为 `200:174`。HTTP error 和 error-code 映射为空。剩余 18 行为 timeout，不会人为补写后端模型归属。原始 prompt、原始 completion、hidden reasoning、Authorization header 和 API key 均未存储。

所有 174 个成功行中，provider 返回的后端模型均为 `glm-5.3`。请求使用的 alias 仍来自既有安全 A2 配置；此处不复现任何凭证。

## Matched Quadruple 分析

一个 matched quadruple 指同一个 scenario × repetition 下，R8、R16、R32、R64 四个层级全部成功。完整运行得到 33 组 matched quadruples，高于预注册最低证据门槛 30。下文所有主要比较仅使用这 33 组 matched quadruples；按层级的总成功行表只作描述。

| Resource 层级 | 行为对齐率 | 规则可执行率 | 关键遗漏率 | Held-out share | Held-out top-3 | 平均输入 token | 输入 token 中位数 | 平均 prompt 字符数 | 平均延迟（秒） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R8 | 0.696970 | 0.969697 | 0.303030 | 0.338023 | 0.848485 | 281.121212 | 282.0 | 982.060606 | 9.924361 |
| R16 | 0.727273 | 0.969697 | 0.272727 | 0.332873 | 0.848485 | 346.121212 | 347.0 | 1161.151515 | 9.609734 |
| R32 | 0.727273 | 0.939394 | 0.272727 | 0.320336 | 0.812500 | 477.121212 | 478.0 | 1528.424242 | 12.258748 |
| R64 | 0.848485 | 1.000000 | 0.151515 | 0.277661 | 0.750000 | 747.121212 | 748.0 | 2297.696970 | 6.465834 |

全部成功行的描述性计数分别为：R8=46、R16=43、R32=39、R64=46。

## 行为对齐

当 proposal 属于该场景的 acceptable action set 时，`resource_alignment` 记为 1。它是本 benchmark 的确定性充分性指标，不是“真人真值”标签。

在 matched quadruples 上，R8=0.696970、R16=0.727273、R32=0.727273、R64=0.848485。R8 明显较弱；R16 提高 0.030303；R32 相比 R16 没有提高；R64 是本次观察中对齐率最高的层级。

## 规则可执行性

规则可执行性由现有确定性 RuleEngine 按当前实验 action profile 评估。生产 RuleEngine 语义没有修改。

matched executable rates 分别为：R8=0.969697、R16=0.969697、R32=0.939394、R64=1.000000。这不能作为把 RuleEngine 替换为 Resource-dependent rule 的依据。

## 真人日记支持度

held-out scorer 仅由独立的 643-day EVAL pool 构建。2,572 份 TRAIN diaries 只进入固定的 BTRAIN_ALL/R1 prior；EVAL 从不进入 context。

matched held-out action share 分别为：R8=0.338023、R16=0.332873、R32=0.320336、R64=0.277661。held-out top-3 rates 为：R8/R16=0.848485、R32=0.812500、R64=0.750000。若某个 action 不属于 Core7 diary vocabulary，则记为 not-supported/NA，而不是强行 remap。

## 关键遗漏

critical miss 指 proposal 不在场景 acceptable action set 中。在 matched quadruples 上，R8=0.303030、R16=0.272727、R32=0.272727、R64=0.151515。R64 最低，但这一下降同时伴随较大的上下文扩张，因此不能单独据此确定“最小测试集合”。

## 上下文成本

随着可见字段增加，prompt 大小单调上升：

* R8：281.121 input tokens，982.061 prompt characters；
* R16：346.121 input tokens，1,161.152 prompt characters；
* R32：477.121 input tokens，1,528.424 prompt characters；
* R64：747.121 input tokens，2,297.697 prompt characters。

输入 token 的相对增幅分别为：R8→R16 为 +23.1217%，R16→R32 为 +37.8480%，R32→R64 为 +56.5894%。延迟受 provider 噪声影响较大：R16→R32 增加 +27.5659%，另外两个观测变化为负。

## 边际收益

| 扩展 | Δ 对齐率 | Δ 规则可执行率 | Δ held-out share | Δ 关键遗漏率 | Δ 输入 token | Δ 延迟 | 信号 |
|---|---:|---:|---:|---:|---:|---:|---|
| R8 → R16 | +0.030303 | 0.000000 | -0.005150 | -0.030303 | +23.1217% | -3.1702% | NONE |
| R16 → R32 | 0.000000 | -0.030303 | -0.012537 | 0.000000 | +37.8480% | +27.5659% | LOW_MARGINAL_RETURN |
| R32 → R64 | +0.121212 | +0.060606 | -0.042675 | -0.121212 | +56.5894% | -47.2553% | NONE |

low-marginal-return 标签遵循预注册的工程阈值：正向行为收益低于 0.03，同时输入 token 或延迟成本增加至少 15%。这不是统计显著性结论。

## 场景 Family 分析

下表使用每个 family 中全部成功行的描述性 alignment rate，因此由于 timeout，各行分母并不相等：

| 场景类别 | R8 | R16 | R32 | R64 |
|---|---:|---:|---:|---:|
| 生理需求 | 0.5000 | 0.8000 | 1.0000 | 0.4000 |
| 工作 | 0.6667 | 1.0000 | 0.8333 | 0.6667 |
| 个人护理 | 0.3333 | 0.6667 | 0.5000 | 0.6667 |
| 家务 | 0.7500 | 0.4000 | 0.5000 | 0.6667 |
| 休闲 | 0.5000 | 0.6000 | 0.6000 | 0.6667 |
| 财务 | 0.3333 | 0.3333 | 0.2500 | 0.4000 |
| 出行 | 0.8333 | 1.0000 | 1.0000 | 1.0000 |
| 食物 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

这些 family 行只作描述，不是第二套选择标准。它们说明为什么不能把 aggregate minimum 解释为通用 action policy：不同 family 对可见状态的反应不同，而且 provider 输出本身存在噪声。

## 可见性前沿

visibility frontier 指某个场景声明的 critical resource 首次变得可见的测试层级。它只是二级审计，不是事后改变实验：

| Critical resource 示例 | 首次可见层级 |
|---|---|
| hunger, sleep_pressure, work_urgency, hygiene_need, chores_backlog, leisure_need, budget_pressure | R8 |
| commute_pressure, work_progress, meal/personal-care/chores recency, social_need, discretionary budget | R16 |
| sleep_debt, sleep_quality, hunger_trend, food_security, work_deadline_pressure, commute_minutes_pressure | R32 |
| shower_due, kitchen_cleaning_need, entertainment_novelty_need, cash_reserve_pressure, transport_availability | R64 |

实际行为并没有在每次 frontier 扩展后都单调改善。这与边际收益递减相容，但 benchmark 太小，不能据此推断一般性的认知规律。

## 最小测试 Resource Set

预注册门槛要求：每个正向指标都必须与 matched best observed value 的差距不超过 0.05，同时 critical miss 与观测最小值的差距不超过 0.05。

没有任何一个测试层级同时满足全部门槛：

`MINIMUM_TESTED_RESOURCE_SET = UNRESOLVED`。

这意味着实验不能声称 R8 或 R16 是最小集合。33 组 matched quadruples 使该结果具有有意义的描述性价值，但仍不足以关闭最小集合选择问题。

## Resource Overload 信号

`RESOURCE_OVERLOAD_SIGNAL = NO`。

没有任何一次扩展达到预注册的负向 overload 条件：alignment 下降超过 0.03，或者 critical miss 上升超过 0.03。R64 是本次 matched alignment 最高且 critical-miss 最低的层级，但也是上下文成本最高的层级。

`LOW_MARGINAL_RETURN_STARTS_AT = R32`，因为 R16→R32 增加了成本，却没有在 alignment、rule executability 或 held-out share 中获得至少 0.03 的正向提升。

## 局限

* 只有一个 provider 和一个成功后端模型；18 次 timeout 仍然只是 provider 观测。
* 仅两次重复、24 个固定单请求状态；不做统计置信结论。
* 合成的 ResourceTruth 值和确定性的 acceptable sets 是工程构造，不是测量得到的人类内部状态。
* scorer 的 alignment 与 critical-miss 指标是 benchmark adequacy contracts，不是 LLM judge，也不是人类真值 oracle。
* R1 prior 和 held-out scoring 复用了既有 A2 TRAIN/EVAL split，但没有任何 diary text 进入 prompt。
* 本次运行不测试全天连续性、身份/库存进度、重复重放、多 Agent 交互、Q5 scaling 或本地 8B 行为。
* 某些 ActionType（WAIT/REST）保留在固定 action vocabulary 中，而当前 RuleEngine 可能拒绝不支持的 proposal；这里按 executability 如实计量，而不是静默 remap。
* family 行因为 timeout 存在不相等的成功样本数。

## 工程结论

```text
RESOURCE_SET_RESULT = PARTIALLY_RESOLVED
MINIMUM_TESTED_RESOURCE_SET = UNRESOLVED
LOW_MARGINAL_RETURN_STARTS_AT = R32
RESOURCE_OVERLOAD_SIGNAL = NO
```

当前证据支持的更窄结论是：在本 benchmark 中，R8 弱于 R16；按预注册成本阈值，R16→R32 表现为低边际收益；R64 是本次 matched 条件下观察到的最佳层级，但既不是 gold standard，也不是已确认的最小集合。没有任何结论声称 Agent 或人类“需要”16、32 或 64 个 Resource。

## 下一步

Q4 Attempt 1 到此 **STOP**。在用户审阅这些数据之前，不启动 Q5、action-set expansion、Activity Commitment、本地 8B、hybrid-object 工作或全天连续性。

## 来源与安全

* Q4 分支基于 Q3 commit `20f5f0c0e6f1aa830075981dc87f9852d356460d`。
* 配置：`config/experimental/resource_set_q4_v1.yaml`。
* 离线 artifact：`run/evaluation/resource_set_size/offline_20260918T081546324092Z/`。
* smoke artifact：`run/evaluation/resource_set_size/real_q4_attempt_1_smoke_20260918T081701224684Z/`。
* full artifact：`run/evaluation/resource_set_size/real_q4_attempt_1_full_20260918T081859853289Z/`。
* 原始 prompts、原始 completions、hidden reasoning、Authorization headers 与 secrets：均未存储。
* Q3 文档与 Q3 分支：未修改。
* 生产 WorldState、RuleEngine 与 A2 profile：未修改。
