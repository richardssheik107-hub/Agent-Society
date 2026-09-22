# 三个核心问题的实验整理与结论

本文将当前 research_status.md 以及 Q3、Q4、Q5 三份原始实验报告整理为一份统一说明，重点回答三个问题：

1. 对象（Object）是否需要一个明确、规范化的对象集？
2. 人物（Agent）每次决策到底需要看到多少状态（Resource）？
3. 当对象规模达到百万、千万级时，规则关系应该怎样维护，才能避免对象数增长导致规则图爆炸？

这三个问题分别对应 Agent 行为系统中的三个层次：

~~~text
对象从哪里来？
→ Q3：Object Set

人物决策时应该看到哪些状态？
→ Q4：Resource Set

对象、动作、资源之间的规则关系如何扩展？
→ Q5：RuleEngine Scaling
~~~

三组实验不是彼此独立的零散测试，而是在逐步确定系统的核心架构：

~~~text
Q3：先确定“模型从什么对象中选择”
↓
Q4：再确定“模型做选择时看到多少个人状态”
↓
Q5：最后确定“对象很多时，规则如何不随对象数量线性膨胀”
~~~

---

# 一、问题一：是否需要保留明确的对象集？

来源：

- 当前状态说明：docs/current/research_status.md
- 原始实验报告：docs/archive/2026-09-20/research_q3_object_set_necessity_real_attempt2.md

## 1.1 为什么要研究这个问题

如果让 LLM 完全自由地决定“使用什么对象”，它不仅要决定行为，还要自己生成对象名称和对象属性。

例如角色想吃东西时，模型可能自己生成一个世界中从未定义过的食品，并同时给出价格、热量和饱腹度。问题在于，这些对象和属性未必真的存在于系统世界中。

于是会出现两个工程风险：

1. 对象无法解析。模型生成了一个世界中不存在的对象，RuleEngine 无法执行。
2. 对象属性不权威。价格、热量、持续时间、效果等字段由模型临时猜测，同一个对象可能前后不一致。

因此 Q3 的核心问题不是“LLM 会不会创造东西”，而是：

> 在需要可执行、可持续的 Agent 世界中，是否应该给模型一个规范化对象目录，让模型从目录中选择，而不是让模型临时创造所有对象和属性？

## 1.2 实验设计

实验比较三个方案。

### A — LLM_ONLY

模型看不到对象目录，可以自由生成任何对象和属性。

~~~text
LLM
→ 自己命名对象
→ 自己生成价格、效果、属性
~~~

### B — CATALOG_TOPK

系统拥有规范化对象目录。每次决策前从目录中检索 Top-K 候选，模型只能从这些对象里选择。

~~~text
Object Catalog
→ Top-K candidates
→ LLM 选择
~~~

对象属性来自目录，因此价格、热量、时长、效果等字段具有统一来源。

### C — HYBRID

模型既可以选择 Catalog 中的对象，也允许输出 NEW 对象。这样可以保留开放世界能力，但新对象的必要属性仍然需要模型提供。

## 1.3 实验规模

完整真实实验：

~~~text
5 个领域
× 6 个固定状态
× 3 个实验臂
× 2 次重复
= 180 个请求
~~~

实际结果：

- 调度请求：180
- success：162
- timeout：18
- HTTP error：0
- parse error：0
- architecture error：0
- 三个实验臂同时成功的 matched ABC case：43 组

主要比较使用这 43 组共同成功样本，避免不同实验臂 timeout 数量不同造成直接比较偏差。

## 1.4 核心结果

| 方案 | 运行时可执行率 | 可用效果字段覆盖率 | 权威字段覆盖率 | 模型估计字段率 |
|---|---:|---:|---:|---:|
| A — LLM_ONLY | 30.23% | 72.87% | 0% | 100% |
| B — CATALOG_TOPK | 100% | 100% | 100% | 0% |
| C — HYBRID | 88.37% | 96.12% | 41.86% | 58.14% |

