# 文档清理记录与旧文件检索

日期：2026-09-23。用户要求清理过时文档、集中汇报与人工审核，并按阶段/问题组织中文阅读。

## 本次具体处理

整理前 main 中有 68 份 docs Markdown：29 份根目录历史跳转、30 份 archive 原文、9 份 current 文档。当前树删除前两类共 59 份；其有效内容归纳到阶段/问题档案，不继续保留大量两行跳转或重复“下一步”。9 个常用 current 路径重写保留，包括用户常用的 research_status 和三问综合稿。

新增 18 份阶段、问题、汇报、审核及参考说明后，现行 docs Markdown 为 27 份。原始报告和旧计划并非销毁：固定 Git 提交保持不变，使用[证据登记](evidence.md)恢复准确字节。此次不改写历史、不删除旧实验结果提交、不操作本机 run 数据。

## 旧文件名对应哪里

| 旧名称/范围 | 新的中文阅读位置 | 原因 |
|---|---|---|
| agentsociety2_bootstrap、architecture_8b、phase*、lunch_closed_loop | [基础阶段](../stages/00_foundation.md) | 阶段限制与旧下一步过期，保留关键职责 |
| research_a1*、research_a2*、research_questions_final_answer | [A 系列](../stages/01_idle_context.md) | 合并单步与连续性证据，避免多个最终版 |
| research_b1* | [B 系列](../stages/02_behavior_data.md) | 合并来源、筛选、分类、时长及边界 |
| research_q3* | [Q3](../studies/q3_object_set.md) | 统一配对分母与字段来源解释 |
| research_q4_resource_set_size | [Q4](../studies/q4_resource_visibility.md) | 统一最小集合、指标补数和 NA 边界 |
| research_q5_rule_engine_scaling | [Q5](../studies/q5_rule_scaling.md) | 明确虚拟索引与真实数据库边界 |
| meeting_2026-09-18_world_model_architecture_notes_zh | [人工讨论单](../review/decisions.md) | 会议是部分记录，不能冒充全部已验证设计 |
| README_before_cleanup | [总目录](../README.md) | Phase0 状态已过期 |

机器映射为 `cleanup_map.json`；`audit_documentation.py` 会枚举整理前 docs 的每个路径、原 blob、处理方式与替代目标，输出逐文件 inventory，确保没有文件靠“没读到”就被删除。

## 不变范围与审计迁移

业务源码、实验配置、原测试、上游 gitlink 和 delivery 文件不动。原档案审计原本要求旧报告的工作树副本字节不变；用户现在要求删除过时副本，因此显式迁移为固定 Git 原文可恢复性/内容指纹校验，仍核对原 32 份，不直接关闭检查。

两个停用的一次性工具代码仍在 archive/legacy_tools，继续逐字节对照；旧文档的原始字节改从冻结 Git 提交读取，并报告 SHA256。正常阅读只链接新的中文文件。完整历史缺失时审计失败，不把无法检查写成通过。

## 分支影响

这次从 main 单独整理文档，不合并研究 PR #4 的业务代码。PR #4 后续同步时应保留本目录结构；发生删除/修改冲突必须人工合并，不能让旧档案重新覆盖当前导航。

## 本轮验收记录

本页中的 68→27 是目录盘点目标及逐文件映射口径。实际链接、中文标题、清单覆盖、Git 原文与受保护代码检查以本轮 CI 结果为准，运行记录将在完成后追加。真实 provider 请求为 0，不生成新的科学实验结论。
