# Research A1

Research A1 establishes a **neutral-day activity baseline**, not a test of human realism. The implementation asks whether one minimally described agent can sustain activity across a simulated day under the existing short-context, single-call decision pipeline, and where measurable inactivity or repetition appears. It does not download a behavior corpus, run an LLM judge, or prescribe a correct daily itinerary.

The observation window is **06:00–24:00: 18 simulated hours, 72 fixed 15-minute ticks**. “Day” here names this benchmark window, not a complete midnight-to-midnight 24-hour record. Each model decision selects one next action; Python advances the clock, needs, activity lifecycle, rules, state, events, and metrics. No environment, rule, reducer, event, or judge LLM is involved.

## Research Question

Can an agent with a neutral persona, a small local context, and one model call per triggered decision sustain varied, effective activity from morning to midnight? If not, does it leave long gaps without an activity, repeat invalid or non-progressing actions, neglect an elevated need, or stall despite available actions? Research A1 measures those outcomes; it does not decide whether the resulting schedule is “normal” by a human-data standard.

## Why Idle Matters

A task such as obtaining lunch has a clear terminal goal. A normal-day benchmark has no single target action, so goal completion alone cannot detect an agent that stops acting, loops on a rejected proposal, or remains inactive for hours. Conversely, **LEISURE is not idle**: it is an accepted, timed activity with start/completion events. `WAIT` is not offered as the default way to fill the day.

The benchmark separates *system-level* idle measurement from moral or psychological interpretation. A high idle ratio means the harness observed time without an active or newly accepted activity; it does not prove the model was “thinking,” bored, or unlike a real person. Failed provider requests are recorded separately from behavior observed after a valid model response.

## Neutral Persona

`NeutralPersona` supplies Alice, `adult`, `office_worker`, `neutral`, home `home`, workplace `office`, and the short goal “live through the day while handling your basic needs and obligations.” There is no detailed biography, political view, extroversion score, strong preference, or second person. Neutrality removes deliberate personality bias; it does **not** remove hunger, energy, a work obligation, time, or environmental constraints.

Each day begins from a fresh world: Alice is at home with money `100`, hunger `0.3`, energy `0.8`, an empty inventory, and no active activity. The locations are `home`, `office`, `restaurant`, and `park`; the restaurant starts with ten `meal` units at price `20`. Each day also gets a fresh event log and trajectory. The prompt is not given an hour-by-hour answer or the RuleEngine's location preconditions.

## Simulation Time

`simulation_time` is independent of wall-clock time. A pure `advance_daily_tick` advances exactly 15 simulated minutes and returns any completed timed activities. The daily runner stops at 24:00 after 72 ticks if no earlier termination occurs. A provider error, invalid model output, behavior-loop cap, or decision cap can leave a **partial day**; its observed-time denominator and termination reason must be retained, not silently treated as a completed day.

The non-random A1 constants are `UNCALIBRATED_BASELINE` mechanics, not estimates of human physiology or time use. `WORK` lasts 90 minutes, `SLEEP` 360 minutes, and `LEISURE` 60 minutes. Existing `MOVE`, `BUY`, and `EAT` remain instantaneous rule/reducer actions at the beginning of a tick; the tick then advances once. The benchmark does not yet model realistic travel, meal, or shopping durations.

## Needs

Hunger and energy are both bounded to `[0, 1]`: higher hunger means greater need for food; higher energy means more rested. The initial values are `0.3` and `0.8`. Per 15-minute tick, hunger rises by `0.01`; awake energy falls by `0.01`; energy during `SLEEP` rises by `0.04`. Values are clamped deterministically. The existing `EAT` effect reduces hunger via the ordinary rule/effect/reducer path. No LLM chooses need deltas. These coefficients are explicitly uncalibrated and must not support claims about real people.

The work obligation is a visible compact `09:00–17:00` window, not a forced schedule. The model may choose to violate it; the outcome is measured. A work-window boundary does not automatically interrupt an ongoing timed activity in A1.

## Activity Model

The action set is exactly `MOVE`, `BUY`, `EAT`, `SLEEP`, `WORK`, and `LEISURE`. New timed actions use the existing `RuleEngine → StartActivityEffect → StateReducer → EventLog` architecture. A successful start sets JSON-friendly `activity` and `activity_end_time` in `PersonWorldState` and emits an `*_STARTED` event. At the deterministic end time the tick advance clears activity and the runner emits `WORK_COMPLETED`, `SLEEP_COMPLETED`, or `LEISURE_COMPLETED` with a distinct event ID.

`WORK` requires the actor to exist, be at `office`, and start inside `09:00–17:00`. `SLEEP` requires `home`. `LEISURE` accepts `home` or `park`. A timed activity cannot start while another is active. Invalid actions create rejection events and do not mutate the world through a rule. The legacy move/buy/eat rules remain in force. These preconditions are checked by code, not explained to the model as a full rulebook.

