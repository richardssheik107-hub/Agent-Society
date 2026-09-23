# Q6.2 小预算真实 A/B 预注册协议

状态：**工程准备完成；真实 A/B 未运行**。更新：2026-09-23。研究分支 `research/q6-real-continuity-pilot`，继续使用 PR #4。

## 问题与两个条件

主问题仅为：给模型展示当前确定性可执行的活动/对象对，是否降低其提出规则不可执行提案的比例。主要指标为 `rule_rejection_rate`，并报告 `proposal_in_feasible_set_rate`。这次不把重复进食直接记作失败，也不声称行为更像真人。

| 条件 | 模型输入 | 其余条件 |
|---|---|---|
| `A_RAW` | 原 Q6.1 `decision_prompt()` 的系统与用户文本，逐字节不变 | 同一初始 fixture、规则、provider client 与执行路径 |
| `B_FEASIBLE` | 相同 observation，额外加入 `executable_options` 和一句选择说明 | 同上 |

候选只读取当前人物、位置、余额、库存、所有权、对象可用性、能力、commitment、剧集进度和规则参数。它不读取 expected action、可接受答案标签、未来状态或 provider 输出。候选按 `activity`、规范目标 ID 排序，并记录 `candidate_count` 与 SHA-256 `candidate_digest`。A 的候选仅在本地计算指标，不展示给模型。模型无视候选时不会自动修正提案；最终仍由 RuleEngine 判断。

## 冻结预算与执行

两臂各有独立 `world.sqlite3`，都由 `seed_demo()` 初始化，初态摘要必须相同。每臂最多四次高层决定，整个 session 最多八次 application-level provider requests。一次高层决定最多一次 HTTP 请求；无传输重试、JSON repair、fallback WAIT、补跑或修改状态后重试。`AB` 或 `BA` 顺序需在 session 建立前固定并写入 `config.json`。单个 replicate 存在顺序效应，不能作为稳定因果估计。

使用与 Q6.1 相同的 `OpenAICompatibleDecisionClient(minimal_request=True, timeout_seconds=60)`。这个请求契约**没有显式发送** `thinking: {"type":"disabled"}`，也没有发送 `max_tokens` 或 `temperature`；不能据此声称服务端已关闭深度思考。两臂使用同一个 client 实例与相同 provider/model。若将来要研究关闭深度思考，必须另立协议并先核对实际请求体，不能悄悄改变本 A/B 的单一变量。

provider 错误、响应契约错误、无效 JSON、越界目标或架构错误：停止整个 session，未开始的臂标记 `NOT_RUN`。规则拒绝或 commitment 失败：停止当前臂，另一臂仍可按预注册顺序运行。任何一臂都不为了凑足四个成功动作而修正或替换模型输出。

## 指标与产物

每臂记录 provider 成功率、严格 JSON 有效率、提案在可执行集中的比例、规则拒绝率、commitment 失败率、接受率、完成率、状态反馈可见率、立即重复活动/餐食/观看率，以及请求数、token、延迟、候选数和提示字符数。以实际 provider 尝试为 provider 分母；提案相关指标只以有效提案为分母；无有效分母时写 `null`。餐食重复只作描述。

产物位于新的 `run/evaluation/q6_2_real_ab/<session>/`，包括 `config.json`、两臂各自的 `summary.json`、`decisions.jsonl`、`final_state.json`、`world.sqlite3`，以及 `comparison.json` 与 `report_zh.md`。不保存 API key、Authorization、原始 prompt、原始 completion 或隐藏 reasoning。已有 session 目录一律拒绝覆盖。原 Q6.1 `q61-runtime-01` 只作历史证据，不是 A/B world。

无凭据 dry-run（**不调用 provider**）：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_real_ab.py --session-id <新的唯一 ID> --schedule AB
```

该命令生成并核对两臂初态、候选摘要、提示长度与完整目录合同，输出 `Q6_2_REAL_AB_EXECUTED=NO`、`PROVIDER_REQUESTS=0`。未来真实执行必须另获明确授权、提供新 session ID，并显式加入 `--allow-provider`；本轮没有执行该分支。

## 验收边界

本轮的原始 Attempt 3 核对、投影工程测试和 dry-run 可以证明协议可准备、可观测、会停止。它们不能证明 `B_FEASIBLE` 降低了真实模型的拒绝率。一次小样本 A/B 即使运行完成，也只能报告观测差异和上下文成本；更长的 12-call、近期状态摘要、游戏获取路径与行为学标注均需独立研究决定。
