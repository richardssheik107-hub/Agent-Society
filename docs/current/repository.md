# 仓库地图：研究问题对应哪些代码和文档

盘点范围：父仓库跟踪文件、main 与 Q6 研究分支、文档引用、历史报告和验收记录。没有逐行证明全部业务代码正确，也没有读取用户本机被忽略的密钥/数据。

## 代码检索地图

以下目录均相对 `src/social_sim/`。

| 模块 | 对应阶段/作用 | 中文入口 |
|---|---|---|
| world、actions、rules、effects、reducer、execution、events | 原确定性世界及逐动作闭环 | [基础阶段](../stages/00_foundation.md) |
| router、context、decision | 只读观察、紧凑上下文、安全客户端 | [架构](architecture.md) |
| daily、evaluation、a2_final、a2_closure | 中性日、轨迹、先验选择及发呆审计 | [A 系列](../stages/01_idle_context.md) |
| human_data、calibration、behavior_prior | 真人日记 ETL、映射、时长及先验 | [B 系列](../stages/02_behavior_data.md) |
| object_benchmark | Q3 三方案单步对照 | [Q3](../studies/q3_object_set.md) |
| resource_benchmark | Q4 状态可见性 | [Q4](../studies/q4_resource_visibility.md) |
| rule_scaling | Q5 虚拟对象规则索引 | [Q5](../studies/q5_rule_scaling.md) |
| continuity | Q6 状态与活动控制器；main 已有基础 | [Q6](../studies/q6_continuity.md) |
| provider_runtime；continuity 中 q6_1/q6_2/action_projection | Q6.1/Q6.2 分支新增，尚非 main 业务代码 | [Q6.1](../studies/q61_real_pilot.md)、[Q6.2](../studies/q62_action_projection.md) |

`tests/` 保留旧回归，`config/` 保留冻结实验参数，`scripts/` 按阶段运行；`smoke/` 的历史入口不等于现行任务。两个写死旧 A2 实验 ID 的工具仍保持停用，原代码留在 `archive/legacy_tools/`，本轮不删除业务复现代码。

## 新文档结构

```text
docs/
  README.md       总目录
  current/        当前状态、唯一计划、架构和运行说明
  stages/         按阶段回顾基础、A 系列、B 系列
  studies/        按问题保存 Q3—Q6.2 的实验档案
  reports/        可直接用于汇报的材料
  review/         人工审核、备选方案与决策记录
  reference/      术语、来源、清理映射、导航目录
```

## 本轮保护范围

不改 `src/`、实验配置、原测试、业务 runner、上游子模块和两份 `delivery.*.jsonl`。只改文档、文档审计与新增文档测试/工作流。没有调用真实模型、没有重算历史实验结果。

过时跳转和旧阶段计划从当前树删除，不再搬一份重复档案；原始报告保留在固定 Git 提交，可从[证据登记](../reference/evidence.md)恢复。删除映射见[清理记录](../reference/cleanup.md)。