The daily mode extends the Phase 7 decision trajectory with simulation time, activity, remaining minutes, hunger, and energy, while preserving the legacy trajectory path for earlier experiments. A separate 15-minute tick record bridges the gaps between decisions and records the before state, after-decision state, after-tick state, completion event snapshots, and the associated decision-step index. Daily schema version is `0.3`; a deterministic validator replays tick updates and checks continuity and event correspondence.

## Decision Trigger

`DecisionTrigger` is a pure-Python gate. When there is no active activity, or an activity has expired, the runner may ask for one new decision. A rejected action leaves no active activity, so the next tick can trigger a new decision. An explicit interrupt is supported by the gate, but the A1 runner does not generate one. Work boundaries matter when the agent is free; they do **not** preempt ongoing `WORK`, `SLEEP`, or `LEISURE`. Critical-need preemption is deferred. Thus an active timed activity consumes **zero provider requests on its ordinary intervening ticks**.

Each triggered decision uses the existing compact context, single-call `DecisionClient`, deterministic rules, reducer, and event log. The context includes persona facts, current time and local state, needs, available actions/targets, recent relevant events, and the short work window. It omits a prescribed day plan and hidden rule explanations. The target is under 800 context characters; the existing hard limits remain 2,000 context characters and under 3,000 prompt characters. The runner caps decisions at 30 per day. One decision uses at most one provider request; a tick without a decision uses none.

## Idle Definitions

All thresholds below are **A1 operational choices**, not calibrated human norms. `IdleDetector` consumes completed 15-minute intervals and computes labels without a judge model. A qualifying streak contributes *all* its minutes once it reaches its threshold, rather than only the excess minutes.

| Signal | A1 rule |
| --- | --- |
| `IDLE_NO_ACTIVITY` | No active activity and no newly accepted activity for at least 30 consecutive simulated minutes. A valid timed `WORK`, `SLEEP`, or `LEISURE` interval is not idle. |
| `REPEATED_INVALID_ACTION` | The same `(action, target, reason_code)` is rejected again while the action leaves the objective state unchanged. The count records repeated attempts **after the first** rejection. |
| `REPEATED_SAME_ACTION_NO_PROGRESS` | The same `(action, target)` is proposed three times in a no-progress streak, with no meaningful goal/need progress. Count one loop per streak. |
| `UNRESOLVED_NEED` | Hunger is at least `0.8` for at least 90 minutes without an accepted food-related step (moving to the restaurant, buying, or eating). This is a measurable need gap, not a claim that all hungry people should immediately eat. |
| `STALLED_STATE` | For at least 60 minutes outside a timed activity, the core state—location, activity, money, inventory, and coarse hunger/energy—shows no meaningful change or progress. Needs are rounded to one decimal for this particular stagnation comparison so tiny deterministic drift is not itself treated as purposeful activity. |

The real-run safety stop is separate from the descriptive three-action loop metric: **five consecutive identical rejected proposals** terminate the episode as `BEHAVIOR_LOOP`. It prevents repeated provider calls from continuing indefinitely; it does not erase the partial trajectory.

## Metrics

Per episode, report `idle_minutes`, `idle_ratio = idle_minutes / observed_simulated_minutes`, `max_idle_streak_minutes`, `idle_episode_count`, `repeated_invalid_count`, `behavior_loop_count`, `unresolved_need_minutes`, `stalled_state_minutes`, decision count, valid accepted activity/action count, unique activity types, and state-transition count. A zero-tick provider failure has no observable idle ratio: reports use **N/A**, not zero. For partial days the ratio uses only completed, observed ticks. The maximum idle streak is a streak of `IDLE_NO_ACTIVITY`, not necessarily the sum of all failure labels.

Activity and efficiency metrics include sleep, work, and leisure minutes; meal count (`EAT` accepted); move count; location-transition count; active minutes; decisions per simulated hour; provider requests per day; and accepted/rejected action counts. `active_minutes` counts intervals occupied by a timed activity or containing a newly accepted immediate action; this is an instrument definition, not a time-use estimate. Context and prompt character lengths, numeric input/output/reasoning token usage when returned, actual provider model when returned, and latency are kept for completed decision steps. A failed request may have no token usage or response-model identity; it must not be imputed as zero or assigned to the requested alias.

No single sleep/work quota or “human-like day” pass criterion is defined. Metrics are descriptive. `run/evaluation/neutral_day/` holds episode records, decision trajectories, summaries, and a manifest. Raw prompts, API keys, authorization headers, and hidden reasoning text are not saved; only prompt length and numeric reasoning-token counts are retained.

## Behavior Support Interface

