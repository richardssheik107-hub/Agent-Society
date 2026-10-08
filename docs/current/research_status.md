# 按问题检索：研究状态与结论边界

更新：2026-10-08。Q6.1/Q6.2 原工程已通过 PR #4 合入 main；本轮从最新 main `53b1244ac0f8562fd01fe8439e73ca900a40dd8c` 实施独立 M2。PR #6 固定研究与 PR #7 事后审计保持 OPEN，以固定 Git 历史引用，不称为已合入本轮 main。会议三问仍为 Q3、Q4、Q5，编号沿用历史，不补造 Q1/Q2。

| 问题 | 实验证据与当前回答 | 状态 | 中文详解 | 人工讨论 |
|---|---|---|---|---|
| 对象能否完全由模型自由生成？ | 43 组共同案例 A/B/C=13/43、43/43、38/43；Catalog + Top-K 为参考 | 受测单步支持，Hybrid 未收口 | [Q3 对象集](../studies/q3_object_set.md) | [D-03](../review/decisions.md#d-03) |
| 每次需要看多少状态？ | R8/R16/R32/R64 固定真值、改变可见字段，没有一档满足全部最小门槛 | 最小值未知 | [Q4 可见状态](../studies/q4_resource_visibility.md) | [D-04](../review/decisions.md#d-04) |
| 千万对象需要显式规则图吗？ | 类型—规则21、能力—类型28项不随虚拟对象数增长 | 结构门槛通过，非真实数据库完成 | [Q5 规则扩展](../studies/q5_rule_scaling.md) | [D-06](../review/decisions.md#d-06) |
| 为什么发呆、频繁决策？ | 动作缺失、时长、拒绝、即时动作链、先验与服务截断分开 | 有分解与局部证据，非全天正常 | [A 系列](../stages/01_idle_context.md) | [D-05](../review/decisions.md#d-05) |
| 真人日记值得引入吗？ | Core5→Core7 全成人分钟覆盖82.17%→93.00%，不取代交易合法性 | 结构校准有据，代表性有限 | [B 系列](../stages/02_behavior_data.md) | [D-07](../review/decisions.md#d-07) |
| 能记住进度和拥有物吗？ | 持久状态、事务、幂等与7/30天脚本验收 | 受测工程机制通过 | [Q6](../studies/q6_continuity.md) | [D-05](../review/decisions.md#d-05) |
| 真实模型能继续用更新状态吗？ | Q6.1 三次完成、一次规则拒绝；观察一致不等于因果利用 | 代码已入 main；原实验结论仍证据不足 | [Q6.1](../studies/q61_real_pilot.md) | [D-01](../review/decisions.md#d-01) |
| 提前给合法候选有用吗？ | 原主线有投影与八请求上限 A/B 入口；PR #6 固定 12 状态、24 配对、48 单元已有历史真实结果 | NO_CLEAR_DIFFERENCE 保持；研究分支未在本轮合并 | [原 Q6.2 工程](../studies/q62_action_projection.md)、[冻结研究](https://github.com/richardssheik107-hub/Agent-Society/blob/b7c6d503dc09c0c2d7dc32467b277a23a1a26404/docs/studies/q62_action_projection.md) | [D-01](../review/decisions.md#d-01) |
| 状态后果是不是整体行为更好？ | PR #7 的 M1.5 对 22 个完整配对做离线净变化审计；宏活动粒度不同 | EXPLORATORY_POST_HOC；不能改写 B 获胜 | [历史审计](https://github.com/richardssheik107-hub/Agent-Society/blob/016fffe28b4a296a24a1ee8c8c4adc63b7394383/docs/studies/q62_outcome_audit.md) | [D-09](../review/decisions.md#d-09)，PENDING |
| 对象存在但未拥有时，能合法获取后使用吗？ | M2 opt-in ACQUIRE 复用 BUY 与 controller；同地零分钟、异地 MOVE→持久 BUY0→交易，重开后独立 PLAY | 实验机制已实现；offline 17/17 PASS；完整验收与 CI 见账本，生产默认 DISABLED | [M2 获取闭环](../studies/m2_object_acquisition.md)、[当前验收](acceptance.md) | [D-02](../review/decisions.md#d-02) 为 NO；人的行为适当性 NOT_TESTED |

证据按报告和代码提交冻结，见[验收账本](acceptance.md)与[证据登记](../reference/evidence.md)。测试数、请求数、成功活动数不能互换。

本轮 LLM_CALLS=0、PROVIDER_REQUESTS=0；不读取 `.env`，不构造真实 provider，不增加 Q6.2 样本，不修改 M1.5 历史产物。下一步真实 ACQUIRE 短链须申请新版本和新预算，不能把工程 READY 当作人工产品语义批准。

只读一份：[三问综合稿](three_core_questions_experiment_summary.md)。按路线回顾：[阶段索引](../stages/README.md)。
