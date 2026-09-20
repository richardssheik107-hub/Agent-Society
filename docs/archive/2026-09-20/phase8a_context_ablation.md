# Phase 8A — Context Ablation

## Research Question

Under a small-model, short-context constraint, how much event history does the existing closed-loop lunch agent need to make stable decisions? Phase 8A varies **only the Context Policy** that selects compact event feedback. It compares current state alone, the last event, the last three events, and a deterministic rejection-prioritizing selection. This is a descriptive pilot, not a claim that one policy is universally better.

Two comparisons are especially diagnostic: S1 compares C0 with C1 when the latest event is a failed `BUY meal`; S2 compares C3 with CR when that rejection has been buried beneath four accepted moves. S3 compares C0 with C3 when history contains only movement noise. S0 checks that the ablation does not break the original lunch task.

## Frozen Baseline

The Phase 7 Git baseline is commit `1cfda31efc2035fa5015db6d2e549982babbcafe` on `main` (`Add Phase 7 evaluation harness and trajectory dataset`). Before implementation, we verified that this commit was an ancestor of local HEAD and inspected local and remote status without resetting, cleaning, or discarding work. The Phase 7 historical results were 234 passing tests, 20/20 scripted lunch episodes, and 3/3 real-provider pilot episodes following `MOVE>BUY>EAT` in nine requests. Those are **not** Phase 8A outcomes.

The executable action set remains `MOVE`, `BUY`, `EAT`. The decision path uses one compact `ContextCompiler`, one decision call and at most one provider request per decision, then deterministic rule execution, state reduction, and event generation. Environment, rules, reducer, events, and evaluation judge make zero LLM calls. No ReAct, CodeGenRouter, PersonAgent, additional action/rule, multi-agent coordination, embedding memory, retrieval, or training is introduced. The model receives only a local observation and bounded compact context—not the complete `WorldState` or `RuleSet`.

## Experimental Controls

Each of the 16 policy × scenario cells uses the same fresh-world constructor, Alice, goal (`reduce hunger by obtaining and eating a meal`), available actions (`MOVE`, `BUY`, `EAT`), targets (`home`, `park`, `restaurant`, `meal`), maximum of five formal decisions, deterministic executor/rules/reducer, context character budget, prompt scaffold, `DecisionClient`, provider alias, and minimal Chat Completions request body: `model` plus `messages` only. No `thinking`, `temperature`, `max_tokens`, `tools`, `response_format`, or `reasoning_effort` field is added. No prompt engineering occurs after the real experiment begins.

The serialized compact context retains the same fields and ordering for every policy. In particular, the event key is always present: C0 uses `"e":[]`. Only the **contents of `e`** change. The compiler—not the policy—owns serialization, field limits, and the hard budget. Compact events remain strings such as `MOVED:restaurant`, `PURCHASED:meal`, `ATE:meal`, and `ACTION_REJECTED:NOT_AT_SELLER`; no timestamp, event ID, full effect, or world snapshot is shown as event feedback. C3 must exactly match the Phase 7 recent-three behavior for nonempty history.

The real pilot uses `ark-code-latest` on the Coding Plan Chat Completions endpoint. It is an alias: each completed step records the **actual** returned provider model. If the actual backend changes, results are separated by backend rather than interpreted as a pooled policy comparison. The schedule is deterministic and interleaved across policies and scenarios, not 8 consecutive episodes of one policy. Its exact execution order is persisted in `experiment_config.json` before requests are made.

## Context Policies

| Policy | Model-visible event selection | Maximum |
| --- | --- | ---: |
| `C0_state` | No history (`e:[]`) | 0 |
| `C1_last` | Most recent event | 1 |
| `C3_recent3` | Three most recent events, original order; Phase 7 baseline behavior | 3 |
| `CR_relevant` | Select newest `ACTION_REJECTED` events first, then newest accepted state-changing events; present selected events in original order | 3 |

