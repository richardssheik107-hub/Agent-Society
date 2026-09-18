# Research Q3 — Object Set Necessity Benchmark

## 问题

这一阶段只回答一个问题：

> 一个长期运行的人类行为 simulator，是否真的需要维护 Object Set，还是让模型自由生成具体对象就足够？

这不是“哪个方案故事更有趣”的测试，而是系统能否长期维护世界状态的测试。

## 三个实验臂

### A — LLM-only

不给模型 Catalog。模型自由提出具体对象。

优点是上下文最少、世界开放；风险是系统可能无法把模型给出的名称映射到唯一 canonical object，也就无法可靠计算价格、热量、时长、库存或长期进度。

### B — Catalog + Top-K

后台存在 Master Catalog，但一次决策只暴露 Top-K 候选。模型必须选一个候选 ID。

Master Catalog 可以很大；Prompt Set 始终有严格上限。

### C — Hybrid

优先使用 Catalog + Top-K，但允许模型输出 `NEW:<name>`。新对象被实例化成 canonical object，并用类型模板补默认属性。

为了诚实区分“真实属性”和“估计属性”，Hybrid 的新对象会有：

- usable effect coverage
- exact effect coverage

两个指标。模板默认值可以让系统继续执行，但不能冒充精确事实。

## 当前 GitHub 实现

新增 package：

`src/social_sim/object_benchmark/`

目前包含：

- 5 个对象域：FOOD / GAME / VIDEO / PRODUCT / ASSET
- 默认 1,000 个 synthetic catalog objects
- 每域 6 个固定状态，共 30 个 scenario
- deterministic Top-K retrieval
- canonical ID / name / alias resolver
- capability-based executability
- exact / usable effect coverage
- strict one-field object selection parser
- optional real-provider A/B/C runner

整个 benchmark 与生产 RuleEngine 隔离，不修改 A2 reference profile。

## 离线 Gate

`scripts/run_object_set_necessity_offline.py`

运行：

```bash
PYTHONPATH=src python scripts/run_object_set_necessity_offline.py
```

它执行：

30 states × 3 arms × 2 repetitions = 180 rows。

**注意：这只是 SYSTEM_CAPABILITY_PROBE，不是模型行为实验。**

它用于验证：

- A 中 unknown object 会失去 canonical resolution / effect coverage；
- B 中 Top-K 对象可唯一解析、可执行并具有精确属性；
- C 中新对象可被实例化，但默认估计属性和精确属性被明确区分；
- 大 Master Catalog 不会进入 prompt。

## 真实模型 Pilot

`scripts/run_object_set_necessity_real.py`

环境变量：

```text
OBJECT_BENCH_BASE_URL
OBJECT_BENCH_API_KEY
OBJECT_BENCH_MODEL
```

示例：

```bash
PYTHONPATH=src python scripts/run_object_set_necessity_real.py --repetitions 2 --top-k 10
```

完整默认预算：

30 states × 3 arms × 2 repetitions = 180 provider requests。

建议先：

```bash
PYTHONPATH=src python scripts/run_object_set_necessity_real.py --repetitions 1 --top-k 10 --max-scenarios 5
```

做 15-request smoke，再决定是否执行完整 180-request pilot。

真实 runner 不保存：

- API key
- Authorization header
- raw prompt
- raw completion
- hidden reasoning

只保存已解析的对象选择和数值 token / latency metadata。

## 主要指标

第一轮重点：

1. resolution_rate — 能否映射到唯一 canonical object；
2. executable_rate — 能否直接交给确定性系统；
3. usable_effect_coverage — 是否有足够属性继续计算后果；
4. exact_effect_coverage — 后果属性是否来自明确对象记录而非模板估计；
5. novel_creation_rate — Hybrid 需要创建新对象的比例；
6. prompt/token cost — Catalog Top-K 的上下文代价。

后续连续性实验再加入：

- object identity consistency
- inventory consistency
- series/game progress consistency
- duplicate/replay error
- long-term maintenance cost

## 如何解释结果

若 A 的 object resolution、effect coverage 和长期一致性与 B/C 接近，则大型 Object Store 的必要性应重新评估。

若 B/C 明显更稳定，则 Object Set 的价值不是“告诉模型世界常识”，而是：

> 为世界提供 canonical identity、可计算属性、库存/进度/所有权和长期一致性。

若 C 接近 B 的稳定性但拥有更好的开放世界覆盖，则 Hybrid 是更值得继续扩展的候选。

## 这一轮不做什么

- 不把 1,000 万对象加载进 prompt；
- 不生成 Object × Action × Resource 的显式边；
- 不修改生产 RuleEngine；
- 不声称 synthetic offline probe 是 LLM 实验；
- 不开始 Resource-size ablation；
- 不开始 10M RuleEngine scaling。

先证明 Object Set 是否值得存在，再决定是否承担千万级 Catalog 的工程成本。
