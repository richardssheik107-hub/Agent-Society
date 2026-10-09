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