Selection is pure Python and deterministic. CR uses neither an LLM nor embedding/vector retrieval. All policies see the same current observation, goal, allowed actions, and targets; event selection cannot mutate the world or event log.

## Scenario Variants

All scenario preludes use **existing** `BUY` and `MOVE` semantics. A prelude is deterministic setup before the first model decision, not a model-generated trajectory step.

| Variant | Prelude actions | Prelude event history | Actions / rejections |
| --- | --- | --- | ---: |
| `S0_BASELINE` | none | `[]` | 0 / 0 |
| `S1_LAST_REJECTION` | `BUY meal` at home | `ACTION_REJECTED:NOT_AT_SELLER` | 1 / 1 |
| `S2_BURIED_REJECTION` | `BUY meal` at home; `MOVE park`; `MOVE home`; `MOVE park`; `MOVE home` | rejection followed by four `MOVED` events | 5 / 1 |
| `S3_NOISE_ONLY` | `MOVE park`; `MOVE home`; `MOVE park`; `MOVE home` | four `MOVED` events; no rejection | 4 / 0 |

In S2, C1 sees only `MOVED:home`, C3 sees only the last three moves, and CR retains `ACTION_REJECTED:NOT_AT_SELLER`. S3 asks whether irrelevant history increases input cost without a visible behavioral benefit. The scenarios add no obstacle, hidden rule, random event, new item, or new action.

## Why model-start state is identical

The formal model episode starts in the **same objective `WorldState`** for S0–S3: Alice is at `home`, money `100.0`, hunger `0.8`, inventory `{}`; the restaurant offers `meal` at price `20` with stock `10`. S1's rejected purchase does not change state. S2 and S3 use park/home round trips, returning Alice to home without changing money, hunger, inventory, or restaurant stock. The prelude must assert structured equality of the entire model-start snapshot with the fresh baseline, not merely compare a few fields.

Therefore the scenario manipulation is *event history*, not the objective state. This controls an important confound but does not make the pilot a general test of memory in other tasks. The first formal `StepTrajectory.state_before` must equal that scenario's `model_start_state`.

## Prelude Design

Each episode gets a fresh `WorldState` and `EventLog`. The deterministic executor runs the prelude, appends its compact events to that episode's log, checks the final state against the baseline, then starts formal model decisions. Prelude actions consume **zero** provider requests and are excluded from `decision_count`, model rejection rate, and `StepTrajectory`. Formal trajectories begin at the first model decision and continue to use Phase 7 `validate_trajectory()` continuity checks.

Episode metadata separately records `scenario_variant`, `prelude_events`, `prelude_action_count`, `prelude_rejection_count`, `prelude_rejection_present`, `model_start_state`, and `experiment_config_hash`. A prelude rejection is never counted as a model policy rejection. The compact event log is allowed to inform the first model decision according to the selected policy.

## Metrics

Report both overall **by policy** and all 16 **policy × scenario** cells; overall averages alone can hide S1/S2 behavior. The inherited Phase 7 measures include episode success/completion, decisions, accepted/rejected formal actions, invalid output, provider error, context/prompt characters, available input/output/reasoning token usage, latency, provider requests, and trajectory signatures such as `MOVE>BUY>EAT` or `BUY!NOT_AT_SELLER>MOVE>BUY>EAT`.

Phase 8A adds these definitions:

- `first_decision_action` and `first_decision_target`: the first **completed formal** step's parsed proposal; absent if no step completed.
- `first_decision_repeats_prelude_rejection`: for S1/S2, true exactly when the first formal proposal is `BUY meal` again. `recovery_after_rejection` is its inverse for episodes with an observed first formal step; it means only “did not immediately repeat that proposal,” **not** task correctness. First-repeat rates use eligible S1/S2 episodes with a completed first step as denominator; pre-step provider failures are unknown, not non-repeats.
- `same_rejected_action_repeat_count`: a formal rejected proposal repeats an earlier rejected action, target, and reason code while the world remains unchanged. Intervening rejected actions do not reset this history, but an accepted state-changing action does. Prelude actions are excluded.
- `rejection_rate`: formal rejected actions divided by formal accepted plus rejected actions. A S1/S2 setup rejection contributes only to `prelude_rejection_count`.
- `context_cost_chars` and `input_token_cost`: sums across completed formal steps with reported values. `success_per_1k_input_tokens = episodes_success / (total_input_tokens / 1000)` when that denominator is positive; it is descriptive, not a ranking score. Missing provider token usage remains missing rather than being inferred as zero.

