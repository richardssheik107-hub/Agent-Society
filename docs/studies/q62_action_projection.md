# Q6.2｜把当前可执行活动提前告诉模型

状态：原始产物核验、投影、A/B 入口与 dry-run 已通过 PR #4 合入 `main`；**真实 A/B 尚未运行**。本页更新纳入整理期间的新推送，不把后续准备工作当作真实模型结果。[证据 E-Q62](../reference/evidence.md#q62)

## 研究问题

对象在目录里，不等于该人物现在能使用。Q6.1 的 `game_a.qty=0` 仍被选作 PLAY，提示应区分“存在的对象”与“现在可执行的活动/对象对”。

A_RAW 保持原 prompt；B_FEASIBLE 保留相同观察和目的地，追加 `executable_options` 及说明。干预只有当前合法候选，不添加最佳答案、偏好排序、近期变化摘要或日记标签。两臂都记录候选成员资格，但 A 不向模型显示候选。

## 工程做法

`ContinuityWorld.preview_activity()` 复用实际活动启动和购买检查；`StateStore.read_snapshot()` 用一致只读快照保护。预览不扣钱、不写事件、不占请求预算，也不通过“先执行再回滚”生成候选。候选按 activity 和规范目标 ID 排序，记录数量与 SHA256 摘要。

区分 `start_allowed` 与 `executable_now`：吃饭可能先允许出发，但按当前已知钱/库存无法完成购买。候选不保证未来库存不变，真正提交时仍由规则再校验。

最多使用旧观察中的五个对象，当前小世界四个；按 ID 的有限候选不是语义检索，也不是千万真实目录能力。未拥有游戏时不提供 PLAY，但不会免费发游戏、偷偷代购或篡改提案。

## 原始产物核验：现在已完成

2026-09-22 的默认回放为 `SCRIPTED_REPORT_SEQUENCE_REPLAY`，当时没有原文件，`SOURCE_ARTIFACT_VERIFIED=False`。2026-09-23 的后续 WSL 报告已使用真实存在的 `q61-runtime-01/attempt_3/` 文件逐项核对，时间、版本、位置、金额、饥饿、库存变化、媒体进度、观察摘要和终态全部相符：**SOURCE_ARTIFACT_VERIFIED=True，comparison_mismatches=[]，新增 provider 请求 0。** 两次不同证据阶段均保留，不覆盖旧历史。

| 步骤 | 原意图 | 已核对饥饿值 | B 候选是否保留 | 原规则结果 |
|---|---|---:|---|---|
| 1 | TRAVEL restaurant | 800→815 | 是 | 完成 |
| 2 | MEAL food_meal | 815→245 | 是 | 完成 |
| 3 | MEAL food_meal | 245→0 | 是 | 完成 |
| 4 | PLAY game_a | 0→0 | 否 | ITEM_NOT_OWNED |

核验产物在本机 `run/evaluation/q6_2_projection/20260923T091537191524Z/`，Git 不含原始目录。这里依据已提交核验报告整理，并非本次文档整理亲自读取了用户电脑。

原离线 A/B 提示字符数依次为 1236/1772、1243/1659、1245/1661、1245/1661。额外候选增加成本；**没有真实 B 模型输出，不能报告真实拒绝率下降**。

## 已实现的 A/B 协议

每臂从同一 fixture 建立独立 world，初态摘要一致；每臂最多四请求，总上限八次；AB/BA 顺序在 session 前固定。provider/契约/输出/架构错误停止整个 session；规则拒绝或 commitment 失败停止当前臂，另一臂按预注册顺序运行。不补跑、不修提案、不覆盖旧 session。

主指标是规则拒绝率与提案在可执行集中的比例；还报告完成率、状态反馈、重复活动、token、延迟及候选成本。provider 指标以实际尝试为分母，提案指标以有效提案为分母，无有效分母写 null。

注意：这两条自主短链只有初始状态相同，后续选择不同就会分叉，不能逐步当作同态配对实验。如果要隔离同一状态的提示因果效应，需另用固定状态面板。八次小试验也不是稳定统计结论。

客户端沿用 `minimal_request=True`；没有显式发送关闭思考、max_tokens 或 temperature，不能说后端思考已关闭。修改这些字段属于另一项干预。

## 实际验收与未做事项

早期投影 CI：核心119、全库660通过/8跳过。后续准备版：本地新旧 Q6.2 57项、联合专项129；CI `35842428974` 核心129、全库670通过/8历史数据跳过，Ruff、审计、AS2、7/30天及 A/B dry-run通过。不同范围不可相加，不能用后来的成功抹掉早期环境失败。

