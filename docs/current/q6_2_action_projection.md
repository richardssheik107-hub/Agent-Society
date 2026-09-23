# Q6.2：当前可执行活动投影与状态利用审计

更新：2026-09-23。范围：原始产物离线核验、投影工程验证与小预算 A/B dry-run；真实 A/B 尚未执行。继续在 `research/q6-real-continuity-pilot` 交付，经 PR #4 审阅，不直接合并主线。

## 1. 为什么做这一轮

[Q6.1 Attempt 3 报告](q6_1_real_continuity_pilot.md)记录了：前往餐厅、吃饭、再次吃饭、尝试玩未拥有的游戏。前三项完成，第四项被 `ITEM_NOT_OWNED` 正确拒绝。正式结论仍是 `INSUFFICIENT_EVIDENCE`，本轮不改写。

这需要拆成两个问题：**规则是否允许做**，以及**人在这个状态下为什么想做**。本轮先把前者变成可供模型读取的结构化候选，后者不靠强行禁用动作“解决”。

尤其注意：连着吃两次饭不自动等于模型忘了上一顿。按冻结 Q6.1 参数回放，第一次餐食后 `hunger_milli=245`，还不是 0。此前把“重复吃饭”直接解释成模型没利用状态，证据不足。

## 2. 现在的代码怎么工作

```text
当前人物、对象、所有权、库存和活动状态
    ↓ 一致只读快照
共享的活动/购买前置检查
    ↓
当前可执行的 activity + target 候选对
    ↓（仅 Q6.2 显式启用）
模型提出高层活动
    ↓
原规则再次检查并执行；状态已变化时仍可拒绝
```

新增 `ContinuityWorld.preview_activity()`，复用实际执行中的 `_prepare_activity()` 和 `_check_purchase()`。没有另抄一套近似的判定规则，也不通过“执行一次再回滚”来生成候选。读取在 SQLite `query_only` 快照中完成，不写余额、事件、命令、请求预算或活动状态。

例如 `PLAY(game_a)` 在 `qty=0` 时从可执行候选对里排除，但原对象目录仍可以保留这个游戏。若外部合法购买后拥有量变成 1，它才成为可执行候选。执行端依然保留所有权检查，模型无视投影时照常拒绝，不免费发游戏或偷偷代购。

MEAL 需要额外区分两个层次：旧控制器可以先接受“去吃饭”，到店后才因缺钱或缺货失败。因此预览分别提供 `start_allowed` 和 `executable_now`，把已知购买条件不足提前标出。原控制器的接纳/失败时间不改：已经到达餐厅的事实仍然保留。

## 3. A/B 接线与冻结边界

A 为 `A_RAW`，字节级复用原 `decision_prompt()`。B 为 `B_FEASIBLE`，保留完全相同的 observation 和目的地，只附加 `executable_options` 与一句解释该列表的说明。

B 不添加“正确答案”、最优行为、偏好排序、未来事件或真人日记标签。阻塞原因保留在审计产物，不附加到 B 提示；这避免同时测试多个干预。字符数会增加，必须和将来的可执行率收益一起评估，不能先声称节省 token。

接线方式：

```python
from social_sim.continuity.action_projection import projected_prompt
from social_sim.continuity.decision import ActivityDecisionRunner

runner = ActivityDecisionRunner(world, client, prompt_builder=projected_prompt)
```

默认不提供 `prompt_builder`，Q6.1 仍走原提示。原真实入口、预算、对象参数、动作集合、provider 配置、上游子模块均不变。小预算 A/B 协议和独立运行入口见 [Q6.2 A/B 预注册协议](q6_2_real_ab_protocol.md)；默认入口只做零请求 dry-run。

候选来自原 observation 的最多 5 个对象，本轮小世界是 4 个；对固定活动、目的地和这些对象做有限检查。可执行活动/目标对按活动名和规范目标 ID 排序，记录数量与 SHA-256 摘要；顺序不是偏好排序。对象检索仍使用旧的按 ID 排序候选，不把它称为语义 Top-K，更不据此声称千万对象检索已解决。

## 4. 离线回放结果与证据来源

Git 不收录用户 WSL 中被忽略的 `q61-runtime-01` 原始运行目录；现在已在该 WSL 中直接读取并核对。无来源参数时仍明确叫 `SCRIPTED_REPORT_SEQUENCE_REPLAY`，只回放报告序列；带 `--source-artifact` 时叫 `ARTIFACT_DRIVEN_DETERMINISTIC_REPLAY`，对原始文件逐步校验，不伪造模型响应、不重跑 provider。

冻结来源：执行代码 `54ed48f93f452718e59bda1368e15737f173084c`；报告提交 `a338f0b3171bf1692032bfd6818f47620fba3fdb`。2026-09-23 使用原始本地 artifact 核对的实际结果为 `SOURCE_ARTIFACT_VERIFIED=True`、`comparison_mismatches=[]`、`PROVIDER_REQUESTS=0`；无来源参数的默认模式仍不能自称已核对。

