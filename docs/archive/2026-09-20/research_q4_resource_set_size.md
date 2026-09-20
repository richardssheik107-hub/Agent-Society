# Research Q4 — Resource Set Size

## Research Question

When objective world truth is identical, how does changing only the visible personal Resource Set affect one-step behavior alignment, deterministic rule executability, held-out human-diary support, critical misses, and context cost?

This phase tests only the four preregistered nested conditions:

`C8 = R8`, `C16 = R16`, `C32 = R32`, and `C64 = R64`.

It does not retest Q3's object arms, start Q5 scaling, start local 8B, or run full-day continuity.

## Definition of Resource

A Resource is a personal state variable that can persist and affect a later action choice. Resource values are normalized to `[0,1]`: zero means low need/pressure (or exhausted energy), one means high need/pressure (or high energy).

The fixed schema contains exactly 64 fields. R8, R16, R32, and R64 are projections of the same immutable `ResourceTruth64`; no arm-specific value mutation is allowed.

World facts such as meal, restaurant, office, targets, object availability, and the catalog are not Resources. They remain in every condition.

## What Is Held Constant

Across all four levels, the following are identical:

* persona, time, location, objective world facts, object availability and Catalog + Top-K architecture;
* available actions and targets;
* previous activity, recent events, and the R1 behavior-prior query;
* the full 64-field truth, scenario seed, deterministic RuleEngine, and scorer;
* provider, request contract, temperature, retry policy, and prompt text outside the resource block.

Only the visible `r` block changes. The artifact records both `truth_values` and `visible_resources`, plus a truth hash and fixed-context hash for auditability. Acceptable actions, critical resources, scenario family, and expected labels never enter the prompt.

Q3 remains historical and unchanged: Object architecture is fixed at Catalog + Top-K.

## R8

The eight coarse resources are:

`hunger`, `energy`, `sleep_pressure`, `work_urgency`, `hygiene_need`, `chores_backlog`, `leisure_need`, and `budget_pressure`.

## R16

R16 includes all R8 fields plus:

`stress`, `social_need`, `commute_pressure`, `discretionary_budget_remaining`, `work_progress`, `meal_recency`, `personal_care_recency`, and `chores_recency`.

## R32

R32 includes all R16 fields plus:

`physical_fatigue`, `mental_fatigue`, `sleep_debt`, `sleep_quality`, `hunger_trend`, `food_security`, `cash_on_hand`, `checking_balance`, `credit_available`, `debt_pressure`, `work_minutes_today`, `work_deadline_pressure`, `commute_minutes_pressure`, `household_load`, `leisure_minutes_today`, and `recent_spending_ratio`.

## R64

R64 includes all R32 fields plus:

`hydration_need`, `caffeine_level`, `physical_discomfort`, `temperature_discomfort`, `sickness_signal`, `exercise_fatigue`, `work_stress`, `financial_stress`, `social_stress`, `social_contact_recency`, `friend_availability`, `family_contact_recency`, `loneliness`, `shower_due`, `dental_care_due`, `clothing_cleanliness_need`, `laundry_load`, `dish_load`, `trash_load`, `kitchen_cleaning_need`, `bedroom_cleaning_need`, `cooking_prep_need`, `grocery_stock_pressure`, `appointment_urgency`, `transport_availability`, `mobility_friction`, `cash_reserve_pressure`, `savings_health`, `credit_pressure`, `currency_liquidity`, `entertainment_novelty_need`, and `routine_disruption`.

## Scenario Design

The frozen manifest contains 24 deterministic fixed-state decisions: three each for physiology, work, personal care, chores, leisure, finance, mobility, and food/consumption. Each has objective world facts, a full ResourceTruth64, previous activity, recent events, the BTRAIN_ALL/R1 prior query, an acceptable action set, and critical resource fields.

Scenarios avoid a single subjective answer and avoid stacking several extreme pressures. Acceptable sets are deterministic adequacy contracts used only by the scorer; they are never shown to the provider.

