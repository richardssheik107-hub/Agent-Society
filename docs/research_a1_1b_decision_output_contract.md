# Research A1.1b

## Problem

The A1.1 fixed-prompt provider probe returned 30/30 successful responses (mean 6.29 s, p95 16.37 s, backend `glm-5.3`), but its only real B0 full-day attempt ended at 13:00: 28/72 ticks, 19 decisions and 19 provider requests, with decision 19 reported only as `INVALID_MODEL_OUTPUT`. No provider timeout was recorded. Its response text and parse subtype were deliberately not retained, so this phase cannot retroactively classify that particular output. A1.1b asks whether output-contract failures on fresh, Neutral-Day-like decisions are format-only and safely recoverable or genuinely semantic. It makes no claim about human-likeness or behavior quality.

## Failure Taxonomy

Failures are separated by the layer that can address them:

| Layer | Categories | Meaning |
| --- | --- | --- |
| Format | `CODE_FENCED_JSON`, `EXTRA_TEXT_AROUND_JSON`, `MULTIPLE_JSON_OBJECTS`, `MALFORMED_JSON` | The visible text is not one bare JSON decision object. Multiple complete objects and malformed JSON are observed but never guessed into a decision. |
| Semantic/schema | `MISSING_ACTION`, `INVALID_ACTION`, `MISSING_TARGET`, `INVALID_TARGET`, `EXTRA_FIELDS`, `WRONG_FIELD_TYPE` | The parsed object does not satisfy the two-field action contract or the offered action/target set. The sole exception is an omitted null target for an action that cannot take a target. |
| Provider/envelope | `EMPTY_CONTENT`, `PROVIDER_REFUSAL`, `TOOL_CALL_INSTEAD_OF_TEXT`, `NO_CHOICES`, `OUTPUT_BUDGET_EXHAUSTED`, `PROVIDER_SCHEMA_MISMATCH` | There is no usable assistant final text or the provider response envelope violates its contract. HTTP, timeout, and network errors remain separate provider failures. |
| Provider/transport | `TIMEOUT`, `HTTP_ERROR`, `NETWORK_ERROR`, `PROVIDER_ERROR` | No usable completion reached the parser. These never increase format or semantic-invalid counts. |

`failure_type` explains a strict failure even when a permitted repair makes the output usable; `recoverable_valid` determines whether a decision exists after repair. Accordingly, `semantic_invalid_count` counts **unrecoverable** semantic/schema failures, not safe `ADD_NULL_TARGET` cases.

## Strict Parser

Strict evaluation accepts one complete JSON object with exactly `action` and `target`. It rejects code fences, surrounding prose, multiple objects, duplicate/extra fields, wrong field types, unknown or currently unavailable actions, and invalid or unavailable targets. `MOVE`, `BUY`, and `EAT` require a nonempty listed target; `SLEEP`, `WORK`, and `LEISURE` require `target:null`. JSON whitespace is harmless, but no structural repair is used. The original production `DecisionParser.parse()` remains backward-compatible (it already accepted one code fence and an omitted target for targetless actions); the new strict measure is therefore deliberately distinct from historical production acceptance.

## Deterministic Recovery

`deterministic_recover()` computes strict and recoverable results from the same final-visible string. In addition to ordinary JSON whitespace, it permits only a single Markdown JSON fence (`STRIP_CODE_FENCE`), a single complete object inside a short prefix/suffix (`EXTRACT_SINGLE_JSON`), and an omitted `target` changed to null only for `SLEEP`, `WORK`, or `LEISURE` (`ADD_NULL_TARGET`). Repairs can compose; each component is checked against the allow-list. Two complete objects are always rejected. It does not repair malformed JSON, select one of several candidate objects, infer a natural-language action, correct spelling, map synonyms, or fuzzily match target IDs.

## Safety Boundary

The architecture remains one provider request per decision, with no LLM repair, application retry, ReAct, CodeGenRouter, or LLM use by the environment, rules, reducer, or judge. The old production parser entry point stays compatible. The new strict/recoverable evaluation is observational by default; acceptance of additional deterministic repairs is feature-flagged off until the stress gate is assessed. Response-envelope metadata is captured before parsing. Artifacts may hold at most 500 characters of redacted assistant *final visible* content for diagnosis, never hidden reasoning text, credentials, authorization headers, or raw prompts.

## Stress Cases