For each policy, report context-character mean/median/max; prompt-character mean/max; per-completed-step mean input/output/reasoning tokens; and latency mean/p50/p95. A p95 computed from a small pilot is descriptive only. Provider errors and timeouts remain episode failure categories, separate from valid rejected actions and invalid model output. Provider backend counts reflect actual response models, not merely the requested alias.

## Offline Validation

**Gate before any Phase 8A real request:** run all policy and scenario unit tests, context isolation, C3 regression, four-policy budget checks, model-start state equality, prelude side-effect audit, trajectory validation, and the full offline suite. A fixed `ScriptedDecisionClient` then runs 4 policies × 4 scenarios × 2 repeats = **32 fresh offline episodes**. It always proposes `MOVE restaurant`, `BUY meal`, `EAT meal`, regardless of policy. Expected result: 32/32 reach the goal. This checks wiring and metric attribution; it does **not** estimate a context-policy effect.

The offline smoke should emit `CONTEXT_ABLATION_OFFLINE_OK`, `POLICIES=4`, `SCENARIOS=4`, `EPISODES=32`, `SUCCESS=32`, `MODEL_START_STATE_EQUAL=YES`, and `CONTEXT_BUDGET_PASS=YES`. Phase 7's 234 passing tests are the historical baseline, not the Phase 8A test count.

**Validation status: PASS.** The final offline suite passed **277 tests**. The fixed scripted smoke completed **32/32** episodes, with `CONTEXT_ABLATION_OFFLINE_OK`, `POLICIES=4`, `SCENARIOS=4`, `EPISODES=32`, `SUCCESS=32`, `MODEL_START_STATE_EQUAL=YES`, and `CONTEXT_BUDGET_PASS=YES`. Formal trajectories passed continuity validation; prelude actions remained outside model steps and provider-request counts. This is a wiring check, not evidence that any context policy improves behavior.

## Real Pilot

After all offline gates pass, run the real provider ablation **once**: 4 policies × 4 scenarios × 2 repetitions = **32 episodes**, with at most five formal decisions per episode and an absolute ceiling of **160 provider requests**. An episode stops immediately on goal completion; if all follow the three-action baseline, approximately 96 requests would be needed. There is no application retry: an HTTP or parse failure ends that episode and ordinarily moves to the next. A poor policy outcome is data, not grounds to stop or rerun a cell.

The interleaved schedule is fixed before execution and stored in `experiment_config.json`; provider prompt order must not be randomized. Persist a SHA-256 `experiment_config_hash` over canonicalized scenario configuration, policy configuration, prompt template, and minimal request mode before the first request, and copy that hash into every episode's metadata. A changed prompt/config after launch requires a **new** experiment ID; do not mix episodes across configurations or rerun failed cells to improve results. Artifacts live under ignored `run/evaluation/context_ablation/<experiment_id>/`, including `experiment_config.json`, `episodes/`, `trajectories.jsonl`, `policy_metrics.json`, `policy_scenario_metrics.json`, `ablation_summary.md`, `ablation_summary.csv`, and `dataset_manifest.json`. The manifest records schema version, experiment type, policies/scenarios, two repeats per cell, requested alias, actual models, and `contains_hidden_reasoning=false`, `contains_raw_prompt=false`.

