# Research A2-Fast — Behavior Prior + Corpus Size Joint Pilot

## Goal

Estimate whether a compact empirical activity prior helps the neutral agent avoid idle or repeated non-progress decisions, and whether a small employed-weekday diary sample supplies enough retrieval support for this engineering pilot. Separately summarize which simulator components should be deterministic and which can be calibrated from open human time-use data. This is a directional 20-episode pilot, not a statistical significance study.

## Why A2.1 and A2.2 Were Combined

Five fixed conditions answer three narrow comparisons in one 5×4 run: C0 versus C3 for a prior effect, C1/C2/C3 for corpus size at R1, and C3 versus C4 for R1 versus R3 at BALL. One repetition per independent MORNING, WORK, MIDDAY and EVENING segment is intentionally small; provider truncation and missing matched complete cells limit interpretation.

## Frozen Simulator Baseline

The locally uncommitted A2.0 G2 profile is the sole simulator arm: Core7, SLEEP 360, WORK 270, LEISURE 75, PERSONAL_CARE 30 and CHORES 30 minutes; EAT/MOVE remain instantaneous. Start states, neutral persona and goal, rules, needs, trigger, compact recent-three memory and eight-decision cap are unchanged. Production duration config and B1.2 experimental YAML have their pre-run SHA256 recorded and are checked again at completion. No A2.0 local changes were reset or discarded.

## Human Behavior Corpus

The immutable NHAPS/AHTUS 1992–94 Core7 candidate artifact contains 7,341 valid adult diaries. Exactly 3,215 are employed weekdays, the relevant subgroup for the office-worker persona. The B1.1 sorted-ID, `Random(2025).shuffle`, prefix-sampling method is reapplied within this subgroup, giving B100⊂B1000⊂BALL with **100/1,000/3,215 eligible diaries**. This avoids labeling an all-adult B100 as if it contained 100 worker weekdays (the earlier all-adult B100 contains only 47). No diary is duplicated, oversampled, downloaded, or shown to the model. Source and sample-ID hashes are recorded.

## Deterministic Retrieval

The index counts *canonical episode onsets*, by 30-minute clock bucket and immediately previous canonical activity. Day type and employment are fixed to weekday/employed. It uses no hunger, energy, money, inventory, model, embedding, or private simulator similarity. L0 exact bucket+previous, L1 bucket-only, L2 ±30-minute adjacent buckets, L3 global eligible distribution. `OTHER` remains in the denominator and excluded-mass audit but is never returned as an executable prior. Ranking is count descending with alphabetical ties; prompt text contains names only and is neutral (`prior: common around now after … -> …`).

The minimum support count is 10. On the 384-query B100 coverage grid (48 buckets × None/Core7 previous), threshold 10 gives 44 exact hits (11.46%) and 16 global fallbacks (4.17%); threshold 20 gives only 3 exact hits (0.78%) and 48 global fallbacks (12.50%). The lower threshold retains more local evidence in the smallest arm without creating an empty query. This is a pragmatic sparsity choice, not a population-estimation confidence bound.

## Corpus Conditions

| Condition | Eligible diary corpus | Prior limit |
|---|---:|---:|
| C0 | B0, none | R0 |
| C1 | B100 | R1 |
| C2 | B1000 | R1 |
| C3 | BALL = 3215 employed weekdays | R1 |
| C4 | Same BALL | R3 |

The 7,341 all-adult source size and the 3,215 eligible retrieval denominator are never conflated. C1/C2/C3 compare corpus size only at R1; C3/C4 compare prior-list length only at BALL.

## Context Conditions

C0 adds no field, not even `prior:none`: its compact context string and SHA256 equal the A2.0 G2 R0 path for identical state. C1–C4 add only a short behavior-prior list under the existing compact behavior-hints field. The persona, system/user prompt scaffold, actions, targets, work window and event policy are unchanged. R1 returns at most one unique activity and R3 at most three; no probabilities or commands are exposed. Feasibility is counted offline from deterministic rules but is not shown to the model.

## Offline Validation

