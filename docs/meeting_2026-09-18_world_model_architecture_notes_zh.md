# 2026-09-18 会议记录：世界建模、Object / Resource / RuleEngine 架构议题（部分）

> 状态：PARTIAL MEETING NOTES  
> 本文只记录当前已经整理到的会议片段，不代表整场会议的完整内容，也不代表所有讨论项已经形成最终结论。后续收到剩余会议内容后继续补充。
>
> 与 Research A2 的关系：
> - A2 已经主要回答“Agent 为什么会发呆”以及“真人行为数据和确定性规则如何分工”；
> - 本次会议把问题进一步推进到世界建模规模、对象库、资源状态和规则维护；
> - Q3 / Q4 / Q5 属于下一阶段研究问题，不覆盖 A2 已形成的工程结论。

## 一、会议讨论的核心变化

这部分会议已经不再只讨论 Agent 为什么发呆，而是在追问一个更底层的问题：

> 一个长期运行的人类行为 simulator，需要维护多少世界知识、多少对象、多少人物状态，以及这些东西怎样在千万级规模下保持可维护？

会议中反复出现的四个核心集合是：

- Action Set
- Resource Set
- Object Set
- Rule Set

真正的问题不是这些集合能不能继续增加，而是：增加到什么程度已经足够支撑“像一个正常人”的日常行为，再继续增加是否只会增加成本和维护负担。

## 二、真人行为日记的重新定位：更像 Action Top-K，而不是完整 Action Set

现实里人可以做的活动远不止当前 Core7。如果不断细分，Action 候选可能达到数百、上千。

因此不应该每次把完整 Action Set 都暴露给模型。

更合理的理解是：

巨大 Action Pool
→ 时间 / 前序行为 / 人群统计
→ 真人日记行为先验
→ Action Top-K
→ Agent 选择

也就是说：

> Diary 的作用更接近行为候选检索器 / Top-K prior，而不是世界规则本身。

这与 A2 中的 R1 行为先验方向一致，但会议把它提升成了更一般的 Action retrieval 机制。

## 三、Resource Set：不是越多越好，而是要找“足够像人”的最小状态集合

基础 Resource 可能只有 time、location、money、inventory、hunger、energy、work obligation、current activity。

继续细分则可以加入 cash、saving account、credit card、debt、多币种、crypto、real estate、vehicle、sleep debt、stress、social need 等。

问题不在于“能不能加”，而在于：

Resource 越多
→ 模型能考虑的信息更多
→ 上下文更长
→ 推理成本更高
→ 状态维护更复杂

但行为质量未必持续改善。

因此新的研究问题是：

> Resource 数量在什么位置开始出现明显的边际收益递减？

后续可设计 R8 / R16 / R32 / R64 等不同 Resource 可见规模，测行为可执行率、行为合理度、矛盾行为率、重复失败率、token、latency 和边际提升。

会议目前没有给 Resource 最终数量。

## 四、Object Set：会议中争议最大的架构问题

### 4.1 为什么最初认为 Object Set 有必要

如果只有 Action=EAT 和 Resource=hunger，仍然无法回答：

- 吃什么？
- 这个东西多少热量？
- 价格多少？
- 饱腹影响多少？
- 当前库存有没有？

例如 EAT(croissant) 和 EAT(instant_noodle) 都属于 EAT，但对 Resource 的影响不同。

会议中的关键判断是：

> 如果没有 Object Set，Action 的接收方就没有可维护的属性。

也就是：

Action + Object attributes → Resource effect

### 4.2 反方向问题：能不能彻底取消 Object Set，让模型自己输出？

会议同时提出：

> 现在模型本身已经知道什么是牛角包、方便面、王者荣耀、电视剧，我们有没有必要维护一个巨大的对象库？

如果直接让模型说“我想吃牛角包”或“我想玩王者荣耀”，千万级 Catalog 似乎可以省掉。

但删除 Object Set 并没有自动删除这些问题：

- 价格是多少？
- 热量是多少？
- 是否拥有？
- 库存是多少？
- 以前是否买过？
- 这部剧看到第几集？
- 同一个对象以后还能不能认出来？

因此真正需要实验的问题不是“模型知不知道这个东西”，而是：

> 模型自由生成对象后，系统是否还能长期保持 canonical identity、可计算属性和状态一致性？

## 五、Object Set 可能真正解决的是“世界一致性”，而不是“常识”

会议中很重要的长期一致性例子包括：

- Day 1 看某节目第 1 集，Day 3 又看第 1 集，Day 7 再次看第 1 集；
- 买过一个游戏，后面又忘了自己拥有；
- 吃掉了一个物品，但库存没有变化；
- 同一作品换名字后被当成新对象；
- 拥有某设备，后面模型又说自己没有。

