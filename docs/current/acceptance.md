# 验收账本：哪些数字属于哪一轮

本页整理已有记录，不把文档更新当作重新运行科学实验。不同测试范围不能相加；服务返回、动作接受、活动完成与人类真实性分开。

| 阶段/版本 | 已记录验收 | 未覆盖 |
|---|---|---|
| Q3 Attempt 2 | 180请求162成功；43组配对；focused11、当时全库485 | 长期状态、真实参数 |
| Q4 | 192请求174成功；33组四臂共同成功 | 精确最小Resource、动态投影 |
| Q5 | focused11、全库508、四档虚拟规模通过 | 真实千万payload/搜索/并发 |
| Q6初版 | 全库555通过、8历史数据跳过；7/30天恢复一致 | 真实模型自主多天 |
| Q6.1 Attempt 3本机54ed48f | 预检1次PASS；正式4请求、3完成1拒绝；专项113 | 原四次全部接受门槛、媒体/所有权变化 |
| 同次全库/AS2 | 缺litellm，2收集错误，AS2阻塞 | 不能写PASS |
| Q6.2初始代码1f4a177的CI | 核心119、全库660通过/8跳过；AS2/Ruff/回放/长脚本通过 | 当时原文件未核验、无真实A/B |
| Q6.2后续准备（报告e2d85c6） | WSL源artifact核验True、无差异；本地Q6.2 57、联合129；CI核心129、全库670通过/8跳过；AS2及A/B dry-run通过 | 真实A/B未运行、模型收益NOT_TESTED |
| 主线文档整理 | 文档/仓库专项19；全库570通过/8跳过；AS2及7/30天通过 | 当时不含研究分支业务代码 |
| Q6.1/Q6.2 主线集成 `bea7dbf` → PR #4 | runtime-contract PASS；core-contract PASS；full regression **685 passed、8 skipped**；AS2 PASS；Q6.2 回放、A/B dry-run、7/30天均PASS | 真实A/B仍未运行 |

Q6.2初版运行ID `35680426146`；后续准备运行ID `35842428974`。文档整理验证 `35843575445` / `35843575443`。主线集成第一次 CI `35951653671` 暴露 1 个旧文档保护测试不兼容（684 passed、8 skipped），修复为新 Git-history 退役策略后，最终 CI `35951841827` 全绿并合并 PR #4，merge commit `cce3e7bd850f72faf0efa41017491d392b00ee11`。

八项跳过依赖未入 Git 的历史真人语料，不计通过。后续 CI 成功不改写用户早期本机失败，也不等于远程修好了本机所有环境。

## 当前研究判定

Q3目录是工程参考；Q4最小值未知；Q5结构门槛通过；Q6状态机制通过；Q6.1原结论仍证据不足；Q6.2 原产物核验与旧短链工程已进入主线，旧8-call真实短链未测；固定面板v2已真实执行，主指标为NO_CLEAR_DIFFERENCE、可评分覆盖PARTIAL，不证明等价或长期真人效果。

分支与主线代码位置见[分支状态](branches.md)。

## 2026-10-08｜Q6.2 固定状态配对面板（本轮新增，零真实请求）

