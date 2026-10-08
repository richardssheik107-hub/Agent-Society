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

Q3目录是工程参考；Q4最小值未知；Q5结构门槛通过；Q6状态机制通过；Q6.1原结论仍证据不足；Q6.2原产物核验与A/B工程准备已进入主线，真实收益待测。

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
