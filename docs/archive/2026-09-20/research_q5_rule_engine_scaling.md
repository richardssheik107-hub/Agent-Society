# Research Q5 — 10M Object RuleEngine Scaling

## Research question

会议第三个核心问题是：

当 Object Set 最终达到一千万甚至更多对象时，怎样维护 Action × Object × Resource × Rule 的关系，而不是让人维护十亿级显式边？

本阶段只研究 rule graph / index 的规模化方式。它不测试 LLM 行为，不测试真人相似度，也不测试真实 10M 商品、电影或游戏 payload 数据库。

## Two designs

### A. Naive explicit graph

坏基线会对每个具体 Object 展开：

Object → applicable Rule → affected Resource

每个 Object 对每条适用规则产生一条 applicability relation，并对每个 affected Resource 继续产生关系。

显式基线使用 packed uint64，因此已经是非常乐观的存储下界，不计算 Python tuple 或 object overhead。

为了避免故意把机器打爆：

- 10K 和 100K 可以真实 materialize；
- 1M 和 10M 只计算精确 relation 数量和 packed lower-bound bytes；
- 超过 safety cap 的显式图会明确拒绝 materialize。

### B. Type + Capability + Rule Template

目标设计不让具体 Object 拥有自己的 Rule edge。

人工只维护：

- Object Type；
- Capability；
- Resource definition；
- Rule Template。

例如 food 拥有 edible capability。

EAT 规则只定义一次，影响 inventory、hunger、energy。

一千万个 food object 不会生成一千万份 EAT rule。

运行时路径是：

Object ID → Type → applicable Rule Templates

因此 rule index 的规模只由 Type 和 Rule Template 决定，而不是由 Object Count 决定。

## Synthetic schema

Q5 固定一个小的可审计 schema：

- 10 个 Object Types；
- 11 个 Capability 左右；
- 16 个 Resources；
- 11 个 Rule Templates。

Types 包括 food、game、video、product、asset、vehicle、place、service、tool、book。

Rules 包括 BUY、SELL、INVEST、EAT、PLAY、WATCH、USE、DRIVE、VISIT、BOOK、READ。

这不是 production ontology，只用于回答 scaling question。

## Why 10M objects are virtual ids

本实验不是在测试 Python 能不能 new 一千万个 dataclass。

真实系统中的 Object payload 最终可能在数据库、KV store、列式存储或搜索索引里。

Q5 真正要测试的是：

RuleEngine 是否需要随着 10M Object 一起复制 10M 份规则关系。

VirtualObjectCatalog 实际支持 canonical integer object ids 0 到 N-1，并会对 10M 地址空间执行真实 Top-K retrieval 和 runtime rule matching，但不会把每个 payload 实例化成 Python object。

因此，本实验如果 PASS，只能说明 rule graph 和 rule index 的设计能够 scale；不能宣称真实 10M payload database 已经完成。

## Retrieval path

目标路径：

Capability → eligible Types → Top-K Object IDs → Type → Rule Templates

而不是：

scan 10M objects → test every rule

Benchmark 会记录：

- candidate touches；
- object scan count；
- Top-K query latency；
- matched rule count；
- max object id touched。

结构门槛要求：

- object_scan_count = 0；
- candidate touches 被 Top-K 限制；
- 查询实际触达 10M 地址空间上半区；
- rule matching correctness PASS。

## Scale levels

固定四档：

- 10K
- 100K
- 1M
- 10M objects

默认每档：

- Top-K = 50
- 1000 deterministic queries
- seed = 2026

不调用 LLM、provider 或网络。

## Metrics

每个规模报告：

- object_count
- type_count
- capability_count
- resource_count
- rule_template_count
- human_maintained_units
- capability_type_index_entries
- type_rule_index_entries
- target_per_object_rule_edges
- target_build_seconds
- target_metadata_bytes
- explicit_relation_estimate
- explicit_packed_lower_bound_bytes
- explicit materialization metrics（安全范围内）
- query p50 / p95
- candidate touches
- object scan count
- rule matches
- max object id touched

## Structural acceptance gate

CLOSED_ENGINEERING 只表示当前 synthetic rule-graph 问题满足：

1. Rule Template 数量不随 Object Count 增长；
2. Type→Rule index entry 数不随 Object Count 增长；
3. Capability→Type index entry 数不随 Object Count 增长；
4. target design 没有 per-object rule edges；
5. retrieval 不扫描全部 Object；
6. candidate touches 被 Top-K 上限约束；
7. 10M 查询真实触达大 object id，而不是只在前几千对象上运行。

Wall-clock latency 不作为硬 PASS/FAIL，因为 GitHub runner、本地机器和未来数据库后端会不同。Latency 只做描述。

## What this can answer

如果 gate PASS，可以说：

对于当前 Type / Capability / Template schema，RuleGraph 本身不需要随 Object 数量线性展开；千万级 Object 可以共享常数规模的规则模板和类型索引，并只对 Top-K 候选做 runtime matching。

这直接回答会议里的问题：人不需要维护 B 级 edge 图，代码通过 Type / Capability / Template 自动解释对象和规则之间的关系。

## What this cannot answer

本实验不能证明：

- 真实 10M Object payload database 已经设计完成；
- 真实搜索或向量检索的 Top-K latency；
- 分布式存储方案；
- 多机并发；
- 最终 production ontology；
- 所有真实 Action / Resource；
- Agent 行为质量；
- Hybrid Object；
- Resource retrieval；
- full-day continuity。

## Run

Focused tests:

PYTHONPATH=src pytest -q tests/test_rule_engine_scaling.py

Full benchmark:

PYTHONPATH=src python scripts/run_rule_engine_scaling.py

默认会执行 10K / 100K / 1M / 10M 四档，并把 summary.json 写到 run/evaluation/rule_engine_scaling/。