基线 `53b1244ac0f8562fd01fe8439e73ca900a40dd8c`；分支 `research/q62-fixed-state-panel`。首个实现提交 `5aad834257bcc51f390b21c0b3abae4011e19405`；补修提交 `31a2bdc0062ef12029d29c3d0f43a32847df23ba`，保留未知HTTP收据并收紧安全元数据，不改写前一个提交。中文文档与首轮离线账本提交 `2c90612a9f361e8988136cfc1b253642c4086a3f`；新[PR #6](https://github.com/richardssheik107-hub/Agent-Society/pull/6)面向main，PR #4/#5 不追加、不自动merge。测试环境和轻量runtime均为Python3.12.14；runtime pip check无依赖冲突，复用现有环境，未读取实际.env或provider配置。

### M0 差距与最小修复

| 已有机制 / 实际缺口 | 本轮最小补齐 | 没有改什么 |
|---|---|---|
| world 已持久化REQUEST_STARTED、最终decision、commands/events；缺整个面板身份/48预算 | session排他创建、48预分配计划、逐cell原子claim、唯一request ID | 业务真值仍在各world，没建第二个RuleEngine |
| 请求响应到解析/执行前之间缺安全分阶段receipt | ActivityDecisionRunner可选evidence_hook；RESPONSE/PARSE/DECISION阶段仅安全字段 | 默认旧prompt、动作、日志行和停止语义不变 |
| world已提交但面板汇总没写，中断发送状态可能未知 | SQLite mode=ro/query_only恢复，不初始化/迁移，不client/凭据/动作重放 | 不实现resume/retry，不补写源库，不删失败目录 |
| 旧双短链用调用减失败推成功、token缺失求和归零 | 新Q6_2_FIXED_PANEL_METRICS_V1逐阶段计数、显式分母、known subtotal/缺失/覆盖率 | 不重写旧summary与历史结果 |
| 复用client时可能误用上一receipt、未知失败被混合 | 本cell元数据/计数隔离；HTTP/传输/契约/JSON/目录/规则/取消/架构分类 | 不改变真实client请求体、思考或输出参数 |

### 实际执行记录

| 范围 | 本轮实测结果 |
|---|---|
| 新面板专项 | 154 passed（27 runner/CLI、76 fixtures、30 ledger/recovery、21 reporting）；未知HTTP收据与敏感响应元数据新增回归均通过 |
| 新旧联合回归 | 最新279 passed：含上述154专项、原Q6.1、原Q6.2投影/双短链和continuity三文件；补修前曾为276 passed，不累加不同范围 |
| Ruff | 新增模块、共享continuity目录、入口与四个新增测试文件PASS |
| 默认dry-run | q62-panel-dry-20261008-01及干净提交上的-02：48 NOT_RUN，0真实请求，未构造真实client |
| 完整offline演练 | q62-panel-offline-20261008-01及干净提交上的-02：48 fake调用、48有效提案、22规则拒绝、26启动/完成、不变量48 PASS；24完整配对；0真实请求；input/output/reasoning各缺48行、known subtotal=null、覆盖0/48 |
| 脚本正反例 | A非法/B合法、两者合法、B更差、零有效分母均专项验证；不是模型行为结果 |
| 故障与恢复 | HTTP200无效JSON、HTTP/传输/timeout/取消/契约/导入错误、目录外字符串哨兵、未知backend/token、已知餐食失败、执行上限等测试PASS；意图/响应/world已提交三断点恢复源文件SHA256不变 |
| CLI只读导出 | q62-panel-offline-20261008-01及-02恢复报告各写新目录，NEW_PROVIDER_REQUESTS=0；源目录不重跑 |
| 本机全库/AS2 | NOT_RUN：独立测试环境缺litellm；没有往轻量runtime塞完整依赖，由完整CI验收 |
| 仓库/文档审计 | audit_repository / audit_documentation 均exit0、status PASS、errors=[]；文档/仓库专项19 passed；限定17文件范围、敏感格式扫描与保护文件/固定子模块核对PASS；Attempt1两历史commit仍为HEAD祖先 |
| 完整CI / AS2 | 首轮提交2c90612：核心283 passed；全库839 passed、8 skipped、0 failed；AS2_CONTINUITY_ADAPTER_PASS，LLM_CALLS=0、PROVIDER_REQUESTS=0；Ruff/审计/48演练/只读恢复/7天30天恢复均PASS；不沿用历史685作为本轮数字 |
| 本轮真实provider | 0；实际.env、key、真实配置读取0 |

开发期一次误填旧测试路径导致0 tests ran，已纠正为实际三个continuity测试文件；不是测试通过。首次Ruff发现4个闭包绑定问题和1个无用局部变量，已修复后重验PASS。保留失败事实，不放宽规则/删除测试。

本机产物在 `run/evaluation/q6_2_fixed_state_panel/`；只读报告在 `run/evaluation/q6_2_fixed_state_panel_recovery/`。这些忽略产物不入Git；配置、构造配方、代码和测试入库。早期-01产物是在开发工作树生成，记录对应基线，不能冒称最终commit执行证据。新-02产物记录干净提交 `2c90612a9f361e8988136cfc1b253642c4086a3f`、Python3.12.14，协议hash `693199e8c14ba54e75f580826c7cc2282b117d12774a021edc8df50875359cbf`；独立验证24对结构与有效覆盖均PASS。后续仅文档补账不改执行代码。

### CI证据与完成门槛

关联分支头 `2c90612a9f361e8988136cfc1b253642c4086a3f` 的[完整CI 37728484043](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37728484043)及[文档CI 37728484029](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37728484029)均SUCCESS；GitHub PR checkout实际测试临时合并提交 `a6b9e9638b73f777e9bf8836003253378c1c5d5a`（该head与基线53b1244），不是已经合并main。文档专项19 passed；核心环境Python3.12.15，全库/AS2为Python3.12.14，不能统写为一个patch版本。全库8项跳过：test_a2_final三项、test_behavior_prior_context两项、test_behavior_prior_index三项，均缺 `run/calibration/neutral_day_v1/calibration_manifest.json` 与 `behavior_days_core7_candidate.jsonl`，未伪造语料或改为通过。开发期失败事实与本机缺litellm限制仍保留。

CI核心产物 `continuity-core-evidence` 包含 ci-panel-dry/offline、只读恢复与原回放/长脚本证据；`continuity-regression-evidence` 包含全库JUnit、依赖和固定上游版本；文档产物为 `chinese-documentation-audit`。七天/三十天均 completed_days等于计划天数、不变量PASS、recovery_equivalent=true、provider_calls=0；AS2真实上游适配器PASS不代表本机安装了完整依赖。最终文档补账提交的重新验收状态见PR检查，不混作新的业务实验。

`M0_EVIDENCE_GATE=PASS`；`PANEL_SCENARIOS=12`；`PLANNED_CELLS=48`；`PLANNED_PAIRS=24`；`FIXED_STATE_PAIRING=PASS`；`OFFLINE_SYNTHETIC_RUN=PASS`；`READ_ONLY_RECOVERY=PASS`；`Q6_2_FIXED_PANEL_ENGINEERING_READY=YES`。工程门槛与模型收益分开，不授权真实运行。

`Q6_2_FIXED_PANEL_REAL_AUTHORIZED=NO`；`Q6_2_FIXED_PANEL_REAL_EXECUTED=NO`；`REAL_PROVIDER_REQUESTS_THIS_TASK=0`；`MODEL_BENEFIT=NOT_TESTED`。Q6.1 `SHORT_HORIZON_STATE_CONTINUITY=INSUFFICIENT_EVIDENCE` 保留，48只为未来容量。

## 2026-10-08｜v2 超时策略验收与唯一真实面板预注册

起点 `1b926a58ad986136aa121accf98f7dbb7dbaa2a6`，仍使用研究分支和PR #6；上面v1交付、零真实请求和当时未授权的记录原样保留。当前用户单独授权 `q62-panel-real-v2-01`，最多48客户端尝试（包含失败、超时和未知发送意图），额外真实探针0；不是长期授权，也不是48次成功保证。

v1配置字节不变、默认CLI仍v1；v2只增加版本、共享连续超时计数和安全终结证据。冻结12状态、48分配单元、24配对、seed20261008与A/B输入指纹不变。单次超时必须本地调用终结、无pending任务、状态/证据完整且不变量通过才进入不同的下一cell；连续两次超时以第二cell原始PROVIDER_TIMEOUT和session CONSECUTIVE_TIMEOUT_LIMIT停止。合法提案（含规则拒绝/已知活动失败）重置streak；其他错误仍立即停止。

开发期首轮集成376项通过；完整v2离线session `q62-panel-offline-v2-20261008-01` 已处理48 fake调用、48有效提案、22拒绝、26启动/完成、24完整配对、不变量48 PASS、真实请求0。此产物来自开发工作树，不冒称冻结提交的执行证据。最新专项、完整新HEAD CI、AS2和执行commit须在门禁完成后另记，不能沿用v1的839项。

开发期曾出现v2请求证据被旧导出字段覆盖造成27失败（8通过），修正合并语义后重验通过；同步aclose抛错漏出cleanup边界也已补修。独立审查发现真实授权记录碰到敏感字段守卫、末cell fatal恢复误报完成、HTTP408超时恢复误分类三处缺口，均新增回归，不放宽凭据守卫、不删除失败历史。报告另保留NOT_LOCALLY_SETTLED及请求计数缺失，不补0。

取消/清理各自有界等待；v2 CLI退出不使用asyncio.run对残余任务的无界gather，取消后只推进一次事件循环再关闭。残余调用仍报告未终结，而非伪装CLOSED；这是本机进程收尾，不证明服务端未收到/未计费。持续吞取消的fake需用离线子进程测试自然退出，不以测试finally人工清理冒称CLI有界验收。v1执行路径保持原样。

执行前必须代码、测试、五份中文预注册文档全部提交，干净HEAD的新CI完整回归/AS2通过，核对临时merge业务树；再安全只读检查指定.env的非敏感有效地址/别名和唯一session未使用，冻结规范JSON digest与实际HEAD。不增加OK/SLEEP探针，不改provider body、思考参数、prompt或初态。此处为预注册，真实尚未运行：`Q6_2_FIXED_PANEL_REAL_AUTHORIZED=YES`（仅指定session），`Q6_2_FIXED_PANEL_REAL_EXECUTED=NO`，`REAL_PROVIDER_REQUESTS_THIS_TASK=0`，`MODEL_BENEFIT=NOT_TESTED`。真实结束后才追加结果。

冻结前最终本机联合专项 **390 passed（64.93秒）**：新面板265（runner/CLI27、fixtures123、reporting38、recovery32、v2 timeout45）加原Q6.1/Q6.2/continuity125；文档/仓库专项另为19，不与全库混加。Ruff、audit_repository、audit_documentation、15文件限定范围/敏感格式扫描（命中0）、13保护文件字节与固定clean detached子模块审计PASS。两次误填不存在的测试路径产生0 tests ran，已纠正；末次恢复占位码缺口曾导致389通过/1失败，修正后390全通过，失败事实保留。

v2完整offline `q62-panel-offline-v2-20261008-02`：48 fake调用/有效提案、22拒绝、26完成、不变量48 PASS、24完整配对；只读导出到同名新恢复目录PASS、源不变、真实请求0。v1/v2公平性指纹完全相等：scenario `cf7794f6809f82bab7d50ef911aad14c861f3b1d10e4b78318a73a26a9070ede`，schedule `590331b29f0cc0ff66cc5ad055e68f03c06af550214cf704f312eca6c3251696`，fairness `ae7a53c51ea0fa4c6e76cf6af4133baae807bf931aedcef91bc10e67ccbd7f92`；规范v2协议hash `b66217fa18ce8740deec38334b157ff35f00455d8d2b431dd0b48531debffcc6`（不是文件原始SHA）。上述开发树产物仅为离线验收，新HEAD完整CI/AS2 **PENDING**，实际受保护配置尚未读、真实尚未运行。

### v2 执行前新HEAD门禁：已通过，不沿用v1数字

代码/预注册提交与真实执行commit均 `ae2123f50beaaca6bcac2dcca8e34659bd0a8b24`；[完整CI 37744586404](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37744586404)及[文档CI 37744586620](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37744586620)全部SUCCESS。核心 **394 passed**；全库 **950 passed、8 skipped、0 failed**；文档19 passed；Ruff/两审计/v1和v2的dry-run、全48 fake及只读恢复/7天30天恢复均PASS，实际AS2 `AS2_CONTINUITY_ADAPTER_PASS`、LLM_CALLS=0/PROVIDER_REQUESTS=0。核心与全库该run均CPython3.12.15；本机既有runtime为3.12.14，pip check通过，未重装本机litellm，local full/AS2仍NOT_RUN而非本机PASS。

CI临时merge `c7e41519c3dc73373d442e9aa336a20f040ea954` 的父为main基线53b1244和head ae2123f；执行前git diff HEAD/临时merge为空，整树相同。本机运行只用ae2123f，不用临时merge代替EXECUTION_COMMIT，也没有merge main。8项跳过仍为test_a2_final三项、behavior_prior_context两项、behavior_prior_index三项，缺两个冻结真人语料文件；不计通过、不伪造语料。GitHub日志中的Node/runner镜像迁移提示不是测试失败。

### v2 唯一真实执行、只读结果与交付

版本、协议、新CI、干净树、正确parent/fixed clean detached子模块、依赖、配置映射、唯一ID与其他进程检查通过。既有load_provider_config仅只读指定 `.env`，仅记录非敏感base/别名/key存在；有效配置匹配火山coding/v3与ark-code-latest，不打印API key。正式 `q62-panel-real-v2-01` 只启动一次，运行窗不改tracked文件/HEAD/环境；调用48后结束(exit0)且原runner已停止，不补发。额外真实探针、smoke/preflight、旧短链、重试/修复/补样本均0。

|真实范围|实际结果|
|---|---|
|计划 / 处理 / 登记意图 / 客户端尝试|12状态、24对；48 / 48 / 48 / 48|
|HTTP / 契约 / 严格JSON / 目录有效 / 规则检查|各46；超时无回复2，不算契约/JSON fatal|
|启动 / 活动完成 / 候选成员|各46；A/B各23|
|拒绝 / 已知commitment失败 / 其他fatal|0 / 0 / 0|
|超时 / NOT_RUN / UNKNOWN状态|2（A/B各1） / 0 / 0；提案字段未知2|
|client provider计数 / 证据缺失|已知48、缺失调用计数0、未知意图0；服务端收到/计费未知2不能据本地counter证明|
|实际响应后端|46次glm-5.3、2次UNKNOWN；不说全部48确认同模型|
|超时继续 / 最大streak / session终态|c027(A s06)、c041(B s04)均本地安全终结并进入下一不同cell；2 / 1 / PANEL_COMPLETED|
|cleanup / 不变量|CLOSED、local_settled=True、exception=null；48/48不变量PASS|
|配对|22有效完整、22可评、22同后端；后端不同0、未知2；双方接受且完成22，两个超时配对缺失|
|主要差值|完整及同后端配对拒绝B−A=0、完成B−A=0；不补未知、不混超时为行为拒绝|
|成本|input/output/reasoning已知小计20309/30024/29398，各缺2行、覆盖46/48；分开记录不相加；不能声称关闭思考|
|配对成本|完整22对input平均+119.3182（+31.25%，原计划覆盖22/24）；latency平均+3.5042秒；全24对含超时latency平均+3.1029秒、字符平均+502.0833（+40.56%）|
|行为分布|A18TRAVEL restaurant+5MEAL food_meal；B19MEAL food_meal+4MEAL food_bread；B非更多LEISURE|
|只读核对 / 恢复|原进程结束后本地确定性重算counts/stages/ratios/24pairs与原一致；新恢复目录、297源文件hash全不变、新请求0|

原安全summary与runner NOT_TESTED未手工改写，独立中文研究结论为 **NO_CLEAR_DIFFERENCE**：本面板主指标未见改善，不是等价证明，也不因输出更集中MEAL而另设需求满足评分宣布胜利。客户端尝试与终态归档覆盖48/48，HTTP及评分覆盖46/48、完整配对22/24，故REAL_DATA_COVERAGE=PARTIAL。长期真人相似性NOT_TESTED；Q6.1证据不足历史不变。

源 `run/evaluation/q6_2_fixed_state_panel/q62-panel-real-v2-01/`；只读恢复 `run/evaluation/q6_2_fixed_state_panel_recovery/q62-panel-real-v2-01/`；确定性分析 `run/evaluation/q62_v2_analysis/q62-panel-real-v2-01/`。中文完整小型结果表、全部24配对、分层与成本、源SHA见[问题档案](../studies/q62_action_projection.md)。大run/DB/原始文本与凭据不强行上传，代码/配置/测试/脱敏中文证据入Git。本次许可已用完，PR #6继续OPEN、不自动merge，结果提交后的文档/审计与新CI另列，不重跑真实面板。

结果阶段只改上述五份中文文档与对应文档状态断言，不改已冻结业务/协议/provider代码。文档专项首次18 passed/1 failed：旧断言硬要求所有Q6.2“真实尚未运行”，与新固定面板结果冲突；改为同时守护旧8-call未运行、新面板已运行、NO_CLEAR_DIFFERENCE/PARTIAL、非等价和长期未测试，未删除测试或把未运行塞回现行状态。最新相关专项 **89 passed**（文档/仓库19＋reporting38＋recovery32，范围与390有重叠，不相加）；Ruff与两审计PASS。全部24配对中文表逐行与原safe pairs一致、297源hash复核PASS、执行后src/scripts/config/.github业务字节未变；本轮最终16文件敏感格式命中0、13保护文件与子模块审计PASS。本文提交前结果HEAD新CI为 **PENDING**；推送后的实际状态以PR #6 checks与最终交付汇报为准，不能混作执行前950/8完整CI。

## 2026-10-08｜M1.5：真实行为结果、需求改善与提示干预离线审计

起点 `b7c6d503dc09c0c2d7dc32467b277a23a1a26404`（PR #6 的已核验 OPEN 分支头），新分支 `research/q62-outcome-audit`。本轮是 **EXPLORATORY_POST_HOC**，不是新模型实验：只读已有 `q62-panel-real-v2-01`，不加载实际 .env / provider 配置，不构造客户端，不执行真实 runner、探针、补样、重试或动作重放。原执行 commit `ae2123f50beaaca6bcac2dcca8e34659bd0a8b24` 与原协议 hash `b66217fa18ce8740deec38334b157ff35f00455d8d2b431dd0b48531debffcc6` 不变。

### 本轮实测与交付门禁

| 范围 | 实际结果 / 明确限制 |
|---|---|
| 新审计专项 | 129 passed：客观结果 62、完整性/CLI安全 39、冻结提示审计 28；成功 CLI 路径在新解释器中禁止网络、provider/client 导入、凭据读取和原始 journal 解码 |
| 新旧联合专项 | 最终523 passed（68.94 秒；首轮73.70秒）；包含 continuity、Q6.1/Q6.2 与新审计，范围重叠，不与129相加 |
| 来源与只读核对 | 48 world + session SQLite 只读 immutable/query_only；297 源文件全部 SHA256 前后相同；48单元/24配对/22完整可评配对；原恢复与分析一致；c027/c041 两超时保留，效果 null/UNKNOWN，不补0 |
| 提示和输入核对 | 离线重建12冻结状态、48分配单元；初始状态、候选、system/user及长度指纹一致；不公开完整prompt或completion |
| 盲审包 | 24对/48案例、随机中性ID，初始资源/单位/实际购买消费/宏活动粒度齐全，判断全部空白；解盲键仅在忽略的本地目录；HUMAN_REVIEW_COMPLETED=NO |
| 文档/仓库与隐私 | 文档18 passed；两审计PASS/errors=[]、29中文md；20文件限定范围、强秘密格式0命中、旧业务/固定clean detached子模块/Attempt1历史保护PASS；公开JSON与最终产物逐字节相等（390675 bytes，SHA256 4d86090b65024ca2a9d634fb20ba44504639fc0bca04728aeb4f3a372fe1edfe） |
| 本机全库 / AS2 | NOT_RUN：既有轻量环境缺 litellm，未扩装或修改真实运行环境；完整CI另验，不冒称本机通过 |
| 实现提交完整CI / AS2 | 9528e8d 的新完整CI37778453314与文档CI37778453278均SUCCESS；核心523、全库1082 passed/8 skipped/0 failed；文档22（18导航+4仓库）；AS2 PASS，LLM_CALLS=0/PROVIDER_REQUESTS=0；不用原950/8代替 |
| 新真实请求 / 人工评分 / 新实验实施 | 0 / 0 / 0 |

最终只读审计目录 `run/evaluation/q62_outcome_audit/q62-real-v2-outcome-audit-03`；开发期 -01、-02 产物保留，不覆盖。公开报告和盲审包分别来自最终 report/packet，公开安全 JSON 与最终 safe_delivery 逐字节核对；297文件 SHA 列表摘要 `b72156ff956486cc1f56163037fc0bd588dd8917e1e68eb24ffcaf1df88af3f9`。原 run/SQLite/原始模型文本/实际配置与私有解盲键不入Git。

### 开发期失败与复核修正：不删除失败事实

初轮客观测试出现10失败/34通过：测试参数覆盖、fixture与接口约定及尚未写完的CLI等问题逐项修正；随后新回归发现布尔字段可能保留任意字符串、部分媒体offset误标OBSERVED，两处收紧为安全类型和UNKNOWN，不改变原业务。完整合成来源测试曾错误使用绝对advance目标、缺失冻结指纹和超时A/B分配不符，修正测试构造，未放宽生产来源验真。Ruff早期未使用变量问题也已修复。

独立审查发现公开 JSON 复制混入工具截断提示（本地安全产物原本合法，源不变）；交付前以完整分块读取重新应用，增加公开 JSON 解析/维度/超时null回归。后续复制辅助脚本的空数组映射和误把旧污染文本作为新截断问题，均在写入前停止；不当作审计科学结果或通过。独立读者要求补充单位、初始可用资源、TRAVEL/MEAL宏粒度和购买/消费实数，已更新中性盲审上下文并复查通过，48判断仍空白。新增验收记录的D09链接初写为#d09，独立联合验证145通过/2失败（同一broken anchor）；修正为#d-09后独立复验147 passed，无剩余阻塞。

### 研究与工程分层

匹配22对中，B−A平均饥饿缓解 +422.272727 milli，同时精力变化 −23.181818 milli、金钱变化 −1490.909091 cents、模拟耗时 +24.545455 min；完整指标统计、全部24配对及缺失分母见[本轮报告](../studies/q62_outcome_audit.md)。这反映18个匹配对的到店准备动作与进食宏活动差异，不能以“到店未吃”判人类失败，也不能用“吃饭已完成”证明人类最优。

原主指标结论仍 **NO_CLEAR_DIFFERENCE**；本轮 **HUMAN_NEED_SATISFACTION_CONCLUSION=UNRESOLVED**。长期真人相似性 NOT_TESTED、Q6.1 INSUFFICIENT_EVIDENCE 保留。B是候选信息、system指令、顺序、长度和活动粒度的复合提示干预，无法分离各机制因果。新协议候选仅为[人工讨论D09](../review/decisions.md#d-09)，未实施、未预先胜选；任何新增真实调用需要新冻结协议、预算及单独授权。

本轮仅新增独立离线工具/配置/测试、安全结果及中文文档；旧 Q3/Q4/Q5/Q6/Q6.1/Q6.2/provider 业务文件与官方子模块不改。[新PR #7](https://github.com/richardssheik107-hub/Agent-Society/pull/7)以 `research/q62-fixed-state-panel` 为base；原PR #6继续OPEN，不自动merge，不force-push。

### 本轮新CI证据与最终文档补账

实现提交 `9528e8daa7c82c0ca827bb612a439ccb0a2f4d00` 的[完整CI37778453314](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37778453314)与[文档CI37778453278](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37778453278)均SUCCESS。实际核心523 passed（225.00s）、全库1082 passed/8 skipped（320.87s）、文档22 passed；Ruff/两审计、v1/v2零请求演练与恢复、7天30天均PASS；实际固定上游AS2 `AS2_CONTINUITY_ADAPTER_PASS`，LLM_CALLS=0/PROVIDER_REQUESTS=0。三环境均CPython3.12.15；本机3.12.14缺litellm，local full/AS2仍NOT_RUN，不能说被CI远程修好。

CI临时merge `df70e7154ac0c077f021e2f339facc41b33d3ab7` 的parents严格是base b7c6d503与head9528e8d，GitHubAPI tree `6b1044a1fd46122bf05b4e7421328a6e1881a475` 与本机HEAD整树相同；它是PR测试树，不是已合并main。官方子模块CI与本机同为固定 `670c94fff7c64c4f79b632125f2ccf968155e746`。Git fetch临时ref等待期间一次提前读ref失败，随后结束该未完成取回，以GitHubAPI父提交/整树SHA核对，不把失败命令当PASS；PR创建首次Windows/WSL路径传递失败，之后用原生CLI明确文件路径成功，查询确认只有PR #7。

8跳过仍为test_a2_final三项、behavior_prior_context两项、behavior_prior_index三项，缺 `run/calibration/neutral_day_v1/calibration_manifest.json` 与 `behavior_days_core7_candidate.jsonl`；没有伪造、上传或把缺失语料测试算通过。7/30天均completed_days等于7/30、不变量PASS、recovery_equivalent=true、provider_calls=0、model_behavior_proven=false，不把工程恢复写成模型真人证明。

本次后续补账只修改中文报告/本账本，离线业务与安全结果完全相同；最终文档提交重新触发完整CI，其实际run见PR #7检查与最终交付汇报，不冒称本段9528e8d的run就是后续HEAD。完成后不启动下一研究阶段；NEW_REAL_PROVIDER_REQUESTS=0。


## M2 本轮验收：当前版本单独记录

起点 `53b1244ac0f8562fd01fe8439e73ca900a40dd8c`，分支 `research/m2-acquire-closed-loop`，目标 main；实现提交 `46fb620c0e53a5ab6e03836c95f9a64e1354430b`。[新 PR #8](https://github.com/richardssheik107-hub/Agent-Society/pull/8)为独立交付，未合并；本节所在后续提交只补结果记录，业务代码不变。PR #6/#7 保持原 HEAD 与 OPEN，旧固定面板与 M1.5 结果不是本轮验收数字。

| 本轮范围 | 当前实际记录 | 最终判定 / 待补证据 |
|---|---|---|
| M2 focused tests | 87 passed，包含 79 个专属用例与 8 个 CLI 场景用例 | PASS：本轮统一预检结果 |
| 核心验收组合（与本轮 CI core 合同同范围） | 本机 216 passed | PASS：本机实际执行，独立 CI 结果仍另记 |
| 原 continuity/decision/provider contract/Q6.1/Q6.2/购买消费/规则与 reducer 联合回归 | 159 passed | PASS：仅此受测联合范围，不与 focused 相加 |
| M2 独立 offline runner | clean 实现提交的 `m2-offline-acceptance-01`：17/17 场景 PASS；fake 高层调用 3；LLM_CALLS=0；PROVIDER_REQUESTS=0 | PASS：合成与 fake 工程证据，非真实模型研究 |
| 完整闭环 | 同地 game_a：余额 300000→297000 cents、库存 100→99、拥有量 0→1、获取 0 分钟；重开后独立 PLAY 累计 45 分钟 | PASS：实际离线执行摘要，详情见本轮新 session |
| 异地获取 | 合成物品价格 4200 cents，余额 300000→295800；旅行 15 分钟；饥饿 800→815、精力 700→685 | PASS：到达先保存 BUY0，下一明确 advance 结算 |
| Ruff | 新代码、测试与文档审计工具通过 | PASS：最终提交再核对差异范围 |
| 文档与仓库专项 / 两项只读审计 | 专项 25 passed；audit_repository、audit_documentation 均 PASS | PASS：本轮统一预检结果 |
| 本机完整回归 / AS2 | Python 3.12.14；`find_spec("litellm")` 为 False | NOT_RUN：本机依赖不完整，不冒充全部通过 |
| 独立完整 CI / 固定 AS2 子模块适配器 | 实现 SHA `46fb620`：全库 778 passed、8 skipped；AS2_CONTINUITY_ADAPTER_PASS，LLM_CALLS=0、PROVIDER_REQUESTS=0 | PASS：本轮新 CI，不是本机完整环境或旧 PR 的结果 |
| 历史产物保护 | 四个受保护目录 316 文件的字节复核 unchanged=True；原真实 297 文件 listing digest 与 M1.5 登记一致（前缀 b72156ff） | PASS：未改旧 session、恢复、分析或 M1.5 final |
| 官方子模块保护 | 固定 `670c94fff7c64c4f79b632125f2ccf968155e746`，工作区 clean | PASS：未升级或修改官方子模块；适配器执行结果另列 |
| Secret scan / 受保护文件差异 | 新增及修改文件凭据模式扫描无匹配；共享业务仅 engine.py，旧 context/action_projection/models/store 和 Q3/Q4/Q5 不变 | PASS：启发式扫描不是凭据不存在的数学证明；提交前仅纳入本任务文件 |

本轮[工程 CI 37787843811](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37787843811)已 success：核心216（JUnit 中 M2 精确87）、全库778/8、Ruff、仓库审计、M2离线17/17、七天/三十天恢复等价和固定AS2通过。[文档 CI 37787843755](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37787843755)已 success：25 passed、静态与两审计通过。各 job 为 Python **3.12.15**；本机仍是3.12.14。CI临时合并 `22749ff4a77e9652441cee75ae44051e0ec6f455` 的两个父提交为起点main和实现提交，其整树 `b15a5539010c98b095bd90cb768255054ddd6f33` 与实现HEAD相等，不代表merge main。

八项 SKIP 均因 `run/calibration/neutral_day_v1/calibration_manifest.json` 与 `behavior_days_core7_candidate.jsonl` 未入库：test_a2_final三项、test_behavior_prior_context两项、test_behavior_prior_index三项。没有伪造语料或计入通过。

正式离线产物只放在 `run/evaluation/m2_acquire/m2-offline-acceptance-01/`：provenance记录完整实现SHA、`git_dirty=false`、Python3.12.14；summary SHA256 `99acd6303b404ee0f67b174eb348a12454e05514b170336cead8b94e15b38ed0`，configuration SHA256 `09544b99162372b8bdd06e489662071e7bc1f653dcb60b0afd587e817ef42243`。开发01/02/03输出同样保留，但不冒充clean冻结结果。CI上传纯合成world、case与报告；大型本机run不入Git。旧 `q62-panel-real-v2-01` 不重跑。

```text
M2_EXPERIMENTAL_IMPLEMENTATION = READY
M2_ACQUIRE_ENGINEERING_READY = YES
HIGH_LEVEL_ACQUIRE_AVAILABLE_OPT_IN = YES
ACQUIRE_DEFAULT_ENABLED = NO
ACQUIRE_PRODUCTION_DEFAULT = DISABLED
PURCHASE_RULE_REUSED = PASS
MONEY_INVENTORY_ATOMICITY = PASS
OWNERSHIP_PERSISTENCE = PASS
ACQUIRE_TO_PLAY_PATH = PASS
MID_TRAVEL_FAILURE_HANDLING = PASS
REQUEST_ID_IDEMPOTENCY = PASS
RESTART_RECOVERY = PASS
CONCURRENT_STOCK_RACE = PASS
LEGACY_Q6_COMPATIBILITY = PASS
LEGACY_Q62_FROZEN_BEHAVIOR = PASS
D02_PRODUCT_SEMANTICS_APPROVED = NO
D09_HUMAN_REVIEW = PENDING
HUMAN_BEHAVIOR_APPROPRIATENESS = NOT_TESTED
REAL_PROVIDER_REQUESTS_THIS_TASK = 0
```

机制、事务与恢复边界见[M2 获取闭环](../studies/m2_object_acquisition.md)。以上PASS限实际受测SQLite与fake工程路径，不能扩大为分布式保证或人工产品批准。独立代码审查修复了跨人物请求归属、竞争命令覆盖冲突结果、未知中断误判成交，并有回归；独立文档读者审查修正工作台/运行手册的过时入口，保留唯一现行plan。


## 2026-10-09 分支整合说明

PR #6、PR #7 已合入主线；M2 工程整合使用两父提交，保留两项研究文档、M1.5 的 297 文件来源完整性与 M2 的 316 文件历史保护。M2 源自原 main，先前单独验收 778 passed/8 skipped **不与** PR #7 的 1082 passed/8 skipped 累加；联合主线结果需以本次集成 HEAD 的 CI 为准。无新真实 provider 调用，已使用的 Q6.2 48 次请求许可不再有效。D-02/D-09 仍待人工决定；M2 生产默认禁用。