The schedule is counterbalanced by deterministic Latin-style rotations. Each scenario × repetition × level cell is requested once.

## Offline Validation

The no-network capability probe passed:

* marker: `RESOURCE_SET_OFFLINE_OK`;
* note: `SYSTEM_CAPABILITY_PROBE_NOT_MODEL_BEHAVIOR`;
* 24 scenarios × 4 levels × 2 repetitions = 192 rows;
* nested projections, immutable truth, prompt isolation, deterministic scorer, and 192-cell schedule all passed.

The offline output is not behavior evidence.

## Real Smoke

Artifact: `run/evaluation/resource_set_size/real_q4_attempt_1_smoke_20260918T081701224684Z/`.

The smoke used four different families (hunger, work, personal care, chores), one repetition, and 16 requests.

```text
scheduled=16
success=16
timeout=0
http_error=0
parse_error=0
architecture_error=0
backend_model_counts={glm-5.3: 16}
smoke_gate=PASS
```

All successful rows were strict-parse valid and had valid resource projections. Smoke metrics are pipeline/provider evidence only and are not used to select a Resource level.

## Full Provider Run

Artifact: `run/evaluation/resource_set_size/real_q4_attempt_1_full_20260918T081859853289Z/`.

The full schedule was 24 scenarios × 4 levels × 2 repetitions = 192 requests.

```text
scheduled=192
success=174
timeout=18
http_error=0
parse_error=0
architecture_error=0
backend_model_counts={glm-5.3: 174}
matched_quadruples=33/48
```

All 174 successful envelopes were strict-parse valid. No retry, repair, cosmetic rerun, or automatic resume occurred.

The artifact's recorded source base was `20f5f0c0e6f1aa830075981dc87f9852d356460d`; the final Git commit containing the Q4 implementation and this report is listed in the handoff after verification.

## Provider Reliability

HTTP status counts for successful responses were `200:174`. HTTP error and error-code maps were empty. The remaining 18 rows were timeouts; they have no invented backend attribution. No raw prompt, raw completion, hidden reasoning, Authorization header, or API key is stored.

The successful backend model reported by the provider was `glm-5.3` for all 174 successful rows. The requested alias remains the existing secure A2 configuration; no credential is reproduced here.

## Matched Quadruple Analysis

A matched quadruple is one scenario × repetition for which R8, R16, R32, and R64 all succeeded. The full run yielded 33 matched quadruples, above the preregistered minimum evidence threshold of 30. All primary comparisons below use only these 33 matched quadruples; the per-level table is descriptive over all successful rows.

| Resource level | Alignment | Rule executable | Critical miss | Held-out share | Held-out top-3 | Mean input tokens | Median input tokens | Mean prompt chars | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R8 | 0.696970 | 0.969697 | 0.303030 | 0.338023 | 0.848485 | 281.121212 | 282.0 | 982.060606 | 9.924361 |
| R16 | 0.727273 | 0.969697 | 0.272727 | 0.332873 | 0.848485 | 346.121212 | 347.0 | 1161.151515 | 9.609734 |
| R32 | 0.727273 | 0.939394 | 0.272727 | 0.320336 | 0.812500 | 477.121212 | 478.0 | 1528.424242 | 12.258748 |
| R64 | 0.848485 | 1.000000 | 0.151515 | 0.277661 | 0.750000 | 747.121212 | 748.0 | 2297.696970 | 6.465834 |

The descriptive all-success counts were R8=46, R16=43, R32=39, and R64=46.

## Behavioral Alignment

`resource_alignment` is one when the proposal belongs to the scenario's acceptable action set. It is a deterministic adequacy metric for this benchmark, not a human-truth label.

On matched quadruples, R8=0.696970, R16=0.727273, R32=0.727273, and R64=0.848485. R8 is visibly weaker; R16 improves by 0.030303; R32 does not improve over R16; R64 is the best observed alignment level.