The Core7 source checksum, unique-day and subgroup count gates passed. Same corpus+seed rebuilt identical sample and index hashes, nested inclusion passed, all 384 queries per corpus returned a nonempty Core7 prior, and 25 representative time×previous rows per index were recorded for inspection. C0/R0 context equivalence passed; C1–C4 only added the prior field, remained under context/prompt limits and made zero provider requests in the scripted smoke. Full regression and Ruff results are listed in the final handoff.

## Real Segmented Pilot

The fixed schedule attempted all 20 condition×segment cells exactly once. The initial run was stopped after cell 13 at the user's request; only cells 14–20 were then executed, in the original order, into the same experiment directory. The pre-existing 13 records were not re-run. Each cell used at most eight decisions, one `model+messages` request per decision, a 60-second request timeout and zero transport retries. The 88 actual provider requests yielded 8 complete segments, 6 TIMEOUT, 5 MAX_DECISIONS and 1 INVALID_MODEL_OUTPUT; architecture failures were zero. The configured alias was `ark-code-latest`; 81 successful decision steps reported backend model `glm-5.3`.

| Condition | Complete / 4 | Timeout | Decision cap | Other truncation | Complete-cell idle ratio* |
|---|---:|---:|---:|---:|---:|
| C0 B0/R0 | 2 | 2 | 0 | 0 | 0.083 |
| C1 B100/R1 | 1 | 1 | 2 | 0 | 0.000 |
| C2 B1000/R1 | 2 | 1 | 1 | 0 | 0.083 |
| C3 BALL/R1 | 2 | 1 | 1 | 0 | 0.000 |
| C4 BALL/R3 | 1 | 1 | 1 | 1 invalid output | 0.000 |

`*` Unpaired complete-cell averages are descriptive only. Each condition completed a different subset of segments. The immutable schedule, 20 trajectories, per-cell metrics and paired comparisons are in `run/evaluation/behavior_prior_corpus/real_20260917T085445574770Z/`.

## Prior Effect: C0 vs C3

Only WORK and MIDDAY completed in both arms. WORK was identical on measured behavior: 0 idle minutes, 1 decision and 1 activity in each. MIDDAY showed 30 idle minutes for C0 and 0 for C3, with 7 decisions, 4 activity types, 2 same-state decisions, 5 decision bursts and 2/7 rejected proposals in both. Across these two matched cells, the **mean paired** C3-minus-C0 difference is −15 idle minutes (−0.0833 idle ratio), with zero change in decision count, rejection rate or diversity. C3/MIDDAY had 150 active minutes and 30 minutes without an active activity, but those gaps did not form a qualifying 30-minute idle streak; thus its detector-defined idle minutes were 0. This is a narrow directional idle signal, not a general prior effect: C2/B1000 had the same 30-minute MIDDAY idle as C0, and the pilot has one repetition per cell.

## Corpus Size: C1 vs C2 vs C3

On the 384-query offline grid, B100/B1000/BALL exact-hit rates were 11.46%/70.57%/89.84%; L1 fallback rates were 69.79%/29.43%/10.16%. B100 additionally needed L2 14.58% and L3 4.17%; no corpus produced an empty result. All three R1 arms completed WORK with the same 0 idle minutes and 1 decision. Only B1000 and BALL also completed MIDDAY; BALL had 0 idle minutes versus B1000's 30, while both used 7 decisions and had identical measured rejection and diversity. No B100-vs-other matched non-WORK cell exists. Thus B1000 improves retrieval locality substantially over B100, while BALL improves it further; behavioral sufficiency of any smaller corpus is **UNRESOLVED** here.

## Retrieval Size: C3 vs C4

Only WORK was matched complete. C3/R1 and C4/R3 both had 0 idle minutes and 1 decision. In that cell, the extra prior context was 55 versus 76 characters (+21), and input tokens were 246 versus 255 (+9). The other three C4 cells were truncated, so this is insufficient to establish either R1 or R3 as the minimum useful prior size. `ENGINEERING_MINIMUM_PRIOR = UNRESOLVED`.

## PERSONAL_CARE / CHORES Utilization

