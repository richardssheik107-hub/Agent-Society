# 按问题检索：研究状态与结论边界

更新：2026-09-24。Q6.1/Q6.2 代码已通过 PR #4 合入 `main`（merge `cce3e7bd850f72faf0efa41017491d392b00ee11`）。会议三问为 Q3、Q4、Q5；早期发呆与数据来源是 A/B 系列；Q6 补连续性。编号沿用历史，不补造 Q1/Q2 实验。

| 问题 | 实验证据与当前回答 | 状态 | 中文详解 | 人工讨论 |
|---|---|---|---|---|
| 对象能否完全由模型自由生成？ | 43 组共同案例 A/B/C=13/43、43/43、38/43；Catalog + Top-K 为参考 | 受测单步支持，Hybrid 未收口 | [Q3 对象集](../studies/q3_object_set.md) | [D-03](../review/decisions.md#d-03) |
| 每次需要看多少状态？ | R8/R16/R32/R64 固定真值、改变可见字段，没有一档满足全部最小门槛 | 最小值未知 | [Q4 可见状态](../studies/q4_resource_visibility.md) | [D-04](../review/decisions.md#d-04) |
| 千万对象需要显式规则图吗？ | 类型—规则21、能力—类型28项不随虚拟对象数增长 | 结构门槛通过，非真实数据库完成 | [Q5 规则扩展](../studies/q5_rule_scaling.md) | [D-06](../review/decisions.md#d-06) |
| 为什么发呆、频繁决策？ | 动作缺失、时长、拒绝、即时动作链、先验与服务截断分开 | 有分解与局部证据，非全天正常 | [A 系列](../stages/01_idle_context.md) | [D-05](../review/decisions.md#d-05) |
| 真人日记值得引入吗？ | Core5→Core7 全成人分钟覆盖82.17%→93.00%，不取代交易合法性 | 结构校准有据，代表性有限 | [B 系列](../stages/02_behavior_data.md) | [D-07](../review/decisions.md#d-07) |
| 能记住进度和拥有物吗？ | 持久状态、事务、幂等与7/30天脚本验收 | 受测工程机制通过 | [Q6](../studies/q6_continuity.md) | [D-05](../review/decisions.md#d-05) |
| 真实模型能继续用更新状态吗？ | Q6.1 三次完成、一次规则拒绝；观察一致不等于因果利用 | 代码已入 main；原实验结论仍证据不足 | [Q6.1](../studies/q61_real_pilot.md) | [D-01](../review/decisions.md#d-01) |
| 提前给合法候选有用吗？ | Q6.2 投影、原产物核验、八请求上限 A/B 入口及 dry-run 已准备 | 工程已入 main；真实 A/B 未运行 | [Q6.2](../studies/q62_action_projection.md) | [D-01](../review/decisions.md#d-01)、[D-02](../review/decisions.md#d-02) |

证据按报告和代码提交冻结，见[验收账本](acceptance.md)与[证据登记](../reference/evidence.md)。测试数、请求数、成功活动数不能互换。

只读一份：[三问综合稿](three_core_questions_experiment_summary.md)。按路线回顾：[阶段索引](../stages/README.md)。
