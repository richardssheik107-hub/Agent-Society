# 验收账本：哪些数字属于哪一轮

本页整理已有记录与 2026-10-08 的独立 M2 工程验收。不同测试范围不能相加；服务返回、动作接受、活动完成与人类真实性分开。历史表的“未覆盖”指对应记录当时的范围，不覆盖或改写后续研究事实。

| 阶段/版本 | 已记录验收 | 未覆盖（当时） |
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

## M2 本轮验收：当前版本单独记录

起点 `53b1244ac0f8562fd01fe8439e73ca900a40dd8c`，分支 `research/m2-acquire-closed-loop`，目标 main；实现提交、最终提交和新 PR：PENDING。PR #6/#7 保持 OPEN，旧固定面板与 M1.5 结果不是本轮验收数字。

| 本轮范围 | 当前实际记录 | 最终判定 / 待补证据 |
|---|---|---|
| M2 focused tests | 87 passed，包含 79 个专属用例与 8 个 CLI 场景用例 | PASS：本轮统一预检结果 |
| 核心验收组合（与本轮 CI core 合同同范围） | 本机 216 passed | PASS：本机实际执行，独立 CI 结果仍另记 |
| 原 continuity/decision/provider contract/Q6.1/Q6.2/购买消费/规则与 reducer 联合回归 | 159 passed | PASS：仅此受测联合范围，不与 focused 相加 |
| M2 独立 offline runner | 17/17 场景 PASS；fake 高层调用 3；LLM_CALLS=0；PROVIDER_REQUESTS=0 | PASS：合成与 fake 工程证据，非真实模型研究 |
| 完整闭环 | 同地 game_a：余额 300000→297000 cents、库存 100→99、拥有量 0→1、获取 0 分钟；重开后独立 PLAY 累计 45 分钟 | PASS：实际离线执行摘要，详情见本轮新 session |
| 异地获取 | 合成物品价格 4200 cents，余额 300000→295800；旅行 15 分钟；饥饿 800→815、精力 700→685 | PASS：到达先保存 BUY0，下一明确 advance 结算 |
| Ruff | 新代码、测试与文档审计工具通过 | PASS：最终提交再核对差异范围 |
| 文档与仓库专项 / 两项只读审计 | 专项 25 passed；audit_repository、audit_documentation 均 PASS | PASS：本轮统一预检结果 |
| 本机完整回归 / AS2 | Python 3.12.14；`find_spec("litellm")` 为 False | NOT_RUN：本机依赖不完整，不冒充全部通过 |
| 独立完整 CI / 固定 AS2 子模块适配器 | PENDING | PENDING：补当前 SHA、run 地址与结果 |
| 历史产物保护 | 四个受保护目录 316 文件的字节复核 unchanged=True；原真实 297 文件 listing digest 与 M1.5 登记一致（前缀 b72156ff） | PASS：未改旧 session、恢复、分析或 M1.5 final |
| 官方子模块保护 | 固定 `670c94fff7c64c4f79b632125f2ccf968155e746`，工作区 clean | PASS：未升级或修改官方子模块；适配器执行结果另列 |
| Secret scan / 受保护文件差异 | 新增及修改文件凭据模式扫描无匹配；共享业务仅 engine.py，旧 context/action_projection/models/store 和 Q3/Q4/Q5 不变 | PASS：启发式扫描不是凭据不存在的数学证明；提交前仅纳入本任务文件 |

旧八项真人语料 SKIP 的原因继续保留。完整 CI 未结束时维持 PENDING；不得借用 PR #6/#7 或旧 main 的测试数补成 PASS。新产物只放在 `run/evaluation/m2_acquire/<session>/`，旧 `q62-panel-real-v2-01` 不重跑。

```text
M2_EXPERIMENTAL_IMPLEMENTATION = READY
M2_ACQUIRE_ENGINEERING_READY = PENDING
HIGH_LEVEL_ACQUIRE_AVAILABLE_OPT_IN = YES
ACQUIRE_DEFAULT_ENABLED = NO
ACQUIRE_PRODUCTION_DEFAULT = DISABLED
D02_PRODUCT_SEMANTICS_APPROVED = NO
D09_HUMAN_REVIEW = PENDING
HUMAN_BEHAVIOR_APPROPRIATENESS = NOT_TESTED
REAL_PROVIDER_REQUESTS_THIS_TASK = 0
```

机制、事务与恢复边界见[M2 获取闭环](../studies/m2_object_acquisition.md)。实验实现已具备本机受测能力，整体工程完成标签仍等待完整 CI/AS2 和最终证据；不得用本机 preflight 或停止工作代替尚未完成的门槛。

## 当前研究判定

Q3 目录是工程参考；Q4 最小值未知；Q5 结构门槛通过；Q6 状态机制通过；Q6.1 原结论仍证据不足。Q6.2 原主线工程保留；[PR #6 固定研究](https://github.com/richardssheik107-hub/Agent-Society/pull/6)的原真实主结论为 NO_CLEAR_DIFFERENCE，[PR #7](https://github.com/richardssheik107-hub/Agent-Society/pull/7)的 M1.5 为 EXPLORATORY_POST_HOC。M2 只验收实验性获取和持久使用机制，不改变这些结论；D-02/D-09 人工决定仍未完成。

分支与主线代码位置见[分支状态](branches.md)。