Only an architecture invariant failure, detected secret leak, or **three consecutive infrastructure-level provider failures** aborts the entire real pilot. Ordinary episode-level provider failure is recorded and followed by the next episode. If provider instability makes the data uninterpretable, report `PHASE 8A INCOMPLETE — PROVIDER INSTABILITY`, not a policy conclusion. The real run records `prompt_chars` and numeric reasoning-token usage but never the full prompt, hidden reasoning text, API key, authorization header, or `.env` content. A post-run scan of the artifact directory must verify that privacy boundary; upstream `third_party/AgentSociety` must remain clean.

**Pilot status: COMPLETE, run once.** The frozen run is `phase8a_context_ablation_20260916T140829676446Z`, under `run/evaluation/context_ablation/phase8a_context_ablation_20260916T140829676446Z/`. Its configuration hash is `ad2484d5b4d4a9a3b2056a22965bc56e24c8a306876f34b4b775a153638f8c6f`. All **32** scheduled episodes ran, with **31/32** completing the lunch goal, **94** completed formal steps, and **95** total provider requests (below the 160 ceiling). The extra request is a first-decision `TIMEOUT` in one `C0_state × S0_BASELINE` episode, with no completed step or returned model identity. It is an infrastructure failure, **not** an observed C0 behavioral or policy failure; the failed cell was not rerun. No three-consecutive-failure abort occurred.

The saved dataset contains 32 episode files and 94 trajectory JSONL records; each of the 16 cells has two episodes. The final checks passed model-start-state equality, trajectory continuity, configuration-hash consistency, request-count reconciliation, and the artifact secret/raw-prompt/hidden-reasoning scan. The manifest records `contains_hidden_reasoning=false` and `contains_raw_prompt=false`. The upstream AgentSociety checkout remained unchanged.

## Policy Metrics

Measured values below come from the one-time pilot's `policy_metrics.json`. Each policy has eight scheduled episodes. Context, token, and latency means are per **completed formal step**, so the unattributed timeout contributes to C0's episode/request counts but not to its completed-step cost averages. No composite winner score is used.

`Avg Decisions` counts attempted model decisions, including the request that timed out. Thus C0/S0's 2.00 is the mean of one timed-out first attempt and one successful three-decision episode, not a completed two-step trajectory.

| Policy | Episodes | Success | Completion | Avg Decisions | Rejection Rate | First-Rejection Repeat Rate | Avg Context Chars | Avg Input Tokens | Avg Latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C0_state | 8 | 7 | 0.875 | 2.875 | 0.045 | 1/4 (0.250) | 272.09 | 169.45 | 5.91 s |
| C1_last | 8 | 8 | 1.000 | 3.000 | 0 | 0/4 | 289.58 | 173.92 | 4.89 s |
| C3_recent3 | 8 | 8 | 1.000 | 3.000 | 0 | 0/4 | 312.08 | 180.25 | 5.14 s |
| CR_relevant | 8 | 8 | 1.000 | 3.000 | 0 | 0/4 | 316.83 | 181.75 | 4.49 s |

The rejection-rate denominator is completed formal actions: C0 has one rejected `BUY meal` among 22 completed actions; all other policies have zero formal rejections. Each policy also has four **setup** rejections from S1/S2, excluded from that rate. C0's completion rate includes the infrastructure timeout; among C0 episodes with a completed provider response, 7/7 reached the goal. Per-policy distributions and costs are:

| Policy | Context mean / median / max chars | Prompt mean / max chars | Input / output / reasoning tokens per completed step | Latency mean / p50 / p95 (s) |
| --- | --- | --- | --- | --- |
| C0_state | 272.09 / 283 / 299 | 559.09 / 586 | 169.45 / 185.27 / 173.95 | 5.91 / 4.76 / 10.68 |
| C1_last | 289.58 / 301 / 315 | 576.58 / 602 | 173.92 / 192.63 / 180.79 | 4.89 / 4.15 / 10.37 |
| C3_recent3 | 312.08 / 327 / 366 | 599.08 / 653 | 180.25 / 179.08 / 167.75 | 5.14 / 4.08 / 11.35 |
| CR_relevant | 316.83 / 330 / 366 | 603.83 / 653 | 181.75 / 164.29 / 152.58 | 4.49 / 4.01 / 7.03 |

