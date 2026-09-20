# Research A2-Final — current answers to the two research questions

This document is a self-contained engineering handoff for the AgentSociety 2 integration project. The reference agent chooses one next action at a time in a small deterministic world. A language model proposes the action; the simulator's rules decide whether it is legal and what happens. The goal here is a useful baseline for later model replacement, **not** a claim that simulated behavior is universally human-like. Git baseline: `9b5e6e33f0ea9046e596a649562a1737e98c8491`. Research A2-Final made no production-config or upstream AgentSociety change and ran no local 8B model.

## Question 1 — Why does the agent appear idle, and what is the current minimum support?

### Current answer

“Idle” is not one failure mode. Research A1's idle/repeated-invalid/stalled-state detectors and A1.1's trigger audit separated observed inactivity from technical truncation. A2-Final identified five contributors at different levels; the A2-Closure update below adds the sixth, immediate-action/decision-cap churn:

- **Incomplete action space.** Core5 omitted PERSONAL_CARE and CHORES. Research B1.2 found Core5 described 82.17% of all-adult diary minutes; Core7 described 93.00%, or 94.61% for employed weekdays. Missing common actions can manufacture apparent inactivity, though their addition alone was not proven to cure all idle.
- **Too-short activity sessions.** The old simulator's WORK session was 90 minutes; the employed-weekday merged-episode median was about 270 minutes. B1.2's fixed-block calculation reduced completion-triggered decisions from 11 to 6 under calibrated durations. A2.0's five matched complete G0–G1 cells showed a directional mean reduction of 0.8 decisions; this is not an isolated causal estimate.
- **Rejected or repeated decisions.** A1 observed partial-window invalid loops. Phase 8A showed one immediate repeated rejected purchase in 4 state-only rejection-prelude episodes versus 0/4 with last-event feedback; longer recent-three/relevant history showed no clear extra benefit in that simple lunch task. A rejection should remain visible long enough for the next decision, not be silently treated as model “thinking time.”
- **Insufficient local behavior cue.** A2-Fast built a deterministic time/transition retrieval path but had only 8/20 complete long segments. In A2-Final's 15 matched successful fixed-state C0–C3 pairs, one full-TRAIN prior name raised mean held-out activity share by 0.222 and rule-executable fraction by 0.400. This is useful decision-level evidence, not a guarantee of better continuous trajectories.
- **Provider/output truncation.** A1's three full-day attempts all timed out on their third request; A1.1's 30/30 fixed provider probe passed, yet its one real day stopped at 13:00 on invalid model output after 28/72 ticks. A2-Fast ended 6/20 segments on TIMEOUT and 1/20 on invalid output. These unobserved intervals are **not** counted as behavioral idle. A2-Final's independent panel kept 77/80 successful rows despite three timeouts, showing why independent requests are a better primary comparison here.

### Current minimum corpus candidate

`CURRENT_MINIMUM_BEHAVIOR_CORPUS = BTRAIN_ALL`, **2,572 TRAIN employed-weekday diaries**. This is the smallest *tested* level meeting the preregistered A2-Final gates, not a precise threshold for every corpus size. The 3,215 eligible day IDs were split once with seed 2025 into 2,572 TRAIN and 643 disjoint EVAL; EVAL never entered retrieval. Exact-hit coverage on 384 fixed queries was B100 12.24%, B1000 71.09%, BTRAIN_ALL 86.20%. B100 failed the 60% locality gate. B1000 passed locality, but against BTRAIN_ALL/R1 on 15 matched successful state×repetition pairs it lost 0.098 held-out action share and 0.133 rule-executable fraction; both exceed the 0.05 engineering tolerance. BTRAIN_ALL passed. The 60% and 0.05 values are pragmatic gates, not confidence bounds.

### Current minimum prior candidate

`CURRENT_MINIMUM_BEHAVIOR_PRIOR = R1`: **at most one canonical activity name per decision**, retrieved using the fixed 30-minute bucket plus previous activity and L0–L3 fallback. The model sees no diary, probability table, instruction to imitate, or unique “correct answer.” Against R1 on 15 matched successful full-TRAIN pairs, R3 reduced held-out share by 0.105, executability by 0.267, and top-3 agreement by 0.067 while using roughly 14 more context characters and 6.5 more input tokens. This favors R1 under the preregistered rule, not a theoretical proof that more context is always harmful.

