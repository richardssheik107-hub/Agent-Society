# Q6.1 真实模型短链连续性 Pilot

## 1. 研究问题

Q6.1 只回答一个短链问题：

> 当真实模型连续参与高层决策时，下一次决策是否看到并利用了上一次确定性执行后的环境状态？

本阶段不回答模型能否自主生活 7/30 天，不判断人类相似性，不比较 R16/R64，不测试本地 8B，也不测试千万级真实对象数据库。

## 2. 为什么现在做这个实验

Q6 的离线工程验收已经证明人物—对象状态、库存、余额、媒体进度、活动生命周期、事务、幂等请求和 checkpoint/restore 可以保持一致。脚本驱动的 7/30 天验收没有让模型做连续选择，因此还不能证明模型提案经过一次活动执行后，会在下一次观察中接收到新的事实。

Q6.1 在进入更长自主运行或 Relevant Resource Projection 之前，用最多四次高层请求验证这一条最小闭环。真实 provider 只有在操作者显式授权时才启用。

## 3. 当前架构

~~~text
持久 SQLite 事实
    ↓
有界 observation（对象候选、拥有量、媒体进度、需求、位置）
    ↓
一次严格 JSON 高层 proposal
    ↓
确定性规则校验与 Activity Commitment
    ↓
确定性微步骤、实际模拟时间、事务事件
    ↓
新的持久事实与下一次 observation
~~~

ContinuityWorld 是事实和规则的 source of truth。ContinuityEnv 只做 AgentSociety 2 的薄适配，不替换旧 WorldState，也不启用 PersonAgent、CodeGenRouter 或 ReAct。

## 4. 真实模型负责什么

模型每次只选择一个高层活动：

MEAL、WATCH、PLAY、TRAVEL、WORK、SLEEP、LEISURE、PERSONAL_CARE 或 CHORES。

输出必须是严格的二字段 JSON，例如：

~~~json
{"activity":"WATCH","target":"series_a"}
~~~

模型不负责生成世界真值、计算余额、修改库存、决定进度、判断规则是否合法或保存长期事实。每个高层决策最多一次 provider request；活动的微步骤不再次调用模型。

## 5. deterministic system 负责什么

系统负责：

- 校验 activity、target、catalog 和前置条件；
- 创建、推进、暂停、恢复、取消或失败 Activity Commitment；
- 执行 MOVE/BUY/EAT/观看/游玩等微步骤；
- 推进实际模拟时间并写入余额、库存、进度、位置和需求；
- 用 SQLite 事务、request_id 和版本号保证幂等、回滚和过期状态拒绝；
- 记录领域事件、请求状态和安全元数据。

RULE_REJECTED、COMMITMENT_FAILED、provider 错误和输出错误必须分开记录，不能合并成 idle。

## 6. 四次决策设计

默认 MAX_REAL_DECISIONS=4。初始 synthetic fixture 固定为：

- 位置：home、restaurant、office、park；
- 对象：food_bread、food_meal、game_a、series_a；
- 初始人物在 home，饥饿较高，游戏未拥有，series_a 的下一集为 1；
- 不为保证覆盖某种行为而脚本覆盖模型选择，也不手工 reset 中间状态。

每次循环严格执行：

1. 记录当前状态版本和 bounded observation 的哈希/长度；
2. 发出一个真实高层请求；
3. 解析并校验 proposal；
4. 若接受，运行 commitment 的全部确定性微步骤；
5. 记录实际时间、事件和状态差异；
6. 用更新后的事实生成下一次 observation；
7. 发生停止条件时停止后续请求。

超过 4 次必须同时提供 --extended-pilot，且总数不得超过 12。Q6.1 默认不会自动扩展。

## 7. 评价指标

每条 decision row 保存安全的结构化字段，包括：

- 决策序号、request id、前后模拟分钟和 state version；
- application calls、provider requests、模型别名、HTTP 状态、finish reason、token 元数据和延迟；
- observation 字符数与前后哈希，不保存原始 prompt；
- proposal activity/target、规范化 decision status、rule reason；
- commitment id/status/activity、微步骤数、实际耗时和事件数；
- 前后余额、饥饿、精力、位置、库存差异、媒体进度和游玩分钟。