| Policy | Invalid outputs | Provider errors | Timeouts | Same-rejected-action repeats | Observed context chars | Observed input tokens | Success / 1k observed input tokens | Trajectory signatures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C0_state | 0/8 | 0/8 | 1/8 | 0 | 5,986 | 3,728 | 1.878 | `MOVE>BUY>EAT` ×6; `BUY!NOT_AT_SELLER>MOVE>BUY>EAT` ×1; `!TIMEOUT` ×1 |
| C1_last | 0/8 | 0/8 | 0/8 | 0 | 6,950 | 4,174 | 1.917 | `MOVE>BUY>EAT` ×8 |
| C3_recent3 | 0/8 | 0/8 | 0/8 | 0 | 7,490 | 4,326 | 1.849 | `MOVE>BUY>EAT` ×8 |
| CR_relevant | 0/8 | 0/8 | 0/8 | 0 | 7,604 | 4,362 | 1.834 | `MOVE>BUY>EAT` ×8 |

The provider-error column excludes `TIMEOUT`, which is shown separately. C0 made 23 requests (22 completed responses plus one timeout); each other policy made 24. The displayed context and token totals include only completed steps, not the timed-out request, whose actual token usage is unavailable. The token-efficiency ratio uses observed input tokens only; C0's numerator includes the failed episode while its all-request denominator is unknown, so it must not be used to rank policies. The output/reasoning-token and latency differences cannot be attributed solely to event selection in this small run.

## Policy × Scenario Metrics

Every row below is measured from `policy_scenario_metrics.json`; all 16 cells ran the planned two episodes. The input-token average is per completed formal step, not per episode. Rejections mean **formal model** rejections; setup rejection counts are separate. `N/A` means there was no setup rejection to repeat, not a zero recovery effect.

| Scenario | Policy | Episodes | Completion | First Repeat Rate | Model Rejections | Avg Decisions | Avg Input Tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| S0_BASELINE | C0_state | 2 | 1/2 | N/A | 0 | 2.00 | 170.00 |
| S0_BASELINE | C1_last | 2 | 2/2 | N/A | 0 | 3.00 | 172.67 |
| S0_BASELINE | C3_recent3 | 2 | 2/2 | N/A | 0 | 3.00 | 174.00 |
| S0_BASELINE | CR_relevant | 2 | 2/2 | N/A | 0 | 3.00 | 174.00 |
| S1_LAST_REJECTION | C0_state | 2 | 2/2 | 1/2 | 1 | 3.50 | 168.29 |
| S1_LAST_REJECTION | C1_last | 2 | 2/2 | 0/2 | 0 | 3.00 | 175.67 |
| S1_LAST_REJECTION | C3_recent3 | 2 | 2/2 | 0/2 | 0 | 3.00 | 183.67 |
| S1_LAST_REJECTION | CR_relevant | 2 | 2/2 | 0/2 | 0 | 3.00 | 183.67 |
| S2_BURIED_REJECTION | C0_state | 2 | 2/2 | 0/2 | 0 | 3.00 | 170.00 |
| S2_BURIED_REJECTION | C1_last | 2 | 2/2 | 0/2 | 0 | 3.00 | 173.67 |
| S2_BURIED_REJECTION | C3_recent3 | 2 | 2/2 | 0/2 | 0 | 3.00 | 181.67 |
| S2_BURIED_REJECTION | CR_relevant | 2 | 2/2 | 0/2 | 0 | 3.00 | 187.67 |
| S3_NOISE_ONLY | C0_state | 2 | 2/2 | N/A | 0 | 3.00 | 170.00 |
| S3_NOISE_ONLY | C1_last | 2 | 2/2 | N/A | 0 | 3.00 | 173.67 |
| S3_NOISE_ONLY | C3_recent3 | 2 | 2/2 | N/A | 0 | 3.00 | 181.67 |
| S3_NOISE_ONLY | CR_relevant | 2 | 2/2 | N/A | 0 | 3.00 | 181.67 |