## Rule Executability

Rule executability is evaluated by the existing deterministic RuleEngine with the current experimental action profile. The production RuleEngine semantics were not changed.

Matched executable rates were R8=0.969697, R16=0.969697, R32=0.939394, and R64=1.000000. This does not justify replacing the RuleEngine with a Resource-dependent rule.

## Human Diary Support

The held-out scorer is built only from the independent 643-day EVAL pool. The 2,572 TRAIN diaries enter the fixed BTRAIN_ALL/R1 prior; EVAL never enters context.

Matched held-out action share was R8=0.338023, R16=0.332873, R32=0.320336, and R64=0.277661. Held-out top-3 rates were R8/R16=0.848485, R32=0.812500, and R64=0.750000. An action outside the Core7 diary vocabulary is recorded as not-supported/NA rather than remapped.

## Critical Miss

A critical miss is one proposal outside the scenario's acceptable action set. On matched quadruples the rates were R8=0.303030, R16=0.272727, R32=0.272727, and R64=0.151515. R64 is lowest, but the decrease is paired with a large context expansion and does not by itself establish a minimum tested set.

## Context Cost

Prompt size rose monotonically with visibility:

* R8: 281.121 input tokens, 982.061 prompt characters;
* R16: 346.121 input tokens, 1,161.152 prompt characters;
* R32: 477.121 input tokens, 1,528.424 prompt characters;
* R64: 747.121 input tokens, 2,297.697 prompt characters.

Relative input-token increases were +23.1217% (R8→R16), +37.8480% (R16→R32), and +56.5894% (R32→R64). Latency is provider-noisy: +27.5659% for R16→R32, while the other observed changes were negative.

## Marginal Returns

| Expansion | Δ alignment | Δ rule | Δ held-out share | Δ critical miss | Δ input tokens | Δ latency | Signal |
|---|---:|---:|---:|---:|---:|---:|---|
| R8 → R16 | +0.030303 | 0.000000 | -0.005150 | -0.030303 | +23.1217% | -3.1702% | NONE |
| R16 → R32 | 0.000000 | -0.030303 | -0.012537 | 0.000000 | +37.8480% | +27.5659% | LOW_MARGINAL_RETURN |
| R32 → R64 | +0.121212 | +0.060606 | -0.042675 | -0.121212 | +56.5894% | -47.2553% | NONE |

The low-marginal-return label follows the preregistered engineering threshold: positive behavior gains are below 0.03 while input-token or latency cost rises at least 15%. It is not a statistical significance claim.

## Scenario-Family Analysis

The following descriptive alignment rates use all successful rows in each family and therefore have unequal denominators because of timeouts:

| Family | R8 | R16 | R32 | R64 |
|---|---:|---:|---:|---:|
| Physiology | 0.5000 | 0.8000 | 1.0000 | 0.4000 |
| Work | 0.6667 | 1.0000 | 0.8333 | 0.6667 |
| Personal care | 0.3333 | 0.6667 | 0.5000 | 0.6667 |
| Chores | 0.7500 | 0.4000 | 0.5000 | 0.6667 |
| Leisure | 0.5000 | 0.6000 | 0.6000 | 0.6667 |
| Finance | 0.3333 | 0.3333 | 0.2500 | 0.4000 |
| Mobility | 0.8333 | 1.0000 | 1.0000 | 1.0000 |
| Food | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

These family rows are descriptive, not a second selection criterion. They show why an aggregate minimum cannot be interpreted as a universal action policy: visibility effects differ by family and provider outputs are noisy.

## Visibility Frontier

The frontier is the first tested level at which the scenario's declared critical resource is visible. It is a secondary audit, not a post-hoc change to the experiment:

