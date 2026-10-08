# M2：合法获取对象与后续使用闭环

更新：2026-10-08。实现基线：`53b1244ac0f8562fd01fe8439e73ca900a40dd8c`，独立分支 `research/m2-acquire-closed-loop`，实现 `46fb620c0e53a5ab6e03836c95f9a64e1354430b`，[PR #8](https://github.com/richardssheik107-hub/Agent-Society/pull/8)指向 `main`，未合并。本轮已完成fake闭环、离线与完整新CI/AS2，新增真实请求为 **0**。实际测试范围、提交与CI证据见[验收账本](../current/acceptance.md)。

导航：[唯一现行计划](../current/plan.md) · [研究状态](../current/research_status.md) · [D-02 产品语义](../review/decisions.md#d-02) · [D-09 人工行为评价](../review/decisions.md#d-09)

## 一、为什么需要 M2

对象目录中存在 `game_a`，只说明世界知道这个对象；人物没有所有权时，原 PLAY 规则仍应拒绝。Q6.1 的第四次选择因此得到 `ITEM_NOT_OWNED`。Q6.2 的可执行投影能够隐藏当前非法的 PLAY，却不能替人物完成获取。

M2 增加一个独立实验意图：

```json
{"activity":"ACQUIRE","target":"game_a"}
```

一次高层意图由确定性活动控制器完成必要旅行和购买。获得游戏后，必须由下一次新的高层 PLAY 提案开始使用；ACQUIRE 不自动 PLAY，也不把 PLAY 改成代购。

本轮范围为具有 `purchasable` 能力的非消耗性对象，以游戏为主。可在隔离 fixture 中放置带 `SYNTHETIC_FIXTURE` 来源的异地测试物品。食品采购、消费、订阅、贷款、动态定价、跨人物交易和真实大目录不在本轮范围内。

## 二、BUY 与 ACQUIRE 的职责

底层 `act(..., "BUY", ...)` 是已有的同地购买原语：检查卖家地点、库存、余额和拥有量，再改变事实。它没有“先到卖家、再成交”的高层活动生命周期。

ACQUIRE 使用原 `_check_purchase()` 和 `_buy()`；没有另建交易系统。启动时通过共享检查的 `require_location=False` 参数判断当前购买条件，实际 BUY 阶段再使用要求同地的完整检查。对象可用性与能力检查同样来自原 `_object()`。候选不预留库存，出发前的余额和库存不是未来保证。

规范 ID 和别名仍使用原 `resolve()`。不同别名指向同一对象记录和人物—对象关联，不新增物品身份。原购买规则的拒绝顺序保持不变：库存、余额等条件可能先于重复拥有被报告；不能为 M2 任意改写历史错误码优先级。

## 三、显式启用、版本与持久配置

新世界使用 `ContinuityWorld(path, acquire_enabled=True)` 显式启用。省略参数时，新世界默认禁用；重新打开已有世界时读取已保存配置。`world.activity_configuration` 给出 `M2_ACQUIRE_V1` 和 `acquire_enabled`，保存在 `meta` 表的 `activity_configuration` 键中。

已保存的启用状态与显式参数冲突时拒绝打开，要求明确迁移。没有该键的旧 seeded world 按禁用处理，也不能直接重新打开为启用；实验应使用新 world。打开存档不自动推进旅行、不补买、不重置拥有量。

这项兼容扩展不修改 `RuleParameters`、SQLite schema 版本或旧默认 snapshot 的字段。旧 `decision_prompt()`、`parse_proposal()`、`projected_prompt()`、全局活动常量和 Q6.2 的原 A/B 入口保留。只有独立 M2 提示与解析器增加 ACQUIRE。

```text
HIGH_LEVEL_ACQUIRE_AVAILABLE_OPT_IN = YES
ACQUIRE_DEFAULT_ENABLED = NO
ACQUIRE_PRODUCTION_DEFAULT = DISABLED
D02_PRODUCT_SEMANTICS_APPROVED = NO
REAL_PROVIDER_REQUESTS_THIS_TASK = 0
```

## 四、阶段、时间与控制状态

| 情形 | 确定性阶段 | 真实模拟时间与终态 |
|---|---|---|
| 人物已在卖家地点 | start → BUY → COMPLETED | 原 BUY 零分钟；不额外添加旅行或交易时长 |
| 人物不在卖家地点 | start → ACTIVE MOVE → ACTIVE BUY0 → 下一条明确 advance → COMPLETED/FAILED | 原 travel_minutes，默认 15；BUY0 不额外耗时 |
| MOVE 或 BUY0 暂停 | PAUSED，保留原阶段和剩余量 | 全局时钟可继续，人物需求按原规则变化；承诺不推进、不购买 |
| 暂停后恢复 | RESUME → ACTIVE | 继续原阶段，BUY0 等下一条明确 advance |
| MOVE 或 BUY0 取消 | CANCELLED | 已发生时间保留；以后推进时钟也不暗中成交 |
| 到达后购买规则拒绝 | FAILED，保存 failure_reason | 已完成旅行、地点、需求变化保留；钱、库存与所有权无交易效果 |

异地获取的到达边界是真实持久状态：例如从 home 到 office，`advance(..., 15)` 保存地点 office、累计旅行 15 分钟和 `phase="BUY", remaining_min=0`，但尚未购买。下一条不同 request_id 的 `advance(..., 15)` 才结算购买，模拟时钟仍为 15。

即使第一条 advance 请求推进到 30，ACQUIRE 抵达时也先返回 15，留下 BUY0。调用方应读取返回的 `minute` 和 commitment，再发下一条明确推进命令。原到达请求的重放只返回原结果，不能把重放当作新购买步骤。M2 的确定性完成函数负责这个编排，微步骤不再次调用 fake client 或模型。

默认需求规则下，未饱和的 15 分钟清醒旅行使饥饿增加 15、精力减少 15。暂停期间全局时间造成的需求变化和活动累计旅行分钟分开记录，不能混为一次旅行费用。

## 五、候选是当前规则条件，不是预约

独立 `project_m2_actions()` 输出 `M2_ACTION_PROJECTION_V1`，在原有有界对象候选上调用同一 `preview_activity()`，不复制简化购买规则。

| 预览字段 | 同地且购买条件满足 | 异地且当前购买条件满足 |
|---|---|---|
| start_allowed | true | true |
| executable_now | true | false |
| requires_travel | false | true |
| purchase_feasible_at_snapshot | true | true |
| reason | ELIGIBLE | REQUIRES_TRAVEL |
| guarantees_future_stock | false | false |

M2 的 `startable_options` 可以包含合法远程 ACQUIRE；它表示可开始获取，不能声称此刻已经成交。钱不足、零库存、已拥有、不可用、活动冲突或对象能力不符时由共享规则拒绝。旧 Q6.2 的候选顺序、摘要、A/B 输入和可执行性语义不随这项实验扩展改变。

## 六、失败分类与已发生事实

| 失败类别 | 当前结果 |
|---|---|
| 未启用实验 | ACQUIRE_DISABLED |
| 无对象 / 无购买能力 | OBJECT_NOT_FOUND / CAPABILITY_MISMATCH |
| 食品等本轮排除对象 | UNSUPPORTED_ACQUIRE_OBJECT |
| 初始钱不足 / 库存为零 | INSUFFICIENT_FUNDS / OUT_OF_STOCK；启动拒绝，无旅行和购买 |
| 已拥有非消耗性对象 | 依原共享购买检查拒绝；条件齐备时为 ALREADY_OWNED，不重复扣款 |
| 旅行途中下架 | ACQUIRE 保留旅行，到 BUY 时得到 OBJECT_UNAVAILABLE |
| 旅行途中库存被另一人物买完 | 到 BUY 时得到 OUT_OF_STOCK；没有免费物品或重复扣款 |
| 同一 request_id 参数改变 | REQUEST_ID_REUSE，不执行新参数 |
| 非法恢复配置或阶段 | 明确报错并保留存档，要求显式恢复，不自动赠送物品 |

`set_available()` 对原媒体和餐食活动的中断行为保留；只有 ACQUIRE 延迟到 BUY 重新核对可用性。下架后重新上架也不保证购买成功，仍需在成交时核对全部共享前置条件。

## 七、购买原子性与旅行提交边界

SQLite 的 `_command()` 使用 `BEGIN IMMEDIATE`，把命令结果、状态和事件一起提交。M2 在 BUY 与 COMPLETED 外增加内层 savepoint，复用 `_buy()` 完成金额、拥有量、库存和 `PURCHASED` 事件，再保存完成状态与完成事件。

可预期的 `Rejected` 只回滚本次购买效果，记录 FAILED；已经提交的旅行事实保留。事件写入、磁盘或进程退出等基础设施故障使本次整个命令回滚并报错；命令未记录为成功。异地 BUY 之前的 arrival 已单独提交，因此可重开到 BUY0，再按显式请求恢复。这不意味着数据库能保留尚未提交命令内部的时间变化。

验收须检查“扣钱但未获得所有权”“库存扣除却无合法购买事件”和“购买完成后再次成交”均不出现，并检查 `_buy()` 已写入后再发生合成域拒绝时，内层 savepoint 仍能恢复交易事实。

## 八、活动幂等、底层命令与重启

底层 BUY、start、control、advance 都使用原 commands 表的 request_id 和参数指纹。相同参数重放返回原保存结果、不再次推进或交易；相同 request_id 改参数按原冲突规则拒绝。用两个不同别名作为同一 request_id 的不同原始参数，仍可能产生冲突，这与规范对象身份一致不是同一个问题。

活动启动结果和当前 commitment 必须分开查询：异地 start 最初返回 ACTIVE，完成后重放 start 仍是原始响应；`get_commitment()` 才给出当前 COMPLETED/FAILED/CANCELLED。不能因为原始响应仍为 ACTIVE 就再次购买。

新fake runner的decision_attempts另记schema和actor_id；跨人物复用请求拒绝归属，底层竞争命令不能把已经拒绝的提案变成接受。重放只读本次持久结果；REQUEST_STARTED但没有结果表示未知中断，不根据同ID的竞争命令猜测成交，也不再次调用client。活动恢复不等于重发高层决策。

恢复覆盖尚未出发、部分旅行、到达待购买、成交已提交、完成后重复查询和失败后重启。暂停和取消也需要重启验证。配置、规范目标、阶段、剩余量、目的地和活动记录列不一致时拒绝恢复，保留证据。进程在 PURCHASED 事件前退出应恢复原 BUY0，而不是半笔成交。

## 九、SQLite 并发范围

本轮用独立 SQLite 连接竞争最后一件库存，以及两个连接重放同一请求。写事务锁和数据库约束保证受测参考实现只有一次合法成交；购买阶段会重新读取当前库存。不能把进程内布尔变量当作并发控制。

这些结果只说明本 SQLite 实现和受测故障路径，不证明分布式 exactly-once、多数据库一致性、跨服务支付或生产级高吞吐市场已经完成。动态价格、对象版本迁移和长期库存策略留待后续决定。

## 十、离线完整闭环与产物

独立 M2 runner 使用固定 fake 提案，CLI 默认为 `--mode offline`，不得通过默认模式、环境文件或替换真实 client 产生外部请求。一次 ACQUIRE 选择之后仅推进确定性阶段；重开 world 确认所有权，再接收一次新的 PLAY 提案，并按原 PLAY 规则推进媒体分钟。

正式独立runner在clean实现提交上执行 `m2-offline-acceptance-01`：17/17场景PASS、fake高层调用3，LLM_CALLS=0、PROVIDER_REQUESTS=0。provenance为完整实现SHA、`git_dirty=false`、Python3.12.14。此前提交前的development-01/02/03仍保留，不能用其dirty开发HEAD代替冻结证据。主目录 `game_a` 初始拥有量0、余额300000 cents、home卖家、库存100；同地获取后余额297000、库存99、拥有量1，获取耗时0。重开确认所有权后，一次新的独立PLAY完成累计45分钟。异地合成物品价格4200 cents，购买后余额295800；旅行15分钟，饥饿800→815、精力700→685。

可用 `python scripts/run_m2_acquire_validation.py --mode offline --session <新的session>` 复核独立场景；每次使用新 session，不覆盖已有输出。实现位置为 `src/social_sim/continuity/engine.py`、`m2_acquire.py`、`m2_validation.py` 与 `scripts/run_m2_acquire_validation.py`。CLI 只接受 offline，并在运行期间禁止 socket 连接。

新产物写入 `run/evaluation/m2_acquire/<session>/`，保留配置版本、初态、规范对象 ID、阶段、规则接受/拒绝、购买事件、资金和库存变化、拥有量、模拟时间、终态、恢复摘要与中文报告。所有失败一起记录，不复制模型原文、凭据或敏感环境信息。

| 本轮交付 / 验收 | 状态 |
|---|---|
| M2 focused tests | 87 passed；PASS，含 79 个专属用例与 8 个 CLI 用例 |
| 核心验收组合 | 本机和新 CI 均216 passed；其中M2精确87，PASS |
| 旧 Q6 与 Q6.1/Q6.2、购买消费、规则与 reducer 联合回归 | 159 passed；PASS，仅此受测范围 |
| 购买、消费、媒体、幂等与恢复 | PASS：本轮专属与原联合回归的受测范围，不扩大为分布式保证 |
| Ruff | 新代码、测试和文档审计工具 PASS |
| 文档与仓库专项 / 两项审计 | 25 passed；audit_repository、audit_documentation 均 PASS |
| 历史产物 / 官方子模块保护 | 316 文件字节不变、297 文件清单摘要匹配历史登记；官方固定子模块 clean，PASS |
| 完整 CI 与固定 AS2 适配器 | 778 passed、8项缺历史语料SKIP；固定670c94fff适配器PASS；Python3.12.15；新工程CI37787843811、文档CI37787843755成功 |
| Secret scan / 受保护文件差异 | PASS：凭据模式未发现匹配；旧提示/投影/规则参数/存储与 Q3/Q4/Q5 文件未改 |
| 实现提交 / 结果记录 / 新 PR | 46fb620c0e53a5ab6e03836c95f9a64e1354430b；本报告后续提交只补记录；PR #8指向main，不自动合并 |
| M2_EXPERIMENTAL_IMPLEMENTATION | READY：实验机制与本机受测路径可用，生产默认仍禁用 |
| M2_ACQUIRE_ENGINEERING_READY | YES：实际受测门槛通过，不代表生产默认或真人行为批准 |
| HUMAN_BEHAVIOR_APPROPRIATENESS | NOT_TESTED |
| LLM_CALLS / PROVIDER_REQUESTS | 0 / 0 |

历史真人语料缺失的八项 SKIP 保留真实原因；轻量本机缺失 AS2/litellm 时要明确写阻塞，由独立 CI 验证，不能借用 PR #6/#7 的历史计数冒充本轮通过。

## 十一、历史研究和人工评价边界

PR #6 的固定状态面板保留 12 状态、24 配对、48 单元及原 v1/v2 协议，原真实结论为 `NO_CLEAR_DIFFERENCE`。PR #7 的 M1.5 是 `EXPLORATORY_POST_HOC`，22 个完整配对中的状态净变化不等于整体人类效用，更不能改写成 B 获胜。两个 PR 保持 OPEN，本轮从最新 main 独立开发，不导入其研究模块或修改旧产物。

历史位置：[PR #6](https://github.com/richardssheik107-hub/Agent-Society/pull/6)、[PR #6 冻结中文报告](https://github.com/richardssheik107-hub/Agent-Society/blob/b7c6d503dc09c0c2d7dc32467b277a23a1a26404/docs/studies/q62_action_projection.md)、[PR #7](https://github.com/richardssheik107-hub/Agent-Society/pull/7)与[固定中文审计](https://github.com/richardssheik107-hub/Agent-Society/blob/016fffe28b4a296a24a1ee8c8c4adc63b7394383/docs/studies/q62_outcome_audit.md)。[原中文人工盲审包](https://github.com/richardssheik107-hub/Agent-Society/blob/016fffe28b4a296a24a1ee8c8c4adc63b7394383/docs/studies/q62_outcome_human_review.md)保持未代填状态，D-09 继续 PENDING。

工程测试证明动作合法、活动状态和账本一致，不证明人物应该购买这个对象。未来人工评价应分别看动作合法、活动完成、需求变化、准备性活动和行为适当性。模型不能代填盲审，也不能使用已知 A/B 条件制造人工评价结果。

## 十二、仍待批准的产品语义与下一步

D-02 尚未批准生产默认能力，包括重复购买策略、获取失败后的继续策略、自动前往卖家的适用范围、动态库存与价格、获取活动的优先级以及主动积累物品。测试通过只表示当前实验合同可核对。

下一步适合在独立新版本中申请一个小预算真实短链：人物初始未拥有游戏，给出一次 ACQUIRE 机会，保存并重开世界，再观察下一次独立选择是否使用游戏。场景、模拟时间、请求上限、session 和停止规则须另行明确；本轮授权为零，代码和报告不能充当下一轮真实预算。无需继续增加 Q6.2 样本或重复 M1.5 审计。