最明显的是 A 与 B 的差异：

~~~text
LLM_ONLY runtime executable ≈ 30.2%
CATALOG_TOPK runtime executable = 100%
~~~

权威字段覆盖：

~~~text
LLM_ONLY = 0%
CATALOG_TOPK = 100%
~~~

也就是说，在这个实验中，Catalog 不只是让模型“更容易选对对象”，还解决了一个更重要的问题：对象属性由谁负责提供。

如果属性来自 Catalog，那么价格、热量、时长、库存、效果和能力等字段可以由系统维护，而不是让模型每次重新猜。

## 1.5 Hybrid 为什么没有直接采用

Hybrid 的目标，是同时得到 Catalog 的稳定性与开放世界新增对象能力。

但 matched case 中：

~~~text
CATALOG_TOPK runtime rate = 1.0000
HYBRID runtime rate       = 0.8837
~~~

差距约 11.63 个百分点。

Hybrid 确实允许模型创建新对象，但当前还没有保持 Catalog-only 方案的稳定执行水平。

因此：

~~~text
HYBRID = UNRESOLVED
~~~

而不是已经接受。

## 1.6 Q3 的结论

当前工程参考方案确定为：

~~~text
Catalog + Top-K
~~~

即：

> 后台维护规范对象目录，每次只向模型暴露少量相关对象候选。模型负责选择对象，但不负责随意定义世界真值。

Q3 的实验信号为：

~~~text
OBJECT_SET_NECESSITY_SIGNAL = STRONG
~~~

这里的 STRONG 是当前 benchmark 的工程信号，不是统计学总体结论。

## 1.7 Q3 不能推出什么

Q3 不能证明：

- 所有 Agent 都必须使用 Catalog；
- 所有模型都不能生成对象；
- Catalog 中的合成价格和热量就是真实世界事实；
- Hybrid 永远不可行；
- Catalog + Top-K 能保证长期人类行为合理；
- 对象身份、库存、观看进度可以跨天持续。

它只回答一个窄问题：

> 在当前单步真实模型实验中，规范对象集明显提高了对象选择的可执行性和属性来源的一致性。

---

# 二、问题二：人物每次决策应该看到多少状态？

来源：

- 当前状态说明：docs/current/research_status.md
- 原始实验报告：docs/archive/2026-09-20/research_q4_resource_set_size.md

## 2.1 为什么要研究这个问题

Agent 后台可以保存很多状态，例如饥饿、精力、睡眠压力、工作紧急度、卫生需求、家务积压、休闲需求、预算压力、压力、社交需求、通勤压力、睡眠债务、现金和信用等。

问题是：

> 这些状态是不是每次全部塞给模型？

如果状态太少，模型可能看不到关键事实。如果状态太多，则会增加 prompt、token 成本和无关信息，也会增加后续小模型部署难度。

因此 Q4 研究的是：

> 在底层世界完全相同的情况下，只改变模型可见 Resource 数量，会怎样影响行为选择与成本？

## 2.2 实验设计

后台固定一个完整的 ResourceTruth64，即 64 个状态全部存在。

实验并不是让 R8 世界只有 8 个状态，而是：

~~~text
后台真值始终 = 64 个 Resource

R8  → 模型只看其中 8 个
R16 → 模型看其中 16 个
R32 → 模型看其中 32 个
R64 → 模型看全部 64 个
~~~

因此这是一个 visibility / projection experiment，而不是四个不同世界。

## 2.3 四种 Resource 条件

### R8

8 个最基础、粗粒度状态：

- hunger
- energy
- sleep_pressure
- work_urgency
- hygiene_need
- chores_backlog
- leisure_need
- budget_pressure

### R16

在 R8 基础上增加 stress、social_need、commute_pressure、discretionary_budget_remaining、work_progress、meal_recency、personal_care_recency、chores_recency。

### R32

进一步增加疲劳、睡眠质量、趋势、财务和工作细节等字段。

### R64

