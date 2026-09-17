# Research A2-Final — fixed-state decision benchmark

## Scope and frozen baseline

This is an engineering comparison for one small-context neutral-agent simulator and one remote reference provider. It is **not** a significance test, a universal human-behavior result, or a local-8B result. The frozen Git baseline was `9b5e6e33f0ea9046e596a649562a1737e98c8491` on `main`. The simulator stayed on A2.0 G2: Core7; SLEEP 360, WORK 270, LEISURE 75, PERSONAL_CARE 30, CHORES 30 minutes; EAT and MOVE retain immediate effects. Production duration configuration and AgentSociety upstream were not changed.

The research design replaces A2-Fast's long-chain main comparison (only 8/20 complete segments) with 80 independent, one-request fixed-state decisions. Stage B is a separate 90-minute continuity check, not the primary corpus selector. There are no LLM calls for retrieval, held-out scoring, environment, rules, reducer, or judge.

## Split and retrieval

The 3,215 eligible NHAPS/AHTUS employed-weekday diaries were split by whole `day_id`, using sorted IDs and `Random(2025)` into **2,572 TRAIN** and **643 EVAL** diaries with zero overlap. Only TRAIN entered the retrieval index. Nested B100 ⊂ B1000 ⊂ BTRAIN_ALL were formed by prefix sampling without duplication. The split hash is `2366dbe80d95fe57137358b43bb8ede0b77380d91ac28675aaebad6f318c88db`; the source artifact SHA256 is `777553282692dec01f31deaa72ef67c8c2646d797cfc341ab55b75b5fa353dca`. Day-ID and sample hashes are in `stage_a/train_eval_split.json`.

Retrieval is unchanged from A2-Fast: 30-minute bucket and previous canonical activity, L0 exact then L1 bucket-only, L2 adjacent buckets, L3 global employed-weekday onsets, minimum support 10. `OTHER` remains in the denominator but is never a model action hint. The independent EVAL scorer uses its **own** L0–L3 distribution; it never reuses a TRAIN prior. On the predeclared 384-query coverage grid, L0 exact-hit was **12.24% for B100**, **71.09% for B1000**, and **86.20% for BTRAIN_ALL**. The EVAL pool's own L0 coverage was 61.46%.

## Stage A: 80 independent requests

Eight fixed world states (morning through late evening) × five interleaved conditions × two repetitions yielded exactly 80 one-request cases. C0=B0/R0; C1=B100/R1; C2=B1000/R1; C3=BTRAIN_ALL/R1; C4=BTRAIN_ALL/R3. Previous activity entered the normal event history path. The provider received no answer label, empirical score, or forced schedule. R1 exposes at most one activity name and R3 at most three. A failed request was not retried or replaced.

The result was **77 success, 3 TIMEOUT, 0 invalid output, 0 other provider error**: 96.25% successful independent decisions, above the preregistered 90% comparison gate. All 77 returned response envelopes identified backend `glm-5.3` behind requested alias `ark-code-latest`; the three timed-out requests have no proven backend identity. Failure was not counted as idle or an invalid action. The successful fixed-state comparisons are matched by state and repetition; 15/16 pairs are available for C0–C3, C2–C3, and C3–C4.

Adding the one-name full-TRAIN prior (C3 versus C0) raised mean held-out action share by **0.222** (0.279→0.501), rule-executable fraction by **0.400** (0.467→0.867), and top-3 agreement by **0.200** across 15 matched successful pairs. This is a directional within-panel contrast, not a randomized population effect. `prior_follow` alone was not used as a quality criterion: a model can reject a hint and still choose a supported, executable action.

The predeclared corpus rule required L0 exact-hit ≥60%, an absolute held-out-share gap ≤0.05, an absolute executability gap ≤0.05 versus C3 on matched successful rows, and no condition-specific provider collapse. B100 failed coverage (12.24%). B1000 passed coverage (71.09%) but fell short on matched behavior: C3 exceeded it by **0.098** held-out share and **0.133** executable fraction, both beyond the 0.05 tolerance. BTRAIN_ALL alone passed all gates. Thus **BTRAIN_ALL = 2,572 TRAIN diaries is the smallest passing tested level**, not a proof that every size between 1,000 and 2,572 would fail.