| 步骤 | 报告中的意图 | 回放饥饿值前→后 | 回放金额前→后（分） | 新投影保留 | 原规则结果 |
|---|---|---:|---:|---|---|
| 1 | TRAVEL / restaurant | 800→815 | 300000→300000 | 是 | 接受并完成 |
| 2 | MEAL / food_meal | 815→245 | 300000→298000 | 是 | 接受并完成 |
| 3 | MEAL / food_meal | 245→0 | 298000→296000 | 是 | 接受并完成 |
| 4 | PLAY / game_a | 0→0 | 296000→296000 | 否 | ITEM_NOT_OWNED |

A/B 提示字符数分别为 1236/1772、1243/1659、1245/1661、1245/1661（早期未排序候选的离线记录；候选排序后以新 artifact 为准）。这里只比较同一状态下的输入差异，**没有 B 模型行为结果，更没有证明 B 减少了真实拒绝率**。

回放时即使发现第四项不在新投影里，仍执行报告中的原提案，以验证原规则正确拒绝；不会挑一个合法动作替换它。共享检查重构前后的四步完整状态哈希和事件哈希由冻结脚本基线测试核验一致。该哈希基线是离线脚本，不是原 provider artifact。

## 5. 本地原始产物核对入口

普通离线审计：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_projection_offline.py
```

在有原始 session 的 WSL 上，进一步核对：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_projection_offline.py \
  --source-artifact run/evaluation/q6_1_provider_runtime/q61-runtime-01
```

工具只读原 `attempt_3/summary.json`、`decisions.jsonl` 与 `final_state.json`，检查来源版本、逐步时间/位置/余额/饥饿/状态版本、库存变化、媒体进度、观察摘要与回放终态。只有这些都匹配才标记 `source_artifact_verified=true`。不一致时仅输出字段名和期望/实际值的摘要，不复制 provider 原文。这表示与传入文件相符，不对外部文件的真实性做额外认证。

输出写到新的 `run/evaluation/q6_2_projection/<时间>/`：中文报告、summary、逐步回放审计和独立数据库。拒绝覆盖目录、向源目录内部输出或默默忽略来源不匹配。额外 provider 字段不复制，未知异常不回显正文。CLI 没有 `--allow-provider`，并阻断网络连接；模型调用固定为 0。

## 6. 测试范围

原投影新增 47 项测试案例；本轮继续增加逐步库存/媒体比较、候选摘要、提案 membership、A/B 隔离、失败停止、重复 session 与零凭据 dry-run 测试。覆盖未拥有/已拥有游戏、位置、能力不符、下架、缺钱/缺货、已持有食物、忙碌/暂停、剧集顺序与显式重看、状态过期、投影后库存变化、只读无副作用、A/B 上下文隔离、旧行为哈希不变，以及本地 artifact 核对与隐私字段过滤。

十类状态中，投影的每个候选都与独立副本的实际完整执行结果比较；副本只用于测试，不在投影实现里运行。接线测试让 fake provider 真正接收 B 输入，验证完成第一集后下次输入确实出现第二集；另测模型无视投影时仍由规则拒绝。

本地开发环境（Python 3.13.5）中，Q6.1/Q6.2/continuity/仓库联合专项 **160 passed**。正式目标 Python 3.12 的 CI 结果在后续验收段记录，不能拿开发环境替代目标环境。

## 7. 尚未解决的边界

**游戏获取路径仍缺失。** 当前高层 JSON 不接受 BUY，而 PLAY 本身不会购买未拥有游戏。因此投影能排除不合法 PLAY，却不能让这个角色靠当前高层接口自己买到游戏。这不是“只要模型更聪明就行”，后续需单独设计获取活动，不能暗中改变本轮动作集。

**行为真实性仍未验证。** 饥饿、疲劳、偏好与近期活动应如何影响选择，需要数据与受控实验。当前投影只解决可执行条件；无偏好排序不意味着顺序对模型完全没有影响。

**可执行候选不是预约保证。** 对象会下架、库存会变，候选只能代表读取时刻；提交时仍要校验。没有多机并发、外部事件预测或大目录性能的结论。

## 8. 下一轮计划

WSL 原始 artifact 已只读核对通过；小预算真实 A/B 协议和 dry-run 已准备，详见 [预注册协议](q6_2_real_ab_protocol.md)。未来需另行明确授权真实运行：两臂各最多四次请求，使用相同初态、模型和请求契约，主要看规则拒绝率、提案 membership 与上下文成本；重复进食仅作行为描述，不作为规则失败。

“加入近期状态变化摘要”是另一项状态显著性干预，应另设实验条件，不能与可执行候选同时修改后归因。媒体进度和已拥有游戏用明确标注的独立场景覆盖，不向旧 Attempt 3 偷加动作。

未获新授权前，不发真实请求、不扩到 12-call、不新增采购宏活动、不合并 main。