## Handoff for executor

执行者只需要：

1. 切到 research/rule-engine-scaling；
2. 跑 focused tests；
3. 跑 full regression；
4. 跑 Ruff；
5. 跑 scripts/run_rule_engine_scaling.py；
6. 把真实 summary 写入本报告 Result 区；
7. push 结果 commit；
8. STOP。

不要修改 schema 去追求更好数字，也不要启动 LLM 实验。

## Result

### 本机环境

- Windows host + Ubuntu WSL2 (`Linux 6.18.33.2-microsoft-standard-WSL2`, x86_64)
- 24 vCPU，7.6 GiB visible memory
- uv-managed CPython 3.12.14 environment from the pinned AgentSociety workspace
- Integration branch: `research/rule-engine-scaling`
- Starting commit: `afd9f9dc8ce80e3d793714d46e5d888a012dadb5`
- No LLM, provider, or network request was made by the benchmark

### Test and lint results

- Focused Q5 tests: **11 passed**
- Full regression: **508 passed, 3 existing warnings**
- Ruff: **PASS** (`ruff check` on the Q5 rule-scaling package, runner, and focused tests)
- Formal benchmark: **PASS**
- Artifact (ignored by Git): `run/evaluation/rule_engine_scaling/q5_20260919T130054787068Z/summary.json`
- Process peak RSS: 39,188 KiB

The full regression was run from the pinned upstream uv workspace with the integration `src/`, repository root, and `smoke/` directories on `PYTHONPATH`; the additional `smoke/` entry resolves an existing top-level smoke-module import used by the historical tests. No source or test file was changed.

### Formal benchmark results

Configuration was unchanged: object counts `10K/100K/1M/10M`, `queries_per_size=1000`, `top_k=50`, `seed=2026`, and `explicit_materialize_max_objects=100000`.

| objects | explicit relations | packed lower-bound bytes | target metadata bytes | target build s | p50 us | p95 us | candidate touches/query | object scans | target per-object edges | type→rule entries | capability→type entries | max object id | upper half |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 10,000 | 75,000 | 600,000 | 17,946 | 0.000020 | 28.679 | 34.669 | 50 | 0 | 0 | 21 | 28 | 9,999 | true |
| 100,000 | 750,000 | 6,000,000 | 17,930 | 0.000025 | 28.315 | 34.268 | 50 | 0 | 0 | 21 | 28 | 99,998 | true |
| 1,000,000 | 7,500,000 | 60,000,000 | 17,914 | 0.000026 | 28.946 | 36.406 | 50 | 0 | 0 | 21 | 28 | 999,936 | true |
| 10,000,000 | 75,000,000 | 600,000,000 | 17,898 | 0.000021 | 28.625 | 34.809 | 50 | 0 | 0 | 21 | 28 | 9,999,914 | true |

The four rows each executed 1,000 deterministic queries. The largest run therefore performed 50,000 candidate touches, never scanned the object space, and reached the upper half of the 10M virtual-id address space. `rule_matches_total` was 108,532 in each row, and the schema counts stayed at 10 types, 11 capabilities, 16 resources, and 11 rule templates.

### Explicit graph estimate and target architecture

The 10K and 100K explicit baselines were materialized. At 1M and 10M, the runner intentionally computed only the exact relation estimate and packed lower-bound bytes. The 10M explicit estimate is 75,000,000 relations and 600,000,000 packed bytes; this is an optimistic uint64 lower bound, not a claim about the memory required by a real Python object/tuple graph. The target path kept constant metadata (`target_metadata_bytes` about 17.9 KiB), zero per-object rule edges, and constant Type→Rule (`21`) and Capability→Type (`28`) index entries while matching only the Top-K candidates.

Structural gate: **PASS**. Therefore:

`RULE_ENGINE_SCALING_RESULT=CLOSED_ENGINEERING`

For the current synthetic Type / Capability / Rule Template schema, the RuleGraph does not need to expand linearly with Object Count. Ten million virtual objects can share constant-scale rule templates and type indexes, with runtime matching restricted to Top-K candidates.

### Limitations and engineering decision

This result is limited to the synthetic schema and virtual integer object-id catalog. It does not validate a production 10M payload database, real search or vector-retrieval latency, distributed storage, multi-machine concurrency, a final ontology, all real actions/resources, or agent behavior quality. It also does not test Resource retrieval, Action Top-K, Activity Commitment, or a local model.

Decision: keep the Type + Capability + Rule Template architecture and stop this phase. Do not interpret the packed baseline as real Python graph memory, and do not expand the conclusion to production database or distributed-search readiness.


## GitHub Actions preflight result

The branch-level GitHub Actions gate completed successfully on commit 37cd03c38bf037de707d4deb4508b547fd9696ea.

Focused tests:

11 passed.

Scaling smoke:

- 10K objects: 75,000 explicit relations; packed lower bound 600,000 bytes; p95 query 90.418 microseconds; scan 0; target per-object edges 0.
- 100K objects: 750,000 explicit relations; packed lower bound 6,000,000 bytes; p95 query 89.355 microseconds; scan 0; target per-object edges 0.
- 1M objects: 7,500,000 explicit relations; packed lower bound 60,000,000 bytes; p95 query 87.102 microseconds; scan 0; target per-object edges 0.
- 10M objects: 75,000,000 explicit relations; packed lower bound 600,000,000 bytes; p95 query 88.074 microseconds; scan 0; target per-object edges 0.

Preflight scaling result:

CLOSED_ENGINEERING

Interpretation boundary:

This CI result verifies the structural rule-graph design and a 10M virtual object-id address space. It does not replace the executor's required local full regression, Ruff run, or default 1000-query benchmark, and it does not claim that a real 10M payload database has been solved.
