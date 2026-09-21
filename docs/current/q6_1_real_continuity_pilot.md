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

## 15. Attempt 2 实际结果（2026-09-21）

本节记录后续明确授权的独立 Attempt 2。第 12 节为初始准备状态，第 14 节为 Attempt 1 的历史记录，均按原文保留；它们不代表 Attempt 2 的结果。

### 执行版本与配置

~~~text
BRANCH = research/q6-real-continuity-pilot
ATTEMPT_1_EXECUTION_COMMIT = 1fe4ba06893d862342bca63fd3868d3ac4e9a8b4
ATTEMPT_1_RESULT_COMMIT = d8e7ec0b61ae4d3c22648f5f1988eee5103f5265
ATTEMPT_1_RESULT = ARCHITECTURE_ERROR
ATTEMPT_1_PROVIDER_REQUESTS = 0
FIX_COMMIT = 50371b139afe18e94ab9b2594f1a9030d34ff360
ATTEMPT_2_EXECUTION_COMMIT = 50371b139afe18e94ab9b2594f1a9030d34ff360
WORKTREE_BEFORE_ATTEMPT_2 = CLEAN
AGENTSOCIETY_SUBMODULE_COMMIT = 670c94fff7c64c4f79b632125f2ccf968155e746
PROVIDER = Volcengine OpenAI-compatible Coding Plan
CONTINUITY_BASE_URL = https://ark.cn-beijing.volces.com/api/coding/v3
REQUESTED_MODEL = ark-code-latest
BASE_URL_SET = YES
MODEL_SET = YES
API_KEY_SET = YES
MAX_DECISIONS = 4
~~~

独立修复提交只修正真实入口的 public import，并加入离线 CLI/client-construction regression test。没有修改 provider client、prompt、初始状态、activity logic、Q6.1 metrics、预算或固定上游子模块。启动前 focused tests 为 17 passed，针对修改文件的 Ruff 为 PASS。

执行进程读取既有火山引擎配置，将 API key 注入 `CONTINUITY_API_KEY`，未打印或提交凭据。真实入口仅启动一次，参数为 `--allow-provider --max-decisions 4`；实际使用 WSL Python 3.12.14 与本机已有缓存依赖。

### 原始 artifact 与请求计数边界

~~~text
ARTIFACT_DIR = run/evaluation/q6_1_real_continuity/20260921T025935532829Z/
REAL_PROVIDER_EXECUTED = YES
APPLICATION_CALLS = 1
PROVIDER_REQUESTS = 1
COMPLETED_DECISIONS = 0
ACCEPTED_DECISIONS = 0
STOP_REASON = PROVIDER_ERROR
PROCESS_EXIT_CODE = 1
~~~

`REAL_PROVIDER_EXECUTED = YES` 严格依据本实验规定的 `provider_request_count >= 1`：`summary.json` 和 Decision 1 都记录了 1 次。客户端在调用 HTTP POST 之前递增该计数，所以它证明的是客户端请求尝试，**不能证明服务端收到请求或模型完成推理**。本次没有 HTTP 状态、响应模型、token 使用量或 proposal 可供核验，不据此认定火山引擎服务端故障。

配置的模型别名为 `ark-code-latest`。原始 `summary.json`、`environment.json` 和 decision row 中 `provider_model` 均为 `null`；现有安全元数据过滤器会排除以 `ark-` 开头的字符串。本次保留原始字段，不修改过滤器或补写 artifact。

artifact 写入后，`client.aclose()` 的 `httpx/httpcore/anyio` 清理路径另报本地依赖错误：`ImportError: cannot import name 'sentinel' from 'typing_extensions'`。这属于本次进程的环境/清理异常，不是第二次实验；原始决策停止原因仍为 `PROVIDER_ERROR`。现有 artifact 未保存首次请求异常的细节，故不把清理 traceback 当作已确认的首次失败根因。

未 retry、rerun、JSON repair、fallback WAIT、补动作、修改 prompt/初始状态后补跑或扩展到 12 calls。Decision 1 触发停止条件后，Decision 2–4 均未执行。

### Decision 1–4

| Decision | 实际结果 | provider requests | 确定性执行与状态 |
| --- | --- | --- | --- |
| 1 | `PROVIDER_ERROR`；request_id=`q6_1:1`；HTTP/model/proposal 均无有效记录 | 1 | commitment 无；micro steps=0；新增 events=0；模拟分钟 0→0；state version 0→0 |
| 2 | `NOT RUN`：Decision 1 已触发停止条件 | 0 | 无 |
| 3 | `NOT RUN`：Decision 1 已触发停止条件 | 0 | 无 |
| 4 | `NOT RUN`：Decision 1 已触发停止条件 | 0 | 无 |