### Current minimum context structure

`CURRENT_MINIMUM_CONTEXT_STRUCTURE = compact current state + current needs/obligation + last relevant event + R1 behavior prior`. The event feedback component is motivated by Phase 8A, and the one-name prior by A2-Final. The **actually tested A2-Final runtime** still uses its normal `C3_recent3` event policy; each fixed panel state carried zero or one prior event. The proposed last-relevant-event reduction was **not jointly ablated with behavior prior** here. The frozen experimental reference profile records both the tested runtime policy and this compact candidate so a later model comparison cannot quietly change context at the same time. No token count is claimed as a universal minimum.

### Evidence

The A2-Final panel ran exactly 80 independent, one-request cases across eight states and five interleaved conditions, with 77 successes, 3 timeouts, 0 invalid outputs and zero retry. All 77 successful envelopes named `glm-5.3`; the requested alias was `ark-code-latest`, not a verified local 8B model. Held-out evaluation used the 643 EVAL diaries' own L0–L3 distribution, with `OTHER` in its denominator and no single ground-truth activity. Rule feasibility was a separate deterministic check. PERSONAL_CARE appeared in 14 prior lists, was proposed 11 times and was executable in all 11; CHORES appeared in 10 lists, was proposed twice and was executable twice. These are decision proposals, not proof of normal-day utilization.

### Limitations

Stage B's 16 scheduled 90-minute episodes yielded only 5 complete, 3 provider timeouts, 7 decision-cap truncations and 1 recording-harness architecture error. The first episode was retained as a failure with unknown request/behavior counts and never rerun. Only two matched complete candidate–control cells existed, both WORK, with equal measured behavior; morning, midday and evening were not comparably complete. CANDIDATE already equals FULL, so there was no duplicate full arm, but two completed candidate episodes were insufficient for the preregistered continuity gate. Therefore the **decision-level** corpus/prior candidates are clear, while continuous-behavior sufficiency remains unverified. Historical 1990s US diaries, one office-worker persona, eight synthetic states, two repetitions, one remote provider, and unweighted episode-onset retrieval further limit generalization. No statistical significance or full-day stability claim follows.

## Question 2 — What should be deterministic, calibrated, and model-chosen?

### Hard rules

Keep **money, inventory, stock, location validity, seller presence, state consistency, activity conflicts, and world consequences** code-owned and deterministic. An empirical frequency must never authorize an impossible purchase, teleportation, conflicting activity, or inconsistent state. The environment, rules, reducer and evaluator make zero model requests.

### Empirical distributions

Use verified open diaries to calibrate **activity ontology, comparable session duration, time-of-day onset distributions, transition priors, behavior corpus and population-level support**. B1.1/B1.2's NHAPS/AHTUS pilot established 7,341 valid adult diaries and the 3,215 employed-weekday subgroup. Core5→Core7 raised all-adult minute coverage from 82.17% to 93.00% and employed-weekday Core7 coverage to 94.61%. The WORK 90→≈270-minute contrast exposed a simulator parameter mismatch. A2-Fast/A2-Final showed deterministic retrieval can form a local time/previous-activity prior and that its exact-hit rate depends materially on TRAIN corpus size. These distributions describe a population and period; they do **not** force an individual's daily schedule.

### Model choice

Let the model select the next action using compact observation, needs/obligation, event feedback, available actions/targets and a bounded behavior hint. Then apply deterministic validation and consequences. In short: **LLM proposes actions; deterministic rules govern consequences.** No LLM judge is needed to compute held-out support, feasibility, idle, or termination.

### Is open behavior data worthwhile?

`OPEN_DATA_CALIBRATION_WORTHWHILE = YES` for this engineering project. The ontology and duration corrections address identifiable simulator gaps, while the retrieved prior improves held-out support and feasibility in the fixed-state panel. This does not certify human likeness, imply that 2,572 diaries are universally optimal, or replace future evaluation on a local model.

### Evidence

