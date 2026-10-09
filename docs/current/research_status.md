# 按问题检索：研究状态与结论边界

更新：2026-10-09。Q6.2、M1.5、M2 已合入 main。当前用户批准 M5 长周期工程与离线验收，D-02 限定 opt-in 获取、D-09 三层评价已批准；真实预算 0。原 Q6.2 主结论 `NO_CLEAR_DIFFERENCE`，M1.5 需求适当性 `UNRESOLVED`，真实自主长期行为尚未验证。历史问题编号沿用，不补造 Q1/Q2。

| 问题 | 实验证据与当前回答 | 状态 | 中文详解 | 人工讨论 |
|---|---|---|---|---|
| 对象能否完全由模型自由生成？ | 43 组共同案例 A/B/C=13/43、43/43、38/43；Catalog + Top-K 为参考 | 受测单步支持，Hybrid 未收口 | [Q3 对象集](../studies/q3_object_set.md) | [D-03](../review/decisions.md#d-03) |
| 每次需要看多少状态？ | R8/R16/R32/R64 固定真值、改变可见字段，没有一档满足全部最小门槛 | 最小值未知 | [Q4 可见状态](../studies/q4_resource_visibility.md) | [D-04](../review/decisions.md#d-04) |
| 千万对象需要显式规则图吗？ | 类型—规则21、能力—类型28项不随虚拟对象数增长 | 结构门槛通过，非真实数据库完成 | [Q5 规则扩展](../studies/q5_rule_scaling.md) | [D-06](../review/decisions.md#d-06) |
| 为什么发呆、频繁决策？ | 动作缺失、时长、拒绝、即时动作链、先验与服务截断分开 | 有分解与局部证据，非全天正常 | [A 系列](../stages/01_idle_context.md) | [D-05](../review/decisions.md#d-05) |
| 真人日记值得引入吗？ | Core5→Core7 全成人分钟覆盖82.17%→93.00%，不取代交易合法性 | 结构校准有据，代表性有限 | [B 系列](../stages/02_behavior_data.md) | [D-07](../review/decisions.md#d-07) |
| 能记住进度和拥有物吗？ | 持久状态、事务、幂等与7/30天脚本验收 | 受测工程机制通过 | [Q6](../studies/q6_continuity.md) | [D-05](../review/decisions.md#d-05) |
| 真实模型能继续用更新状态吗？ | Q6.1 三次完成、一次规则拒绝；观察一致不等于因果利用 | 代码已入 main；原实验结论仍证据不足 | [Q6.1](../studies/q61_real_pilot.md) | [D-01](../review/decisions.md#d-01) |
| 提前给合法候选有用吗？ | 旧8-call短链未运行；固定v2已完成48尝试、46有效/完成、22完整配对，两臂拒绝均0 | 原主指标 `NO_CLEAR_DIFFERENCE`；不是等价证明 | [Q6.2](../studies/q62_action_projection.md) | [D-01](../review/decisions.md#d-01)、[D-02](../review/decisions.md#d-02) |
| 合法且完成以后，人物状态怎样变？ | M1.5只读审计原48单元/24配对；TRAVEL准备步骤与MEAL宏活动、客观delta及提示混杂分开 | `EXPLORATORY_POST_HOC`；需求适当性 `UNRESOLVED`，不修改旧主结论 | [M1.5结果审计](../studies/q62_outcome_audit.md)、[人工盲审包](../studies/q62_outcome_human_review.md) | [D-09](../review/decisions.md#d-09) |

当前边界：原 v2 为 **48 attempts**；本轮 `NEW_REAL_PROVIDER_REQUESTS=0`。两个超时配对 p014/p021 的行为后果保持 `UNKNOWN`，不补0、不补请求。`HUMAN_REVIEW_COMPLETED=NO`；`HUMAN_NEED_SATISFACTION_CONCLUSION=UNRESOLVED`；长期真人相似性 `NOT_TESTED`；Q6.1 `INSUFFICIENT_EVIDENCE` 均不改变。客观饥饿、精力、金钱和模拟时间变化不合成为未经批准的人类合理性总分。

| 未拥有对象怎样获取并在之后使用？ | M2 可选 ACQUIRE 复用原 BUY、交易/承诺/重启；17/17 历史离线场景、零模型请求 | D-02 新批准限定 opt-in；全局默认关闭，真实自主未测 | [M2 合法获取闭环](../studies/m2_object_acquisition.md) | [D-02](../review/decisions.md#d-02) |
| 新 Runtime 怎样连续运行多日并可恢复？ | 复用原世界，独立会话、决策/微步骤、持久收据、每日 checkpoint 与多维评价 | 新七天/三十天运行的实测数字单独登记，不复用旧脚本成绩；真人适当性 UNRESOLVED | [M5 长周期系统](../studies/m5_long_horizon_autonomy.md) | [D-09](../review/decisions.md#d-09) |

证据按报告和代码提交冻结，见[验收账本](acceptance.md)与[证据登记](../reference/evidence.md)。测试数、请求数、成功活动数不能互换。

只读一份：[三问综合稿](three_core_questions_experiment_summary.md)。按路线回顾：[阶段索引](../stages/README.md)。
