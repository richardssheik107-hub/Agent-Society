# Research A2.0 — Calibrated Neutral-Day Baseline

## Research Question

How much of the neutral-day decision frequency follows from short timed-activity durations, and how much observed idle can be attributed to an incomplete action space? G0→G1 isolates duration; G1→G2 isolates the two new executable domains. Neither comparison measures model cognition directly.

## Why Calibration Before Corpus Study

The later B0/B100/B1000/BALL comparison would confound behavioral data with simulator timing and missing everyday activities. A2.0 leaves the corpus empty and estimates these mechanics first.

## Frozen Git Baseline

`9139744cc67d8d0279821ef9750990af5642dc87` (`Research B1.2: experimental behavior ontology calibration`) was the clean integration HEAD and `origin/main` at the start. No baseline reset, commit, or push was performed. A2.0 changes remain local. Upstream `third_party/AgentSociety` remains untouched.

## Empirical Basis

Research B1.2 uses 7,341 valid NHAPS/AHTUS 1992–94 adult diaries (4,774 employed adults, 3,215 employed-weekday diaries). Core5 covers 82.17% of all-adult minutes, Core7 93.00%; employed-weekday minute coverage is 86.25%→94.61%, episode coverage 68.32%→91.54%, transition coverage 47.11%→81.35%. The source is `config/experimental/neutral_day_calibrated_v1.yaml`, which records the source archive SHA256. These are descriptive historical data, not day-level behavior hints.

## G0 Original

Explicit frozen production-duration snapshot: SLEEP 360, WORK 90, LEISURE 60 minutes, EAT and MOVE instantaneous. Core5 ontology and current executable BUY remain available; the two new experimental actions are not advertised or registered.

## G1 Duration-Calibrated Core5

Same Core5 executable action set and prompt input as G0 at identical start state. SLEEP stays at 360, WORK becomes 270, LEISURE empirical 80 is quantized to 75 minutes. EAT and MOVE remain immediate. Profile durations are injected into the experimental rule engine only; production `daily/time.py` defaults remain unchanged.

## G2 Duration-Calibrated Core7

G1 durations plus PERSONAL_CARE and CHORES as profile-gated home activities. The compact context differs from G1 only in the available-actions list at equal state; no instruction about human typicality, prior, retrieval, or time-of-day behavior is added.

## Duration Quantization

One deterministic nearest-tick round-half-up function applies to all empirical candidate durations: 80→75, 25→30, 30→30, 270→270 minutes. Profiles retain empirical values alongside simulated overrides. SLEEP 360 is deliberately retained because a 240-minute segmented median is not an overnight-duration replacement. EAT 30 and MOVE 15 are *not* activated occupancy semantics. The frozen scripted 18-hour blocks SLEEP 360 + WORK 480 + LEISURE 240 mechanically give 10→5 full activity completions and 11→6 completion-triggered decision estimates when calculated from G0/G1 profile durations; this is not an LLM result.

## Experimental PERSONAL_CARE

G2-only, at home with no active conflicting activity; `target:null`, 30-minute timed occupancy, `PERSONAL_CARE_STARTED` and `PERSONAL_CARE_COMPLETED`. No energy, hunger, inventory, or money effect beyond ordinary fixed tick drift.

## Experimental CHORES

G2-only, at home with no active conflicting activity; `target:null`, 30-minute timed occupancy, `CHORES_STARTED` and `CHORES_COMPLETED`. No meal production, cleanliness state, or household inventory effect.

## Experimental Controls

All arms use B0_NONE, corpus size zero, no retrieved days or behavior priors. Same 15-minute tick, needs drift, work window, DecisionTrigger, IdleDetector, compact memory, target set, and reference provider alias `ark-code-latest`. Request body uses only model and messages, one request per decision, zero transport retries. Rules, environment, reducer, and judge make zero LLM calls. Segment start states are independent and deterministic (06–09 home, 09–12 office, 12–15 office and hungry, 18–21 home); history starts empty and goal is identical across arms.

## Offline Full-Day Validation

Three scripted 06:00–24:00 days reached 72 ticks, passed deterministic trajectory validation, and used zero provider requests. G0 had 19 scripted decisions; G1 had 11; G2 had 12 and selected both experimental activities. These differences are an offline scripted mechanics check, not real-model effect estimates. Whole test suite: 456 passed (three external deprecation warnings); Ruff passed.

## Segmented Real Pilot

The one-time deterministic schedule comprised 3 profiles × 4 independent three-hour segments × 2 repeats, interleaved rather than arm-by-arm. Per-segment cap was eight decisions. The run is `run/evaluation/calibrated_neutral_day/real_20260917T080501903875Z/`: 24/24 segments executed, **14 complete**, 5 provider TIMEOUT, 5 MAX_DECISIONS, **0 architecture failures**. It made 122 requests (117 recorded successful decision steps, 5 timed-out requests). All 24 trajectories carry one identical experiment-config SHA256. The actual backend was `glm-5.3` on all 117 successful steps. The profile and profile×segment JSON tables exclude truncated segments from complete behavioral averages.