Core5 covered 82.17% of all-adult diary minutes; Core7 covered 93.00% of all-adult and 94.61% of employed-weekday minutes. The historical WORK episode median of about 270 minutes exposed the simulator's former 90-minute setting. The A2-Final TRAIN retrieval index achieved 12.24%/71.09%/86.20% exact-hit rates at 100/1,000/2,572 diaries, and the full-TRAIN one-name prior improved matched held-out support and rule feasibility versus no prior. These observations justify calibration as an input layer, not as an overriding rule.

### Limitations

The survey is historical US data; diary categories and episode onsets are imperfect proxies for this synthetic office worker. EVAL and TRAIN are day-disjoint but come from one source population. Model choices can be stochastic and provider routing can change. Stage B did not clear the continuity acceptance gate, and one failure was in the experiment recording harness. The final status is **RESEARCH QUESTION 1 PARTIALLY UNRESOLVED**: Question 2 has a clear ownership boundary and Question 1 has a decision-level engineering candidate, but not the required no-architecture-failure continuous validation.

## Frozen reference and audit trail

The recommended **experimental** profile is `config/experimental/neutral_day_recommended_reference_v1.yaml`: G2 Core7, calibrated durations, BTRAIN_ALL=2,572 TRAIN diaries, R1, unchanged deterministic retrieval and tested `C3_recent3` runtime context. Later remote→local model comparison should change only DecisionClient/model; A2-Final itself does not run local 8B. The compact last-relevant-event structure remains a candidate, not an untested silent baseline change.

The detailed [A2-Final benchmark](research_a2_final_decisive_benchmark.md) and ignored local `run/evaluation/a2_final/real_20260917T101056138346Z/` contain the split, hashes, 80 panel rows, matched comparisons, 16 scheduled micro cells, failure audit, final JSON and CSV. No raw prompts, hidden reasoning text, secrets, or failed-cell replacements are stored. No commit or push was made so these conclusions can be reviewed first.

## A2-Closure Update

The A2-Final conclusion above is preserved as the historical finding. A new, entirely offline [continuity audit](research_a2_closure_continuity_audit.md) classified **all seven** original `MAX_DECISIONS` cells without rerunning or changing any A2-Final artifact. Primary causes were **5 immediate-action churn, 1 need-loop, 1 mixed**, with no insufficient-data cell. The five-cell dominant pattern is ordinary next-tick redecision after intentional instantaneous MOVE/BUY/EAT effects, not a same-tick duplicate trigger. Three cells each met the predeclared `PRIOR_LOOP_SIGNAL=YES` test through one prior-followed rejected action; this is a secondary feasibility weakness, not the dominant five-cell explanation. Four decisions within 60 observed minutes cannot establish a 90-minute idle rate.

The one A2-Final recording failure was a harness scenario-name mismatch. Its old cell remains invalid with unknown request/behavior counts and was never rerun. The existing daily validation path (`scenario_name=neutral_day`) is now covered by a no-provider regression test; no world, rule, reducer or AgentSociety core change was needed. The dominant instantaneous-action chain is intentional, and there is no evidence that a prior filter would resolve it. Thus `runtime_behavior_change=NONE`, `runtime_guard=NONE`, and `REAL_CONTINUITY_RERUN=NOT_NEEDED`: the optional eight-episode Stage C3 confirmation was not triggered by this decision gate.

The refined statuses are `QUESTION_1_DECISION_LAYER=CLOSED_ENGINEERING`, `QUESTION_1_CONTINUITY_LAYER=PARTIALLY_UNRESOLVED`, and `QUESTION_2=CLOSED_ENGINEERING`. The smallest passing **tested** decision-layer configuration remains 2,572 TRAIN diaries + R1. The reference context recommendation is compact state, needs/obligation, **1–3 short recent events**, and R1; this range was not jointly tested, last relevant event is a minimum candidate, and `C3_recent3` is the actually tested runtime event setting (distinct from Stage C3 confirmation). `OPEN_DATA_CALIBRATION_WORTHWHILE=YES` remains unchanged. The overall engineering status remains **RESEARCH QUESTION 1 PARTIALLY UNRESOLVED**, because this phase did not identify a single continuity repair that meets the evidence gate or verify continuous behavior.
