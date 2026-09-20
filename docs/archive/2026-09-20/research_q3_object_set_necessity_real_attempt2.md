# Research Q3 — Object Set Necessity: Real Experiment Attempt 2

Status: complete for the bounded real-pilot objective; no long-term claim is made.

## 1. Scope and decision rule

This report records the second provider-backed attempt at the Q3 object-set
necessity experiment. The question is deliberately narrow:

> Does a canonical object set improve single-step object selection
> executability and effect-field authority compared with unconstrained model
> naming, and does a hybrid open-world arm preserve the benefit while allowing
> novel objects?

The experiment compares three arms on the same deterministic scenario cases:

* **A — LLM_ONLY:** the model sees no catalog and names any concrete object.
* **B — CATALOG_TOPK:** the model chooses one of the retrieved catalog
  candidates.
* **C — HYBRID:** the model chooses a retrieved candidate or emits `NEW:<name>`
  with the complete required effect attributes.

The protocol is one structured decision per row:
`{"object":"...","attributes":{...}}`. There is no fuzzy repair or second
model call. Catalog attributes are authoritative; model-supplied attributes
for A and C-NEW are explicitly marked estimated and are only checked by a
bounded plausibility validator.

This is an engineering acceptance experiment, not a statistical population
study. The signal labels below use the existing benchmark thresholds and do not
mean statistical significance.

## 2. Provenance and preservation

* Branch: `research/object-set-necessity`
* Starting remote commit: `25db38f4306b68d79fe3db160a60e1189763b7a9`
* Attempt 1 was not reused or overwritten. Its 15-row HTTP-error artifact and
  its report remain at:
  `run/evaluation/object_set_necessity/real_20260918T033858277073Z/` and
  `docs/research_q3_object_set_necessity_real_result.md`.
* Attempt 2 uses a distinct `attempt_id=attempt_2` and writes under
  `run/evaluation/object_set_necessity/real_attempt_2_<timestamp>/`.
* No RuleEngine, WorldState, ActionType, A2 profile, upstream AgentSociety, or
  other production core behavior was changed.

## 3. Provider and safe diagnostics

The preflight connectivity probe used the existing secure `.env` source in
memory and the same minimal request contract as the pilot. It returned HTTP
200 from backend model `glm-5.3` in 1.54 seconds (22 input tokens, 13 output
tokens, 10 reasoning tokens) and returned the expected `OK` response. The
provider endpoint and secret value are intentionally not reproduced here.

Attempt 2 records only sanitized provider metadata on failure rows:
`http_status`, error code/type/parameter, request id, and a sanitized error
message. Raw prompts, raw completions, hidden reasoning, API keys, and other
credential material are not stored.

In the smoke run there were no HTTP errors, so status/error-code maps are empty.
The full run likewise had no HTTP errors. Successful responses identify
`glm-5.3`; timed-out requests have no invented backend attribution.

## 4. Offline capability gate

The offline capability probe passed before the real run:

* catalog size: 1,000 objects;
* generated rows: 180;
* A/B/C structured protocol and bounded attribute validation executed without
  network access;
* output marker: `OBJECT_SET_NECESSITY_OFFLINE_OK`;
* note: `SYSTEM_CAPABILITY_PROBE_NOT_MODEL_BEHAVIOR`.

The offline probe is a system-capability check only and is not included as model
behavior evidence.

## 5. Smoke gate (Attempt 2)

Artifact: `run/evaluation/object_set_necessity/real_attempt_2_20260918T061537054924Z/`.

The smoke scheduled 15 rows. Fourteen completed successfully and one timed out;
there were zero HTTP errors, parse errors, or architecture errors. Successful
rows used `glm-5.3`. The arm counts were A=5, B=4, C=5, with four matched ABC
scenario cases (12 matched rows).

The smoke gate passed: success rate met the gate, architecture errors were
zero, every successful B row was candidate-compliant and executable, and every
successful C row was either candidate-compliant or a valid NEW object.

Because the evaluator was tightened after this smoke to ensure that B never
counts catalog fields as model-estimated, the corrected, network-free summary
is recorded in `posthoc_summary.json` beside the original result. No provider
request was replayed and the original result is preserved.

| Arm | rows | runtime executable | usable effect coverage | authoritative coverage | model-estimated field rate | plausible attrs |
|---|---:|---:|---:|---:|---:|---:|
| A | 5 | 0.200000 | 0.733334 | 0.000000 | 1.000000 | 0.200000 |
| B | 4 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 |
| C | 5 | 0.800000 | 0.933333 | 0.200000 | 0.800000 | 0.800000 |

Matched smoke deltas (A minus B) were runtime `-0.75`, usable effect
coverage `-0.25`, and authoritative coverage `-1.00`. The smoke signal was
`object_set_necessity_signal=STRONG`; the hybrid signal remained
`UNRESOLVED`.