| Profile | Complete / 8 | Provider timeout | Decision cap | Avg decisions* | Avg bursts* | Avg idle ratio* | Avg unique activities* |
|---|---:|---:|---:|---:|---:|---:|---:|
| G0 Original | 5 | 1 | 2 | 5.20 | 3.00 | 0.083 | 2.80 |
| G1 Duration | 6 | 1 | 1 | 4.83 | 3.17 | 0.056 | 3.00 |
| G2 Core7 | 3 | 3 | 2 | 2.67 | 1.33 | 0.000 | 2.00 |

`*` Averages over *complete segments only*; these overall arm averages are **not balanced by segment**, so they are descriptive, not paired treatment estimates. WORK was complete for all six cells, MORNING for none; MIDDAY was complete for G0/G1 but never G2. Profile×segment completeness and means are in `profile_segment_metrics.json`. The run used one scheduled attempt per cell; no retry or cosmetic rerun.

## Duration Effect: G0 vs G1

On the matched complete WORK cells, G0 used 2 decisions per replicate and G1 1; MIDDAY means were 7.0→6.5 decisions with equal 4.5 burst counts. First-repetition EVENING was 8→7 decisions and 6→5 bursts. Across the five paired complete cells, G1 had four fewer decisions/requests in total (mean paired Δ −0.8), while burst count changed only in EVENING (mean paired Δ −0.2). This is a *directional reduction consistent with duration mechanics*, not an isolated causal effect: independent provider choices can also change MIDDAY/EVENING trajectories. The unpaired overall means (5.20→4.83) are selection-sensitive and should not be used as the causal estimate. Offline scripted full-day 19→11 decisions and the fixed-block 11→6 estimate are separate deterministic checks.

## Ontology Effect: G1 vs G2

**No interpretable Core7 utilization effect was observed.** G2 made `PERSONAL_CARE` proposals=0, accepted=0, minutes=0 and `CHORES` proposals=0, accepted=0, minutes=0 over all eight assigned segments, including truncated ones. G2's two WORK cells (1 decision and 0 idle in each) matched G1 exactly; its one completed EVENING had 6 decisions, 0 idle and 4 unique activities, but a single cell with no Core7 selection cannot establish an ontology effect. G2 MIDDAY and all MORNING cells lack complete behavioral samples. The apparently lower G2 overall idle average is heavily selected by completion and must **not** be presented as Core7 reducing idle. An action-space-completeness effect remains untested by the real model's chosen actions despite validated mechanics.

## Provider Failures

Five TIMEOUTs (G0 1, G1 1, G2 3) and five MAX_DECISIONS (G0 2, G1 1, G2 2) produce truncated records and are never scored as complete idle behavior. No run of three consecutive infrastructure failures occurred. Each failed request counted toward the 122-request total; no provider failure was silently reassigned as behavioral idle. Partial metrics remain auditable separately. The unequal completion (5/6/3) creates selection bias in naive cross-profile averages.

## Context Cost

Per-decision context/prompt character counts, prompt SHA256, token counts (including reasoning-token *counts*), latency, and actual backend model are logged. Raw prompts and hidden reasoning are not retained. At identical initial state G0 and G1 contexts match byte-for-byte; G2 adds only its two available-action names. Complete-segment mean per-step context chars are approximately 510/508/507 (G0/G1/G2), corresponding prompt chars 808/806/805; these unequal per-arm averages reflect different observed states and completion selection, not a changed G0/G1 initial prompt. Mean total input tokens per completed segment are 1270/1190/667; mean total measured decision latency 57.6/53.8/21.9 seconds. These latency means exclude failed and truncated segments and do not represent full wall-clock cost. G2's small totals primarily reflect fewer complete decision chains and should not be read as a token efficiency improvement.

## Limitations

NHAPS is 1990s US adult data; one reference provider; two repetitions per profile×segment cell; segmented rather than uninterrupted real days. Core7 rules are intentionally simplified: CHORES has no household production and PERSONAL_CARE no physiological effect. EAT/MOVE occupancy remains inactive. No behavior corpus support, no statistical significance claim, and no human-likeness conclusion.

## Decision for A2.1

`A2_1_READY = YES` under the stated *engineering readiness* gate: G2 rule mechanics and gating pass offline, baseline and production defaults remain intact, all three full-day scripted trajectories validate, the 24-cell segmented pilot executed, and no architecture invariant failed. This does **not** mean ontology utilization, idle reduction, or human-likeness was demonstrated. A2.1, retrieval, larger corpus arms, and local-model work are outside this phase and were not started.