再增加健康、社交、家务细项、流动性、交通可用性、娱乐新鲜度等完整状态。

## 2.4 实验规模

固定：

~~~text
24 个场景
× 4 个 Resource level
× 2 次重复
= 192 requests
~~~

实际：

- scheduled：192
- success：174
- timeout：18
- HTTP error：0
- parse error：0
- architecture error：0
- 四个层级全部成功的 matched quadruple：33 / 48

主要比较只使用这 33 组共同成功样本。

## 2.5 核心结果

| Resource | 行为对齐率 | 规则可执行率 | 关键遗漏率 | Held-out share | 平均输入 token |
|---|---:|---:|---:|---:|---:|
| R8 | 69.70% | 96.97% | 30.30% | 33.80% | 281 |
| R16 | 72.73% | 96.97% | 27.27% | 33.29% | 346 |
| R32 | 72.73% | 93.94% | 27.27% | 32.03% | 477 |
| R64 | 84.85% | 100% | 15.15% | 27.77% | 747 |

这里最重要的不是简单宣布“R64 最好”，而是观察收益与上下文成本之间的关系。

## 2.6 R8 → R16

行为对齐：

~~~text
69.70% → 72.73%
~~~

提高约 3 个百分点。

输入 token：

~~~text
281 → 346
~~~

增加约 23%。

因此有一定改善，但改善并不巨大。

## 2.7 R16 → R32

行为对齐：

~~~text
72.73% → 72.73%
~~~

没有观察到提高。

规则可执行率略有下降：

~~~text
96.97% → 93.94%
~~~

但 token 从 346 增加到 477，增幅约 37.85%。

因此这一段被标记为：

~~~text
LOW_MARGINAL_RETURN
~~~

即：增加了不少上下文，但在本次实验中没有观察到相应行为收益。

## 2.8 R32 → R64

行为对齐：

~~~text
72.73% → 84.85%
~~~

明显提高。

关键遗漏：

~~~text
27.27% → 15.15%
~~~

明显下降。

但 token 同时从 477 增加到 747，增加约 56.6%。

因此 R64 在这次 benchmark 中表现最好，但代价也是最大。

## 2.9 为什么不能直接说“64 个状态最好”

因为 R8/R16/R32/R64 不只是字段数量不同，它们同时改变了字段数量与具体加入的字段。

例如 transport_availability 只在 R64 才出现。如果某个出行场景在 R64 变好，我们不能区分是因为“有 64 个字段”，还是因为“transport_availability 终于出现”。

因此当前不能把实验解释成：

> Agent 最优状态数量就是 64。

## 2.10 Q4 的正式结论

实验结论：

~~~text
RESOURCE_SET_RESULT = PARTIALLY_RESOLVED
MINIMUM_TESTED_RESOURCE_SET = UNRESOLVED
LOW_MARGINAL_RETURN_STARTS_AT = R32
RESOURCE_OVERLOAD_SIGNAL = NO
~~~

已经知道：

1. R8 在本 benchmark 中偏弱；
2. R16 相比 R8 有小幅改善；
3. R16 → R32 出现明显的低边际收益；
4. R64 在这次 matched 数据中对齐率最高、关键遗漏最低；
5. 没观察到“字段越多反而明显整体恶化”的 overload 信号。

仍然不知道：

> 真正最小且足够的 Resource Set 是多少。

## 2.11 Q4 更重要的架构启示

Q4 最重要的意义，不是寻找一个固定数字 8、16、32 或 64，而是区分：

~~~text
后台应该保存多少状态
~~~

与：

~~~text
每次决策应该让模型看到多少状态
~~~

这两件事。

因此当前更合理的架构方向是：

~~~text
Rich Resource Store
        ↓
Relevant Resource Projection / Retrieval
        ↓
短上下文
        ↓
LLM
~~~

即后台可以保存丰富真值，但每次只给模型当前决策真正相关的状态。

