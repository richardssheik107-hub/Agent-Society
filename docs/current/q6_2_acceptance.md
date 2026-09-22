# Q6.2 代码交付与实际验收

日期：2026-09-22。分支：`research/q6-real-continuity-pilot`。在现有 PR #4 继续交付，不自动合并 main。

## 已完成的代码

代码提交：`1f4a1774898bb307c54852b0b7173c3553c203dd`。本页是后续文档回填，不把文档提交当成下面 CI 的执行版本。

- `ContinuityWorld.preview_activity()`：共享实际启动/购买条件的只读预览。
- `StateStore.read_snapshot()`：一致快照和 SQL 只读保护，不通过执行后回滚生成候选。
- `action_projection.py`：有限对象上的可执行活动/目标候选，A 原提示不变，B 显式追加候选。
- `ActivityDecisionRunner(..., prompt_builder=projected_prompt)`：可选接线，默认 Q6.1 路径不变。
- `q6_2.py` 与 `scripts/run_q6_2_projection_offline.py`：报告序列回放、可选原始 artifact 核对、中文报告和机器可读结果。
- 47 项新增测试案例、冻结旧行为状态/事件哈希基线、CI 离线回放。

更完整的语义、用法和研究边界见[投影设计](q6_2_action_projection.md)。

## 实际测试证据

[GitHub Actions 35680426146](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35680426146) 的 core-contract 与 regression 均 SUCCESS。该流程在代码提交与当时 main 的预合并版本上测试：`1e0a0f7f8f8f06281f438d3eee39966f7d1df4b0`。这不是实际合并 main。

| 验收范围 | 环境 | 结果 |
|---|---|---|
| Q6.2 新增测试 | 本地开发环境 Python 3.13.5 | 47 passed |
| Q6.1/Q6.2/continuity/仓库联合专项 | 本地开发环境 Python 3.13.5 | 160 passed |
| CI 核心专项（不含全部运行时测试文件） | Python 3.12.14 | 119 passed |
| 全库回归 | Python 3.12.14 + 固定上游完整依赖 | 660 passed，8 skipped |
| Ruff E4/E7/E9/F/B 已配置范围 | CI | PASS |
| 原文归档及受保护文件审计 | CI | PASS，32 份原文继续核验 |
| Q6.2 报告序列离线回放 | CI | PASS，0 provider requests |
| 实际固定上游 AS2 观察/时钟/恢复 | CI | AS2_CONTINUITY_ADAPTER_PASS，0 LLM/provider calls |
| 七天/三十天脚本一致性 | CI | PASS，恢复版与不停机版一致 |

不同专项的测试文件范围不同，不把 47、160、119 和 660 相加为独立样本数。八项跳过需要未入库的历史真人语料，涉及 test_a2_final、test_behavior_prior_context、test_behavior_prior_index；不计入通过，不用假数据替代。

用户本地此前缺少 litellm 的全库收集失败记录仍保留。本次完整 CI 环境安装了既有上游依赖并通过 AS2 验证；不要求把整个 AS2 依赖塞回轻量 provider venv，也不宣称用户本机已被远程修复。

证据产物：

- [核心测试、Q6.2 回放与长期脚本结果](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35680426146/artifacts/10674167013)
- [全库 JUnit、依赖与上游版本](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35680426146/artifacts/10675281832)

Actions 产物按服务保留期存放，关键结果与运行 ID 留在本页。临时导出已提交源码用于隔离测试的工作流已从最终工作树移除，未导出用户的 ignored 配置或本机运行目录。

## 回放实际发现

按原报告的四个意图回放：新候选保留 TRAVEL、第一次 MEAL、第二次 MEAL，排除未拥有游戏的 PLAY。原规则仍对第四项返回 ITEM_NOT_OWNED；不会为了得到成功轨迹而替换动作。

第一次餐食后的饥饿值为 245/1000，第二次后为 0。连吃两次属于需要解释的行为现象，不足以单独证明模型忘记状态。投影不把饥饿阈值偷偷改成进食禁令。

所有权为 0 时 PLAY 被提前排除，但当前高层动作集仍没有购买游戏的入口。本轮没有免费授予所有权、增加 BUY、代购或更改对象价格/饱腹参数。

## 本次没有做什么

真实 provider 请求为 0，真实 A/B 未执行；Q6.1 Attempt 1/2/3 的报告和结果不覆盖，正式 INSUFFICIENT_EVIDENCE 不改写。

Git 不包含用户 WSL 的原始 q61-runtime-01 文件，本次默认结果为 SCRIPTED_REPORT_SEQUENCE_REPLAY，SOURCE_ARTIFACT_VERIFIED=False。已有原始产物的机器可使用下面命令核对，不会发送模型请求：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_projection_offline.py \
  --source-artifact run/evaluation/q6_1_provider_runtime/q61-runtime-01
```

只有与传入文件的逐步状态、观察摘要、版本及终态都相符，才标记 source_artifact_verified=true；这不是对外部文件真实性的额外认证。

当前结论：**可执行活动投影已实现并通过受测工程检查；是否改善真实模型选择、增加上下文是否划算，仍需单独授权的真实对照实验。**