`Q6_2_REAL_AB_EXECUTED=NO`，模型效果差异 `NOT_TESTED`。游戏获取路径仍缺失，正常行为标准仍待审核，原 Q6.1 的 INSUFFICIENT_EVIDENCE 不改变。[人工 D-01、D-02](../review/decisions.md#d-01)

代码现已位于 `main`：`continuity/action_projection.py`、`continuity/q6_2.py` 及 A/B 运行层；入口 `scripts/run_q6_2_real_ab.py` 默认零请求，真实运行仍需另获授权。[运行手册](../current/runbook.md)

## 2026-10-08｜固定状态配对面板（M0 / M1）

M0 指必要执行证据、计数与只读恢复的最小补齐；M1 指固定状态面板的可运行实现。本节的 genesis 是空 world 的初始化事实，Resource 是模型可见的对象事实字段，assessment 是原只读规则预览对一个 activity / target 的条件评估；AS2 指官方 AgentSociety 2 适配器验收，不是本轮模型测试。

本轮从 `main` 基线 `53b1244ac0f8562fd01fe8439e73ca900a40dd8c` 开始，在 `research/q62-fixed-state-panel` 交付独立面板。旧自主双短链与历史实验目录保留；新入口不是把旧每臂四请求改成二十四请求。本轮真实 provider 授权为 **0**，48 是未来面板容量，不是已获授权的调用数。Q6.1 的 `SHORT_HORIZON_STATE_CONTINUITY=INSUFFICIENT_EVIDENCE` 与 Q6.2 的 `MODEL_BENEFIT=NOT_TESTED` 均不改变。

### 同一世界状态下只比较一项提示干预

问题是：在完全相同的初始世界状态下，额外展示当前规则可执行的 activity/target 候选，是否减少不可执行提案，以及增加多少上下文成本？

A_RAW 字节级复用原 `decision_prompt`。B_FEASIBLE 调用既有 `projected_prompt(..., mode=FEASIBLE)`，只增加原投影的 `executable_options` 与原选择说明。对象目录、Resource 字段、所有权、规则、日记、近期摘要和模型请求契约均不作为额外干预。沿用 `minimal_request=True`；不新增 thinking、max_tokens、temperature 参数，也不声称已关闭后端思考。

每单元一个独立 world、一次高层提案；活动内部只由原控制器确定性推进，不再问模型。不用 A 的结果初始化 B，也不用上一状态或第一次重复的结果初始化下一单元。评分沿严格解析、目录检查、原规则启动、活动执行的实际路径产生；“在候选中”是辅助指标，不替代实际完成结果。

### 十二个冻结状态及合法来源

所有场景保留 `seed_demo` 的四个对象及其原有定义，尤其 `series_a` 仍为 120 集、每集 30 分钟。fixture 专用代码只在新建空 world 的 genesis 设置明示的余额、饥饿或餐食库存；所有权与媒体进度经原合法命令生成。没有 SQL 改写生产状态，也没有免费发食物或游戏。场景编号、family、描述和评分标签仅在 manifest，不进入提示。

| 家族 | 状态一 | 状态二 | 来源及家族内差异 |
|---|---|---|---|
| 所有权 | s01：game_a 未拥有 | s02：game_a 已拥有 | 同一 genesis；s02 合法 BUY，余额 −3000 分、游戏库存 −1、拥有量 +1，版本和购买事件同时变化 |
| 餐后需求 | s03：明显饥饿 815/1000，餐食可获得 | s04：餐后剩余饥饿 245/1000 | 同一初始饥饿 800；均合法 TRAVEL restaurant，s04 再完成 30 分钟 MEAL；因此时间、库存、余额、热量和历史也变化，不禁止第二次进食 |
| 媒体进度 | s05：第一集 offset=10，未完成 | s06：120 集全部完成，next_episode=null | s05 WATCH 10 分钟后先 PAUSE 再 CANCEL，终态 CANCELLED；s06 逐集完成 3600 分钟 WATCH；无阻塞承诺，时间、饥饿、能量、版本与账本不相同 |
| 活动地点 | s07：home | s08：office | 两者 genesis 饥饿同为 600；s08 合法旅行 15 分钟，位置、饥饿、能量、时间和版本随原规则变化 |
| 餐食支付能力 | s09：未持餐食，余额 2000 分 | s10：未持餐食，余额 1999 分 | genesis 仅差一分；food_meal 原价 2000 分，s10 仍有较便宜面包及其他合法选择 |
| 餐食供应 | s11：未持餐食，余额 5000 分，food_meal 库存 1 | s12：其他条件相同，库存 0 | 仅 seed 库存差异；对象仍可见，其他对象定义、库存及普通选择保留 |

这六组是规则边界覆盖，不是模型必须选择的标准答案。同家族两状态不伪称完全同态；合法生成连带改变的事实和历史由配方、时间、版本、事件数记录。严格相同只要求同一 scenario / repeat 的 A/B 副本。

选择包含“已拥有”“余额足够”“库存可用”等正边界，也包含负边界；所有十二状态都有正常合法候选，并非只挑使 A 失败的世界。家族内场景不是研究对象的独立随机样本，仍可能存在覆盖偏差，不能据此估计真实人群行为分布。

配置和配方在 `config/experimental/q6_2_fixed_state_panel_v1.json`，构造在 `continuity/q6_2_panel_fixtures.py`。世界须通过 `validate_world`，没有 ACTIVE / PAUSED 承诺、候选非空且观察与提示未超长，才允许准备完成。语义状态 hash 使用规范 JSON 的 `StateStore.snapshot()`，不是 SQLite 文件字节。

### 四十八单元与二十四配对

固定 seed `20261008`：12 状态 × A/B 两条件 × 2 重复 = 48 单元。每状态 repeat 1 为 AB、repeat 2 为 BA，状态 / 重复组确定性打乱；同配对两单元相邻。单元 c001–c048、配对 p001–p024 在首个请求前全部持久保存，执行结果不能反向改变分配顺序。

准备和请求前核对冻结的世界状态 hash、observation hash、对象候选、底层可执行集合 hash，并检查对应条件的 prompt hash 与大小。A 审计候选但不显示候选。请求只带本单元 system / user，不追加前一个答案或对话历史。请求模型别名与实际返回后端分别记录，身份不同或未知的配对注明可比性，不补写身份、不重跑以凑配对。

### 停止映射与失败事实

新面板中 `RULE_REJECTED` 是有效观测，记录后继续下一预分配单元；不修复、不替换模型提案。`COMMITMENT_FAILED` 仅在原规则返回已知原因、世界不变量和账本完整时允许继续。已知原因冻结为 `OUT_OF_STOCK`、`INSUFFICIENT_FUNDS`、`OBJECT_UNAVAILABLE`、`ITEM_NOT_OWNED`，常规静态支付 / 库存场景核查前两项；后两项是原 `_buy` / `_eat` 与对象可用性检查已有的确定性失败分支，不是 catch-all 白名单。

以下实际状态停止整个 session：`PROVIDER_TIMEOUT`、`HTTP_ERROR`、`TRANSPORT_ERROR`、`PROVIDER_CONTRACT_ERROR`、`INVALID_MODEL_OUTPUT`、`OUTSIDE_CATALOG`、`REQUEST_CANCELLED`、`ARCHITECTURE_ERROR`、`STATE_INVARIANT_FAILED`、`EVIDENCE_INCOMPLETE`、`REQUEST_BUDGET_EXHAUSTED`、`EXECUTION_LIMIT_EXCEEDED`、`UNKNOWN_EXECUTION_FAILURE`。意外已有记录 / 尝试 / 承诺同样停止。剩余单元标记 NOT_RUN 并记录原因，不退还调用预算、不自动 resume / retry。

每单元从冻结快照开始所选活动最多推进 96 个十五分钟以内微步骤；超限停止，不能把仍在活动中的状态写成完成。这不是 fixture 准备阶段所有合法活动共享的累计上限：s06 的 120 次准备 WATCH 各自完成后再开始下一集，每次两步，累计形成 3600 分钟的合法快照而不调用模型。餐食从 home 出发后才发现钱或库存不足时，已经合法发生的 15 分钟旅行、需求和位置变化保留，不回滚成“没有发生”。新面板的继续 / 停止策略不修改旧双短链的停止当前臂策略。

### 最小执行证据与只读恢复

各单元业务事实仍在原 world 的 `commands`、`decision_attempts`、`events` 与 state。新增 session SQLite 账本只保存分配、请求身份、预算占用与安全阶段证据，不另建业务真值。共享 decision runner 的证据钩子为 opt-in，旧 prompt、规则、活动、预算和默认停止策略保持。

请求前原子登记唯一 cell / request 与不可退还预算；每单元至多一次 client 调用尝试，整轮至多 48 个意图。固定注册根排他创建 session，不允许通过另改 output 绕过身份；仅声明本机受测范围，不宣称跨机器网络 exactly-once。每个完成单元增量写结果、配对比较、中文报告，并输出当前 cell、状态及累计调用数。

只读导出不创建 client、不读取凭据、不发送请求、不再次执行动作；源 SQLite 以 `mode=ro` 打开，不迁移或补写，新报告写到新恢复目录。它区分三个断点：

- 意图已登记而无最终事实：发送 / 结果可能未知，写 UNKNOWN，不能冒充 0 请求。
- 响应已观察而结果未提交：保留安全响应与解析阶段证据，不编造提案、接受或完成。
- world 已提交而汇总未写完：从已提交 commands / decision_attempts / commitments / events / state 导出结果，不重做动作。

恢复报告列出最后完整日志位置与缺失证据，原 session 保留并停止。日志不保存完整 prompt、completion、隐藏推理、HTTP headers、异常正文或密钥；目录外任意模型目标只保留安全解析状态和 hash，不直接持久化字符串。

### 新统计口径与缺失数据

面板使用独立 schema，不改写旧汇总。分别计数 planned、意图登记、client 尝试、HTTP 已观察、服务契约有效、严格 JSON 有效、目录有效、规则检查、启动接受、活动完成、规则拒绝、commitment 失败、NOT_RUN 与 UNKNOWN；不能以“调用数减 provider failure”推响应成功。

主指标是 **规则拒绝数 / 有效提案数**，有效提案定义为严格 schema 解析通过且目标通过原目录检查。严格解析要求只含 activity / target 两个键、activity 在旧高层动作集中、target 满足原 null / 字符串契约；目录检查沿用当前 observation 对象 ID 与四个既有目的地的集合，不代表目标已经满足活动能力、所有权或购买条件。合法 JSON 但目录外目标单列 OUTSIDE_CATALOG，停止整轮，不混入规则拒绝，也不进入有效提案分母。辅助指标包括候选成员资格、启动接受率、活动完成率、完成数 / 全部计划数、失败分类、状态不变量及上下文成本。各比例均保存 numerator / denominator / value；无分母 value=null，未运行写 NOT_RUN，未知发送写 UNKNOWN。

input / output / reasoning token 分别记录 known subtotal、缺失行数和覆盖率；token 成本覆盖的 eligible_rows 为已明确进入 client 调用的单元，known_rows 是该字段有合法非负整数的行数，missing_rows=eligible_rows−known_rows，coverage=known_rows/eligible_rows。仅有意图、发送未知的单元另报数量，不伪装成已调用行；没有 eligible_rows 时覆盖率 value=null。全部缺失时 subtotal=null，不把缺失当零。部分已知只能称已知小计，不称完整总成本；未知包含关系时不重复相加。请求延迟、活动仿真分钟、session 墙钟分开。配对报告同时展示完整配对与全部分配覆盖，按状态、家族汇总；24 配对来自 12 状态的两次重复，不当作 24 个独立人群。

每单元只有一次决策，`STATE_FEEDBACK_VISIBLE`、跨决策重复率和长期连续性均为 NOT_APPLICABLE。重复进食不是本次合法性错误。该面板不输出真人正确率，也不能推出长期自主行为、人格稳定或真人相似性。

### 已执行验收及解释边界

本轮 fixture / 分配专项 `tests/test_q6_2_panel_fixtures.py` 已在既有 WSL Python 3.12 测试环境实际执行：**76 passed，Ruff PASS**。范围包括十二合法状态、48 / 24 分配、固定 seed 与 AB / BA、A/B 初态与隔离、全部投影 assessments 对原规则实际执行、餐后 245 可继续进食、媒体边界、地点、支付 / 库存、原目录与 A 提示不变、元数据不泄漏、协议类型 / schema / 停止映射拒绝修改，以及冻结初态事实不追随后来执行而变化。v1 的类型、schema 与停止映射冻结检查防止受测协议被静默修改，不表示永远不能研究新版协议；未来改版须另行审核、版本化且保留旧记录。

集成、48 单元演练、故障恢复、旧专项、全库及 AS2 的实际结果统一记入[验收账本](../current/acceptance.md)，本段不提前填写尚未完成的通过数。入口 `scripts/run_q6_2_fixed_state_panel.py` 的默认 dry-run 不读取真实配置；offline 明示 `OFFLINE_SYNTHETIC`。脚本案例 A 非法 / B 合法、双方合法、B 更差、没有有效分母用于检查执行与汇总不内置“B 必胜”，不是模型行为证据。

未来真实结果可以无差异、负结果或证据不足；应连同失败停止造成的不完整覆盖、未知后端、上下文成本与十二状态覆盖局限解释。工程就绪不等于授权：**本轮真实请求 0，真实协议与 48 次预算仍待人工审核，MODEL_BENEFIT=NOT_TESTED**。游戏获取、Resource 新检索器、本地模型替换、长期运行和界面不在本轮范围。[D-01](../review/decisions.md#d-01) 与[运行手册](../current/runbook.md)继续作为授权和命令入口。
