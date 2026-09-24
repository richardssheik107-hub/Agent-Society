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

机器映射为 `cleanup_map.json`；`audit_documentation.py` 会枚举整理前 docs 的每个路径、原 blob、处理方式与替代目标，输出逐文件 inventory，确保每一项删除都有记录和中文替代位置。

## 不变范围与审计迁移

业务源码、实验配置、原测试、上游 gitlink 和 delivery 文件不动。原档案审计原本要求旧报告的工作树副本字节不变；用户现在要求删除过时副本，因此显式迁移为固定 Git 原文可恢复性/内容指纹校验，仍核对原 32 份，不直接关闭检查。

两个停用的一次性工具代码仍在 archive/legacy_tools，继续逐字节对照；旧文档的原始字节改从冻结 Git 提交读取，并报告 SHA256。正常阅读只链接新的中文文件。完整历史缺失时审计失败，不把无法检查写成通过。

## 分支影响

文档整理最初独立于研究 PR #4。2026-09-24 合并 Q6.1/Q6.2 时已按本策略处理冲突：保留当前中文目录和 pinned Git history 保护，只带入研究业务代码/测试；旧 archive、跳转和重复计划没有恢复。

## 本轮实际验收（2026-09-23）

文档与审计代码提交为 `2eaf4d34b4fdc9af58f10c9384836ecb46da6422`；测试使用与当时 main 的预合并提交 `53000dfb15bb9dc336b40f1f980280be0bc0f6f1`。本节是通过后的结果回填，不把后续文档提交当成下面运行的代码版本。

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 中文目录、链接、锚点、可达性、旧文件迁移覆盖 | PASS；68 份旧文档逐项登记，59 份退出当前树，27 份现行中文文档 | 文档 CI 35843575445 |
| 文档和仓库专项 | 19 passed（15 项新增文档测试、4 项既有仓库质量测试） | 同上，Python 3.12.14 |
| 原32项历史来源与受保护代码/数据 | PASS；历史原文可恢复、工具字节一致 | 同上审计 JSON |
| 文档审计工具 Ruff | PASS | 同上 |
| 全库回归 | 570 passed，8 skipped | 仓库 CI 35843575443 |
| 实际固定上游 AS2 适配器 | AS2_CONTINUITY_ADAPTER_PASS，0 LLM/provider calls | 同上 |
| 七天/三十天脚本工程验证 | PASS | 同上 core-contract |

八项跳过仍属于未提交到 Git 的历史真人语料：test_a2_final、test_behavior_prior_context、test_behavior_prior_index；没有用假数据替代。570 是当前主线加文档测试的范围，研究分支另有新增测试，因此不能与研究分支此前的 660 直接比较增减。

运行记录：[中文文档 CI](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35843575445)、[主线范围回归 CI](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35843575443)。

文档审计产物 ID `10741723786` 包含 navigation.json（逐文件迁移清单）、repository.json（32项原文指纹与保护检查）、tests.xml；回归产物 ID `10742084782` 包含测试结果、依赖和上游版本。Actions 下载产物可能过期，关键运行 ID 与结果保留于此。

本轮未读取本地凭据、未调用真实模型、未生成新的科学实验结果。全部业务源码、原实验配置、原业务测试和业务 runner 的差异已核对为零。


## Q6.1/Q6.2 合并补记（2026-09-24）

研究 PR #4 最终 merge commit 为 `cce3e7bd850f72faf0efa41017491d392b00ee11`。第一次集成 CI 暴露 1 个旧版文档映射测试，修复 `bea7dbf64fd8a61eced09820503b46ae3f56ad59` 后最终运行 `35951841827` 全绿：full regression 685 passed、8 skipped，AS2 PASS，真实 provider 请求 0。该兼容修复强化了当前“删除工作树旧副本、从固定 Git 历史恢复原文”的策略，没有重新引入旧档案。
