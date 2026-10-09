# M5：长周期自主生活 Runtime 与分层评价

本轮基线：`3603d68d43738a7fe1683211e7c7919b17ef5a14`。日期：2026-10-09。本页记录新 Runtime 合同，实际验收版本、分钟数和覆盖由本轮运行产物及[验收账本](../current/acceptance.md)登记；不会用已有 Q6 脚本成绩替代 M5 实测。

导航：[运行手册](../current/runbook.md) · [唯一计划](../current/plan.md) · [D-02](../review/decisions.md#d-02) · [D-09](../review/decisions.md#d-09) · [历史 M2](m2_object_acquisition.md)

## 一、两个批准与两个不能混同的运行结果

用户本轮明确批准 `APPROVED_SCOPED_OPT_IN` 的已有 ACQUIRE：新世界显式开启，旧世界不迁移，全局默认关闭；只买有库存、足额支付的非消耗性对象，不重复拥有、不预留、不借款、不隐式购买、不自动 PLAY。必要旅行后成交复查，失败不回滚已提交的旅行。底层 BUY、原事务和活动状态机均复用。

D-09 批准 `APPROVED_MULTIDIMENSIONAL_EVALUATION`：L1 检查工程不变量，L2 分列不同单位的需求和任务后果，L3 由人判断。预警不触发行为干预，没有医学含义，不生成真人相似度总分。批准框架不等于人工完成审核。

`SCRIPTED_OR_FAKE_LONG_RUN` 是合成自适应策略调用新 Runtime 的工程验收。`REAL_MODEL_AUTONOMOUS_LONG_RUN` 是真实服务持续独立决策的实验。当前后者预算为 **0**，本轮只实现接口和 mock 合同，不执行付费请求。

## 二、世界与会话职责

独立 `src/social_sim/longrun/` 保存 Runtime 会话、上下文、provider 接线、合成驱动、评价和报告。它复用 `ContinuityWorld`、`StateStore`、`m2_decision_prompt`、`parse_m2_proposal` 和现有 OpenAI-compatible 客户端，不重写活动规则或 SQL 交易。

人物观察 → 一次严格高层提案 → 原规则启动 → 确定性微步骤 → 已提交事实 → 下一次观察。未完成活动优先推进，不为每十五分钟再次问模型。获取结束后 PLAY 必须是新的独立提案。模型只提交活动和目标，不能直接修改钱、库存、媒体或数据库。

会话生命周期与世界活动状态分开。会话可以 CREATED、RUNNING、COMMITMENT_ACTIVE、CHECKPOINTED、PAUSED、COMPLETED、STOPPED_BY_BUDGET、STOPPED_BY_FAILURE 或 RECOVERY_REQUIRED；原世界 ACTIVE、PAUSED、COMPLETED、FAILED、CANCELLED 不被替换。

## 三、有界、可追溯上下文

基于当前持久事实提供日期时段、位置、饥饿精力、钱、可用物品和拥有量、媒体进度、当前承诺、最近至多五项已提交活动以及明确实验给定目标。历史摘要由事件确定性生成，不用额外 LLM，也不编造日记。

`OPEN_AUTONOMOUS` 不规定必须完成的具体任务；`GOAL_CONDITIONED` 显式标注实验目标，不能将目标条件成功解释为自发偏好。合成 fake policy 是工程覆盖驱动器，不代表真实模型或人类策略。

配置分别限制字符和 token。token 检查若采用 UTF-8 字节保守上界，会明确标注这不是服务端实际 token；实际响应 usage 另外记录，缺失保持 null。超预算停止，不静默删掉钱、所有权或关键状态。

## 四、时间、午夜与模拟终点

一天严格为 1440 模拟分钟；七天 10080，三十天 43200。API 等待与真实墙钟不进入世界时间。只有原规则合法活动推进时钟。

微步骤在午夜边界保存实际快照和日报，不重新 seed、不重置余额或进度、不强制完成跨日睡眠/观看。活动越过实验终点时保存尚未完成的承诺；达到时长不代表最后活动完成。预算耗尽而只运行部分日，就报告部分时间，不快进补足。

## 五、中断、请求阶段与只读导出

每个新运行采用唯一 session，产物根为 `run/evaluation/m5_longrun/`。会话与请求阶段收据持久保存，世界命令、事件、交易和承诺仍由原 SQLite 管理。

请求登记后发送是否发生不明时保留 UNKNOWN，停止为 `UNCERTAIN_REQUEST_STATE`，禁止重发。安全响应、严格解析提案、世界已提交和汇总完成分别留痕。世界已提交而最后汇总缺失，按同 ID 的持久命令恢复报告，不能再执行一笔交易。

确定性活动恢复继续已保存的活动，不再次请求相同意图。只读导出使用 SQLite `mode=ro`，不构造可能写 schema 的 World，不读凭据、不问模型、不推进动作。锁确保同一 session 不并发写；停止后保留故障、原收据和真实终止原因。

## 六、安全真实接口与预算

默认 offline，不读取 `.env`，不构造真实 client，不连接外部网络。real 必须同时具备显式模式与 allow-provider、独立用户授权记录、正预算、新 session、干净且验收通过的执行 commit、冻结配置 hash、匹配的受保护 provider 配置以及排他锁。环境里存在 key 本身不是授权。

真实接线复用原客户端单次请求、无重试与严格 final JSON 合同；不切模型、endpoint 或思考设置，不 repair、不 fallback。mock HTTP 验证实际请求生命周期与安全元数据，而不是仅断言 READY 标签。响应只保留别名、可观察后端、HTTP、proposal/规则结果、已知 token 与延迟；不留原始 completion、隐藏推理或 Authorization。费用未知不补零。

请求前检查模拟、决策、provider、墙钟、单次超时、微步骤、连续错误、无进展和上下文预算。非法提案不替换等待；冻结协议允许有限次新的独立行为选择，重复错误/无进展达到门槛停止。确凿 L1 错误立即停，不借预警隐藏故障。

## 七、评价与当前不能证明的部分

逐日、逐活动和逐请求分别记录工程一致性、任务连续性、需求/钱/时间/工作/饮食/娱乐/物品/媒体、风险窗口和成本缺失率。行为预警只反映受测合成状态信号，不是人类正确答案。

`ENGINEERING_CONSISTENCY` 可自动检查。`TASK_CONTINUITY` 依实际发生的获取后使用、观看、工作与恢复覆盖判定；未触发标 NOT_EXERCISED。没有人工标注时 `HUMAN_BEHAVIOR_APPROPRIATENESS=UNRESOLVED`、`HUMAN_LIKENESS_PROVEN=NO`。

旧 Q6.1 正式证据不足、Q6.2 `NO_CLEAR_DIFFERENCE`、M1.5 `EXPLORATORY_POST_HOC` 均保持。新 Runtime 不证明真实模型已经自主生活七天，不证明人格、真人偏好、医学需求、多人社会或真实大目录；这些必须有新的明确实验和预算。

## 八、正式验收中的预算截断记录

初始实现提交 `7c243d727f529e34efb0770baf35461d6e1fa0e7` 在干净工作树运行 `m5-offline-acceptance-01`。七天达到10080分钟、113高层决策；不中断与重启6次的语义状态、事件及请求账本一致。该版本离线墙钟上限120秒，在本机三十天不中断运行中实际达到34530分钟、364决策、2303微步骤、4253事件后以 `WALL_CLOCK_LIMIT` 停止（120.019139671秒），**不是三十天 PASS**。当时 WORK 已执行150分钟、尚余120分钟，保留 ACTIVE，不补动作、不跳时间。

原目录不改写；只读失败导出另存 `run/evaluation/m5_longrun/m5-offline-acceptance-01-day30-stop-export/`。后续仅将新协议有限离线墙钟改为600秒，并补上验收 helper 在拒绝 PASS 前先导出失败报告/资源的回归测试；不修改世界参数、初态、驱动策略、规则或真实预算0。新正式会话使用全新ID，不能恢复旧会话并暗中充值预算。最终完整结果另按其实际执行提交登记。

## 九、600秒协议的正式七天与三十天结果

执行提交 `d379dbee780ab7436cc2f05ae6912cf962da2f3d`，干净工作树，Python **3.12.14**。实际命令：`.venv/bin/python scripts/check_m5_longrun.py --session-id m5-offline-acceptance-02`。这是新的 Runtime，不是旧 Q6 日程循环。整个验证器禁止 socket 连接和 DNS，四个子会话均采用相同的合成自适应驱动；OPEN_AUTONOMOUS 的声明目标为空，但驱动器具有明确的工程覆盖优先级，不能解释成自发偏好。

完整世界、请求、阶段收据、微步骤、日报及资源文件留在本机 `run/evaluation/m5_longrun/m5-offline-acceptance-02/`。可在 GitHub 直接查看[安全实测 JSON](../reference/m5_longrun_acceptance_results.json)，完整可再现产物由 PR #9 的 CI artifact `continuity-core-evidence` 交付；忽略的本机 SQLite 不宣称已入 Git。

|实际指标|七天|三十天|
|---|---:|---:|
|模拟分钟 / 天数|10080 / 7|43200 / 30|
|高层决策 / 完成活动|113 / 112|457 / 456|
|微步骤 / 事件|673 / 1230|2881 / 5323|
|规则拒绝 / 真实请求|0 / 0|0 / 0|
|多次恢复对照重启数|6|29|
|不中断运行墙钟（含导出）|29.686101秒|156.922508秒|
|多次重启墙钟（含导出）|30.046216秒|170.943618秒|
|不中断 / 重启 DB字节|6750208 / 6782976|32845824 / 32923648|
|不中断最大字符 / token保守界|4087 / 4153|4118 / 4184|
|重启最大字符 / token保守界|4107 / 4173|4138 / 4204|
|资金起→止（cents）|300000→290000|300000→289500|
|工作分钟 / 收入cents|2700 / 27000|13650 / 136500|
|购买支出cents / 进食次数|37000 / 17|147000 / 72|
|购买游戏数 / 后续PLAY分钟|1 / 405|1 / 1485|
|完成剧集 / 观看分钟|18 / 540|72 / 2160|
|L1 / 语义状态与账本恢复等价|PASS / true|PASS / true|

两组都实际完成 WORK、MEAL、SLEEP、TRAVEL、LEISURE、ACQUIRE、PLAY、WATCH。游戏足额购买一次、库存100→99、持久拥有量1，PLAY是之后独立决策；食物按真实购买和消费计数，未增送钱/库存。最终未完成活动没有伪装完成：七天 LEISURE 已执行60分钟、剩15分钟；三十天 WORK已执行150分钟、剩120分钟，均为 ACTIVE。真实跨日睡眠例如分钟2685→3045，午夜只生成 checkpoint/日报。`cross_day_activities` 按开始/终止事件日期列出，也包含恰在午夜完成的活动；分钟分布仍严格按半开区间分配，不把午夜端点虚构成下一日执行时间。

七天协议规范hash `11f3c284c36629dfa6f33d015aa3b52268fb91ecdf1f55ea80181ed38613e77a`；三十天只改变天数，hash `594e62fbc648c7828c6ec3e92ff2eac0713ff3c4bb50d4a686f2ba58a6f0e15d`。上下文限12000字符、12000 token保守界，近期活动最多5项；实测最大4138/4204。恢复会话ID较长使字符数略增，不表示关键事实被裁剪。

### 七天逐日实际活动、状态与工程进度

每行都是1440分钟。工作/吃饭/睡眠/移动/游戏/观看/闲暇均为已执行阶段分钟，不是模型调用次数。饥饿、精力是合成milli值；资金为cents。日报含起止值、事件、收入/支出、提案/状态和 token缺失率，以下列日末状态与累计工程进度；不是人工判定的生活达标。

|日|工作/吃饭/睡眠/移动/游戏/观看/闲暇分钟|决策/完成|进食|日末饥饿/精力|日末资金|累计PLAY分钟/剧集|
|---|---|---:|---:|---|---:|---|
|1|270 / 90 / 360 / 105 / 120 / 120 / 375|21 / 20|3|440 / 340|293700|120 / 4；已合法购游戏1|
|2|270 / 60 / 555 / 60 / 15 / 30 / 450|15 / 15|2|655 / 565|292400|135 / 5；持有1|
|3|270 / 90 / 525 / 75 / 45 / 60 / 375|16 / 16|3|295 / 700|289100|180 / 7；持有1|
|4|540 / 60 / 360 / 60 / 90 / 120 / 210|16 / 16|2|535 / 340|290500|270 / 11；持有1|
|5|540 / 60 / 600 / 75 / 0 / 0 / 165|12 / 12|2|775 / 700|291900|270 / 11；持有1|
|6|390 / 90 / 480 / 90 / 45 / 120 / 225|17 / 17|3|415 / 700|289800|315 / 15；持有1|
|7|420 / 60 / 360 / 60 / 90 / 90 / 360|16 / 16|2|655 / 340|290000|405 / 18；持有1|

七天饥饿800→655、精力700→340；三十天饥饿800→685、精力700→700。钱的变化分别为27000−37000=−10000、136500−147000=−10500cents，均与账本一致。L2描述这些不同维度，不宣称终值越高就越好。两个正式轨迹的配置预警为0，不能据此断言人物行为正常；L3依旧未审核，理由/异议数组为空，真人相似性未证明。

### 资源与内存的准确边界

三十天不中断运行采样RSS为71916..285284KiB；重启轨迹为136112..295244KiB。整个四轨迹同一Linux进程的 `getrusage` 生命周期峰值为 **319440KiB**，不是独立三十天进程峰值。日报完整审计和最终导出读取历史，因此观测内存随账本/导出规模增长；不能称为常数内存、无限期运行稳定或生产级资源证明。已验证的是冻结最多30天、1000决策、有限墙钟下未OOM且完成，未来更久/更多人物需独立资源设计。API实际token未返回，因为没有真实调用；input/output/reasoning均null、缺失率1，不推算费用或填0。

## 十、恢复、故障和历史保护验收

相同seed/状态驱动的不中断与多次重启，对比完整世界事实、排序事件、请求提案/结果及命令数，只规范化会话ID、忽略真实墙钟/重启次数；不屏蔽钱、库存、时间或活动差异。七天两轨迹hash均 `1a3c3b6361367e80ca1736cd616d14ef21f4a46dd395fa821d9be00469e0ec46`，三十天均 `1ce52c2b8a7a01f3fae7d8256ac843cb0f619fb53dfdefb1cb6d9812bbccfb26`。

149项M5专项包含实际子进程 `os._exit` 后恢复、请求登记后UNKNOWN、活动启动/world已提交但回执未写、旅行抵达尚未BUY、购买已提交未汇总、跨日SLEEP、WATCHoffset恢复、重复request_id、库存竞争、无进展、决策/provider/墙钟/上下文预算及默认真实授权0。严格审计回归还验证篡改购买价格和余额、篡改活动剩余时间、修改静态规则/目录都会FAIL；全量/restart检查不弱于增量，最终L1非PASS时CLI返回1并保留失败报告。未知请求不重发，不修JSON，不fallback WAIT。

真实接口40项provider/CLI测试使用实际httpx POST+MockTransport：单次调用、最小请求体、严格JSON、ACQUIRE后独立PLAY、预算拒绝、超时/非法输出、未知token/后端、客户端finally有界关闭和真实恢复门禁。mock没有外部provider流量，也没有宣称已经关闭深度思考。

实际 `--export-only` 七天、三十天分别输出到新的 `m5-offline-acceptance-02-day7-readonly` / `m5-offline-acceptance-02-day30-readonly`，完整源目录文件hash前后分别相同为 `4b4af2c6020fc8132bc7f287427b7523bbd9a3ad43838df0cb065c6d48a4f464`、`41c7f77fddaca6d85d28f50adc9bd5a6ea6aac0d06a4581d24b5fcd8da9e950f`。没有新世界动作或请求。

原Q6.2真实/恢复/分析、M1.5审计和M2验收共5目录353文件，树hash前后同为 `ee7a5a46734396a2ae6a99d63078b1651002cb72c8ec875da9048dea2533f306`；13份冻结旧代码/配置证据字节回归通过。旧continuity/provider/decision源文件无diff，官方子模块固定clean detached `670c94fff7c64c4f79b632125f2ccf968155e746`，Attempt1历史提交仍为祖先。未读实际.env或APIKey，未覆盖旧报告。未来真实七天及安全恢复的参数和授权合同见[运行手册](../current/runbook.md#m5-多日生活停止与恢复)。

## 十一、CI与最终门槛

初实现C1[完整CI 37875308024](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37875308024) SUCCESS：核心758、全库1324 passed/8 skipped、AS2 PASS、M5七天/三十天及6/29次恢复一致、真实请求0；[文档CI 37875307967](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37875307967)29 passed。临时merge为 `88a9ba9ed720bb5fcc2f76dac6dbb30226a68be2`，不是本机执行commit；CI Python3.12.15，不混成本机3.12.14。

C2[完整CI 37875680783](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37875680783)全库1325 passed/8 skipped、AS2 PASS、核心759 passed及Ruff/审计PASS，但整核心job在新M5步骤超过原10分钟上限而 **CANCELLED**；不能称本次全部CI通过或三十天CI完成。[文档CI 37875680749](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37875680749)29 passed。最后结果提交将整核心任务上限调为有限20分钟，仅改变CI容许时间，不改Runtime协议/行为；其最新CI必须重新全部通过，状态和链接以[PR #9](https://github.com/richardssheik107-hub/Agent-Society/pull/9)最新head检查为准。

八项skip为未入库的冻结历史真人语料（a2_final三项、behavior_prior_context两项、behavior_prior_index三项），不补造数据，不计为通过。本机全库收集/AS2仍因缺litellm受阻；远程完整AS2通过不等于本机环境被修改。独立安全/研究及中文读者检查无未解决P1/P2；读者反馈促使本页区分历史待审核和新批准，并明确实验协议ACQUIRE opt-in。

下列工程标记来自本机C2完整实测和mock；不代替最终CI合并门槛：

```text
LONG_HORIZON_RUNTIME_IMPLEMENTED = YES
D02_SCOPED_ACQUIRE_APPROVED = YES
ACQUIRE_DEFAULT_ENABLED = NO
D09_MULTIDIMENSIONAL_EVALUATION_APPROVED = YES
PERSISTENT_WORLD_CONTINUITY = PASS
MODEL_DECISION_LOOP_READY = PASS
REAL_PROVIDER_INTERFACE_READY = PASS
REAL_PROVIDER_MOCK_CONTRACT = PASS
SEVEN_DAY_OFFLINE_AUTONOMY_DRIVER = PASS
THIRTY_DAY_OFFLINE_STRESS = PASS
CROSS_DAY_COMMITMENT = PASS
INTERRUPT_AND_RESTORE = PASS
REQUEST_BUDGET_ENFORCED = PASS
CONTEXT_BOUNDED = PASS
MONEY_INVENTORY_CONSISTENCY = PASS
ACQUIRE_TO_PLAY = PASS
MEDIA_PROGRESS_PERSISTENCE = PASS
BEHAVIOR_METRICS_AVAILABLE = YES
HUMAN_LIKENESS_PROVEN = NO
NEW_REAL_PROVIDER_REQUESTS = 0
REAL_MODEL_SEVEN_DAY_VALIDATED = NO
```
