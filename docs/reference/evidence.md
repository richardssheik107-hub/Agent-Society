# 证据登记与原文追溯

本轮正常阅读入口均为中文。旧英文计划和报告从当前文档树退出，但**Git 历史不重写**。以下编号可从中文档案找到实验出处；精确原文用固定提交和路径恢复，不依赖旧分支名继续存在。

<a id="foundation"></a>
## E-BASE｜基础闭环与会议原始议题

原始 Phase 文档、启动文档、短上下文设计：固定提交 `7e537cef22fca73c7e1cc6be22d55a829aed6d9a` 的 `docs/`。包含 Phase1/2/3、午餐、Phase6.5、Phase7、Phase8A。会议片段整理位于提交 `bbebaf6720e8fadf25e4de0ee5b62021ae84c358` 的 `docs/meeting_2026-09-18_world_model_architecture_notes_zh.md`；它是部分会议记录，不是完整会议转录。

中文替代阅读：[基础阶段](../stages/00_foundation.md)、[人工讨论](../review/README.md)。

<a id="a2"></a>
## E-A2｜发呆、上下文与语料先验

固定提交 `7e537cef22fca73c7e1cc6be22d55a829aed6d9a` 的 `docs/research_a1_*`、`research_a2_*`、`research_questions_final_answer.md`。A2-Final 实验执行基线 `9b5e6e33f0ea9046e596a649562a1737e98c8491`；主结果本机目录 `run/evaluation/a2_final/real_20260917T101056138346Z/`；Closure 只读审计目录 `run/evaluation/a2_closure/audit_20260917T111536910509Z/`。

中文替代阅读：[A 系列](../stages/01_idle_context.md)。

<a id="b1"></a>
## E-B1｜真人日记来源与 Core7 校准

同一冻结 Q5 提交中的 `docs/research_b1_*`、`research_b1_1_nhaps_ahtus_calibration.md`、`research_b1_2_behavior_ontology_duration_calibration.md`。NHAPS/AHTUS 原 ZIP SHA256：`030ae6009bf30316379ec49c8da174f85b4726dc6a3c64f202617c3285ea07ca`，文件大小 3,208,441 字节。这个校验和不是重新下载的声明。

中文替代阅读：[B 系列](../stages/02_behavior_data.md)。原始日记与完整 CSV 在本机受忽略路径；本轮未获取或上传。

<a id="q3"></a>
## E-Q3｜对象集必要性

原始英文报告：提交 `7e537cef22fca73c7e1cc6be22d55a829aed6d9a`，路径 `docs/research_q3_object_set_necessity_real_attempt2.md`。整理前中文阅读版：提交 `2351b8159fe1d0767d1377741590c36b00cd20a0`，路径 `docs/archive/2026-09-20/research_q3_object_set_necessity_real_attempt2.md`。

完整运行目录：`run/evaluation/object_set_necessity/real_attempt_2_20260918T071513907540Z/`。smoke 原结果与 posthoc_summary 分开保留，不重新请求。中文档案：[Q3](../studies/q3_object_set.md)。

<a id="q4"></a>
## E-Q4｜Resource 可见性

原始报告：冻结 Q5 提交的 `docs/research_q4_resource_set_size.md`；中文阅读版：整理前 main 提交的 `docs/archive/2026-09-20/research_q4_resource_set_size.md`。Q4 阶段提交 `9aa5d96b4339aac6affbb783a913c2f4a366c3ac`，配置 `config/experimental/resource_set_q4_v1.yaml`。

本机全量结果：`run/evaluation/resource_set_size/real_q4_attempt_1_full_20260918T081859853289Z/`。本轮没有原始逐行输出，因此不补造置信区间或 NA 分母。中文档案：[Q4](../studies/q4_resource_visibility.md)。

<a id="q5"></a>
## E-Q5｜规则规模微基准

冻结提交 `7e537cef22fca73c7e1cc6be22d55a829aed6d9a` 的 `docs/research_q5_rule_engine_scaling.md`；中文阅读版位于整理前 main 的对应 archive 路径。正式基准起始提交 `afd9f9dc8ce80e3d793714d46e5d888a012dadb5`，本机产物 `run/evaluation/rule_engine_scaling/q5_20260919T130054787068Z/summary.json`。

中文档案：[Q5](../studies/q5_rule_scaling.md)。

<a id="q6"></a>
## E-Q6｜主线长期事实验收

整理前 main `2351b8159fe1d0767d1377741590c36b00cd20a0` 的 `docs/current/acceptance.md`、`architecture.md`、`runbook.md`。初版已测代码 `86ee049…`，文档交付 `534f1e396e7c2e2d4e7c62a73b28f0e45c6ba560`；本登记不把缩写当完整 Git 标识使用。

中文档案：[Q6](../studies/q6_continuity.md)。

<a id="q61"></a>
## E-Q61｜真实短链与运行时失败历史

研究分支报告核对至 `51cdf5c8b1bb0d0618dba41c6b1d9511fd6ba624`：`docs/current/q6_1_real_continuity_pilot.md`、`q6_1_provider_runtime.md`、`q6_1_provider_runtime_acceptance.md`。

Attempt1 执行 `1fe4ba06893d862342bca63fd3868d3ac4e9a8b4`，结果 `d8e7ec0b61ae4d3c22648f5f1988eee5103f5265`；Attempt2 执行 `50371b139afe18e94ab9b2594f1a9030d34ff360`，结果 `c3c41efeb0ec2fb860ad0c4463385082d515c269`；Attempt3 执行 `54ed48f93f452718e59bda1368e15737f173084c`，结果 `a338f0b3171bf1692032bfd6818f47620fba3fdb`。

本机原 session：`run/evaluation/q6_1_provider_runtime/q61-runtime-01/`。中文档案：[Q6.1](../studies/q61_real_pilot.md)。

<a id="q62"></a>
## E-Q62｜投影实现与离线验收

代码提交 `1f4a1774898bb307c54852b0b7173c3553c203dd`；文档 `51cdf5c8b1bb0d0618dba41c6b1d9511fd6ba624` 的 `docs/current/q6_2_action_projection.md` 与 `q6_2_acceptance.md`。GitHub Actions 运行 `35680426146`；预合并提交 `1e0a0f7f8f8f06281f438d3eee39966f7d1df4b0`。八个历史数据测试跳过不计为通过。

当前只确认报告序列回放，未看到本机原 artifact 核验成功记录，也没有真实 A/B 结果。中文档案：[Q6.2](../studies/q62_action_projection.md)。

## 恢复原文而不污染当前工作树

完整历史克隆中使用只读命令，例如：

```bash
git show 7e537cef22fca73c7e1cc6be22d55a829aed6d9a:docs/research_q3_object_set_necessity_real_attempt2.md
git show 2351b8159fe1d0767d1377741590c36b00cd20a0:docs/archive/2026-09-20/research_q3_object_set_necessity_real_attempt2.md
```

历史原文是证据，不是当前执行指令。32 份旧原文/工具的固定来源继续由审计检查；原文从工作树归档改为 Git 历史保存的规则在[清理记录](cleanup.md)说明。
