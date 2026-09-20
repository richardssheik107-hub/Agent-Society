# Research B1 — ATUS behavior calibration pilot

**Status: RESEARCH B1 INCOMPLETE — DATA ACCESS (2026-09-17).** The [official 2025 BLS file page](https://www.bls.gov/tus/data/datafiles-2025.htm) and the [2025 interview dictionary](https://www.bls.gov/tus/dictionaries/atusintcodebk25.pdf) were readable, but direct retrieval of the official Activity ZIP returned HTTP 403 (Akamai). The scripted WSL request, Windows `curl`/web request, and official alternate BLS host checks did not yield a ZIP; the in-app browser check was unavailable. No third-party mirror, synthetic row, or fabricated numerical result was substituted. All numerical sections below are intentionally pending.

## Research Question

Which behaviors are hard deterministic world rules, which parameters might be calibrated against real human diaries, and which decisions remain agent choices?

## Dataset Survey

See [dataset registry](research_b1_dataset_registry.md) and `config/human_behavior_datasets.yaml`. ATUS is the P0 diary source. AHTUS and GeoLife are P1 future historical/mobility checks. SocioPatterns workplace and hospital, and MTUS, are P2 contact/cross-country sources; none were downloaded.

## Why ATUS First

The BLS 2025 single-year release supplies episode-level activity, time, place, and respondent labor-force information in small public-use ZIPs. Its year-specific [coding lexicon](https://www.bls.gov/tus/lexicons/lexiconnoex2025.pdf) permits a transparent, conservative mapping. The pilot avoids multi-year files, weights, ATUS-CPS, and unrelated data collections. The intended result is descriptive and unweighted; it is not an official population estimate.

## ATUS 2025 Files Used

Required official files are Activity (`atusact-2025.zip`, approximately 1.8 MB), Respondent (`atusresp-2025.zip`, 0.4 MB), and Roster (`atusrost-2025.zip`, 0.08 MB). Roster is needed because `TEAGE` occurs there, not on Respondent. Who (`atuswho-2025.zip`, 0.4 MB) is included for schema inspection only. At present **none was downloaded**. The official dictionary identifies `TUCASEID`, `TUACTIVITY_N`, `TUACTDUR24`, `TUSTARTTIM`, `TUSTOPTIME`, `TUTIER1CODE`/`TUTIER2CODE`/`TUTIER3CODE`, and `TEWHERE` on Activity; `TELFS`, `TUDIARYDATE`, `TUDIARYDAY` on Respondent; `TULINENO`, `TEAGE` on Roster; and `TUWHO_CODE` on Who. Actual ZIP member headers remain unverified until download.

`TUACTDUR24` is the 24-hour-truncated duration; ATUS diary time runs 04:00–04:00. The loader uses cumulative durations on that axis and checks source clocks modulo midnight. It does not turn a cross-midnight sleep interval into a negative duration. Last-activity stop-time mismatch is allowed when the duration was truncated at 04:00, while other clock mismatches mark a diary invalid. Raw ZIPs are immutable. `SOURCE.json` records download date, URLs, sizes, and SHA256 after all official files succeed.

## Unified Human Activity Schema

`HumanActivityEpisode` has anonymous `person_id`/`day_id`, ordered index, start/end/duration minutes, raw code/label, separate `HumanActivityType`, raw place code and source. `HumanDayDiary` holds raw episodes, 24-hour total and basic age/employment/week metadata. `BehaviorDay` holds the canonical-merged sequence. Invalid totals, indexes, overlap, gaps and clock disagreement are recorded and excluded, never silently repaired. `HumanActivityType` is independent of executable `ActionType`.

## Mapping to Core Activities

Rules in `config/atus_activity_mapping.yaml` are based on the official 2025 lexicon. The following are **all** Core5 mapped prefixes. Longest-prefix matching applies. Any code not listed is OTHER.

| Canonical | Mapped ATUS code/prefix and official category |
|---|---|
| SLEEP | `010101` Sleeping. `010102` Sleeplessness and all other personal care remain OTHER. |
| WORK | `050101` Work, main job; `050102` Work, other job(s). Job search, job-associated eating/socializing, waiting and other income generation are not silently WORK. |
| EAT | `110101` Eating and drinking; `110199` Eating and drinking, n.e.c. Food preparation and waiting for food remain OTHER. |
| LEISURE | `1201` Socializing and communicating; `1202` Attending/hosting social events; `1203` Relaxing and leisure; `120401` Performing arts; `120402` Museums; `120403` Movies; `120404` Gambling establishments; `120499` Arts/entertainment n.e.c. Sport/exercise (`13`) remains OTHER pending separate judgment. |
| MOVE | `1801`–`1816` Travel related to the 16 lexicon purposes, and `1899` Traveling n.e.c. `1818` travel security procedures remain OTHER. `HumanActivityType.MOVE` is an empirical travel/time-use category, **not** an executable simulator transition. |

Each mapping stores label, rationale and high confidence. The `OTHER` label table preserves useful major-category names for later review without increasing coverage artificially.

## Mapping Coverage

Pending real Activity/Respondent/Roster rows. The ETL will report Core5 and OTHER ratios by both episode count and duration-weighted minutes for all valid adults and employed weekdays. `OTHER` is not simulator IDLE.

## Adult Sample

Pending. `TEAGE >= 18`, one ATUS respondent per case; no income, marriage, occupation, region or gender filtering. The ETL reports raw rows, unique cases, minors filtered, unmatched cases, adult diaries, rejected diaries, and valid 24-hour diary totals.

## Employed Weekday Sample

Pending. The year-specific dictionary defines `TELFS=1` as employed-at-work and `TELFS=2` as employed-absent, and `TUDIARYDAY=2..6` as Monday–Friday. This descriptive subset is closest to—but not equivalent to—the neutral office worker. It does not condition on actually working that day.

## Activity Durations

Pending. `activity_duration_stats.csv` will contain canonical-merged episode count, mean, median, p25, p75, p90 and p95 for each activity and sample. Canonical merge removes artificial self-transitions while retaining raw episode counts separately.

## Daily Time Allocation

Pending. `daily_duration_stats.csv` will include zero-minute days for activities not undertaken, with count, mean, median, p25 and p75. Daily totals are ATUS 24-hour minutes, not simulator 06:00–24:00 minutes.

## Start-Time Distribution

Pending. `start_time_histogram.csv` will contain 48 half-hour local-clock bins for each Core5 activity and sample, counted from canonical-merged episode starts.

## Activity Transitions

Pending. `transition_counts.csv` and `transition_probs.csv` will hold six-by-six matrices by sample. Probabilities are row-normalized descriptions, not a policy import. The report's top 20 transitions cannot be filled without real rows.

## Simulator vs ATUS

Current `UNCALIBRATED_BASELINE`: WORK 90-minute episode, LEISURE 60-minute episode, SLEEP 360-minute episode. ATUS median/IQR and status (`TOO_LOW`, `TOO_HIGH`, `WITHIN_EMPIRICAL_RANGE`) remain pending. Simulator EAT has no timed duration and is `NOT_COMPARABLE`. All **daily** comparisons are `NOT_COMPARABLE` without reconciling the simulator's 18-hour observation window to the ATUS 24-hour diary. No production value was modified.

## Top OTHER Activities

Pending. The ETL will write `top_other.json` with the 20 raw six-digit OTHER codes ranked by summed minutes, retaining a lexicon-level label; this is the ontology-gap review, not a mandate to add CHORES.

## Rule Calibration Boundary

See [boundary document](research_b1_rule_calibration_boundary.md). Hard world invariants stay deterministic; empirical durations/starts/transition/travel/contact distributions are candidate parameters; contextual action choices stay model-driven. No fixed-clock forced activity was introduced.

## Behavior Corpus

The `BehaviorCorpus` interface supports `len`, `get_day(day_id)` and deterministic `sample_days(n, seed)`. The same seeded shuffled order makes B100 ⊂ B1000 ⊂ B10K when enough natural valid diaries exist; no diary is copied or oversampled. The number of usable days, B100/B1000 availability and corpus JSONL remain pending. Retrieval of 1–3 relevant priors is a separate later design question.

## Limitations

ATUS is U.S.-only, self-reported, and this is a one-survey-year pilot. The Core5 mapping is coarse, and OTHER may contain important household work, care, education, shopping, sports and religious activity. Travel time is not the same as executable MOVE. Who-present is not calibrated pairwise interaction; there is no interaction calibration, no local 8B, and no claim of universal human behavior. Future numerical results will be unweighted descriptive sample statistics unless a separate weighting plan is made. Current limitation is stronger: no downloaded 2025 microdata, hence no observed sample statistics at all.

## Recommendations for Research A2

Do not start A2 until ATUS files are obtained and the real valid-day count and coverage are known. Candidate levels are B0, B100 if N≥100, B1000 if N≥1000, and BALL_2025. B10K is justified only if the single-year validated corpus naturally has at least 10,000 days. No retrieval, corpus-size experiment, local 8B or simulator parameter change is part of B1.

### Reproduction and current blocker

From the repository root, after official access works:

```bash
cd third_party/AgentSociety
uv run --frozen python ../../scripts/download_atus_2025.py
uv run --frozen python ../../scripts/build_atus_behavior_corpus.py
PYTHONPATH=../../src:../.. uv run --frozen pytest ../../tests -q
```

The first command currently fails on `https://www.bls.gov/tus/datafiles/atusact-2025.zip` with **HTTP 403 Forbidden**. Minimum next action: obtain the four ZIPs from the [official BLS 2025 page](https://www.bls.gov/tus/data/datafiles-2025.htm) through an allowed network/browser, place them unchanged under `data/external/atus/2025/raw/`, then rerun the download script to create/check `SOURCE.json` and run ETL. No third-party mirror is permitted.