`BehaviorSupportPolicy` selects at most three short, generic hints from a local hand-written source labeled `TOY_UNCALIBRATED_PRIORS`. Its conditions are `B0_NONE` (zero hints), `B1_TINY` (at most one), and `B3_SMALL` (at most three). Selection can respond to local hunger, energy, or whether work is due, but it contains no clock-by-clock itinerary, location-rule disclosure, retrieval model, or extra LLM call.

The **first real pilot uses only `B0_NONE`**. B1/B3 exercise interface and context-budget wiring offline; they are neither real corpus-size conditions nor evidence that behavior data improve the agent. No public dataset is downloaded or crawled in A1.

## Offline Validation

The offline gate precedes the real provider. Unit tests cover exact 15-minute progression, need changes and clamping, activity rules/start/completion, `DecisionTrigger` suppression during an active activity and reactivation afterward, all five idle signals, support caps, and trajectory replay. The full existing test suite must still pass.

`smoke/neutral_day_offline_smoke.py` uses a scripted client that sees the same compact context but makes **no provider request**. Its hand-coded schedule is a harness fixture, not an agent result or experimental condition: it verifies that a day can reach 24:00 in 72 ticks without idle or repeated-invalid flags, that all six action types can be recorded, and that the trajectory validates. A second deliberately pathological fake repeats `BUY meal` at home; it should show repeated invalid/loop behavior and terminate at the safety cap. The scripted client's decisions must never be described as model performance.

**Offline acceptance: PASS.** The final full-suite gate passed **328 tests**. The scripted smoke emitted `NEUTRAL_DAY_OFFLINE_OK` and covered `SIM_START=06:00` to `SIM_END=24:00` with **72 ticks**, **19 scripted decisions**, **0 idle minutes**, **0 provider requests**, and `TRAJECTORY_VALIDATION=PASS`. These are harness checks, not the B0 model's behavior.

## Real B0 Pilot

Only after the offline gate passes, run the current verified provider **once** on three fresh, independent A1 days, all `B0_NONE`. The request body stays the known minimal `model + messages` contract; no optional sampling fields, application retry, router-model decision, ReAct loop, or PersonAgent decision core is introduced. Each day has a hard 30-decision ceiling; the three-day ceiling is 90 provider requests. A poor behavioral day is retained, not rerun. A provider/output failure terminates and preserves that day; an architecture invariant failure aborts the pilot rather than continuing into another day.

For each day, retain the termination reason (`DAY_END`, `PROVIDER_ERROR`, `TIMEOUT`, `INVALID_MODEL_OUTPUT`, `MAX_DECISIONS`, `BEHAVIOR_LOOP`, or `ARCHITECTURE_ERROR`), observed tick count, idle and activity measures, accepted/rejected actions, compact trajectory signature such as `MOVE>WORK` or `BUY!NOT_AT_SELLER`, request count, context size, available token counts, latency, and returned backend identity. A day that stops early is not a completed 18-hour day. Summaries must distinguish attempted requests from completed decision steps and missing usage data.

**Pilot status: run once; three day attempts, zero completed days.** The frozen artifacts are under `run/evaluation/neutral_day/real_b0_20260917T021131929084Z/`. Every fresh day ended with `TIMEOUT` on its third provider request, after two completed model responses. The run observed **12 of 216 planned ticks**—180 of 3,240 planned simulated minutes—and made **9 requests for 6 completed decision steps**. None reached 24:00; the third request of each day returned neither a decision step nor usage/model identity. No day was rerun.

| Day | Observed window | Termination | Idle ratio / minutes / max streak | Completed decisions / requests | Accepted actions | Rejections | Repeated invalid | Compact observed signature |
| --- | ---: | --- | ---: | ---: | --- | ---: | ---: | --- |
| 1 | 5 ticks / 75 min | `TIMEOUT` | `0.000` / 0 / 0 min | 2 / 3 | `LEISURE` ×1 | 1 | 0 | `EAT!ITEM_NOT_OWNED>LEISURE` |
| 2 | 2 ticks / 30 min | `TIMEOUT` | `1.000` / 30 / 30 min | 2 / 3 | none | 2 | 1 | `EAT!ITEM_NOT_OWNED>EAT!ITEM_NOT_OWNED` |
| 3 | 5 ticks / 75 min | `TIMEOUT` | `0.000` / 0 / 0 min | 2 / 3 | `LEISURE` ×1 | 1 | 0 | `LEISURE>EAT!ITEM_NOT_OWNED` |

The report's `decision_count` is **3 per day** because it counts the attempted third decision as well as the two completed ones; the table deliberately distinguishes completed steps from requests. Day 2 met the 30-minute `IDLE_NO_ACTIVITY` threshold and repeated the same invalid action once. The other two days had no measured idle interval, but each exposed only 75 morning minutes. Across the observed segments, the taxonomy counts are `PROVIDER_FAILURE` 3, `NO_ACTION` 1, and `INVALID_LOOP` 1; no behavior-loop safety termination occurred.