这一方向在 Q4 中只是提出的后续假设，Q4 本身没有完成动态 Resource Retrieval 的真实消融实验。

## 2.12 Held-out diary 为什么不能直接当“真人正确率”

Q4 还比较了 held-out diary action share。结果并没有随着 Resource 更多而上升。

这并不意味着 R64 更不像真人。

原因是 diary 数据统计的是现实生活中的活动分布，而 Q4 场景往往人为设置了明确需求。例如“当前特别饥饿”时选择 MEAL 很合理，但普通日记中 MEAL 占比不一定高。

因此：

> 日记频率不能直接等价于给定强需求状态下的“正确答案”。

---

# 三、问题三：对象达到千万级后，规则关系怎么维护？

来源：

- 当前状态说明：docs/current/research_status.md
- 原始实验报告：docs/archive/2026-09-20/research_q5_rule_engine_scaling.md

## 3.1 为什么要研究这个问题

确定 Catalog 后，会出现新的规模问题。

假设最终有 10,000,000 个 Objects，同时存在 Action、Resource、Rule 和 Capability。

如果对每个对象都单独维护 Object → Action → Rule → Resource 关系，关系数量会迅速爆炸。

例如：

~~~text
apple_1 → EAT
apple_2 → EAT
apple_3 → EAT
...
apple_5,000,000 → EAT
~~~

实际上这些对象共享同一类规则。

因此 Q5 的问题是：

> 是否可以只维护类型和规则模板，而不是为每个具体对象复制规则关系？

## 3.2 两种架构

### A. 朴素显式关系图

每个对象单独连接规则。对象数增长，rule relation 也线性增长。

在 Q5 固定 schema 下：

~~~text
10M objects
→ 75M explicit relations
~~~

即使只按 packed uint64 的极乐观下界计算，也需要约 600 MB。

这还没有计算 Python object overhead、tuple、dictionary、allocator、database index 和对象 payload。

### B. Type + Capability + Rule Template

目标设计：

~~~text
Object
↓
Object Type
↓
Capability
↓
Rule Template
~~~

例如 apple、banana、bread、rice 都可以属于：

~~~text
Type = food
Capability = edible
~~~

EAT 规则只需要定义一次。

~~~text
EAT(edible object)

inventory -= 1
hunger -= satiety(object)
calories += calories(object)
~~~

不同对象之间的差异来自对象属性，例如 price、satiety、calories、duration，而不是复制不同规则。

因此：

> 规则决定“怎么作用”，对象属性决定“作用多少”。

## 3.3 实验设计

Synthetic schema 固定为：

- 10 个 Object Types；
- 约 11 个 Capabilities；
- 16 个 Resources；
- 11 个 Rule Templates。

对象规模测试：

~~~text
10K
100K
1M
10M
~~~

每个规模：

~~~text
1000 deterministic queries
Top-K = 50
~~~

实验不调用 LLM，不访问 provider。

10M 对象使用虚拟 canonical integer object IDs，而不是在 Python 内存中真的创建一千万个 payload。

因此研究的是 Rule Graph / Rule Index 是否扩展，而不是真实千万商品数据库是否已经完成。

## 3.4 主要结果

| 对象数 | 显式关系估计 | 显式 packed 下界 | Target metadata | candidate touches/query | object scans | per-object rule edges |
|---:|---:|---:|---:|---:|---:|---:|
| 10K | 75K | 0.6 MB | ≈17.9 KB | 50 | 0 | 0 |
| 100K | 750K | 6 MB | ≈17.9 KB | 50 | 0 | 0 |
| 1M | 7.5M | 60 MB | ≈17.9 KB | 50 | 0 | 0 |
| 10M | 75M | 600 MB | ≈17.9 KB | 50 | 0 | 0 |

同时：

~~~text
Type → Rule index entries = 21
Capability → Type index entries = 28
~~~

从 10K 到 10M 都保持不变。

目标架构没有 per-object rule edges，并且每次 query 只访问 Top-K=50 个候选，没有扫描整个对象空间：