## 6. Full real pilot

Artifact: `run/evaluation/object_set_necessity/real_attempt_2_20260918T071513907540Z/`.

Configuration was two repetitions over the full 30-scenario matrix (5 domains
× 6 fixed states) and `top_k=10`, for 180 scheduled rows (30 scenarios × 3
arms × 2 repetitions). Results:

* success: 162;
* timeout: 18;
* HTTP error: 0;
* parse error: 0;
* architecture error: 0;
* successful backend model: `glm-5.3` (162 rows);
* matched ABC cases: 43 (129 matched rows).

### 6.1 Per-arm results

| Arm | successful rows | structured | runtime executable | usable effect coverage | authoritative coverage | model-estimated field rate | plausible attrs | candidate compliance | NEW rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — LLM_ONLY | 60 | 1.000000 | 0.283333 | 0.700000 | 0.000000 | 1.000000 | 0.283333 | 0.000000 | 0.000000 |
| B — CATALOG_TOPK | 51 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | 0.000000 |
| C — HYBRID | 51 | 1.000000 | 0.901961 | 0.967320 | 0.411765 | 0.588235 | 0.901961 | 0.411765 | 0.588235 |

The full matched-ABC metrics are:

| Arm | runtime executable | usable effect coverage | authoritative coverage | model-estimated field rate |
|---|---:|---:|---:|---:|
| A | 0.302326 | 0.728682 | 0.000000 | 1.000000 |
| B | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| C | 0.883721 | 0.961240 | 0.418605 | 0.581395 |

Matched A-minus-B deltas were runtime `-0.697674`, usable effect coverage
`-0.271318`, and authoritative coverage `-1.000000`.

For the direct B-versus-C hybrid comparison, B minus C was runtime `+0.116279`,
usable coverage `+0.038760`, and authoritative coverage `+0.581395`. Thus C
does allow novel objects, but it does not yet preserve the B runtime level.

### 6.2 Cost and latency

| Arm | mean input tokens | median input tokens | mean prompt chars | mean latency (s) |
|---|---:|---:|---:|---:|
| A | 121.566667 | 123.0 | 495.3 | 8.156149 |
| B | 366.901961 | 365.0 | 1041.568627 | 16.464719 |
| C | 382.019608 | 380.0 | 1124.098039 | 19.174707 |

The 18 timeouts are provider/runtime reliability observations for this run,
not parse or architecture failures. There was no retry in the pilot.

## 7. Interpretation

### Object-set necessity

The result is an engineering-level **STRONG** signal for the narrow
single-step question. Against the same matched cases, unconstrained A had a
0.697674 lower runtime-executable rate and a 0.271318 lower usable effect
coverage than catalog-constrained B. A also had zero authoritative effect
coverage, while B had 1.0. The canonical set therefore supplies both
resolvability and trusted effect fields in this benchmark.

This does not prove that a catalog is necessary for every agent task, nor does
it establish a causal or population-level effect beyond this synthetic pilot.

### Hybrid open-world status

The hybrid arm is **UNRESOLVED**, not accepted. It created/model-described
novel objects on 58.8235% of matched successful rows, but its matched runtime
rate was 0.883721 versus B's 1.0, a gap of 0.116279 and therefore above the
configured acceptance tolerance. The experiment supports continuing to treat
open-world creation as a separate engineering problem.

### Meaning of attribute metrics

“Authoritative” means the field came from the catalog record. “Model-estimated”
means it came from A or C-NEW. “Plausible” means only that the value passed the
bounded type/range validator; it is not a factual validation of the model's
claim. The synthetic catalog is intentionally deterministic and cannot stand in
for a real-world knowledge base.

## 8. Limitations and stop condition

The pilot has one provider, two repetitions, a single structured decision per
row, five object domains, and a synthetic 1,000-object catalog. It does not test
20-step identity/inventory/progress continuity, duplicate replay, long-horizon
state mutation, multi-agent interactions, or statistical uncertainty. Timeout
rows also do not identify a backend model. These limits prevent a long-term
necessity claim.

The current engineering decision is **STOP** for Q3 Attempt 2: preserve the
artifacts and report the result; do not launch Q5/R8 or infer long-term agent
behavior from this pilot. A future continuation would need a separately scoped
continuity experiment and an explicit hybrid acceptance criterion.

## 9. Verification and safety checklist

* Focused Q3 tests: 11 passed.
* Full regression: 485 passed, 3 existing deprecation warnings.
* Ruff: passed.
* Offline capability probe: passed.
* Attempt 1 artifact/report: preserved.
* Raw prompt/completion/hidden reasoning: not stored.
* Secrets/API keys: not printed or committed.
* Production core/upstream changes: none.
