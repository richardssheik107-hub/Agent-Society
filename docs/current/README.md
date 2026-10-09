# 当前研究工作台

更新：2026-10-09。Q6.2 固定真实面板（PR #6）和 M1.5 离线审计（PR #7）已经合入 `main`；M2 通过独立工程验收及联合回归，也已通过 PR #8 正式合入 `main`。`ACQUIRE` 仅可选启用，生产默认禁用，新增真实请求0。[中文总目录](../README.md)。

## 现在先看什么

**先看[完整研究计划](plan.md)。** 新计划将工作分为M0—M6：证据检查、Q6.2真实对照、对象获取、Resource相关投影、本地模型对照、长期行为验收、真实目录与规则维护。每阶段都有进入条件、交付、退出标准和当前状态。

**接着确认[D-01](../review/decisions.md#d-01)。** 旧 main 双短链 A/B 入口最多八请求，仍未真实运行；Q6.2 固定状态面板已完成唯一真实 session，主结论 NO_CLEAR_DIFFERENCE。两项研究不能混为一项，原面板许可已用完；本轮 M2 不发送模型请求。

**并行讨论[D-02](../review/decisions.md#d-02)与[D-09](../review/decisions.md#d-09)。** [M2 获取机制](../studies/m2_object_acquisition.md)已实验性实现，但是否进入生产默认仍待批准；人的行为适当性也未验收。不能为了漂亮结果免费赋予物品、强禁第二餐或强制日程。

## 已完成，不要反复重做

Q6.1真实四次提案为旅行、两次进餐、未拥有游戏的PLAY被拒绝；原始artifact已核验，三次活动完成，原正式结论仍为INSUFFICIENT_EVIDENCE。Q6.2只读投影、双世界A/B和零请求试运行已入main，但模型收益尚未证明。不默认重建有效环境或重跑q61-runtime-01。

## 检索入口

| 目的 | 中文材料 |
|---|---|
| 本轮具体怎么开始 | [计划T-01—T-05](plan.md#十一下一轮可直接交接的任务包) |
| 回忆三个会议问题 | [综合实验说明](three_core_questions_experiment_summary.md) |
| 查看真实执行与状态反馈 | [Q6.1](../studies/q61_real_pilot.md) |
| 查看候选投影与现有A/B | [Q6.2](../studies/q62_action_projection.md) |
| 查看合法获取与后续使用 | [M2 获取闭环](../studies/m2_object_acquisition.md) |
| 需要人拍板 | [人工审核](../review/README.md)、[决定记录](../review/decisions.md) |
| 查命令与环境 | [运行手册](runbook.md) |
| 查版本和历史证据 | [分支状态](branches.md)、[验收账本](acceptance.md) |

本次实现独立、可选启用的 M2，并执行零模型工程验收；当前提交与完整 CI 状态见[验收账本](acceptance.md)。没有新增真实请求，也没有改写旧研究结论。