~~~text
object_scan_count = 0
~~~

## 3.5 10M 结果的核心意义

对象数从 10,000 增加到 10,000,000，增长了 1000 倍。

但是：

~~~text
Type→Rule entries = 21
Capability→Type entries = 28
Rule templates = 11
~~~

没有随着对象数增长。

因此结构上可以得到：

~~~text
Rule graph complexity
≈ function(Type, Capability, RuleTemplate)

而不是

≈ function(ObjectCount)
~~~

## 3.6 查询路径

目标设计不是：

~~~text
扫描 10M 对象
→ 对每个对象检查规则
~~~

而是：

~~~text
Capability
→ eligible Types
→ Top-K Objects
→ Type
→ Rule Templates
~~~

因此规则匹配只发生在少量候选上。

10M benchmark 中：

~~~text
candidate touches/query = 50
object scans = 0
~~~

并且实际触达了 10M 地址空间上半区，不是只测试前几千个 object ID。

## 3.7 Q5 的正式工程结论

结构门槛全部通过：

~~~text
RULE_ENGINE_SCALING_RESULT = CLOSED_ENGINEERING
~~~

这里的 CLOSED_ENGINEERING 指：

> 对于当前 synthetic schema，“规则关系是否需要随着对象数线性复制”这个狭窄工程问题已经关闭。

当前保留设计：

~~~text
Object
→ Type
→ Capability
→ Rule Template
→ Resource Effect
~~~

而不是：

~~~text
Object
→ 独立 Rule Edge
~~~

## 3.8 Q5 不能推出什么

Q5 没有验证：

- 真实 10M payload 数据库；
- 向量数据库；
- 实际商品搜索；
- 真实 Top-K retrieval latency；
- 分布式存储；
- 多机并发；
- production ontology；
- 所有真实 Action；
- 所有真实 Resource；
- Agent 行为质量；
- 长期状态连续性。

因此约 17.9 KB 只表示小型规则索引的估计大小，绝不等于“一千万个真实对象只需要 17.9 KB”。

同样，几十微秒的本地查询延迟也不能解读为真实生产对象搜索一定只需要几十微秒。

---

# 四、三个实验放在一起说明了什么？

三组实验实际上确定了系统中三个不同职责。

## 4.1 Object 层

Q3 给出的方向：

~~~text
后台拥有规范 Object Catalog
↓
按当前上下文检索 Top-K
↓
LLM 从候选中选择
~~~

模型不应该负责重新定义全部对象真值。

## 4.2 Resource 层

Q4 给出的方向：

~~~text
后台保存 Rich Resource State
↓
每次决策只投影相关 Resource
↓
LLM 使用短上下文做决策
~~~

“后台保存多少”和“模型看到多少”必须分开。

## 4.3 Rule 层

Q5 给出的方向：

~~~text
Object ID
↓
Type
↓
Capability
↓
Rule Template
↓
Deterministic Effect
~~~

对象越多，不需要复制越多规则模板。

---

# 五、最终统一架构

综合 Q3、Q4、Q5，当前最合理的总体结构是：

~~~text
                    Persistent World State
                            │
             ┌──────────────┴──────────────┐
             │                             │
      Object Catalog                Resource Store
             │                             │
        Object Top-K              Relevant Resource
         Retrieval                   Projection
             │                             │
             └──────────────┬──────────────┘
                            │
                    Bounded Observation
                            │
                            ▼
                           LLM
                    高层行为 / 对象选择
                            │
                            ▼
                 Deterministic RuleEngine
                            │
                Object → Type → Capability
                            │
                      Rule Template
                            │
                            ▼
                     State Transition
                            │
                            ▼
                    Persistent World State
~~~

一句话概括：

> 模型负责“在当前上下文中想做什么”，系统负责“世界中有什么、当前状态是什么、动作是否合法、动作产生什么后果”。

---

# 六、三个问题当前的最终状态

