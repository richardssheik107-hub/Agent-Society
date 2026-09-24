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
