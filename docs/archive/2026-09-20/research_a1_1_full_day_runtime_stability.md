# Research A1.1

## Goal

Research A1.1 asks whether the current decision provider is reliable enough for a day-long run and, only if it is, whether the Neutral-Day runtime can reach 24:00. It does not test human realism, corpus benefit, or a local 8B model. The observation window remains 06:00–24:00, or 72 deterministic 15-minute ticks.

## Why Provider Reliability Is Separate

Research A1 observed three B0 day attempts, all truncated on their third provider request: 9 attempts, 6 completed responses, and only 12/216 planned ticks. Those data cannot establish full-day behavior. A provider timeout, HTTP error, empty content, or invalid provider envelope is an infrastructure/output-contract outcome, not an idle or behavioral outcome. A1.1 therefore probes `DecisionClient` alone, before any real world simulation.

## Completed vs Truncated Days

`DAY_COMPLETED` means the runner reached 24:00 with all 72 ticks. `DAY_TRUNCATED_PROVIDER`, `DAY_TRUNCATED_MODEL_OUTPUT`, and `DAY_TRUNCATED_ARCHITECTURE` identify early endings at different technical boundaries; behavioral safety caps remain separately identified. Every episode records `day_completed`, `observed_minutes`, `observed_ticks`, `truncation_reason`, `provider_failures`, and `behavior_metrics_valid`.

Only a completed day has valid full-day behavioral metrics. A truncated day retains its partial observed window, requests, completed decision steps, and failure metadata, but contributes nothing to full-day idle, activity-mix, need-resolution, or obligation-completion averages. In particular, a provider failure must stop the episode immediately; unobserved time until 24:00 is not imputed as idle.

## Provider Reliability Benchmark

The reliability benchmark makes 30 sequential calls to the same `OpenAICompatibleDecisionClient` configuration intended for a full-day run. Each request has one attempt, no retry, a fixed tiny JSON instruction unrelated to Alice or the world, and the verified `model + messages` body. It records latency even on timeout, but absent token usage stays unknown rather than zero. Raw prompts, final response text, hidden reasoning text, authorization, and secrets are not stored; the fixed prompt is identified by length and hash.

The report separates success, timeout, HTTP error, empty content, invalid JSON, and invalid action; it also records returned backend identity, finish reason, content length, and numeric usage when available. The engineering gate is `success_rate >= 0.95` and `timeout_rate <= 0.05`. This is a 30-request go/no-go gate for the next pilot, **not a provider SLA** or a statistically precise reliability estimate. If it fails, no real full-day attempt is permitted.

A secret-free `decision_client_config_hash` covers provider endpoint category, model alias, minimal request mode, timeout, and retry policy. Reliability and full-day artifacts must carry the same hash. The A1 timeout remains 60 seconds; this phase does not tune it upward to make a run pass.

## Decision Trigger Audit

Every model decision records a trigger reason: `NO_ACTIVE_ACTIVITY`, `ACTIVITY_COMPLETED`, `ACTION_REJECTED`, `OBLIGATION_BOUNDARY`, `CRITICAL_NEED`, or `WORLD_EVENT`, as applicable. Ordinary ticks during an active timed activity use zero model calls. The audit measures 30-minute decision bursts, repeated decisions from the same core-state bucket, decisions per simulated hour, ticks per decision, and active minutes per decision. More than 30 decisions/day is a frequency warning, distinct from the one-day real pilot's 30-decision safety cap.

The offline full-day scripted test checks trigger reasons, call spacing, activity start/completion, 15-minute time continuity, and deterministic need updates during no-call ticks. A fake timeout on decision 3 checks immediate truncation and verifies that only partial-window metrics survive.

## Full-Day Runtime

Only if the 30-request reliability gate and full offline suite pass, A1.1 permits **one** fresh real B0 day attempt. It uses the identical decision-client configuration and hash, no behavior hints, no retries, a 30-decision safety cap, and the existing five-identical-rejection behavior-loop stop. Reaching 24:00 is a runtime pass even if the chosen activities are unusual. A provider timeout is a truncated-provider result, not a behavioral verdict, and does not trigger another day.

The runtime report includes a compact decision trace (simulation time, trigger, action, activity duration, provider latency), compact tick timeline, continuity validation, attempted request count, decision bursts, and same-state repetitions. The existing trajectory retains only completed decision steps.