因此 Object Set 的价值可能不是“告诉模型现实世界有哪些东西”，而是：

> 为 simulator 提供对象身份、所有权、库存、进度和历史的一致性。

候选分工：

LLM knowledge → 开放世界常识  
Object / World Store → identity / ownership / inventory / progress / history

这一点仍需要真实实验确认。

## 六、大 Object Catalog 不代表 Agent 每次要看到所有对象

即使后台有 1,000、100,000、10,000,000 个对象，一次决策也不应该全部放进 prompt。

更合理的分层是：

Master Catalog
→ availability / world event
→ Active World Pool
→ preference / state / history
→ Candidate Set
→ Top-K
→ Agent 最终选 1 个

会议以游戏为例：后台可以保存 1,000 个游戏，但当前世界只“上架” 50 个，Agent 当前真正看到的可能只有 10 个。

之后可通过世界事件动态上下架，例如游戏公司倒闭、旧游戏下架、新游戏上线、热度变化。

## 七、Object 候选管理的两个方案

### 方案 A：动态 Preference / Retrieval Top-K

大 Catalog
→ 根据 Persona / history / current state
→ 每次动态检索 Top-K

优点是个性化强、候选随 Agent 改变、Prompt 始终受控。

### 方案 B：有限 Active Pool + 世界事件动态上下架

例如 Master Game Catalog=1000，Current World Games=50。

过一段时间通过世界事件下架低使用率项目、关闭某些项目、上线新对象。

Active Pool 始终有绝对上限。

会议对这种方式表现出较强兴趣，因为它兼顾候选规模受控和世界变化。最终也可能采用二者组合。

## 八、模拟世界不应该追求“无限真实”

会议形成的重要工程观念：

> 目标不是完整复制现实世界，而是构建对研究任务有用的有限世界。

如果下游任务真正关心的游戏只有王者荣耀、鹅鸭杀、炉石传说等，可以主动构造任务相关对象 + 少量随机干扰项，而不是收集所有现实游戏。

因此：

真实世界 ≠ 模拟世界  
模拟世界 = 与实验目标相关的有限投影

## 九、RuleEngine 的最大问题：千万对象下不能显式维护关系图

假设 Object=10M+、Action=10–20+、Resource=10–20+，再乘上多条 Rule，如果全部展开成显式关系，很容易达到 100M、1B 甚至更多 edge。

这种图不可能靠人工维护。

会议中的方向是：

> 人只维护少量抽象 Set / schema / rule template，具体关系由代码维护。

## 十、一个更合理的 RuleEngine 表达方式

错误方向：

方便面 → EAT → hunger  
牛角包 → EAT → hunger  
螃蟹 → EAT → hunger

候选方向：

Object Type = food  
Capability = edible  
Action Template = EAT(target)

Rule Template：
- target has edible
- target in inventory
- consume target
- using target attributes update hunger / energy

具体 Object 只携带 calories、price、satiety 等属性，Rule 只定义一次。

未来候选结构：

Object Type
+ Capability
+ Action Template
+ Object Attributes
+ Rule Template

而不是提前生成十亿级 edge。

## 十一、Action 也不应该因为 Object 数量而无限膨胀

不能走向 EAT_CROISSANT、EAT_NOODLE、PLAY_WANGZHE、PLAY_HEARTHSTONE 等对象专属 Action。

更合理的抽象是：

Action = verb  
Object = noun  
Resource = state  
Rule = how verb(noun) changes state

例如 EAT(food)、PLAY(game)、WATCH(video)、BUY(product)、SELL(asset)。

## 十二、方法论要求：以后不能只讨论 Idea，必须优先跑有限实测

会议明确要求：

Idea
→ 独立最小实现
→ 有限实验
→ 真实数据
→ 决定是否进入底层架构

原因是整个 simulator 交互复杂。局部看来合理的改动，接入真实系统后可能导致行为异常、状态失控、token / latency 爆炸或长期一致性下降。

因此后续底层架构采用：

> experiment-driven，而不是 imagination-driven。

## 十三、模型大小也成为未来架构变量

会议后段讨论了未来可能不只测试 7B / 8B，也可以把 20B 作为 baseline。

然后反向测试：

> 模型能力提高后，Persona / Resource / Object context 是否可以进一步减少？

因此未来可以做 Model Size × Context Size / Resource Size 的联合实验。

## 十四、当前三个新研究问题

### Q3 — Object Set Necessity

问题：

> Object Set 是否真的有存在必要？

候选：

- A. LLM free generation
- B. Catalog + Top-K
- C. Hybrid

重点测试：