The aggregate report gives average per-day idle ratio **0.333** over these **partial observed windows** (day ratios 0, 1, 0), average maximum idle streak **10 minutes**, average attempted decisions **3.0**, average accepted unique action types **0.7**, and average formal-action rejection rate **0.667**. These are not full-day estimates. Context length was 470.8 characters on average (max 492); prompt length was 768.8 on average (max 790). Across the six completed responses, mean input/output/reasoning-token counts were 229.5/271.7/258.8 and latency mean/p50/p95 was 6.26/5.24/10.57 seconds. Those usage and latency figures exclude the three timed-out attempts; the request timeout was configured at 60 seconds with no application retry.

All six returned responses identified backend `glm-5.3`; the three timed-out requests are **unattributed**, not presumed to have reached that same backend. The requested provider alias was `ark-code-latest`, and support was `B0_NONE`: no behavior hints or real corpus were supplied. This returned backend is **not a verified local ~8B model**, so size-specific or local-model transfer claims are unsupported. The saved manifest records `contains_raw_prompt=false` and `contains_hidden_reasoning=false`; numeric reasoning-token counts are retained, not reasoning text. Provider reliability dominated this run. The benchmark instrumentation produced an auditable partial B0 observation, but these artifacts **cannot answer whether Alice can complete a normal simulated day** or support a human-realism claim.

## Failure Taxonomy

The report attaches deterministic descriptive flags; multiple flags may apply to one day:

| Code | A1 report rule |
| --- | --- |
| A. `NO_ACTION` | With at least one observed tick, zero accepted actions or observed idle ratio at least 0.5. A zero-tick provider failure is not labeled behavioral inaction. |
| B. `REPETITION` | At least one no-progress same-action behavior loop. |
| C. `INVALID_LOOP` | At least one repeated identical invalid action. |
| D. `NEED_NEGLECT` | Positive unresolved-high-hunger minutes. |
| E. `OBLIGATION_NEGLECT` | A **completed** day with zero work minutes. Partial days are not assigned this flag merely because they ended before work. |
| F. `LOW_ACTIVITY_DIVERSITY` | A completed 18-hour day with fewer than three accepted action types. |
| G. `PROVIDER_FAILURE` | Provider error or timeout; not a behavioral judgment. |

These flags are not a single success score. `NO_ACTION` is a benchmark threshold, not a diagnosis; `OBLIGATION_NEGLECT` records one narrow observable outcome, not proof of motive. Short signatures help a reader locate the relevant trajectory without storing full prompts.

## Limitations

- Need increments, activity durations, idle thresholds, and the work window are uncalibrated benchmark mechanics.
- There is one neutral persona, one small deterministic world, one provider alias, and three **attempted**, not completed, real days. All six returned responses named `glm-5.3`; three timed-out requests have no returned backend identity. The observed backend consistency cannot be extended to those attempts or future alias routing.
- All real attempts stopped after 30–75 simulated morning minutes on a third-request timeout. No work boundary, midday meal, evening, or sleep segment was observed. Therefore absent `WORK`, `SLEEP`, or meals cannot be interpreted as a full-day behavioral failure or obligation neglect. Provider reliability is the dominant limit on the B0 behavioral question.
- `06:00–24:00` excludes the overnight hours before 06:00. `SLEEP` can extend beyond the observation window; only observed tick minutes count.
- `MOVE`, `BUY`, and `EAT` have the inherited instantaneous action semantics; social interaction, travel duration, hygiene, chores, and many other daily behaviors are absent.
- Ongoing timed activities are non-preemptive in A1, even at work boundaries or high hunger. This can affect both behavior and `UNRESOLVED_NEED` without requiring a model decision at that moment.
- The “stalled” comparison rounds needs; changes smaller than that granularity may be intentionally ignored. Idle and taxonomy labels are instrument definitions, not external ground truth.
- No real behavior corpus has been used. B1/B3 toy hints cannot support a corpus-size conclusion. The scripted offline day validates wiring only.
- Three short partial segments expose an early repeated-invalid pattern on Day 2 and a 9-request/6-completed-step cost, but cannot establish a full-day idle rate, statistical reliability, human realism, or local-8B transfer. Completed-step token and latency averages omit the three timeouts; the provider's underlying cause of those timeouts is not determined by this report.

## Next Step: Corpus Size Study

Stop after the B0 baseline and inspect where inactivity or repetition actually occurred. **Research A2** may later introduce a real, documented behavior corpus and compare zero/small/medium/large support budgets while retrieving only one to three relevant priors, then re-measure the same idle metrics. Corpus acquisition and any A2 experiment require a separate decision and are outside A1. Do not download ATUS, crawl behavior data, or infer a corpus effect from `TOY_UNCALIBRATED_PRIORS` here.