The fixed pilot uses eight prepared Neutral-Day states spanning 06:00 home through 22:30 home, including office hunger, restaurant with zero and one meal, and four feedback variants (`ACTION_REJECTED:NOT_AT_SELLER`, `WORK_COMPLETED`, `LEISURE_COMPLETED`, `ACTION_REJECTED:NOT_AT_WORKPLACE`). The existing NeutralPersona goal, six daily actions, local observation shape, `ContextCompiler`, and daily `PromptBuilder` produce the actual request prompts. No RuleEngine or world transition runs. Each case appears three times in a sequential, rotated 36-request schedule; there are no retries. The schedule and prompt hashes are saved, not prompt bodies.

## Stress Results

The offline fake-response smoke passed: 36 scripted requests, 33 strict-valid and 36 recoverable-valid, including separate provider/semantic/format classification probes. The full regression suite passed **414 tests** (three pre-existing SWIG deprecation warnings).

The **one real** stress attempt is recorded at `run/evaluation/decision_contract_stress/real_stress_20260917T032547500231Z/`. All 36 requests were sequential, with one attempt each. Provider success was **35/36 = 0.9722**; strict-valid and recoverable-valid were both **35/36 = 0.9722**. No provider-successful response failed the strict parser; the one invalid row was request 24, `TIMEOUT` at 60.06 seconds, not a parser failure. Semantic-invalid and format-failure counts were both **0/36**. `failure_type_counts={"TIMEOUT":1}` and `repair_applied_counts={}`. The format-failure metric counts any strict-format deviation, including a recoverable one, had one occurred. These rates use all 36 scheduled requests as denominator, so provider failures cannot inflate parser success. Conditional on the 35 provider-successful responses, strict validity was 35/35, but that conditional figure is not the gate denominator.

The engineering gate passed: provider success and recoverable validity each exceeded 0.95; semantic invalidity was below 0.05. Since strict and recoverable validity were equal and no repair occurred, deterministic recovery was **not enabled** for the sole full-day rerun. The gate is a small-pilot go/no-go decision, not a significance test.

## Provider Results

Across the 36 stress attempts, mean/p50/p95 latency was **9.90/7.21/21.46 seconds**, including the 60.06-second timeout. All 35 returned model labels were `glm-5.3`; the timed-out request has no returned backend label. Observed aggregate input/output/reasoning-token usage was **8,070/9,531/9,125** over those 35 returned responses; the timeout's usage is unknown, not zero. No hidden reasoning body was saved. The prior A1.1 tiny-prompt reliability probe had 30/30 success; the richer-context stress timeout shows why those two probes must not be conflated.

## Full-Day Rerun

The stress gate permitted **one** B0 real full-day attempt, at `run/evaluation/decision_contract_full_day/real_day_20260917T033259205366Z/`, with `ALLOW_DETERMINISTIC_OUTPUT_RECOVERY=False`. The attempt stopped at **06:15** on decision/request **2** with a **provider timeout** (`TIMEOUT`, `DAY_TRUNCATED_PROVIDER`), not a parser or output-contract rejection. The failed request waited **60.08 seconds**. No response envelope was available: returned backend, finish reason, content length, and input/output/reasoning-token usage are all unknown, not zero. The single preceding completed decision was strict-valid; there were **0 recovered outputs, 0 semantic-invalid outputs, and 0 output-failure records**. One of 72 ticks and 15 of 1,080 simulated minutes completed before truncation; `day_completed=false` and `behavior_metrics_valid=false`.

The full-day attempt was not repeated. **Research A1.1b status: incomplete — full-day provider timeout.** This phase demonstrates failure classification and the stress contract gate, but **does not demonstrate full-day runtime stability or establish a long-run output-contract rate**. The provider timeout is reported separately from `INVALID_MODEL_OUTPUT`; no full-day behavior conclusion is drawn.

## Limitations

This is a 36-request engineering pilot on one provider alias, not a statistically significant reliability estimate or a provider SLA. It does not test a local 8B model. At most one new real full-day rerun is allowed, and only after the stress gate passes. Recovery covers limited presentation deviations and the explicit omitted-null-target schema case only; it cannot infer intent, repair invalid target IDs, or establish whether the agent acts like a person. A truncated run has no valid full-day behavioral metrics.

## Next Step

Stop after reporting the output-contract gate and, if eligible, the sole full-day result. Any later prompt, constrained-decoding, corpus-size, or local-model study requires separate authorization.