## Results

The provider reliability probe ran once under `run/evaluation/provider_reliability/real_30_20260917T023943612757Z/`. All **30/30 sequential requests succeeded**: success rate `1.000`, timeout rate `0.000`, and zero HTTP, empty-content, envelope, JSON, or action failures. Attempt latency mean/p50/p95/max was **6.29/5.11/16.37/26.34 seconds**. All 30 returned backend labels were `glm-5.3` (`MODEL_BACKEND_STABLE=YES` in this small sample). Observed aggregate input/output/reasoning-token counts were 870/4,444/4,114. The engineering gate was **RELIABILITY_OK**, so a single real full-day attempt became permissible; this is not evidence of a provider SLA or of reliable performance on longer Neutral-Day prompts. The secret-free decision-client configuration hash is `c86255d331a662835bee1710fb1bc0e5575bf4175a86f20e7e24f04556e892d3`.

The full offline suite passed **350 tests** (three pre-existing SWIG deprecation warnings). The scripted Neutral-Day smoke again reached 24:00 in 72 ticks with 19 scripted decisions, zero provider requests, zero measured idle, and trajectory validation PASS. A separate 30/30 fake-provider reliability smoke passed. These are harness checks, not real-model behavior.

The **one permitted real full-day attempt** is under `run/evaluation/neutral_day_stability/real_day_20260917T024453313356Z/`. It used the same secret-free client configuration hash as the reliability probe and stopped at **13:00** with `INVALID_MODEL_OUTPUT` / `DAY_TRUNCATED_MODEL_OUTPUT`. Thus `day_completed=false` and `behavior_metrics_valid=false`: **28/72 ticks** and **420/1,080 simulated minutes** were observed, with **19 decision attempts and 19 provider requests**. There was no provider timeout or HTTP failure recorded in this attempt; the failed decision produced no completed trajectory step. The raw output was intentionally not retained, so its precise parse-error subtype and failed-attempt latency cannot be reconstructed from the artifact; the compact trace covers the preceding 18 completed decisions. The day was not rerun.

The compact trigger audit records **14 decision bursts** (overlapping windows of at least three decisions within 30 simulated minutes) and **3 same-state repeated decisions**. Reasons for the 19 attempted calls were `NO_ACTIVE_ACTIVITY` 11, `ACTIVITY_COMPLETED` 2, `ACTION_REJECTED` 5, and `OBLIGATION_BOUNDARY` 1; critical need and world-event interruptions were 0. The **partial observed window only** contains 60 idle minutes (partial ratio `60/420 = 0.143`) and accepted actions MOVE 6, BUY 3, EAT 2, WORK 2, SLEEP 0, LEISURE 0. These are not full-day activity-mix, need-resolution, obligation, or idle results. The runtime report sets `full_day_behavior_metrics=null`.

**A1.1 outcome: incomplete — full-day runtime truncated by model output.** The 30-request fixed-prompt provider gate passed, but that does not establish the richer Neutral-Day output contract across a complete day. The independent classifications prevent a model-output failure from being counted as provider instability or as a behavioral full-day observation.

## Behavioral Metrics Validity

`behavior_metrics_valid` is true exactly when `day_completed` is true. Only then may the report expose formal full-day idle, activity diversity, repeated invalid actions, unresolved need, sleep/work/leisure minutes, and meal count. Partial idle minutes and ratio are explicitly labeled partial; they are never mixed into a completed-day aggregate.

## Limitations

The provider probe has only 30 sequential requests and no retry; it is an engineering screen, not an SLA estimate. A1.1 allows only one real full-day attempt. The current provider alias is not a verified local 8B backend. No real behavior corpus or behavior support is used. Need dynamics, action durations, and idle thresholds remain uncalibrated. **No claim of human realism.**

## Next Step

The observed next technical question is why the nineteenth Neutral-Day response violated the two-field decision contract. A future, separately authorized diagnostic can record only a safe parse category and envelope metadata—never the response or hidden reasoning text—before deciding whether to change prompting or backend. The current one-day attempt is not rerun, and its partial behavior must not be used for corpus-size analysis. Corpus-size study, ATUS acquisition, local-8B experiments, and Research B are outside this phase.
