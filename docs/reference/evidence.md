# 证据登记与原文追溯

正常阅读入口全部中文；旧原文退出当前树但Git历史不改写。以下固定提交/路径可恢复准确字节，不依赖旧分支名称存在。新增研究结果以代码/报告版本区别于本轮文档整理。

<a id="foundation"></a>
## E-BASE｜基础闭环与会议议题

原始Phase、启动、短上下文文档：固定提交 `7e537cef22fca73c7e1cc6be22d55a829aed6d9a` 的 `docs/`。包含Phase1/2/3、午餐、Phase6.5、Phase7、Phase8A。

会议片段为提交 `bbebaf6720e8fadf25e4de0ee5b62021ae84c358` 的 `docs/meeting_2026-09-18_world_model_architecture_notes_zh.md`；它不是整场完整转录。中文阅读：[基础阶段](../stages/00_foundation.md)、[人工议题](../review/README.md)。

<a id="a2"></a>
## E-A2｜发呆、上下文与语料先验

上述冻结Q5提交的 `docs/research_a1_*`、`research_a2_*`、`research_questions_final_answer.md`。A2-Final执行基线 `9b5e6e33f0ea9046e596a649562a1737e98c8491`；本机结果 `run/evaluation/a2_final/real_20260917T101056138346Z/`，Closure审计 `run/evaluation/a2_closure/audit_20260917T111536910509Z/`。[中文A系列](../stages/01_idle_context.md)

<a id="b1"></a>
## E-B1｜日记与Core7校准

冻结Q5提交的 `docs/research_b1_*`、`research_b1_1_nhaps_ahtus_calibration.md`、`research_b1_2_behavior_ontology_duration_calibration.md`。NHAPS/AHTUS ZIP SHA256 `030ae6009bf30316379ec49c8da174f85b4726dc6a3c64f202617c3285ea07ca`，3,208,441字节；这是已登记来源，不是本轮新下载。原始数据和CSV在本机受忽略路径。[中文B系列](../stages/02_behavior_data.md)

<a id="q3"></a>
## E-Q3｜对象集

原英文报告：Q5冻结提交 `7e537cef22fca73c7e1cc6be22d55a829aed6d9a` 的 `docs/research_q3_object_set_necessity_real_attempt2.md`。整理前中文版本：`2351b8159fe1d0767d1377741590c36b00cd20a0` 的 `docs/archive/2026-09-20/research_q3_object_set_necessity_real_attempt2.md`。

全量本机运行 `run/evaluation/object_set_necessity/real_attempt_2_20260918T071513907540Z/`；smoke原结果与posthoc_summary分开，没有重放provider。[中文Q3](../studies/q3_object_set.md)

<a id="q4"></a>
## E-Q4｜Resource可见性

原报告为冻结Q5提交中的 `docs/research_q4_resource_set_size.md`；整理前中文为main2351的对应archive路径。Q4提交 `9aa5d96b4339aac6affbb783a913c2f4a366c3ac`，配置 `config/experimental/resource_set_q4_v1.yaml`。本机结果 `run/evaluation/resource_set_size/real_q4_attempt_1_full_20260918T081859853289Z/`。本轮没有逐行数据，不补造NA分母或置信区间。[中文Q4](../studies/q4_resource_visibility.md)

<a id="q5"></a>
## E-Q5｜规则规模

冻结提交 `7e537cef22fca73c7e1cc6be22d55a829aed6d9a` 的 `docs/research_q5_rule_engine_scaling.md`；整理前main2351的对应archive中文版本。正式起始提交 `afd9f9dc8ce80e3d793714d46e5d888a012dadb5`，本机结果 `run/evaluation/rule_engine_scaling/q5_20260919T130054787068Z/summary.json`。[中文Q5](../studies/q5_rule_scaling.md)

<a id="q6"></a>
## E-Q6｜主线长期状态

整理前main2351的 `docs/current/acceptance.md`、`architecture.md`、`runbook.md`。已测初版代码 `86ee0492a3f159450f56dd0ba2afa0a9f6da38c0`，文档交付 `534f1e396e7c2e2d4e7c62a73b28f0e45c6ba560`。[中文Q6](../studies/q6_continuity.md)

<a id="q61"></a>
## E-Q61｜真实短链历史

研究分支最新核对 `e2d85c670a46b0dc5598ec21ea6dab8d3681a6a1` 的 `docs/current/q6_1_real_continuity_pilot.md` 与运行时报告。

Attempt1执行 `1fe4ba06893d862342bca63fd3868d3ac4e9a8b4`，结果 `d8e7ec0b61ae4d3c22648f5f1988eee5103f5265`；Attempt2执行 `50371b139afe18e94ab9b2594f1a9030d34ff360`，结果 `c3c41efeb0ec2fb860ad0c4463385082d515c269`；Attempt3执行 `54ed48f93f452718e59bda1368e15737f173084c`，结果 `a338f0b3171bf1692032bfd6818f47620fba3fdb`。

本机原session为 `run/evaluation/q6_1_provider_runtime/q61-runtime-01/`。原正式结论不因后续核验改写。[中文Q6.1](../studies/q61_real_pilot.md)

<a id="q62"></a>
## E-Q62｜投影、原产物核验与A/B准备

初始代码 `1f4a1774898bb307c54852b0b7173c3553c203dd`，文档 `51cdf5c8b1bb0d0618dba41c6b1d9511fd6ba624` 的q6_2_action_projection/q6_2_acceptance；初版CI `35680426146`，预合并 `1e0a0f7f8f8f06281f438d3eee39966f7d1df4b0`。当时只有报告序列回放、SOURCE_ARTIFACT_VERIFIED=False。

最新提交 `e2d85c670a46b0dc5598ec21ea6dab8d3681a6a1` 的 `docs/current/q6_2_acceptance.md`、`q6_2_real_ab_protocol.md` 已记录2026-09-23本机核验：SOURCE_ARTIFACT_VERIFIED=True、comparison_mismatches=[]、provider请求0。核验目录 `run/evaluation/q6_2_projection/20260923T091537191524Z/`；A/B dry-run为 `q62-ab-dry-20260923`，不是实际模型实验。

后续CI `35842428974` 核心129、全库670通过/8跳过、AS2与dry-run通过。已准备A/B CLI，总预算上限八次，真实未运行。本轮文档根据提交报告更新，不冒称亲自访问了WSL文件。[中文Q6.2与协议说明](../studies/q62_action_projection.md)

## 只读恢复原文

```bash
git show 7e537cef22fca73c7e1cc6be22d55a829aed6d9a:docs/research_q3_object_set_necessity_real_attempt2.md
git show 2351b8159fe1d0767d1377741590c36b00cd20a0:docs/archive/2026-09-20/research_q3_object_set_necessity_real_attempt2.md
```

原文是证据，不是当前执行指令。原32项来源继续核验，删除映射与本次实际检查见[清理记录](cleanup.md)。