The prespecified contrasts show a narrow signal, not a policy ranking:

- **S1, C0 versus C1:** both completed 2/2, but C0 immediately repeated `BUY meal` in 1/2 and incurred one formal `NOT_AT_SELLER` rejection; C1 repeated it in 0/2. Mean input tokens were 168.29 versus 175.67 per completed step. This is directionally consistent with the latest rejection being useful, but one differing episode cannot establish a reliable effect.
- **S2, C3 versus CR:** both completed 2/2, with 0/2 first repeats and no formal rejections, despite only CR retaining the buried rejection. CR cost 187.67 versus C3's 181.67 input tokens per completed step (mean context 336 versus 317 chars). The additional retained feedback yielded no observed behavioral gain in this cell.
- **S3, C0 versus C3:** both completed 2/2 in three decisions and had no formal rejections. The move-only history raised C3's mean input from 170.00 to 181.67 tokens per step (mean context 317 versus 273.67 chars) without a visible behavior difference. First-repeat is inapplicable because neither prelude contains a rejection.

The sole non-completion was C0/S0's first-request timeout. It cannot be interpreted as evidence against state-only context. Across the 31 episodes with completed responses, 30 followed `MOVE>BUY>EAT`; one C0/S1 episode followed `BUY!NOT_AT_SELLER>MOVE>BUY>EAT` and still completed.

## Provider Model Stability

The requested `ark-code-latest` alias does not guarantee an unchanging backend. Count actual `provider_model` values across completed requests and report `MODEL_BACKEND_STABLE=YES` only if a single actual backend is observed; if multiple appear, report `MODEL_BACKEND_CHANGED_DURING_EXPERIMENT`, `MODEL_BACKEND_STABLE=NO`, and model-stratified metrics. Failed requests without a response-model field remain unattributed, not silently assigned to a backend. Do not pool cross-backend results into a causal context-policy interpretation.

**Observed actual provider models:** `glm-5.3` on all **94 completed requests**. Thus `MODEL_BACKEND_STABLE=YES` for requests that returned a model field. One first-request timeout returned no model field and remains **unattributed**; the experiment cannot establish what backend, if any, handled that attempt. The requested alias was `ark-code-latest` throughout. There is no observed cross-backend mixture to stratify, but the unobserved request is not assigned to `glm-5.3` by assumption.

## Limitations

- Only **two repetitions per policy × scenario cell**: any separation is directional and descriptive, not statistically significant.
- One deterministic lunch scenario family and one provider alias; outcomes do not establish general memory value or transfer to other tasks.
- Observed responses all named one backend, but one timed-out request had no returned model identity. Backend stability therefore describes 94 observed responses, not the unknown request or future alias routing.
- Provider reasoning behavior, output tokens, and latency may vary independently of input context; prompt-cost differences are easier to interpret than reasoning-token differences.
- These results do **not** represent local 8B performance. No local 8B model, embedding memory, multi-agent behavior, or training is tested here.
- Completion alone weakly separates policies here because all 31 completed-response episodes succeeded, while one unrelated timeout lowered C0's raw completion. The S1 first-step 1/2 versus 0/2 contrast is a directional behavioral difference, so an unqualified `NO_CLEAR_POLICY_SEPARATION_OBSERVED` would conceal it. Conversely, S2 and S3 showed no behavioral separation. Do **not** conclude that event history is useless; the scenario may be weakly discriminating, and two repeats per cell are insufficient for a robust estimate.

## Next Step

The one-time pilot, raw tables, backend audit, privacy check, trajectory validation, offline gates, and independent reader check are complete. The reader check clarified attempted-decision and observed-token denominators; it found no mismatches in the reported episode, step, request, success, rejection, or backend counts. Stop at Phase 8A; only after reviewing these results should the next phase be chosen among a larger Phase 8A.1 sample, a local 8B benchmark, or memory selection. Do not silently expand scope, commit, or push as part of this phase.