Decision 1 记录的延迟为 0.038139 秒。observation 长度为 866 字符，前后摘要相同：`81e7437378979937f05ef11c307df2f71e3028c5be17fccaa52e07577f439238`。余额 300000→300000，饥饿 800→800，精力 700→700，位置 home→home，库存差异 `{}`，series_a 下一集 1→1，game_a 游玩分钟 0→0。

### 全部 continuity markers

以下是原始 summary 的值；`null` 表示没有可衡量的跨决策反馈。未发生活动时的 `true` 一致性指标只表明初始状态没有被破坏，不构成模型连续决策成功的证据。

~~~text
STATE_FEEDBACK_VISIBLE = null (NOT MEASURED)
STATE_FEEDBACK_CHANGED = false
MEDIA_CONTINUITY_EXERCISED = false
MEDIA_PROGRESS_MONOTONIC = true
OWNERSHIP_CONTINUITY_EXERCISED = false
OWNERSHIP_CONSISTENT = true
INVENTORY_CONSISTENT = true
MONEY_CONSISTENT = true
NO_DUPLICATE_EFFECT = true
NO_TIME_REVERSAL = true
IMMEDIATE_ACTIVITY_REPEAT = false
IMMEDIATE_MEAL_REPEAT = false
IMMEDIATE_WATCH_REPEAT = false
REPEATED_OWNERSHIP_CONFLICT = false
RULE_REJECTION_COUNT = 0
COMMITMENT_FAILURE_COUNT = 0
PROVIDER_FAILURE_COUNT = 1
INVALID_OUTPUT_COUNT = 0
FINAL_INVARIANTS = PASS
FINAL_SIMULATION_MINUTE = 0
FINAL_EVENT_COUNT = 1
FINAL_STATE_HASH = b51280a21758ab18749da2324e97ea1b3c8f1c2d68c64847f2f85a07b778aca1
~~~

最终唯一事件为初始 seed，没有决策产生的世界事件。

### Attempt 2 结束后的离线回归

~~~text
Q6.1 focused tests = 17 passed
Continuity/repository tests = 55 passed
Full regression = 580 passed, 3 warnings, 0 skipped
Ruff (scripts/run_q6_1_real_continuity.py, tests/test_q6_1_real_continuity.py) = PASS
Repository audit = PASS
AS2 smoke = AS2_CONTINUITY_ADAPTER_PASS (LLM_CALLS=0, PROVIDER_REQUESTS=0)
~~~

首次离线检查所选解释器未包含 `httpx`/`agentsociety2`，分别导致 collection/import error。随后仅调整测试进程的缓存依赖路径：focused/continuity 使用 `uv run --offline --no-project --with httpx --with pytest`；AS2/full regression 使用缓存包、固定上游源码路径及兼容的 `typing_extensions 4.16.0`。三条 warning 均为 SWIG 类型缺少 `__module__` 的弃用提示。依赖解析与测试保持离线，未修改业务代码或子模块，未再次启动真实 pilot。

### 证据完整性与结论

原始 artifact 保留在上述本地目录（`run/` 按仓库规则不入 Git）；本报告提交关键事实与哈希，不覆盖 artifact：

| 文件 | SHA-256 |
| --- | --- |
| summary.json | `0c73c1028eb03646c8dc43ba9d5175debb20dc90e23a3177bcf3932daeae0e50` |
| decisions.jsonl | `c63172f969e4a7ceeb0727ebc23c14b2da38326962173ed3ae2116281ad484a9` |
| events.jsonl | `1ce86d972f5a1e08bf42a65817ef96f46ea7186c36797b8f19b16daf20bd5e88` |
| final_state.json | `0ad5de1ea06a906cf77d7eafc445a0e56ed25656d34249f25aa37d27e97eccbb` |
| environment.json | `d9ce0fc718d72528fb042d5e1a4db9014e8996f210cb89f989ebdc2d5cdc76e1` |
| report_zh.md | `0f8511f4cd2f7d9eeed4016386362555bcece7634a5c927d53e72c1088dd6481` |

~~~text
SHORT_HORIZON_STATE_CONTINUITY = INSUFFICIENT_EVIDENCE
RUNNER_RAW_CONTINUITY_RESULT = UNRESOLVED
~~~

没有完成真实模型 proposal 或任何 activity，也没有产生 state→observation→next decision 链路，因而无法支持短链连续性成立，亦不能据此判断其不成立。离线回归通过不改变这次真实 pilot 的失败结果。不声称长期行为或人类相似性得到证明；任何下一次真实实验都需要新的明确授权。
