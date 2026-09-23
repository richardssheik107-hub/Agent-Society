# 中文文档总目录

整理基准：2026-09-23。主线内容基于 `2351b8159fe1d0767d1377741590c36b00cd20a0`；Q6.1/Q6.2 分支内容核对至 `51cdf5c8b1bb0d0618dba41c6b1d9511fd6ba624`。后续提交不自动视为已验收。

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
| 人工审核 | [待决事项总表](review/README.md)、[讨论单与决策记录](review/decisions.md) |
| 前置阶段 | [基础闭环](stages/00_foundation.md)、[发呆与最小上下文](stages/01_idle_context.md)、[真人日记与行为校准](stages/02_behavior_data.md) |
| 三个会议问题 | [Q3 对象集](studies/q3_object_set.md)、[Q4 可见状态](studies/q4_resource_visibility.md)、[Q5 规则扩展](studies/q5_rule_scaling.md) |
| 持续运行 | [Q6 长期事实](studies/q6_continuity.md)、[Q6.1 真实短链](studies/q61_real_pilot.md)、[Q6.2 可执行活动投影](studies/q62_action_projection.md) |
| 工程参考 | [架构职责](current/architecture.md)、[仓库模块地图](current/repository.md)、[运行手册](current/runbook.md)、[分支状态](current/branches.md) |
| 查词与追溯 | [术语及指标](reference/glossary.md)、[证据登记](reference/evidence.md)、[删除与迁移记录](reference/cleanup.md) |

## 怎样理解状态标签

“主线已有”是代码位置，不等于行为已证明；“分支已验证”必须同时写提交和测试范围；“报告记载”不等于本轮重跑；“待验证”不能改写成工程结论；“待人工确认”不是已批准。

所有正常阅读链接都指向中文说明。英文类名、变量名和机器标签保留以便搜代码。旧英文报告不再作为阅读必经路径，其原始字节通过证据登记中的固定提交追溯。

## 快速定位代码

按问题用 `Q3`、`Q4`、`Q5`、`Q6.1`、`Q6.2` 搜文档；按故障用 `ITEM_NOT_OWNED`、`MAX_DECISIONS`、`PROVIDER_ERROR`；按机制用“幂等”“只读投影”“人物—对象状态”。每份问题文档都列出相关模块，详见[仓库地图](current/repository.md)。
