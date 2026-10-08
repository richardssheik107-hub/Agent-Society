# Q6.2｜把当前可执行活动提前告诉模型

状态：原始产物核验、投影、旧双短链A/B入口与dry-run已通过PR #4合入main；旧8-call真实短链仍未运行。研究分支的固定状态v2面板已完成唯一真实session：48尝试、46有效并完成、2隔离超时、22完整配对；主指标研究判断为 **NO_CLEAR_DIFFERENCE**，不是等价证明。以下早期阶段保留当时未测试的历史，最新结果见页末。[证据 E-Q62](../reference/evidence.md#q62)

当前M1.5另做[客观状态后果与提示干预审计](q62_outcome_audit.md)，仅使用这批历史证据，`NEW_REAL_PROVIDER_REQUESTS=0`。新增指标是 `EVALUATION_TYPE=EXPLORATORY_POST_HOC`，不是原48请求的预注册主指标；原 `NO_CLEAR_DIFFERENCE` 不改写。TRAVEL完成、MEAL完成与人物需求改善分开，两个超时的行为后果保留 `UNKNOWN`；[人工盲审包](q62_outcome_human_review.md)尚未标注，`HUMAN_REVIEW_COMPLETED=NO`，`HUMAN_NEED_SATISFACTION_CONCLUSION=UNRESOLVED`。新标准与提示消融只提交[D-09](../review/decisions.md#d-09)讨论，不自动运行。

## 研究问题

对象在目录里，不等于该人物现在能使用。Q6.1 的 `game_a.qty=0` 仍被选作 PLAY，提示应区分“存在的对象”与“现在可执行的活动/对象对”。

A_RAW 保持原 prompt；B_FEASIBLE 保留相同观察和目的地，追加 `executable_options` 及说明。干预只有当前合法候选，不添加最佳答案、偏好排序、近期变化摘要或日记标签。两臂都记录候选成员资格，但 A 不向模型显示候选。

M1.5澄清上面“只有候选”的原设计简称：冻结B还在system中明确要求从 `executable_options` 选择activity/target，并声明这不是偏好排序。因此它是候选数据与选择指令的综合干预，还增加上下文、固定排列与名称重复曝光；原实验并未分别消融这些因素。只读重建的12场景/48单元hash与字节数均需和冻结产物一致才报告PASS；不改原提示，不读取或保存原模型completion，不能编造模型隐藏思考解释。[提示审计与机制边界](q62_outcome_audit.md)

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

原离线 A/B 提示字符数依次为 1236/1772、1243/1659、1245/1661、1245/1661。额外候选增加成本；**当时没有真实B模型输出，不能报告真实拒绝率下降**。后面的新版固定面板是独立证据，不补写旧短链的模型结果。

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

## 2026-10-08｜v2 超时增量与唯一真实面板预注册

上节是v1工程轮的历史记录（真实请求0），不因本轮授权改写。v1配置保持原字节，入口默认仍v1，一次超时仍停止整轮；`--protocol v2`显式选择新schema/protocol_version。v2只改变超时调度与兼容描述字段；12场景、seed20261008、48独立world、24相邻配对、A/B提示、对象及规则和minimal_request均不改变。公平性指纹比较排除协议元数据，完整manifest hash可以不同。

v2单次PROVIDER_TIMEOUT仅在调用协程返回或完成取消、无遗留本地任务、当前世界无未解释提交且不变量/持久证据完整时继续下一预分配单元，不重发原cell。取消中的晚到回复不解析、不执行。记录streak前/后、local_call_settled、timeout_locally_safe与继续/停止理由；记录本地终态不证明服务端没收到或没计费。取消无法终结或证据不足停止session。每调用60秒，v2取消收尾最多再观察5秒；不能等待取消的同时启动下一请求。

连续计数跨A/B、pair和场景。有效提案正常记录执行结果（包括RULE_REJECTED和已知COMMITMENT_FAILED）才清零；第二次连续超时cell仍为PROVIDER_TIMEOUT，session为CONSECUTIVE_TIMEOUT_LIMIT。HTTP错误含408、非超时连接错误、契约/JSON/目录外输出、外部取消、架构/不变量/预算/证据异常均立即停止。cleanup最多5秒，安全异常类型单列，不覆盖原失败。旧双短链与Q6.1停止语义不变。

本轮[D-01](../review/decisions.md#d-01)只批准 `q62-panel-real-v2-01` 一次，最多48客户端调用尝试，额外探针/真实smoke/旧双短链0；所有失败、超时与未知占用预算。代码、预注册、专项、Ruff、审计和新版本完整CI/AS2全部通过后，冻结本地干净HEAD与同加载器的规范JSON协议hash；CI临时merge SHA另列，不替代本地EXECUTION_COMMIT。执行窗口不改tracked文件、不换commit/环境、不merge；已有session不删除/不换ID/不重跑。

结果先报告全部分配覆盖、阶段计数、token缺失与backend；同时看拒绝率和活动完成，不能只报启动接受。完整可评配对与同后端敏感性描述分别计算B−A，保留全部24对的不完整原因。行为分布检查B是否只是多选LEISURE，不增加事后正确答案。只允许透明归纳OBSERVED_IMPROVEMENT、NO_CLEAR_DIFFERENCE、OBSERVED_REGRESSION或INSUFFICIENT_EVIDENCE；未执行时NOT_TESTED。固定状态面板不能证明连续追剧、长期自主或人类相似性；Q6.1历史结论不变。实际结果结束后追加，门禁与产物见[验收账本](../current/acceptance.md)。

## 2026-10-08｜v2 唯一真实面板结果与收束

**本面板未观察到B在规则拒绝或活动完成指标上改善。** A/B都对23个有效提案完成活动，拒绝均0；B明显改变了活动选择，并增加已知上下文与耗时。独立研究判断 `MODEL_BENEFIT=NO_CLEAR_DIFFERENCE` 只描述这次冻结面板，不证明两种提示等效、候选无用或长期行为相同。原runner `MODEL_BENEFIT=NOT_TESTED` 保留：它不自动做科学判断，不能用这个字符串否认真实请求。

### 冻结、预算和真实请求证据

起点 `1b926a58ad986136aa121accf98f7dbb7dbaa2a6`；v2代码/预注册及实际执行commit均为 `ae2123f50beaaca6bcac2dcca8e34659bd0a8b24`。唯一session `q62-panel-real-v2-01`，协议 `q62_fixed_state_panel_v2`，规范JSON hash `b66217fa18ce8740deec38334b157ff35f00455d8d2b431dd0b48531debffcc6`。v1配置原字节不变；12状态、调度、候选及A/B提示指纹相等，具体SHA见验收账本。执行前新CI全库950通过/8历史语料跳过、AS2通过；临时merge `c7e41519c3dc73373d442e9aa336a20f040ea954` 与本地HEAD整树相等，不是合并main。

指定.env仅由既有安全加载器只读解析；有效base为 `https://ark.cn-beijing.volces.com/api/coding/v3`、请求别名 `ark-code-latest`，未记录密钥。执行前唯一ID不存在且无其他runner，运行窗tracked文件/commit/环境保持冻结。只执行一次正式CLI，授权上限48全部使用，额外探针、preflight、旧8-call、retry/resume/repair/fallback及补样本均0。

48个意图和客户端尝试均有持久记录；client请求计数已知小计48、缺失调用计数0、未知发送意图0。**这不是服务端必然收到48次的证明。** 46次有HTTP200与有效提案，实际响应后端均 `glm-5.3`；另2次本地安全超时，无HTTP/后端证据，backend为UNKNOWN，服务端收到/完成/计费未知。未把超时混入规则拒绝或JSON/契约错误。

c027（A、s06、p014）与c041（B、s04、p021）原状态均PROVIDER_TIMEOUT、streak 0→1，local_call_settled/timeout_locally_safe均True，理由SINGLE_TIMEOUT_LOCALLY_SETTLED_CONTINUE；分别转到不同的c028/c042，正常结果使streak 1→0。单次安全超时继续2次，最大连续超时1，没有触发连续两次上限。最终PANEL_COMPLETED；cleanup=CLOSED、local_settled=True、exception_type=null，不覆盖主要结果。墙钟682.084438秒，调用延迟已知小计674.443739秒（48/48，含两次约60秒超时），不要与1425仿真分钟相混。

### 阶段和分母

|指标|全部|A_RAW|B_FEASIBLE|
|---|---:|---:|---:|
|计划 / 已处理 / 意图 / 客户端尝试|48 / 48 / 48 / 48|24 / 24 / 24 / 24|24 / 24 / 24 / 24|
|HTTP已观察|46|23|23|
|契约、严格JSON、目录有效、规则检查|各46|各23|各23|
|候选成员、启动接受、活动完成|各46|各23|各23|
|规则拒绝 / 已知commitment失败 / 其他fatal|0 / 0 / 0|0 / 0 / 0|0 / 0 / 0|
|PROVIDER_TIMEOUT|2|1|1|
|NOT_RUN / UNKNOWN状态|0 / 0|0 / 0|0 / 0|
|有效提案证据未知|2|1|1|
|不变量已检查且通过|48/48|24/24|24/24|
|拒绝 / 有效提案|0/46|0/23|0/23|
|候选成员 / 有效提案|46/46|23/23|23/23|
|启动接受、活动完成 / 有效提案|各46/46|各23/23|各23/23|
|已观察完成 / 全计划|46/48|23/24|23/24|

契约有效的false两行是超时没有有效返回的既有标记，不是两次响应契约错误；HTTP与严格JSON等有2行未知，UNKNOWN状态数0不代表所有字段已知。已观察完成/全计划保留超时占用，不把未知提案补为有效或行为失败。终态归档48/48完整，但可评分提案46/48、完整配对22/24，所以 `REAL_DATA_COVERAGE=PARTIAL`。

各状态都是4次尝试、4次不变量PASS、拒绝与已知commitment失败0。下表给出有效提案/活动完成（两者相同）和超时；家族按状态合并，不把重复当独立人群。

|状态 / 家族|有效并完成A/B|超时A/B|
|---|---:|---:|
|s01 游戏未拥有|2 / 2|0 / 0|
|s02 游戏已拥有|2 / 2|0 / 0|
|s03 餐前|2 / 2|0 / 0|
|s04 餐后仍饥饿|2 / 1|0 / 1|
|s05 媒体进行中|2 / 2|0 / 0|
|s06 媒体已结束|1 / 2|1 / 0|
|s07 home|2 / 2|0 / 0|
|s08 office|2 / 2|0 / 0|
|s09 支付足够|2 / 2|0 / 0|
|s10 支付不足|2 / 2|0 / 0|
|s11 餐食库存可用|2 / 2|0 / 0|
|s12 餐食库存为零|2 / 2|0 / 0|
|OWNERSHIP（8尝试）|4 / 4|0 / 0|
|POST_MEAL_NEED（8尝试）|4 / 3|0 / 1|
|MEDIA_PROGRESS（8尝试）|3 / 4|1 / 0|
|ACTIVITY_LOCATION（8尝试）|4 / 4|0 / 0|
|MEAL_PAYMENT（8尝试）|4 / 4|0 / 0|
|MEAL_SUPPLY（8尝试）|4 / 4|0 / 0|
|已知glm-5.3后端（46响应）|23 / 23|0 / 0|
|未知后端（2无响应尝试）|0 / 0|1 / 1|

### 全部24个配对，而非只列成功者

下表“完整”同时指双方有效、双方原规则可评分及双方完成；“同”指已确认同glm-5.3后端，“未知”不推断相同或不同。超时方完成字段为未知，不能当作拒绝或已知活动失败。

|配对|状态|重复|A / B|有效 / 可评|后端|不完整原因|
|---|---|---:|---|---|---|---|
|p001|s10|1|完成 / 完成|完整 / 完整|同|无|
|p002|s03|2|完成 / 完成|完整 / 完整|同|无|
|p003|s07|2|完成 / 完成|完整 / 完整|同|无|
|p004|s10|2|完成 / 完成|完整 / 完整|同|无|
|p005|s08|2|完成 / 完成|完整 / 完整|同|无|
|p006|s09|2|完成 / 完成|完整 / 完整|同|无|
|p007|s11|2|完成 / 完成|完整 / 完整|同|无|
|p008|s01|1|完成 / 完成|完整 / 完整|同|无|
|p009|s11|1|完成 / 完成|完整 / 完整|同|无|
|p010|s12|1|完成 / 完成|完整 / 完整|同|无|
|p011|s09|1|完成 / 完成|完整 / 完整|同|无|
|p012|s02|2|完成 / 完成|完整 / 完整|同|无|
|p013|s06|2|完成 / 完成|完整 / 完整|同|无|
|p014|s06|1|未知 / 完成|不完整 / 不完整|未知|A_PROVIDER_TIMEOUT|
|p015|s07|1|完成 / 完成|完整 / 完整|同|无|
|p016|s12|2|完成 / 完成|完整 / 完整|同|无|
|p017|s04|1|完成 / 完成|完整 / 完整|同|无|
|p018|s02|1|完成 / 完成|完整 / 完整|同|无|
|p019|s05|1|完成 / 完成|完整 / 完整|同|无|
|p020|s03|1|完成 / 完成|完整 / 完整|同|无|
|p021|s04|2|完成 / 未知|不完整 / 不完整|未知|B_PROVIDER_TIMEOUT|
|p022|s08|1|完成 / 完成|完整 / 完整|同|无|
|p023|s01|2|完成 / 完成|完整 / 完整|同|无|
|p024|s05|2|完成 / 完成|完整 / 完整|同|无|

有效完整22、可评分完整22、同后端可评分22；已知不同后端0、后端未知2。22对均双方接受且完成；A拒绝/B接受0、A接受/B拒绝0、双方拒绝0。两不完整对分别A未知/B完成和A完成/B未知，不进入可评分差值。

全部完整可评对与同后端敏感性子集恰好相同：拒绝率B−A=0个百分点、活动完成率B−A=0个百分点，覆盖22/22；相对于原计划覆盖22/24（91.67%）。同时保留全分配口径：每臂已观察完成23/24（95.83%），不隐藏超时。超时可能不随机；完整配对并不能消除其选择偏差，也不把24对当24个独立人群。没有事后换检验、阈值或选择有利子集。

### 已知成本和缺失

|成本类别|A已知小计|B已知小计|全部已知小计|缺失行（A/B/全部）|覆盖（A/B/全部）|
|---|---:|---:|---:|---|---|
|input tokens|8783|11526|20309|1 / 1 / 2|23/24 / 23/24 / 46/48|
|output tokens|12578|17446|30024|1 / 1 / 2|23/24 / 23/24 / 46/48|
|reasoning tokens|12274|17124|29398|1 / 1 / 2|23/24 / 23/24 / 46/48|
|prompt字符|29710|41760|71470|0 / 0 / 0|24/24 / 24/24 / 48/48|
|调用延迟秒（含超时）|299.987451|374.456288|674.443739|0 / 0 / 0|24/24 / 24/24 / 48/48|

token只是已知小计；2个超时的服务端token及收费未知，不能补0或称完整付费成本。output与reasoning分别保存，**不把reasoning再加到output**。已实际返回reasoning使用量，因此本轮不能宣称关闭深度思考；短输入也不意味着短输出预算，更不是模拟小模型能力。

|分析口径|输入token B−A均值|延迟B−A均值秒|prompt字符B−A均值|覆盖说明|
|---|---:|---:|---:|---|
|全部24已分配对|119.3182|3.102868|502.0833|input只知22/24，延迟与字符24/24；保留两超时|
|全部22完整可评对|119.3182|3.504199|506.3182|22/22已知，原计划22/24|
|同后端22完整可评对|119.3182|3.504199|506.3182|同一子集，不另挑有利对|

完整22对输入A/B小计8400/11025，差2625，均值381.8182→501.1364（**+31.25%**）；全臂已知小计差2743来自不同单侧可见集合，不冒充配对差。完整对延迟均值10.0702→13.5744秒（+3.5042秒，约+34.80%）；全24对含超时均值差+3.1029秒。全计划prompt总字符增加40.56%，完整对子集增加40.92%。这些是描述性成本，不证明服务时延因果稳定；p017的长延迟、两超时和仅两重复使均值受尾部影响。没有报价信息，不推算人民币费用。

### 行为分布、案例和不能下的结论

|条件|activity / target|次数 / 有效提案|
|---|---|---:|
|A_RAW|TRAVEL / restaurant|18 / 23|
|A_RAW|MEAL / food_meal|5 / 23|
|B_FEASIBLE|MEAL / food_meal|19 / 23|
|B_FEASIBLE|MEAL / food_bread|4 / 23|

B的有效输出全为MEAL，**不是更多选择LEISURE**；A大多TRAVEL。安全案例c001/c002（s10支付不足同态）：A出行到restaurant、B选择已有food_bread进食，二者都经原规则接受并完成；c003/c004（s03餐前）双方MEAL food_meal并完成。没有免费赋予对象、自动代购或替换模型提案。

出行完成和吃饭完成是不同活动的完成，不能只凭“完成”把它们当同一种需求满足。这里只描述选择变化，不事后把“必须吃饭”立为标准答案来宣布B改善；重复MEAL也不判错。没有PLAY/WATCH等真实选择覆盖，不能因所有权/媒体状态在面板里存在就声称模型已自主取得游戏或连续追完series_a。s06是合法长历史终态，其时间和需求与其他状态差异继续保留为限制。

保留工程参考：只读候选共享规则、执行再检查、冻结同态对照、预算与持久证据、受测安全单超时继续及只读恢复。现在不能声称B必要/稳定增益、短上下文模拟小模型、长期人格/真人相似性、总体错误率为0。若未来需要评价需求满足/活动适当性或检验更难对照，先另行预注册评分和预算，不在本轮追补。

### 产物、完整性与最终标记

源目录 `run/evaluation/q6_2_fixed_state_panel/q62-panel-real-v2-01/`（manifest/config/session/session.sqlite3、逐cell world与安全证据、cells/summary/paired/report）。本地确定性重算的安全指标、中文片段和hash在 `run/evaluation/q62_v2_analysis/q62-panel-real-v2-01/`；只读导出在 `run/evaluation/q6_2_fixed_state_panel_recovery/q62-panel-real-v2-01/`。原进程停止后才导出，全部297个源文件hash前后相同、counts和原termination一致，新请求0；不改原summary、DB或runner结论，不resume动作。

脱敏可复核SHA256：原summary `f491c6421a2ae54f12baeabed4c8100f18d096593b5563fb6486f21d94535635`；cells `7daaaf34262c8dea2164084eabf3b7ec8622d2b20a6440d606cb6d9b91e85311`；paired `9a55bde906b132ed4a0b4dcfa649369cdadec3fe734c2edd9c162eb39832684c`；manifest `a3a1546a371e299a251251e555d404ee72876d4fc6da2f2c26c26f98b8a35d64`。大型run和原始文本不上传Git，本文小表/hash与代码/配方/测试可复核；真实实验不重跑。

`Q6_2_FIXED_PANEL_REAL_AUTHORIZED=YES`（本次一次许可已使用完）；`Q6_2_FIXED_PANEL_REAL_EXECUTED=YES`；`REAL_PROVIDER_REQUESTS_THIS_TASK=48`（客户端边界）；`REAL_DATA_COVERAGE=PARTIAL`；独立研究`MODEL_BENEFIT=NO_CLEAR_DIFFERENCE`；`LONG_TERM_HUMAN_LIKENESS=NOT_TESTED`；原Q6.1 `SHORT_HORIZON_STATE_CONTINUITY=INSUFFICIENT_EVIDENCE`。

本轮到此收束：推送现有PR #6供人工review，不自动merge。下一步只建议审核成本、宏活动与需求满足的评分边界，之后如需新实验另立协议/授权；不自动追加样本或新功能。完整离线/CI与后续结果文档验收见[验收账本](../current/acceptance.md)。

## 2026-10-08｜M1.5独立后续：真实后果与提示干预审计

本节是原v2结束后的新零请求工作，不改写上面真实实验的判断、runner自动字段或原产物。基线 `b7c6d503dc09c0c2d7dc32467b277a23a1a26404`；新分支 `research/q62-outcome-audit`，以仍OPEN的PR #6研究分支为stacked PR base，不自动合并。

审计分三层：L1事实约束；L2可观测的饥饿、精力、钱、模拟时间及对象变化；L3待人工确认的行为适当性。原单次TRAVEL通常是准备性出行，MEAL可能内含旅行、购买、进食；完成不同粒度的活动不能自动得出相同需求满足，更不能预言A未观测的下一步。全部24配对及两个超时保留，主要描述性统计使用22完整对；不将缺失变成零，也不把相同十二个冻结状态的重复当独立人类样本。

冻结提示核对发现：B system比A追加116字符的选择说明；用户JSON只多候选、共享事实相同；activity/target字典序使12/12状态MEAL先于TRAVEL。24次B分配中的候选名称曝光MEAL44、TRAVEL72、WATCH22、PLAY2、WORK2，MEAL宏步骤没有在候选对里展开。实际B选择MEAL23次，而A选择TRAVEL18/MEAL5；这个联合模式只是机制假设证据，不能分离数据、指令、长度、顺序、重复曝光与宏粒度的各自因果作用。

完整客观delta、家族分布、成本权衡与七个问题的回答见[M1.5中文报告](q62_outcome_audit.md)，小型[安全结果表](../reference/q62_outcome_audit_results.json)可核对；[条件隐藏的人审包](q62_outcome_human_review.md)不包含任意模型原文或研究条件标签。未触发WATCH/PLAY/WORK不能宣布媒体/所有权/工作机制已在真实行为中通过；原31.25%输入增幅、缺失token和延迟事实保留，不推算费用。

`EVALUATION_TYPE=EXPLORATORY_POST_HOC`；`NEW_REAL_PROVIDER_REQUESTS=0`；`ORIGINAL_Q62_CONCLUSION=NO_CLEAR_DIFFERENCE`；`HUMAN_REVIEW_COMPLETED=NO`；`HUMAN_NEED_SATISFACTION_CONCLUSION=UNRESOLVED`。下一步先[D-09人工讨论](../review/decisions.md#d-09)，没有批准新的真实请求、提示改写、采购或饥饿参数调整。
