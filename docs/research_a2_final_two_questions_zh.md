# 研究 A2 最终版：两个研究问题的最新答案

> 本文是当前 AgentSociety 2 集成项目在 Research A2 阶段结束后的中文结论版。  
> 它总结的是**当前工程证据能够支持到什么程度**，不是“人类行为已被完全模拟”的宣称。

当前主线基线已推进到：

- Core7 日常行为集合
- 真人时间日记校准后的活动时长
- NHAPS/AHTUS 在职工作日行为语料
- 短上下文行为先验
- 确定性规则执行
- 单步决策层的 TRAIN/EVAL 隔离评估
- 连续运行失败原因审计

---

# 研究问题 1

## Agent 为什么会“发呆”？最少需要多少上下文和行为先验，才能持续产生较合理的日常活动？

## 当前答案

“发呆”不是一个单一问题。

目前已经拆出了至少六类不同来源。

### 1. 行为集合不完整

最初的 Core5 只有：

- SLEEP
- WORK
- EAT
- LEISURE
- MOVE

NHAPS/AHTUS 真人日记显示，Core5 只能覆盖约 **82.17%** 的全体成人日常分钟数。

加入：

- PERSONAL_CARE
- CHORES

以后形成 Core7，全体成人分钟覆盖率提高到约 **93.00%**，在职工作日人群达到约 **94.61%**。

这说明以前一部分“无事可做”并不一定是模型能力差，而是 simulator 没有提供洗漱、个人护理、家务等普通日常行为。

---

### 2. 活动持续时间太短

旧版 WORK 一次只持续 **90 分钟**。

NHAPS/AHTUS 在职工作日数据中，合并后的 WORK episode 中位数约为 **270 分钟**。

如果活动过短，系统会频繁结束活动并重新调用模型，例如：

```text
09:00 WORK
10:30 activity complete
→ ask model again
→ WORK
12:00 activity complete
→ ask model again
```

这会人为制造 decision burst。

A2.0 的真实配对结果已经出现方向性信号：使用校准时长后，决策/请求次数减少。

---

### 3. 动作被拒绝后反复决策

早期 Neutral-Day 实验中已经出现：

- 重复 EAT，但没有 meal
- 被规则拒绝后很快再次决策
- same-state redecision
- repeated invalid action

所以有些“发呆”其实不是完全不行动，而是：

> 一直在做不能成功的事情，世界状态没有有效进展。

事件反馈对此有帮助。Phase 8A 中，保留最近一次失败事件后，立即重复同一失败动作的现象出现下降方向。

---

### 4. 缺少局部真人行为提示

只把 PERSONAL_CARE 和 CHORES 加到菜单里，并不能保证模型会主动想到它们。

A2.0 中，模型已经可以选择这两个动作，但真实运行里几乎没有主动利用。

因此后来加入真人行为先验：

> “这个时间、做完这种活动之后，真人通常接下来做什么？”

后台可以保存数千份真人日记，但每次模型只看非常短的一条行为提示。

---

### 5. 即时动作链会快速消耗 decision budget

A2-Closure 对 7 个历史 MAX_DECISIONS episode 做了完整离线审计。

主因分布：

- **5/7：B_IMMEDIATE_ACTION_CHURN**
- 1/7：need/obligation loop
- 1/7：mixed
- 0/7：数据不足

最典型的链条是：

```text
MOVE restaurant
→ BUY meal
→ EAT meal
→ next decision
```

MOVE、BUY、EAT 当前都是即时动作。

因此一个很正常的吃饭过程就可能连续消耗 3 次高层 decision。

如果后面再出现一个失败动作，很容易达到实验设置的 MAX_DECISIONS。

所以：

> MAX_DECISIONS 不等价于“Agent 不会生活”。

其中很大一部分是当前“高层行为”和“低层操作”没有分层造成的连续运行问题。

---

### 6. Provider timeout / output failure 不是行为性发呆

远程 reference provider 多次出现：

- TIMEOUT
- 少量 invalid output
- 长链 episode 被技术性截断

这些必须和行为性 idle 分开。

未观察到的时间不能被当作 Agent 在发呆。

A2-Final 改成 80 个互相独立的单步请求之后，77/80 成功，说明“独立请求”比长链 episode 更适合当前 reference provider 的工程比较。

---

# 当前最小行为语料候选

