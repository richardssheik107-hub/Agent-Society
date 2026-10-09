# 中文文档总目录

更新：2026-10-09。Q6.2、M1.5、M2 已合入 main；本轮用户追加批准 D-02 限定 opt-in 获取与 D-09 三层评价，授权交付 [M5 长周期 Runtime](studies/m5_long_horizon_autonomy.md)。**全局 ACQUIRE 默认仍关闭，新的真实请求预算仍为 0**。原 Q6.2 `NO_CLEAR_DIFFERENCE` 和 M1.5 `EXPLORATORY_POST_HOC` 不改写。

当前M5已实际完成10080/43200模拟分钟及6/29次恢复对照，属于合成自适应工程验收；查看[逐日结果与限制](studies/m5_long_horizon_autonomy.md)、[实测JSON](reference/m5_longrun_acceptance_results.json)、[启动/停止/恢复手册](current/runbook.md#m5-多日生活停止与恢复)。真实七天未运行，L3未人工审核。

历史 M1.5 是对已有真实证据的**事后探索性审计**，新增真实请求0：查看[中文客观结果与提示审计](studies/q62_outcome_audit.md)、[安全结果表](reference/q62_outcome_audit_results.json)及[人工盲审包](studies/q62_outcome_human_review.md)。需求变化不自动等于行为适当性，人工尚未标注；新评价结构见[D-09追加决定](review/decisions.md#d-09)，没有批准新的付费实验。

## 四种检索方式

| 入口 | 适合的问题 |
|---|---|
| [按阶段](stages/README.md) | 从基础闭环、A/B 数据研究，到 Q3—Q6.2，先后做了什么？ |
| [按研究问题](current/research_status.md) | 对象集要不要？状态给多少？千万规则怎么维护？长期进度怎么保存？ |
| [汇报专区](reports/README.md) | 哪些内容可以直接讲给导师和团队？ |
| [人工审核专区](review/README.md) | 现在需要人决定什么？需要哪些证据？未决定前不能做什么？ |

## 全部现行文档

| 分类 | 文档 |
|---|---|
| 当前状态 | [工作台](current/README.md)、[问题索引](current/research_status.md)、[唯一现行计划](current/plan.md)、[验收账本](current/acceptance.md) |
| 汇报 | [一分钟/五分钟汇报](reports/meeting_brief.md)、[三个会议问题综合说明](current/three_core_questions_experiment_summary.md) |
| 人工审核 | [待决事项总表](review/README.md)、[讨论单与决策记录](review/decisions.md)、[M1.5人工盲审包](studies/q62_outcome_human_review.md) |
| 前置阶段 | [基础闭环](stages/00_foundation.md)、[发呆与最小上下文](stages/01_idle_context.md)、[真人日记与行为校准](stages/02_behavior_data.md) |
| 三个会议问题 | [Q3 对象集](studies/q3_object_set.md)、[Q4 可见状态](studies/q4_resource_visibility.md)、[Q5 规则扩展](studies/q5_rule_scaling.md) |
| 持续运行 | [Q6 长期事实](studies/q6_continuity.md)、[Q6.1 真实短链](studies/q61_real_pilot.md)、[Q6.2 可执行活动投影](studies/q62_action_projection.md)、[M1.5行为结果与提示干预审计](studies/q62_outcome_audit.md)、[M2对象获取与使用闭环](studies/m2_object_acquisition.md)、[M5长周期Runtime](studies/m5_long_horizon_autonomy.md) |
| 工程参考 | [架构职责](current/architecture.md)、[仓库模块地图](current/repository.md)、[运行手册](current/runbook.md)、[分支状态](current/branches.md) |
| 查词与追溯 | [术语及指标](reference/glossary.md)、[证据登记](reference/evidence.md)、[删除与迁移记录](reference/cleanup.md) |

## 怎样理解状态标签

“代码已入主线”不等于研究结论已经成立；Q6.2 v2 许可已用完，研究主结论 `NO_CLEAR_DIFFERENCE` 不变；M1.5 属于 `EXPLORATORY_POST_HOC`，需求适当性 `UNRESOLVED`、人工盲审 `HUMAN_REVIEW_COMPLETED=NO`；M2 仅证明 opt-in 的工程闭环，生产默认 `DISABLED`，不得自动启动真实请求。

正常阅读链接均指向中文说明。英文类名、变量名和机器标签保留以便搜代码。旧英文报告不再作为阅读必经路径，其原始字节通过证据登记中的固定提交追溯。

## 快速定位代码

按问题用 Q3、Q4、Q5、Q6.1、Q6.2 搜文档；按故障用 ITEM_NOT_OWNED、MAX_DECISIONS、PROVIDER_ERROR；按机制用幂等、只读投影、人物—对象状态。每份问题文档列出对应模块，详见[仓库地图](current/repository.md)。