- object resolution
- runtime executability
- effect coverage
- canonical identity
- ownership / inventory
- progress consistency
- long-term consistency
- context/token cost
- maintenance cost

当前状态：IN EXPERIMENT

已有独立研究分支：

research/object-set-necessity

已有 benchmark PR：

PR #1

当前离线 gate 只证明实验 pipeline 可以工作，不代表真实模型结论。

### Q4 — Resource Set Size

问题：

> Resource Set 多大以后已经足够让 Agent 看起来像正常人？

候选实验：

R8 / R16 / R32 / R64

重点看行为质量、可执行率、矛盾率、token cost、latency 和边际收益。

当前状态：NOT STARTED

### Q5 — 10M+ Object RuleEngine Scaling

问题：

> 千万级 Object 下，如何避免显式维护十亿级边？

候选方向：

Type
+ Capability
+ Rule Template
+ Runtime Matching
+ Retrieval

可做纯 Python synthetic scaling test：

10K / 100K / 1M / 10M Objects

测试 index build time、memory、query latency、Top-K retrieval latency、rule matching latency、explicit edges 和维护复杂度。

当前状态：NOT STARTED

## 十五、与 Research A2 的关系

A2 已经确定：

真人行为数据
→ 校准 activity ontology / duration / transition / time prior

模型
→ 选择行为

确定性规则
→ 判断是否合法并执行后果

本次会议进一步提出：

Behavior Prior
→ Action Top-K

Resource Set
→ Agent 当前可见状态

Object Retrieval
→ 当前具体对象候选

LLM
→ Action + Object

Rule Template
→ deterministic effect

World State
→ 下一状态

因此这次讨论不是推翻 A2，而是在补齐 A2 之后的世界规模化和具体对象交互层。

## 十六、当前候选整体结构

Human Diary / Behavior Data
→ Activity / Action Top-K
→ Agent Resource State
→ High-level choice
→ Object Master Catalog（如果 Q3 证明必要）
→ World Availability / Preference / History
→ Object Top-K
→ LLM
→ Action + Object
→ Type / Capability / Rule Template
→ Deterministic Effects
→ Resource / World State Update

注意：这仍然是候选架构，不是最终冻结架构。

## 十七、当前比较确定的会议共识

截至当前会议片段，可以认为以下方向比较明确：

1. 真人 Diary 更像 Action Top-K prior，而不是完整 Action Set；
2. Agent 每次不应该看到全量对象；
3. Master Catalog 即使很大，Agent 可见 Candidate Set 也应该严格受限；
4. 世界不需要无限逼真，应围绕实验目标裁剪；
5. Rule 不能按每个 Object 显式人工维护；
6. RuleEngine 应优先考虑 schema / capability / template；
7. Resource 数量不是越多越好，需要通过 ablation 找边际收益点；
8. Object Set 是否必须存在，目前不能靠直觉决定，必须实测；
9. 新的底层架构设计优先采用有限实验验证；
10. 模型大小将来可以作为 Context / Resource 精简实验的控制变量。

## 十八、当前仍未形成结论的问题

以下内容不能写成最终设计：

- Object Set 最终保留、删除还是 Hybrid；
- Object Catalog 最终有多大；
- Active Pool 固定还是完全动态 retrieval；
- Resource 最终是 10、20、32 还是更多；
- LLM 自己生成 Object 属性是否可靠；
- 10M Catalog 最终采用什么数据库 / 索引；
- RuleEngine 最终实现形式；
- 最终 baseline 用 8B、13B、20B 还是其他模型；
- Object 与长期 memory 的最终接口；
- 世界事件如何控制 object 上下架；
- Top-K 最佳 K 值。

这些都需要实验。

## 十九、当前建议实验顺序

Q3 Object Set Necessity
→ Q4 Resource Size Ablation
→ Q5 10M Object RuleEngine Scaling
→ 再决定最终 World/Object/Resource 架构

其中 Q3 已经开始实现。

## 二十、记录原则

后续继续整理会议时，始终区分：

- MEETING IDEA：讨论中的构想
- ENGINEERING HYPOTHESIS：可验证工程假设
- EXPERIMENT RESULT：真实跑出来的数据
- FROZEN DECISION：已经正式进入架构的决定

禁止把会议中提出的想法直接升级成“已验证结论”。

## 当前状态摘要

A2：
行为层和真人数据 / 规则分工基本收口

Q3：
Object Set 是否必要
→ 正在实验

Q4：
Resource Set 最小规模
→ 未开始

Q5：
千万级对象下 RuleEngine 如何 scale
→ 未开始

总体方向：
少量人工维护抽象集合和规则模板
+ 程序负责大规模对象 / 关系
+ Agent 每次只看到有限候选和有限状态
+ 所有重大底层设计先做小实验再冻结