A2-Final 将 3,215 个在职工作日日记按 day_id 严格切成：

- TRAIN：2,572
- EVAL：643

两者无重叠，EVAL 不参与 retrieval。

在实际测试的三个 TRAIN 档位中：

- B100 exact-hit：12.24%
- B1000 exact-hit：71.09%
- BTRAIN_ALL exact-hit：86.20%

B100 明显太稀疏。

B1000 已经有不错的检索覆盖，但和 BTRAIN_ALL 相比，在匹配成功样本中：

- held-out 行为占比低约 0.098
- 规则可执行率低约 0.133

均超过预注册的 0.05 工程容忍差。

因此当前结论是：

> **CURRENT_MINIMUM_BEHAVIOR_CORPUS = 2,572 条 TRAIN diary**

这里的“最小”只表示：

> 在实际测试过的 100 / 1000 / 2572 三个档位中，2572 是第一个满足当前工程门槛的档位。

它不是一个理论最优阈值，也不表示 1500、1800、2200 一定不够。

---

# 当前最小行为先验候选

A2-Final 比较了：

- R1：每次最多给 1 个行为名称
- R3：每次最多给 3 个行为名称

结果 R3 没有带来额外收益，反而增加上下文成本。

当前推荐：

> **CURRENT_MINIMUM_BEHAVIOR_PRIOR = R1**

即：

> 每次模型最多只看一个真人行为先验名称。

模型不会看到完整 diary，也不会看到概率表，更不会被命令“必须模仿真人”。

---

# 当前最小上下文结构候选

当前推荐结构：

```text
紧凑当前状态
+ needs / obligation
+ 最近少量相关事件
+ R1 behavior prior
```

可以理解为模型只需要知道：

- 我现在在哪里
- 现在几点
- hunger / energy 等需求
- 有没有工作义务
- 最近发生了什么关键事件
- 真人在类似时段最常见的一个行为是什么

不需要：

- 一整天历史
- 完整 RuleEngine
- 数千条真人日记
- 长篇思维链
- 大量行为候选解释

需要强调：

A2-Final 实际运行使用的是 `C3_recent3` 事件策略。

“last relevant event”目前只是更小的 context 候选，还没有和 R1 做完整联合消融。

因此不能说已经证明“只保留一个事件一定最优”。

---

# 问题 1 当前状态

当前最准确的状态是：

> **Decision layer：CLOSED_ENGINEERING**

也就是单次决策层已经得到清晰的工程基线：

- Core7
- 校准后的 duration
- 2,572 TRAIN diaries
- R1
- compact context

但是：

> **Continuity layer：PARTIALLY_UNRESOLVED**

连续生活几个小时甚至一整天时，仍然存在：

- 即时动作链消耗过多 decision
- prior 偶尔提示当前不可执行行为
- provider 长链稳定性问题
- 高层 Activity 和低层 Action 还没有真正分层

A2-Closure 没有为了“强行完成”而加入没有证据支持的 runtime guard。

当前：

`runtime_guard = NONE`

这是有意保留的研究边界。

---

# 研究问题 2

## 哪些规则应该手写？哪些行为分布应该来自真实数据？值得引入开源真人行为数据吗？

## 当前答案：已经基本收口

整体架构应分成三层。

---

## 第一层：确定性世界规则

以下内容继续由 Python / RuleEngine 决定：

- money
- inventory
- stock
- location validity
- seller presence
- state consistency
- activity conflict
- world consequences

例如：

- 没钱不能买
- 库存为 0 不能买
- 不在正确地点不能执行对应行为
- 一个 Agent 不能同时处于两个冲突活动
- 动作完成后 WorldState 如何变化

这些不能由统计频率决定，也不能让 LLM 自由修改。

---

## 第二层：真人行为数据负责校准

开放真人时间日记适合校准：

- activity ontology
- activity duration
- time-of-day distribution
- activity transition prior
- behavior corpus
- population-level activity support

NHAPS/AHTUS 已经真实改变了 simulator 设计。

核心证据：

- Core5：82.17% 全体成人分钟覆盖
- Core7：93.00% 全体成人分钟覆盖
- Core7：94.61% 在职工作日分钟覆盖
- WORK：旧 90 分钟 vs 真人约 270 分钟 episode 中位数