确定性分析器输出：

STATE_FEEDBACK_VISIBLE、STATE_FEEDBACK_CHANGED、MEDIA_CONTINUITY_EXERCISED、MEDIA_PROGRESS_MONOTONIC、OWNERSHIP_CONTINUITY_EXERCISED、OWNERSHIP_CONSISTENT、REPEATED_OWNERSHIP_CONFLICT、INVENTORY_CONSISTENT、MONEY_CONSISTENT、NO_DUPLICATE_EFFECT、NO_TIME_REVERSAL、IMMEDIATE_ACTIVITY_REPEAT、IMMEDIATE_MEAL_REPEAT、IMMEDIATE_WATCH_REPEAT、规则拒绝数、commitment 失败数、provider 失败数和 invalid output 数。

这些是可复核事实，不使用 LLM judge，也不读取 acceptable_action_set、未来状态或答案标签。分析器不输出 HUMAN_LIKE=YES 或类似价值判断。

## 8. 停止条件

以下情况发生后，默认停止后续 provider request：

- PROVIDER_TIMEOUT、PROVIDER_ERROR、provider refusal 或 provider wire contract 错误；
- INVALID_MODEL_OUTPUT、OUTSIDE_CATALOG、OUTPUT_BUDGET_EXHAUSTED；
- ARCHITECTURE_ERROR 或持久状态不变量失败；
- RULE_REJECTED 或 COMMITMENT_FAILED。

不自动 retry、JSON repair、fallback WAIT、fake action 或脚本替代。

## 9. Provider 纪律

Q6.1 复用现有 OpenAICompatibleDecisionClient：

- transport retries = 0；
- application retries = 0；
- follow redirects = false；
- hard timeout = 60 秒；
- 每个高层决策最多一个 Chat Completions 请求；
- 不记录 API key、Authorization header、原始 completion、reasoning 或 hidden CoT。

没有 --allow-provider 时，入口只打印 REAL_PROVIDER_EXECUTED=NO 和 PROVIDER_REQUESTS=0，不会建立客户端或发送网络请求。

## 10. 离线验收

真实请求之前必须通过：

~~~bash
python -m pytest -q tests/test_q6_1_real_continuity.py
python -m pytest -q tests/test_continuity*.py tests/test_q6_1_real_continuity.py tests/test_repository_quality.py
python -m ruff check src/social_sim/continuity \
  tests/test_continuity*.py tests/test_q6_1_real_continuity.py \
  tests/test_repository_quality.py tests/conftest.py \
  scripts/run_continuity*.py scripts/run_q6_1_real_continuity.py \
  scripts/check_continuity_as2.py scripts/audit_repository.py
python scripts/audit_repository.py --check
python scripts/check_continuity_as2.py
~~~

CI 只运行 fake-provider、离线 contract、lint、repository audit 和 AS2 零模型 smoke；不会自动发真实 provider 请求。

## 11. 真实执行入口

环境变量只从安全运行环境注入：

~~~text
CONTINUITY_BASE_URL
CONTINUITY_MODEL
CONTINUITY_API_KEY
~~~

显式授权后才运行：

~~~bash
python scripts/run_q6_1_real_continuity.py \
  --allow-provider \
  --max-decisions 4
~~~

每次运行使用新目录：

~~~text
run/evaluation/q6_1_real_continuity/<timestamp>/
~~~

至少包含 summary.json、decisions.jsonl、events.jsonl、final_state.json、report_zh.md 和 environment.json。environment.json 只记录 commit、branch、Python、固定 AgentSociety 子模块提交和安全的模型别名；artifact 不包含 secret。

## 12. 当前准备结果

本协议和离线入口基于最新 main da75a97 准备。当前真实 provider 尚未执行：

~~~text
Q6_1_REAL_PILOT_READY = YES
REAL_PROVIDER_EXECUTED = NO
~~~

已加入的 fake-provider 覆盖包括四次连续合法 proposal、WATCH episode 反馈、所有权重启持久化、request_id 幂等、invalid JSON、timeout、规则拒绝、commitment 失败、重启后不重复请求、第四次预算封顶、artifact 隐私和 marker 不读未来标签。