R3 versus R1 at BTRAIN_ALL reduced held-out share by **0.105**, executability by **0.267**, and top-3 agreement by **0.067** across 15 matched pairs, while adding about **14 context characters and 6.5 input tokens** per matched request. The predeclared engineering choice is therefore **R1, at most one activity name**. These are descriptive values for a small, fixed panel; model stochasticity and the single provider still matter.

PERSONAL_CARE appeared in 14 prior lists and was proposed 11 times, all rule-executable. CHORES appeared in 10 prior lists and was proposed twice, both rule-executable. The panel does not show 90-minute utilization; that is Stage B's separate task.

## Stage B: short continuity check

The selected profile was BTRAIN_ALL/R1. Since CANDIDATE already equals FULL, the fixed schedule has only CONTROL and CANDIDATE: four 90-minute scenarios × two arms × two repetitions = 16 assigned episodes, with six ticks and at most four decisions per episode. The first assigned episode encountered a recording-harness architecture error before a validated trajectory was produced. It was retained as a failed cell and was **not rerun**; the remaining 15 scheduled cells were continued in order. Its request count and behavior measurements are unknown, not zero. The error was isolated to passing `a2_final_micro` as the recorder scenario name: the generic immediate-step validator then rejected valid 15-minute daily tick drift. Changing only that harness name to the existing `neutral_day` validation path allowed the original remaining schedule to run. Simulator rules, world, prompt, and retrieval were untouched.

The 16 assigned episodes yielded **5 complete**, **3 TIMEOUT**, **7 MAX_DECISIONS**, **0 invalid output**, and **1 architecture/recording failure**. CONTROL completed 3/8; CANDIDATE completed 2/8. The only matched complete pair of scenario × repetition cells was `M2_WORK` twice. Both arms had zero idle, zero rejection, one decision, 90 active minutes, and one activity type in each of those cells. No complete candidate–control comparison exists for morning, midday, or evening. Candidate versus FULL is not applicable because they are the same BTRAIN_ALL/R1 configuration; the two complete candidate episodes are below the four-complete continuity threshold. Hence `minimum_validation=INSUFFICIENT_COMPLETE`, not PASS. The observed CONTROL PERSONAL_CARE proposals/acceptances were 2/2 versus CANDIDATE 0/0; CHORES was 0/0 in both arms, excluding the unaudited first episode. These totals do not identify a causal Core7 utilization effect.

Because one architecture failure occurred and Stage B continuity support is insufficient, the final acceptance state is **RESEARCH QUESTION 1 PARTIALLY UNRESOLVED** despite Stage A selecting a clear *decision-level* engineering configuration. There is no claim that a 90-minute or full-day agent with BTRAIN_ALL/R1 has been validated. The Stage B failure is explicitly included, not renamed as a provider or behavioral outcome.

## Interpretation boundary

The panel supports a current **engineering** minimum among the tested levels: 2,572 employed-weekday TRAIN diaries, R1. It does not establish a universal corpus-size optimum, token minimum, human-realism score, or transfer to a local 8B model. Held-out action share is a population-distribution support measure, not a unique correct action; rule feasibility is separately checked by deterministic simulator rules. The EVAL pool is drawn from historical US adult diaries and the panel contains only eight synthetic simulator states. The tested runtime event policy is existing `C3_recent3`; a more compact last-relevant-event structure is a cross-phase candidate from Phase 8A, not a jointly ablated A2-Final configuration.

Artifacts are in `run/evaluation/a2_final/real_20260917T101056138346Z/`; CSV/JSONL rows provide case-level verification without raw prompt, hidden reasoning text, or secrets. No failed cell was cosmetically replaced.