Across all attempted cells, PERSONAL_CARE appeared in 5 prior lists, was proposed 5 times and accepted 5 times. Its observed ticks total 150 minutes, all within truncated MORNING cells; the eight complete segments have 0 PERSONAL_CARE minutes. C0 produced one of those starts without any prior, so the aggregate does not attribute PERSONAL_CARE to retrieval. CHORES appeared in 17 prior lists, was proposed once, never accepted, and occupied 0 observed minutes. Prior visibility alone therefore did not activate CHORES. `prior_follow_rate` describes action/list agreement, not decision quality; feasibility was audited separately and never shown to the model.

## Provider Failures

Six cells timed out at the provider, five hit the fixed decision cap, and one ended on invalid model output. These are distinct termination categories; a timeout is not an idle/behavior failure. Only 8/20 cells completed, below the pre-specified 10-cell interpretation threshold: **BEHAVIORAL CONCLUSION LIMITED BY PROVIDER**. Truncated cells retain their partial-window observations but have no full-segment idle or activity-duration value in `summary.csv`. The trajectory cost fields count completed decision steps; a failed request's elapsed time is in the corresponding failure audit, so the trajectory latency total alone is not whole-cell wall time. No failed cell was replaced.

## Context and Token Cost

R0 added exactly 0 context characters. In complete WORK cells, R1 added 55 characters and R3 added 76. For all attempted C1–C3 steps with a saved context, mean added context was approximately 54–59 characters; C4 was approximately 67–76 depending on cell. Context and prompt sizes remained below the configured limits. The run records prompt SHA256, character counts, input/output/reasoning token *counts*, backend model and measured latency, but no raw prompt, hidden reasoning, credentials or authorization header. It made zero retrieval, environment, rule, reducer or judge LLM calls.

## Answer to Research Question 1

The apparent idle has several separable causes: the earlier Core5 action space omitted PERSONAL_CARE/CHORES; the old 90-minute WORK session was short relative to the empirical 270-minute median; some model decisions were rejected or repeated without progress; the agent sometimes lacked an empirical activity cue; and provider timeouts truncated observation. A2.0's G0/G1 matched cells suggested fewer decisions with calibrated duration. Here, C0/C3 show one matched MIDDAY idle improvement of 30 minutes, but no change in decision count or rejection and only 8/20 segments completed. This does not identify how much knowledge is *minimally* required. `ENGINEERING_MINIMUM_CANDIDATE = UNRESOLVED` for B100/B1000/BALL, and `ENGINEERING_MINIMUM_PRIOR = UNRESOLVED` for R1/R3. The fixed compact recent-three decision context was not independently ablated in this pilot. No normal-human-behavior or significance claim follows.

## Answer to Research Question 2

Keep money, inventory, stock, location validity, seller presence, state consistency and conflicting-activity constraints as **hard deterministic rules**. Use NHAPS/AHTUS for **empirical calibration** of activity ontology, comparable activity duration, time-of-day distribution, transition priors and coverage; let the model choose its next concrete action, subject to rules. Open human time-use data is useful and already materially changed the simulator design: Core5→Core7 raises all-adult minute coverage from 82.17% to 93.00% (94.61% for employed weekdays), and the empirical WORK median of about 270 minutes exposed the old 90-minute session as too short. These are descriptive historical US data, not universal prescriptions or new hard rules.

## Limitations

One reference provider, one repetition per condition×segment cell, segmented rather than uninterrupted day, simplified Core7 actions, fixed 1990s US survey subgroup, unweighted onset counts, deterministic top activities rather than full diary examples, and potentially severe provider/cap selection. No statistical significance test or normal-human-behavior conclusion is warranted.

## Next Decision

Stop at this once-only pilot. The stronger conclusion is the deterministic retrieval coverage gradient and the separation of historical behavior calibration from hard simulator rules; the behavioral minimum remains unresolved because of completion selection and sparse non-WORK pairing. Do not launch another phase, rerun failed cells, or expand the real-run matrix automatically. The protected production duration file and experimental G2 YAML retain their pre-run SHA256; full regression passed 464 tests and Ruff passed. No commit or push was performed.