这说明真实行为数据不是“装饰性数据”，而是能够发现 simulator 本身的结构性偏差。

---

## 第三层：模型负责具体行为选择

模型只负责回答：

> “在我现在这个状态下，我下一步想做什么？”

真人数据不是固定日程。

不能变成：

```text
12:00 → 强制 EAT
18:00 → 强制 CHORES
22:00 → 强制 SLEEP
```

它只提供 population-level prior。

最终仍然由模型做个体选择。

---

# 当前核心架构原则

当前研究最重要的设计原则仍然是：

> **LLM proposes actions; deterministic rules govern consequences.**

中文：

> **模型负责提出行为，确定性规则负责裁决行为及其后果。**

结合连续运行审计后，可以进一步理解成：

```text
真人数据
→ 告诉系统“什么行为通常合理”

小模型
→ 决定“我现在想做什么”

确定性规则
→ 判断“能不能做，以及发生什么”
```

---

# 开源真人行为数据是否值得引入？

当前答案：

> **OPEN_DATA_CALIBRATION_WORTHWHILE = YES**

原因不是理论上“听起来有帮助”，而是已经有实际工程效果：

1. 发现 Core5 行为集合不完整；
2. 推导出 Core7；
3. 暴露 WORK=90 分钟的时长偏差；
4. 建立 time-of-day / transition prior；
5. 构建可审计 deterministic retrieval；
6. 在独立决策评估中，真人行为 prior 提高了 held-out 行为支持度和规则可执行率。

因此，真实行为数据应该作为 simulator 的**校准层和行为支持层**，而不是强制规则层。

---

# 当前推荐的实验 Reference Baseline

当前冻结的实验候选可以概括为：

```text
Ontology:
Core7

Durations:
SLEEP = 360 min
WORK = 270 min
LEISURE = 75 min
PERSONAL_CARE = 30 min
CHORES = 30 min

EAT:
immediate effect

MOVE:
immediate location transition

Behavior corpus:
2572 employed-weekday TRAIN diaries

Behavior prior:
R1

Retrieval:
30-minute time bucket
+ previous canonical activity
+ deterministic fallback

Context:
compact state
+ needs / obligation
+ 1–3 recent short events
+ R1 prior

Runtime guard:
NONE
```

这是实验 reference profile，不是 production default。

---

# 仍未解决的核心问题

当前真正剩下的问题已经非常集中：

> **如何让 Agent 在连续运行几个小时甚至整天时，把高层行为和低层执行动作合理分开？**

例如：

```text
高层意图：MEAL
↓
低层执行：
MOVE restaurant
BUY meal
EAT meal
```

当前三个低层动作都被当成独立 decision，因此会快速消耗 decision budget。

A2-Closure 已确认这是连续运行层的主要问题之一，但当前还没有足够证据支持某一个唯一 runtime 修复方案。

后续更值得研究的是：

- Activity Commitment / Macro Activity Layer
- 高层 Activity 与低层 executable action 分层
- 借鉴 AgentSociety 2 Daily Guidance 的 segment/commitment 思想
- 但不直接把整天计划写死

这属于下一阶段，不是 A2 当前结论的一部分。

---

# 最终结论

## 问题 1

当前答案：

> Agent 的“发呆”并不是单纯模型能力不足，而是行为集合、活动时长、失败反馈、局部行为先验、即时动作链和 provider 截断共同造成。

当前决策层工程候选：

> **2,572 条在职工作日 TRAIN diary + R1 + 短上下文。**

状态：

> **Decision layer：CLOSED_ENGINEERING**  
> **Continuity layer：PARTIALLY_UNRESOLVED**

---

## 问题 2

当前答案：

> **硬世界规则由确定性代码负责；行为本体、活动时长、时间分布和转移先验由真人数据校准；模型只负责当前具体行为选择。**

状态：

> **CLOSED_ENGINEERING**

并且：

> **OPEN_DATA_CALIBRATION_WORTHWHILE = YES**

---

# 当前总状态

```text
研究问题 1：
单步决策层已形成工程基线；
连续运行层仍部分未解决。

研究问题 2：
已形成清晰工程答案。

当前下一步不应该继续扩规则或语料，
而应该固定这套 reference baseline，
再研究连续 Activity Commitment / Macro Activity，
或在相同世界、规则、语料和 context 下切换本地 8B。
```
