# Research Q3 Real Result

## Question

本阶段只测试单步 object choice：没有 Object Set 的 A（LLM-only）、Catalog Top-K 的 B、以及允许 `NEW:<name>` 的 Hybrid C，能否把一次对象选择转成可执行的 simulator effect。结果不外推到长期 identity、inventory、game progress 或完整人类行为。

## Fairness Fix

三臂统一要求严格 JSON：`{"object":"...","attributes":{}}`。A 不再因为对象名无法映射 synthetic catalog 而被判定不可执行；A 的对象属性由同一次模型响应提供。C 的 NEW 对象也必须在同一次响应提供完整属性，并标记 `attribute_source=MODEL_ESTIMATED`。确定性 validator 只检查 schema、required fields 和有界合理范围，不猜测现实世界真值。没有第二次 LLM 请求。

## Provider Contract

本次 smoke 使用既有 reference contract：`https://ark.cn-beijing.volces.com/api/coding/v3`、`ark-code-latest`，每个 cell 最多一次请求、无 retry，wire body 仅 `model + messages`。API key 没有进入代码、命令输出或 artifact。

## Offline Gate

公平性修正后的 focused tests 为 **10 passed**。180-row offline probe 为 **PASS**，输出 `OBJECT_SET_NECESSITY_OFFLINE_OK`，并明确标记 `SYSTEM_CAPABILITY_PROBE_NOT_MODEL_BEHAVIOR`。三条 pipeline 均完成；offline synthetic rows 不是模型行为比较。

## Smoke Gate

Smoke schedule 是预注册的 5 states × 3 arms = **15 requests**，每个 cell 一次请求。实际结果：

- scheduled = 15
- success = 0
- timeout = 0
- parse_error = 0
- architecture_error = 0
- HTTP_ERROR = 15
- backend model = unknown（没有成功 response）

因此 smoke gate **FAIL**。按照预注册规则，本阶段在此停止，未启动 180-request full pilot，也没有补跑或 cosmetic rerun 任何失败请求。由于没有 provider-success rows，A/B/C 的 real runtime metrics、matched ABC comparison、necessity signal 和 hybrid signal 均为 **UNRESOLVED / 未形成**，不能用 offline probe 代替。

## Full Pilot

Full pilot 未执行：`scheduled=0`，原因是 15-request smoke 未达到至少 14 个 provider success 的 gate。

## A — LLM-only

公平性修正后的定义是：A 可以选择 catalog 外对象，只要一次结构化响应提供 domain 所需属性并通过 bounded validator，就可以 `runtime_executable=true`；catalog accidental match 仅为辅助指标，authoritative coverage 保持 0。真实 smoke 没有成功 A row，因此本阶段不能报告模型实际 A 指标。

## B — Catalog Top-K

B 只看到中性的 `available candidates`，并必须选择 Top-K canonical ID。属性来自 catalog authoritative record。真实 smoke 没有成功 B row，因此本阶段不能报告模型实际 B 指标。

## C — Hybrid

C 可以选择现有 candidate，或在没有合适 candidate 时一次性输出 `NEW:<name>` 与完整属性；NEW 必须 canonicalize、instantiate，并把模型字段标记为 estimated。真实 smoke 没有成功 C row，因此本阶段不能报告模型实际 C 指标。

## Matched Comparison

要求中的 matched comparison 是同一个 `scenario × repetition` 下 A/B/C 全部 provider success。实际 `matched_ABC=0`，所以没有因果式 A/B/C 差异可报告。

## Effect Coverage / Canonical / Authoritative Value / Cost

新的 runner 已记录 `structured_object_rate`、`runtime_executable_rate`、`usable_effect_coverage`、`authoritative_effect_coverage`、`model_estimated_field_rate`、candidate compliance、novel creation、input tokens、prompt chars、latency 和 backend model counts。由于本次 15 个请求全部 HTTP_ERROR，真实成功样本的这些字段均为 unavailable，而不是 0。

## Object Set Necessity Signal

`OBJECT_SET_NECESSITY_SIGNAL = UNRESOLVED`。这不是 Object Set 必要或不必要的结论，而是 provider smoke 没有产生可比较的成功样本。

## Hybrid Signal

`HYBRID_OPEN_WORLD_SIGNAL = UNRESOLVED`。C 没有成功 row，不能据此宣布 Hybrid 优于或接近 B。

## Limitations

- synthetic catalog，不是真实 10M catalog；
- 5 个 object domains、30 个固定 scenarios；
- 一个 reference provider；
- 真实 full pilot 未启动，重复数为 0；
- 这是 single-decision benchmark，不是长期连续行为测试；
- 暂未测试 20-step long-term identity consistency、inventory consistency、episode/game progress 或 duplicate replay；
- LLM self-reported attributes 不等于现实事实；
- 没有统计显著性结论；
- `HTTP_ERROR` 在当前 artifact 中只保留安全状态分类，未保存原始 provider error、Authorization、prompt 或 completion，因此本报告不对具体 HTTP 原因做未经证实的推断。

## Next Decision

本阶段停止。下一步只能在确认 provider contract / credential / endpoint 状态后，由用户明确授权重新启动一个新的 smoke experiment；不得把本次失败请求补跑进同一实验，也不得把 offline capability probe 当作 real A/B/C evidence。生产 RuleEngine、WorldState、ActionType、A2 reference profile 和 AgentSociety upstream 均未修改。

## Reproducibility and Safety

- Branch: `research/object-set-necessity`
- Baseline: `7370bb5c9546a22cd838ac911fed3118299da279`
- Smoke artifact: `run/evaluation/object_set_necessity/real_20260918T033858277073Z/result.json`
- Raw prompt stored: NO
- Raw completion stored: NO
- Hidden reasoning stored: NO
- Secrets stored: NO