| 问题 | 当前结果 | 工程决定 |
|---|---|---|
| Q3：是否需要 Object Set？ | 较强支持需要规范对象目录 | 采用 Catalog + Top-K |
| Q4：人物需要多少 Resource？ | 部分解决，最小集合仍未知 | 后台保留丰富状态，下一步研究 Relevant Resource Projection |
| Q5：10M 对象如何维护规则？ | 结构性工程问题已关闭 | 采用 Type + Capability + Rule Template |

对应机器标签：

~~~text
Q3
OBJECT_SET_NECESSITY_SIGNAL = STRONG

Q4
RESOURCE_SET_RESULT = PARTIALLY_RESOLVED
MINIMUM_TESTED_RESOURCE_SET = UNRESOLVED
LOW_MARGINAL_RETURN_STARTS_AT = R32
RESOURCE_OVERLOAD_SIGNAL = NO

Q5
RULE_ENGINE_SCALING_RESULT = CLOSED_ENGINEERING
~~~

---

# 七、为什么后续研究重点从 Q3/Q4/Q5 转向 Q6

完成这三组实验以后，下一步已经不应该继续无限扩大 Object 数量、Resource 数量和 Rule 数量。

更关键的问题变成：

> 这些设计放进一个持续运行的 Agent 后，状态能不能真正连续。

例如：

- 买东西后钱是否减少？
- 吃东西后库存是否减少？
- 看了一半的视频，下次是否从原进度继续？
- 重启后状态是否保持？
- 重复 request 是否会重复扣钱？
- 模型下一次决策是否看到上一次执行后的新状态？

因此研究重点自然进入 Q6：

~~~text
Q3/Q4/Q5
确定世界如何表示
        ↓
Q6
验证这个世界能不能持续运行
~~~

这也是为什么当前优先级已经从“继续设计更大的纸面世界”转向 Persistent State、Activity Commitment、State Feedback、Deterministic Execution 和 Short-context Projection。

---

# 八、最简汇报版结论

如果只用几句话向导师或团队解释，可以概括为：

> 第一个实验研究对象集。结果发现，让模型完全自由生成对象时，只有约 30% 的 matched 选择能够直接被系统执行，而使用 Catalog + Top-K 后达到 100%，并且对象属性全部来自统一目录。因此我们确定后台应该维护规范对象集，模型只从相关候选中选择。

> 第二个实验研究人物状态。我们比较 R8、R16、R32、R64 四种可见状态规模，发现更多状态并不是简单地越多越好：R16 到 R32 增加了约 38% 输入 token，却没有提高行为对齐；R64 在本次实验中表现最好，但成本最高。因此现在不能确定一个固定的最小状态数量，更合理的方向是后台保存完整状态，每次只给模型投影当前真正相关的 Resource。

> 第三个实验研究千万对象下的规则扩展。结果显示，如果每个对象都维护规则边，10M 对象会产生约 7500 万条关系；而采用 Type + Capability + Rule Template 后，规则索引规模基本不随对象数增加，10M 虚拟对象下仍只有 21 个 Type→Rule 和 28 个 Capability→Type 索引项，并且运行时只检查 Top-K 候选。因此规则系统应该围绕类型、能力和共享模板维护，而不是围绕具体对象复制规则。

最终形成的统一原则是：

~~~text
Catalog 管“世界里有什么”
Resource Store 管“人物现在是什么状态”
LLM 管“下一步想做什么”
RuleEngine 管“能不能做、做完会发生什么”
Persistent State 管“这些结果如何延续到下一步”
~~~

这三组实验因此不是三个孤立结果，而是在逐步确定整个持续行为模拟系统的底层架构。

---

# 九、原始材料

- docs/current/research_status.md
- docs/archive/2026-09-20/research_q3_object_set_necessity_real_attempt2.md
- docs/archive/2026-09-20/research_q4_resource_set_size.md
- docs/archive/2026-09-20/research_q5_rule_engine_scaling.md