| Critical resource examples | First visible level |
|---|---|
| hunger, sleep_pressure, work_urgency, hygiene_need, chores_backlog, leisure_need, budget_pressure | R8 |
| commute_pressure, work_progress, meal/personal-care/chores recency, social_need, discretionary budget | R16 |
| sleep_debt, sleep_quality, hunger_trend, food_security, work_deadline_pressure, commute_minutes_pressure | R32 |
| shower_due, kitchen_cleaning_need, entertainment_novelty_need, cash_reserve_pressure, transport_availability | R64 |

The measured behavior does not improve monotonically after every frontier; this is consistent with diminishing returns, but the benchmark is too small to infer a general cognitive law.

## Minimum Tested Resource Set

The pre-registered gate requires every positive metric to be within 0.05 of the best observed matched value and critical miss to be within 0.05 of the minimum observed value.

No tested level satisfies all gates simultaneously:

`MINIMUM_TESTED_RESOURCE_SET = UNRESOLVED`.

This means the experiment must not claim that R8 or R16 is the minimum. The 33 matched quadruples make this a meaningful descriptive result, but not a closed minimum-selection result.

## Resource Overload Signal

`RESOURCE_OVERLOAD_SIGNAL = NO`.

No expansion met the preregistered negative-overload criterion of alignment falling by more than 0.03 or critical miss increasing by more than 0.03. R64 was the best observed matched alignment and lowest critical-miss level, although it is also the most expensive context.

`LOW_MARGINAL_RETURN_STARTS_AT = R32` because the R16→R32 expansion added cost without a positive improvement of at least 0.03 in alignment, rule executability, or held-out share.

## Limitations

* One provider and one successful backend model; 18 timeouts remain provider observations.
* Two repetitions and 24 fixed one-request states; no statistical confidence claim.
* Synthetic ResourceTruth values and deterministic acceptable sets are engineering constructs, not measured human internal states.
* The scorer's alignment and critical-miss metrics are benchmark adequacy contracts, not an LLM judge or human-truth oracle.
* R1 prior and held-out scoring reuse the established A2 TRAIN/EVAL split, but no diary text enters the prompt.
* The run does not test full-day continuity, identity/inventory progression, duplicate replay, multi-agent interaction, Q5 scaling, or local 8B behavior.
* Some ActionType values (WAIT/REST) are retained in the fixed action vocabulary while the current RuleEngine may reject unsupported proposals; this is measured as executability, not silently remapped.
* Family rows have unequal successful-row counts due to timeouts.

## Engineering Decision

```text
RESOURCE_SET_RESULT = PARTIALLY_RESOLVED
MINIMUM_TESTED_RESOURCE_SET = UNRESOLVED
LOW_MARGINAL_RETURN_STARTS_AT = R32
RESOURCE_OVERLOAD_SIGNAL = NO
```

The current evidence supports the narrower statement: R8 is weaker than R16 on this benchmark, R16→R32 shows low marginal return under the pre-registered cost threshold, and R64 is the best observed matched level but is not accepted as a gold standard or minimum. No claim is made that agents or humans “need” 16, 32, or 64 Resources.

## Next Step

STOP after Q4 Attempt 1. Do not start Q5, action-set expansion, Activity Commitment, local 8B, hybrid-object work, or full-day continuity until the user reviews these data.

## Provenance and Safety

* Q4 branch is based on Q3 commit `20f5f0c0e6f1aa830075981dc87f9852d356460d`.
* Config: `config/experimental/resource_set_q4_v1.yaml`.
* Offline artifact: `run/evaluation/resource_set_size/offline_20260918T081546324092Z/`.
* Smoke artifact: `run/evaluation/resource_set_size/real_q4_attempt_1_smoke_20260918T081701224684Z/`.
* Full artifact: `run/evaluation/resource_set_size/real_q4_attempt_1_full_20260918T081859853289Z/`.
* Raw prompts, raw completions, hidden reasoning, Authorization headers, and secrets: not stored.
* Q3 document and Q3 branch: unchanged.
* Production WorldState, RuleEngine, and A2 profile: unchanged.