## 13. 结果边界与下一步判断

若四次真实 decision 的 provider contract、proposal 解析、确定性执行和下一次 observation 均可复核，且无状态回退和重复 effect，只能写：

~~~text
SHORT_HORIZON_STATE_CONTINUITY = SUPPORTED
~~~

不能写：

~~~text
LONG_HORIZON_HUMAN_BEHAVIOR = SOLVED
~~~

若失败，按 PROVIDER、MODEL_OUTPUT、RULE、COMMITMENT、STATE_FEEDBACK 或 ARCHITECTURE 归因。Q6.1 完成后再决定：修复状态反馈、进入 Relevant Resource Projection，或在短链稳定时由人工批准扩展到 12 次；本阶段不提前实现 P2。

## 14. 本次真实 pilot 实际结果（2026-09-20）

本次按一次性授权启动了真实入口，使用既有火山引擎兼容配置（模型别名：`ark-code-latest`）。启动前确认：

~~~text
BRANCH = research/q6-real-continuity-pilot
EXECUTION_COMMIT = 1fe4ba06893d862342bca63fd3868d3ac4e9a8b4
WORKTREE = CLEAN
~~~

入口在构造 provider client 前即触发 `ARCHITECTURE_ERROR`：

~~~text
ImportError: cannot import name `OpenAICompatibleDecisionClient`
from `social_sim.continuity.decision`
~~~

实际实现位于 `social_sim.decision.client`。因此没有创建客户端、没有发出网络请求，也没有生成包含决策行的真实 artifact；本次按停止条件结束，不进行修复、重试或补跑。

~~~text
PILOT_INVOCATION = YES
REAL_PROVIDER_EXECUTED = NO
APPLICATION_CALLS = 0
PROVIDER_REQUESTS = 0
STOP_REASON = ARCHITECTURE_ERROR
FAILURE_ATTRIBUTION = ARCHITECTURE
~~~

### Decision 1–4

~~~text
Decision 1 = NOT RUN due to ARCHITECTURE_ERROR before provider client construction
Decision 2 = NOT RUN
Decision 3 = NOT RUN
Decision 4 = NOT RUN
~~~

### 实际指标

由于没有完成任何 decision，以下连续性指标均为 `NOT MEASURED`：

~~~text
STATE_FEEDBACK_VISIBLE = NOT MEASURED
STATE_FEEDBACK_CHANGED = NOT MEASURED
MEDIA_CONTINUITY_EXERCISED = NOT MEASURED
MEDIA_PROGRESS_MONOTONIC = NOT MEASURED
OWNERSHIP_CONTINUITY_EXERCISED = NOT MEASURED
OWNERSHIP_CONSISTENT = NOT MEASURED
INVENTORY_CONSISTENT = NOT MEASURED
MONEY_CONSISTENT = NOT MEASURED
NO_DUPLICATE_EFFECT = NOT MEASURED
NO_TIME_REVERSAL = NOT MEASURED
IMMEDIATE_ACTIVITY_REPEAT = NOT MEASURED
IMMEDIATE_MEAL_REPEAT = NOT MEASURED
IMMEDIATE_WATCH_REPEAT = NOT MEASURED
RULE_REJECTION_COUNT = 0
COMMITMENT_FAILURE_COUNT = 0
PROVIDER_FAILURE_COUNT = 0
INVALID_OUTPUT_COUNT = 0
~~~

### 离线复核

~~~text
Q6.1 focused tests = 15 passed
Continuity/repository tests = 55 passed
Ruff = PASS
Repository audit = PASS
AS2 smoke = AS2_CONTINUITY_ADAPTER_PASS (LLM_CALLS=0, PROVIDER_REQUESTS=0)
~~~

结论：

~~~text
SHORT_HORIZON_STATE_CONTINUITY = INSUFFICIENT_EVIDENCE
~~~

本次没有原始 prompt、completion、reasoning、Authorization header 或 API key 被写入 artifact 或报告。修复导入路径属于后续代码变更；在得到新的明确授权前，本报告不自动补跑真实 provider。
