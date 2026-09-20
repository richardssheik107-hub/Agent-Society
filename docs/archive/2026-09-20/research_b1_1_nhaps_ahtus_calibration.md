# Research B1.1 — NHAPS/AHTUS

## Why the Data Source Changed

The official BLS ATUS 2025 ZIP returned HTTP 403 under local, Codex, and CI automated downloads. This was an access limitation, not a failure of the HumanDayDiary model. The ATUS adapter, mapping, scripts, and documentation remain intact; its registry status is `DATA_ACCESS_BLOCKED`.

## Source and Provenance

The [official CTUR AHTUS data page](https://www.timeuse.org/ahtus/data) lists “Diaries from ages 18+, 1992-94” for NHAPS. The [AHTUS codebook](https://www.timeuse.org/sites/ctur/files/819/ahtus-codebook-26-january-2014.pdf) and [file listing](https://www.timeuse.org/sites/ctur/files/819/ahtus-data-files-03-july-2013.pdf) document the harmonized person, summary, and episode files. The downloader resolves the current link from that official page; it does not fetch a mirror. CTUR describes AHTUS as freely available to researchers and asks that programs/publications be shared; this report makes no broader license or redistribution claim.

The official resolved URL for this run was `https://www.timeuse.org/sites/default/files/ahtus/public/4931/usa1993-dec2009.zip`. The ignored `SOURCE.json` records UTC download time and the resolution. No LLM was called.

## Raw Package

The immutable ZIP is 3,208,441 bytes, SHA256 `030ae6009bf30316379ec49c8da174f85b4726dc6a3c64f202617c3285ea07ca`. ZIP integrity and all three expected SAV basenames passed. Actual members: `USA92_94quest.sav`, `USA1993hfsum.sav`, and `USA1993hfep.SAV` (uppercase episode extension). Extraction is only to ignored `processed/work`, with member hashes checked on reuse. `data/external/` and `run/` stay Git-ignored.

## Schema

Metadata was read **before** mapping with `pyreadstat==1.3.6` and saved in three ignored `schema_*.json` artifacts (columns, labels, value labels, dtypes, rows, source checksum). The background file has 7,514 rows / 46 columns; summary 7,514 rows / 227 columns; episode 125,554 rows / 38 columns. Each uses `survey,wave,hhid,pid` for matching. Episode order is `epnum`; main code is `main`, duration `time`, diary elapsed `start/end`, clock `clockst`, location `eloc`, transport mode `mtrav`, co-presence fields include `alone/child/cowork`, and diary-quality fields `lowqual/baddem`. `recwght` is labeled “recommended sample/day weight removing low quality diaries and missing age or sex.” The background `age` and `empstat`, and episode `diaryday`, were verified against actual value labels; `empstat=1/2` denotes full-/part-time employed, and `diaryday=2..6` is Monday–Friday.

## Unified Diary Mapping

The adapter joins on the four official keys, sorts `epnum` (not DataFrame order), uses source `start/end/time` verbatim, and produces `HumanActivityEpisode` and `HumanDayDiary` with stable survey keys, not person names. The AHTUS day starts at midnight: `start=0`, `end=1440`; ATUS remains 04:00–04:00. No synthetic filler is added. Every accepted diary has positive durations, contiguous time, 1,440 minutes, sequential episode indices, a matching summary `tottime` and `numep`, and matching available `tmainN` code totals. Observed total/summary mismatches: **0**. Raw episodes on the valid adult diaries: **123,132**; the remaining 2,422 belong to age-missing cases.

## Canonical Activity Taxonomy

The source-specific exact-code YAML uses actual SPSS `main` value labels and rationale/confidence on 48 explicitly mapped codes. Explicit sleep/naps → SLEEP; meals → EAT; paid work plus work breaks/presence → WORK; social, media, and recreational activity (including sports) → LEISURE; codes 90–98 travel → MOVE. Work breaks/presence and some leisure rows carry **medium** confidence. Personal care, domestic work, caregiving, education, religious acts, shopping, and ambiguous computer use remain OTHER. Restaurant/cafe/bar code 56 is source-classified out-of-home leisure, not automatically an eating episode. Empirical MOVE is travel time, not executable simulator MOVE. Label drift makes the adapter fail fast rather than silently remap.

## Mapping Coverage

| Population | Valid days | Core5 episodes | Core5 episode share | Core5 minutes | Core5 minute share | OTHER minute share |
|---|---:|---:|---:|---:|---:|---:|
| All adults | 7,341 | 82,060 / 123,132 | 66.64% | 8,686,276 / 10,571,040 | **82.17%** | **17.83%** |
| Employed adults | 4,774 | 53,738 / 79,105 | 67.93% | 5,821,845 / 6,874,560 | 84.69% | 15.31% |
| Employed weekdays | 3,215 | 36,736 / 53,768 | 68.32% | 3,993,086 / 4,629,600 | 86.25% | 13.75% |

Using the codebook-described `recwght` once per diary, positive-weight records only, weighted Core5 minute share is **82.28%** all adults, **84.88%** employed, **86.34%** employed weekdays. These are first-pass descriptive weightings, not final design-based estimates or confidence intervals. The 292 low-quality zero-weight adult diaries are retained as individual corpus days and in unweighted descriptive counts, but excluded from weighted summaries; the weighting does **not** duplicate corpus diaries. Unweighted and weighted daily/merged-episode CSVs are both emitted.

## Adult Diary Sample

The archive has 7,514 raw diarists, 125,554 raw episodes, and matching 7,514 background/summary rows. Actual age is missing/dirty (`-8`) in 173 cases, which are excluded before adult validation; no observed under-18 case. The remaining **7,341** adult diaries are all valid; invalid adult diaries **0**, unmatched keys **0**, parse errors **0**, daily summary mismatches **0**. `lowqual=1` occurs in 292 otherwise valid diaries. This is not a claim that the raw package has 7,514 verified 18+ ages.

## Employment / Weekday Subsets

Actual `empstat` yields 4,774 employed adult diaries; 3,215 of these fall on Monday–Friday by `diaryday`. The employment field measures respondent status, not whether they worked on that particular diary day. Survey year/day/season are preserved in metadata. No employment is guessed from the observed WORK minutes.

## Episode Durations

These are **canonical-merged, contiguous** episodes (raw fine-grained episodes remain in the corpus source). Employed-weekday unweighted duration, minutes:

| Activity | n merged episodes | median | p25–p75 | p90 | p95 |
|---|---:|---:|---:|---:|---:|
| SLEEP | 6,212 | 240 | 105–360 | 420 | 480 |
| WORK | 4,166 | 270 | 180–460 | 565 | 625 |
| EAT | 5,471 | 30 | 15–45 | 60 | 80 |
| LEISURE | 6,849 | 80 | 40–150 | 225 | 270 |
| MOVE | 11,962 | 15 | 10–30 | 45 | 60 |
| OTHER | 11,425 | 30 | 15–60 | 125 | 195 |

The CSV also contains count and mean for every subset. Midnight splits some SLEEP bouts into two episodes, so a 24-hour diary's *daily* sleep is the sounder quantity for total sleep comparisons. A work break may split paid work unless adjacent WORK episodes merge.

## Daily Time Allocation

Employed-weekday unweighted daily minutes (each of 3,215 diaries contributes one value, including zero for absent activities):

| Activity | mean | median | p25–p75 | p90 |
|---|---:|---:|---:|---:|
| SLEEP | 470.06 | 465 | 410–525 | 595 |
| WORK | 400.63 | 480 | 240–554.5 | 645 |
| EAT | 59.50 | 50 | 30–80 | 120 |
| LEISURE | 221.94 | 195 | 113.5–300 | 434.6 |
| MOVE | 89.89 | 70 | 40–115 | 170 |
| OTHER | 197.98 | 150 | 70–270 | 440 |

All-adult daily medians are SLEEP 480, WORK 0, EAT 60, LEISURE 290, MOVE 60, OTHER 210. Weighted all-adult means are respectively 494.16, 227.94, 67.86, 307.70, 87.12, 255.23; details and quantiles are in `weighted_daily_activity_duration.csv`. The 24-hour all-adult WORK median of zero is not an error: employed status and workday are different concepts.

## Start-Time Distributions

`start_time_histogram.csv` has all 48 half-hour *clock* bins for Core5 and three subsets. The generic stats function now reads each diary's start-clock offset (NHAPS 0; ATUS retains default 240). The histogram counts starts of **merged** canonical episodes, not occupancy in each bin; it does not prescribe a schedule. The simulator's WORK 09:00–17:00 window and 06:00–24:00 run day differ from this midnight-to-midnight diary.

## Activity Transitions

`transition_counts.csv` and row-normalized `transition_probs.csv` use adjacent merged canonical episodes, so no self-transition remains. Top all-adult transitions: OTHER→MOVE 12,087; MOVE→OTHER 11,001; OTHER→LEISURE 6,560; SLEEP→OTHER 6,551; OTHER→EAT 6,487; MOVE→LEISURE 6,298; LEISURE→OTHER 5,858; LEISURE→MOVE 5,464; LEISURE→SLEEP 4,702; EAT→LEISURE 4,452. The complete ranked Top 30 is in `top_transitions.csv` and `summary.md`. OTHER aggregates heterogeneous domains; those transition edges are not a single behavioral mechanism.

## Location Findings

Actual `eloc` codes provide activity × source-location diagnostics in `activity_location.csv`: WORK at workplace 1,228,327 minutes (own home 69,295); EAT at own home 340,638 and restaurant/cafe/bar 111,596; LEISURE at own home 1,835,618; MOVE at travelling 611,547. These are unweighted time totals and the source's harmonized locations, **not** simulator `office/home/restaurant` entities. Location, transport mode, and co-presence are available for later research; this phase only analyzes location and preserves no new simulator rule.

## Top OTHER Categories

All-adult valid-diary minutes: (1) wash/dress/personal care 331,467; (2) cleaning 298,093; (3) food preparation/cooking 212,865; (4) purchase consumer durables 124,664; (5) other domestic work 94,824; (6) worship/religious acts 77,424; (7) laundry/ironing/clothing repair 68,816; (8) home/vehicle repair 67,088; (9) regular education 60,517; (10) writing by hand 59,207. Full Top 30 with code, episode count, minutes, and mapping confidence is in `top_other_categories.csv`. Cooking is preparation, not eating; purchased goods are not travel. The salient missing domains are personal care and household work, with caregiving/education present at smaller volumes. These are **candidate** domains only; no Action is added.

## Core5 Simulator Coverage

The five labels cover 82.17% of valid adult minutes, leaving 17.83% or 1,884,764 minutes outside Core5; they cover only two-thirds of raw episode count. Consequently Core5 alone is useful for a behavior-structure corpus pilot, but cannot represent a complete adult day faithfully. OTHER is intentional and must not be interpreted as simulator idle/failure.

## Simulator vs Empirical Parameters

Read-only baseline from `src/social_sim/daily/time.py`: timed SLEEP 360 min, WORK 90 min, LEISURE 60 min; `rules/eating.py` EAT is instantaneous, and the simulator runs 06:00–24:00. Compare to the **employed-weekday, merged-episode** IQR only:

| Action | Current timed session | Empirical merged-episode median [p25,p75] | Status | Current 24-hour daily emergent vs empirical daily |
|---|---:|---:|---|---|
| SLEEP | 360 | 240 [105,360] | WITHIN_EMPIRICAL_IQR | NOT_COMPARABLE: 18h sim day; midnight split |
| WORK | 90 | 270 [180,460] | BELOW_EMPIRICAL_IQR | NOT_COMPARABLE: no like-for-like matched 24h population estimate |
| EAT | instantaneous | 30 [15,45] | NOT_COMPARABLE | NOT_COMPARABLE: no timed EAT session |
| LEISURE | 60 | 80 [40,150] | WITHIN_EMPIRICAL_IQR | NOT_COMPARABLE: 18h sim day |

The 360-minute SLEEP value merely touches the upper episode IQR bound; daily employed-weekday sleep median is 465 minutes. WORK's 90-minute session is shorter than the empirical merged episode p25, but separate sessions and the different work-window mechanics prevent direct parameter replacement. Empirical MOVE median 15 minutes has no comparable fixed-session baseline. No parameter was changed.

## BehaviorCorpus Sizes

**BALL=7,341**, B100=100, B1000=1,000, fixed seed 2025; B100 ⊂ B1000 ⊂ BALL, without replacement. `behavior_days.jsonl` contains the merged sequence, episode diversity, transitions, IDs and metadata. Survey IDs stay only in ignored local data/run artifacts; there is no reidentification. No B10K is possible without repeating diaries. These tiers are candidates for later B0/B100/B1000/BALL research, not an A2 experiment here.

## Calibration Boundary

Layer A hard world rules (money, inventory, valid location, seller presence, state consistency) stay deterministic. Layer B may later consider episode/daily durations, start-time and transition priors, and location association as *candidates*. Layer C remains model-driven choice. The report and `calibration_candidates.json` are observations, not an automatic schedule or production settings. LLM calls=0; no RuleEngine, ActionType, or upstream AgentSociety core was changed.

## Limitations

NHAPS is 1992–94 U.S. adults, not global or 2026 time use. Harmonized categories and imputed rows are not equivalent to executable behaviors; mapping medium-confidence sports/media/social and work-break codes affects coverage, and OTHER is heterogeneous. Survey weighting is a first-pass descriptive `recwght` calculation without complex design uncertainty; zero-weight quality cases remain in unweighted figures. The 173 age-missing records are excluded, and all 7,341 retained diaries are complete, but completeness does not guarantee substantive diary quality. Midnight splitting affects SLEEP episodes. Day-level allocation cannot be directly compared with a simulator running only 06:00–24:00. No claim that agents behave like humans or that larger corpus size reduces idle is justified.

## Recommendations for Research A2

Use B0/B100/B1000/BALL as *candidate* corpus sizes only after separately approving experiment design. Preserve real diary diversity rather than weight-duplicating trajectories. Carry OTHER and the missing personal-care/household-work diagnosis into evaluation; do not silently relabel them to improve coverage. Evaluate session semantics before calibrating WORK or SLEEP. Stop here; no retrieval, LLM, new action, or A2 trial is performed.

## Direct answers

Q1: Core5 covers **82.17%** of all valid adult minutes (and 66.64% of raw episodes). Q2: Personal care, cleaning, cooking, purchases, and other domestic work lead OTHER. Q3: Yes—personal care and household work are major missing daily domains; no new action is introduced. Q4: Timed WORK 90 min is **BELOW_EMPIRICAL_IQR**, SLEEP 360 and LEISURE 60 are **WITHIN_EMPIRICAL_IQR** on the merged-session comparison, and EAT is **NOT_COMPARABLE**. Q5: **7,341** valid BehaviorDay records. Q6: B100, B1000, and BALL=7,341 are all feasible nested samples.

Reproduce from the integration checkout, with the repository's environment: `python scripts/download_nhaps_ahtus_1992_94.py --dry-run`, then `python scripts/download_nhaps_ahtus_1992_94.py`, followed by `uv run --with-requirements ../../scripts/requirements-human-data.txt --frozen python ../../scripts/inspect_nhaps_ahtus_schema.py` and `uv run --with-requirements ../../scripts/requirements-human-data.txt --frozen python ../../scripts/build_nhaps_ahtus_behavior_corpus.py` when located in `third_party/AgentSociety`. The raw source and all generated outputs are ignored; the report, adapter, mapping, tests, and scripts remain integration-owned.
