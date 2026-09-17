# Research B1.2 — Minimal behavior ontology and duration calibration

## Research Question

Can the smallest explicit extension of SLEEP/WORK/EAT/LEISURE/MOVE describe at least 90% of adult diary minutes, and which **experimental** session durations and temporal priors are supported by the same data? The 90% threshold is an engineering coverage goal, not a scientific definition of a human day. This phase produces no production rule or default change.

## B1.1 Empirical Baseline

The [B1.1 report](research_b1_1_nhaps_ahtus_calibration.md) describes the official [CTUR NHAPS/AHTUS 1992–94 adult diary package](https://www.timeuse.org/ahtus/data). It yielded 7,341 complete, age-known adult diaries (123,132 episodes), of which 3,215 are employed weekday diaries. Core5 covers 82.1705% of all-adult minutes and 66.6439% of raw episodes. B1.2 reverified the source ZIP SHA256 `030ae6009bf30316379ec49c8da174f85b4726dc6a3c64f202617c3285ea07ca`, critical B1.1 artifact checksums, extracted SAV checksums and exact diary IDs. No download or B1.1 ETL rebuild occurred. The B1.1 corpus has merged adjacent OTHER episodes and lost some original source codes; recalculating Core7 sequences therefore requires reading the **existing verified local SAV episode file**, not reclassifying merged OTHER strings.

## Why Core5 May Produce Artificial Idle

Core5 leaves 1,884,764 of 10,571,040 adult diary minutes in OTHER. Missing personal care and household work are normal daily activities. When the simulator lacks a common executable behavior, some measured “idle” can be **action-space incompleteness rather than model cognitive failure**. This is an empirical coverage diagnosis, not proof that adding an action will reduce idle in a later model run.

## Candidate Behavior Domains

Only two explicit shadow domains were considered: PERSONAL_CARE and CHORES. They live in `social_sim.calibration`, **not** the production `ActionType`. The engineering coverage ladder tests only Core5, Core5+PERSONAL_CARE, Core5+CHORES, and Core7. `select_minimal_ontology` minimizes the number of additions among these four; it does not mine arbitrary source labels for new actions. Across **all** adults the smallest option above 90% is Core7 (+2). For the **office-worker reference subset**, Core5+CHORES alone reaches 91.03% (+1), while Core7 reaches 94.61% and describes more transitions. The experimental Core7 profile covers both populations; this does not imply both future rules must be built at once.

## PERSONAL_CARE Mapping

Exact `main` codes: 1 “general or other personal care” (medium confidence), 6 “wash, dress, personal care” (high), 7 “personal medical care” (medium). They add 367,124 valid adult minutes, **3.47 percentage points** of the all-adult day; 15,616 raw episodes. Source code 2 mixes imputed *personal or household* care and remains OTHER rather than being guessed into either category. All labels, counts, confidence and rationales appear in `ontology_mapping_audit.csv`. On employed weekdays, merged PERSONAL_CARE session median is **25 min** [p25 15, p75 40], with daily median **45 min**. Those are different statistics.

## CHORES Mapping

Exact code→label pairs: 20 food preparation/cooking; 21 set table/wash dishes; 22 cleaning; 23 laundry/ironing/clothing repair; 24 home repairs/vehicle maintenance; 25 other domestic work. Codes 24–25 have medium confidence; the rest high. Together they add 777,321 adult minutes, **7.35 percentage points**, and 13,985 raw episodes. Cooking is household preparation, not EAT. Shopping (26–32), caregiving, gardening and religion are *not* quietly absorbed. The employed-weekday merged CHORES session median is **30 min** [15,60], and daily median **30 min**. A high-level CHORES category avoids prematurely implementing separate COOK/CLEAN/LAUNDRY simulator actions.

## Core5 vs Core7 Coverage

Coverage is measured on each original episode; transitions are recomputed after **separate canonical merging for each ontology**. Transition coverage is the proportion of adjacent merged transitions whose *both endpoints* are inside that ontology, with the ontology's own merged-transition count as denominator. Do not treat a changing denominator as a fixed-transition uplift.

| Subgroup / ontology | Episode coverage | Minute coverage | Transition coverage | OTHER minutes |
|---|---:|---:|---:|---:|
| All adults / Core5 | 66.64% | **82.17%** | 42.79% | 1,884,764 |
| All adults / +PERSONAL_CARE | 79.33% | 85.64% | 59.25% | 1,517,640 |
| All adults / +CHORES | 78.00% | 89.52% | 59.35% | 1,107,443 |
| All adults / Core7 | **90.68%** | **93.00%** | **79.38%** | 740,319 |
| Employed adults / Core5 → Core7 | 67.93% → 91.37% | 84.69% → 94.07% | 45.83% → 80.87% | 1,052,715 → 407,884 |
| Employed weekdays / Core5+CHORES | 77.22% | 91.03% | 59.67% | 415,289 |
| Employed weekdays / Core5 → Core7 | 68.32% → **91.54%** | 86.25% → **94.61%** | 47.11% → **81.35%** | 636,514 → 249,451 |

Core5→Core7 improves all-adult minute coverage by **10.83 percentage points** for +2 domains (5.41 points per added domain as a descriptive efficiency ratio), and employed-weekday coverage by **8.36 points**. The complete four-rung, three-subgroup table is `ontology_coverage.csv`. The 90% goal is met for all adults with Core7, not with either addition alone.

## Remaining OTHER

Core7 leaves 740,319 all-adult minutes (7.00%). Top 20 original categories, with exact minutes, appear in `remaining_other_categories.csv`:

| Rank | Source category | Minutes |
|---:|---|---:|
| 1 | Purchase consumer durables | 124,664 |
| 2 | Worship and religious acts | 77,424 |
| 3 | Regular schooling/education | 60,517 |
| 4 | Writing by hand | 59,207 |
| 5 | Homework | 53,501 |
| 6 | Purchase routine goods | 48,945 |
| 7 | General care of older children | 39,139 |
| 8 | Pet care/walk dogs | 31,648 |
| 9 | Adult care | 30,644 |
| 10 | Use computer | 27,490 |
| 11 | Gardening | 25,332 |
| 12 | Purchase medical services | 20,995 |
| 13 | Other formal volunteering | 20,052 |
| 14 | Other child care | 17,643 |
| 15 | Play with children | 16,642 |
| 16 | Care of infants | 12,107 |
| 17 | Purchase repair/laundry services | 8,431 |
| 18 | Purchase personal services | 7,681 |
| 19 | Financial/government services | 7,221 |
| 20 | Supervise/help with homework | 7,002 |

Inspecting predeclared residual domains against **all** valid adult minutes: SHOPPING 2.12%, CARE_GIVING 1.20%, EDUCATION 1.14%, VOLUNTEERING/RELIGION 1.09%. None meets or exceeds the explicit 5% “major gap” engineering screen: `NO_MAJOR_GAP`. These are future coverage candidates, not new Phase B1.2 ontology members. The gap screen says nothing about the importance of a subgroup-specific activity.

## Episode Duration Calibration

Reference = 3,215 employed-weekday diaries; empirical sessions are adjacent **Core7-merged** episodes. Comparisons use current timed simulator session values from `daily/time.py`, not daily total. Candidates are robust medians unless noted:

| Activity | Current session (min) | Empirical episode median [p25,p75] | Status | Experimental candidate (min) |
|---|---:|---:|---|---:|
| SLEEP | 360 | 240 [105,360] | WITHIN_EMPIRICAL_IQR | **360 retained** as placeholder |
| WORK | 90 | 270 [180,460] | BELOW_EMPIRICAL_IQR | 270 (strong candidate) |
| LEISURE | 60 | 80 [40,150] | WITHIN_EMPIRICAL_IQR | 80 |
| EAT | instantaneous effect | 30 [15,45] | NOT_COMPARABLE | 30 future *occupancy* |
| MOVE | immediate location transition | 15 [10,30] | NOT_COMPARABLE | 15 future *travel occupancy* |
| PERSONAL_CARE | no action | 25 [15,40] | NOT_COMPARABLE | 25 shadow candidate |
| CHORES | no action | 30 [15,60] | NOT_COMPARABLE | 30 shadow candidate |

The simulator advances in 15-minute ticks: 80 and 25 minutes are **unquantized empirical candidates**, not immediately executable production settings. SLEEP's empirical episode median of 240 is **not** proposed as a replacement: midnight diary boundaries split bouts and the simulator's 06:00–24:00 horizon omits most overnight sleep. EAT occupancy must not alter hunger/inventory effects; MOVE occupancy must not alter destination validity or the world-state transition.

## Daily Duration Context

Employed-weekday **24-hour daily totals** have medians SLEEP 465, WORK 480, EAT 50, LEISURE 195, MOVE 70, PERSONAL_CARE 45, CHORES 30 minutes. A day may contain multiple episodes, and a zero is included if the activity was absent. These daily totals cannot be compared one-to-one with the 18-hour simulator or substituted for a session parameter. `duration_candidates.json` keeps separate `episode` and `daily` distributions including count, mean, median, quartiles and upper quantiles.

## Start-Time Priors

`time_prior_candidates.json` records the three most frequent 30-minute **episode-start** bins for each Core7 activity on employed weekdays. Examples: WORK 07:30, 08:00, 07:00; EAT 12:00, 18:00, 18:30; PERSONAL_CARE 06:00, 07:00, 06:30; CHORES 18:00, 17:00, 17:30. SLEEP peaks at 00:00, 22:00 and 23:00; **00:00 is strongly affected by diary-boundary splitting**, not a recommendation to begin sleeping at midnight. SLEEP has no naive linear median/IQR; other activities have descriptive linear quartiles alongside the histogram, not a mandatory schedule. No time prior enters a model prompt.

## Transition Priors

`transition_prior_candidates.json` retains the top three next activities per Core7 origin, recomputed from raw episode sequences after Core7 mapping and adjacent merging. On employed weekdays, WORK→MOVE 77.58% of observed WORK departures, WORK→EAT 14.99%; SLEEP→PERSONAL_CARE 64.40%; CHORES→EAT 38.10%. These are conditional descriptive proportions, not executable commands. Core5's aggregated OTHER transitions cannot be post-processed into this matrix.

## Decision-Frequency Counterfactual

One fixed *synthetic*, clock-agnostic 18-hour allocation is held constant: SLEEP 360 + WORK 480 + LEISURE 240 minutes. Only **fully completed** sessions within each block are counted using `floor(block/session_duration)`; a partial remainder stopped by the scripted boundary is **not** an activity-completion event. Add one initial decision. EAT/MOVE are excluded from both profiles because their current effects are instantaneous. Current durations (360/90/60) produce **10 completions / 11 estimated decisions**; experimental candidates (360/270/80) produce **5 completions / 6 estimated decisions**, a mechanical reduction of **5**. Scripted boundary decisions are outside this completion-only estimate. The script does not replay an LLM or make a real behavior-quality, token-cost, or API-call prediction. Activity durations that are too short mechanically increase `DecisionTrigger` opportunities and the chance of invalid loops.

## Experimental Neutral-Day Profile v1

`config/experimental/neutral_day_calibrated_v1.yaml` is labeled **EXPERIMENTAL CALIBRATION PROFILE / NOT PRODUCTION DEFAULT**. It stores the Core7 shadow ontology, source SHA256, employed-weekday reference, all subgroup coverage, session/occupancy candidates, and `RECOMMENDED_FOR_NEXT_EXPERIMENT`. Recommendation requires **≥90%** Core7 minute coverage in both all-adult and employed-weekday populations, every one of the seven experimental durations to have an observed positive session median (except the documented SLEEP placeholder), and no residual domain at **≥5%** of all-adult minutes. This operational check does not assert tick alignment or production readiness. The recommendation is for a research input, **not** approval to register rules, round durations to ticks, or run A2 automatically. The new candidate corpus (`behavior_days_core7_candidate.jsonl`) retains the original B1.1 Core5 corpus; B100 ⊂ B1000 ⊂ BALL=7,341 with seed 2025 and no duplication. Its manifest declares `ontology_status=EXPERIMENTAL`, LLM_calls=0 and input/output checksums.

## What Remains Deterministic

Hard world rules continue to check money, inventory, existing locations, seller presence, state invariants and valid transitions. No production `ActionType`, `RuleEngine`, activity defaults, clock/tick behavior, or upstream AgentSociety file changes. File hashes and supported-action tests guard this separation.

## What Is Empirically Calibrated

Only *offline candidates*: source-code-to-shadow-ontology coverage, merged-session distributions, 24-hour daily context, clock-start histograms, and Core7 transition proportions. A candidate profile is not a production config.

## What Remains Model-Driven

The agent still chooses its next action given state and constraints. Survey priors are neither a prescribed timetable nor a retrieval strategy. This phase calls no model and runs no corpus-size experiment.

## Limitations

The dataset represents U.S. time use in 1992–94, not a 2026 universal baseline. The sampled office-worker reference uses survey employment status and weekday, not a verified day of paid work. Medium-confidence source codes and diary splitting affect ontology and duration estimates. Survey-weighted population uncertainty is not estimated in this phase; coverage is unweighted against valid diaries. The transition-coverage denominator changes when mapping changes and merging is rerun. “No major gap” depends on the stated 5% screen and aggregate categories; caregiving may matter greatly to individual subgroups. Values like 25/80 minutes need a future explicit tick-quantization policy. The scripted counterfactual ignores interruptions, windows, inventory, rejected actions and real agent choices.

## Recommendation for Research A2

**RECOMMENDED_FOR_NEXT_EXPERIMENT** as an *offline research profile*: evaluate Core5 versus candidate Core7 and B0/B100/B1000/BALL only in a separately authorized future phase. For a narrowly employed-weekday coverage threshold, CHORES alone crosses 90%; PERSONAL_CARE adds substantial episode/transition coverage and enables the all-adult threshold. The future behavior-action recommendation is **PERSONAL_CARE, CHORES**, but neither action is implemented here. Tick semantics, overnight sleep, and occupancy effects must be designed before production calibration. Stop before retrieval, model calls, or A2.
