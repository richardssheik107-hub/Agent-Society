# Phase 6.5 — Real Closed Loop Acceptance

## Goal and architecture

The acceptance target is one bounded, real-model-driven lunch loop. Alice receives only the short goal `reduce hunger by obtaining and eating a meal`. The model proposes one action per decision; deterministic Python validates and applies it. The model never edits world state.

`WorldState → ObservationBuilder → ContextCompiler → real DecisionClient (one call) → DecisionProposal → ActionIntent → RuleEngine → StateReducer → DomainEvent → new WorldState → new Observation`

The real adapter and the scripted test adapter use the same `CompactDecisionService`, `ClosedLoopStep`, `LunchScenarioRunner`, observation, context, rules, reducer, and event log. Only the `DecisionClient` changes. AgentSociety is initialized and closed with `RuleWorldEnv` and `DeterministicRouter`; no `PersonAgent`, `society.ask()`, ReAct, or `CodeGenRouter` is used. The AgentSociety lifecycle is not the source of subsequent observations: each decision step builds its observation from the latest domain `WorldState`.

## Fixed setup and budgets

Alice begins at `home` with money `100.0`, hunger `0.8`, and no meal. The restaurant has ten meals at `20.0` each. Locations are `home`, `park`, and `restaurant`. The available actions are `WAIT`, `REST`, `MOVE`, `BUY`, and `EAT`; the compact target candidates are the three locations and `meal`. No rule preconditions or scripted action sequence are put in the prompt.

The terminal condition is a deterministic check of `hunger <= 0.2` and `meal inventory == 0`. There are at most five decisions, at most one provider POST per decision, no repair call, no retry, a 60-second request timeout, `max_tokens=64`, and `temperature=0`. The configured hard character budgets are context `< 2000` and prompt `< 3000`; recent events are limited to three. The real attempt stopped before it emitted its character measurements, so those budgets were not empirically checked in that attempt. A valid but rule-rejected action would create a rejection event and continue; an invalid model response stops immediately. Five valid decisions without the terminal condition would print `REAL CLOSED LOOP NOT COMPLETED` and exit 0, explicitly distinct from completion.

## Verification and actual real run

Before the real run, the full offline suite passed: **174 passed**, including six new network-free runner tests for scripted completion, rejection/event feedback, updated-world observation, five-decision cap, invalid output, and timeout without retry. The existing three-action scripted lunch path still reaches hunger `0.2`, meal inventory `0`, money `80.0`, and restaurant stock `9`.

Exactly one real smoke was run on 2026-09-16. AgentSociety initialized successfully with the deterministic router. The first real DecisionClient request returned normally from the provider adapter, but the returned completion text had **0 characters**. The HTTP status and response usage fields were not retained. `DecisionParser` rejected the empty text as invalid JSON before producing a proposal. The run stopped immediately: no second provider request, no rule execution, no event, and no world-state change. AgentSociety closed successfully. The process exited with code 1. Its **observed** terminal marker was `PHASE 6.5 INCOMPLETE: INVALID_MODEL_OUTPUT`. After the run, only the local smoke's category label was changed to the requested `INVALID_JSON`; this did not change the observed result and did not modify upstream. The run was not repeated because an invalid response is explicitly a stop condition, not a JSON-repair opportunity.

During startup, LiteLLM warned that fetching its public model-cost map timed out and fell back to a local copy. That warning was not a decision-model request or a retry of the one provider POST.

Commands used from `third_party/AgentSociety` (no credentials are included):

```text
PYTHONPATH=/home/fergeson/projects/agent-society/src uv run --frozen python -m pytest /home/fergeson/projects/agent-society/tests -q
PYTHONPATH=/home/fergeson/projects/agent-society/src uv run --frozen --env-file .env python ../../smoke/real_lunch_closed_loop.py
```

The safe terminal excerpt from that single real run was:

```text
AGENTSOCIETY_INIT_OK
LLM_CALL_START
LLM_CALL_END
PHASE 6.5 INCOMPLETE: INVALID_MODEL_OUTPUT
LAST_SUCCESSFUL_STEP=0
FAILED_DECISION_ATTEMPT=1
ERROR_TYPE=DecisionParseError
ERROR_SUMMARY=Invalid decision JSON: Expecting value: line 1 column 1 (char 0)
RAW_OUTPUT_CHARS=0
AGENTSOCIETY_CLOSE_OK
TOTAL_DECISIONS=1
APPLICATION_LLM_CALLS=1
PROVIDER_ATTEMPTS=1
EVENT_COUNT=0
ENV_LLM_CALLS=0
RULE_LLM_CALLS=0
REDUCER_LLM_CALLS=0
EVENT_LLM_CALLS=0
```

| Measure | Observed result |
| --- | --- |
| Decision sequence | Attempt 1: empty completion; no valid action or target |
| Accepted / rejected rule results | 0 / 0; the parser stopped before rules |
| Events | 0 |
| Final state | `home`, money `100.0`, hunger `0.8`, meal `0`, restaurant stock `10` |
| Application decision calls | 1 |
| Provider POST attempts | 1 |
| Environment / rule / reducer / event LLM calls | `0 / 0 / 0 / 0` |
| Decision latency and provider tokens | Not captured for the failed parse; no extra request was made to obtain them |
| Real-run context / prompt character counts | Not emitted because the decision failed before `DecisionResult`; the offline tests validate both budgets on valid replies |
| World and rejection feedback in the real run | Not exercised: there was no valid proposal or event |

This is **not** a model policy failing to finish a valid five-step loop: the first response could not be parsed. It is also **not** a successful real-model-driven closed-loop acceptance, because no deterministic state transition or second observation occurred. The narrower evidence is that lifecycle, single-call accounting, no-retry behavior, parser stop, cleanup, and zero environment LLM usage worked. The response's cause cannot be established from the retained safe metrics; an output-token cap or provider behavior is a hypothesis, not a finding. No API key, authorization header, full prompt, or hidden reasoning is stored here.

The next real-provider attempt should be a separately authorized run. Before it, record failed-call elapsed time, context/prompt character counts before parsing, raw text length, and any usage already present in the same response—without logging the prompt, response reasoning, key, or headers. Investigate why this provider returned an empty completion before changing the generation budget. Acceptance then requires a valid proposal, deterministic rule/event/state transition, a subsequent observation of that state, and eventually the terminal condition within five decisions; otherwise report the precise failure without an automatic repair request. This phase did not commit or push changes, and it made no upstream code changes.

## Provider Contract Diagnosis (Phase 6.5A)

The original symptom was one successful provider request whose final `message.content` had length 0. The original adapter used Chat Completions at `/chat/completions`, read only `choices[0].message.content`, and sent `max_tokens=64`, `temperature=0`, `stream=false`, `n=1`, without an explicit thinking setting. Phase 2 used that same 64-token cap and obtained a 39-character valid JSON decision, with 134 input tokens, 64 output tokens, and 2.872 seconds latency. Because the reported output token count equaled the configured cap, **POSSIBLE_OUTPUT_BUDGET_EXHAUSTION** is a hypothesis; the old run retained no `finish_reason` or reasoning-token breakdown, so it is not a diagnosis.

| Attempt | Thinking / output cap | Actual result |
| --- | --- | --- |
| Phase 2 historical decision | Unspecified / `max_tokens=64` | Valid 39-character JSON; 64 output tokens |
| Phase 6.5 lunch | Unspecified / `max_tokens=64` | Final content length 0; parser stopped; state unchanged |
| Phase 6.5A contract | Requested disabled / `max_tokens=128` | HTTP 400; no completion envelope or parser input |

The adapter now retains only safe Chat Completions envelope metadata before parsing: HTTP status, response-ID presence, returned model, choice count, finish reason, final-content type/length, reasoning/refusal field presence and lengths, tool-call count, and numeric usage. It never parses reasoning as a proposal, logs reasoning text, or adds diagnostics to context. Empty final content, budget exhaustion, refusal, tool calls, no choices, invalid JSON/action, and schema mismatch have distinct categories. Failed-call latency is measured independently of parsing. The provider-specific diagnostic setting `thinking={"type":"disabled"}` stays in the adapter; the output cap for this attempt was `max_tokens=128`, with temperature 0 and no retry. The [official Ark Chat SDK schema](https://pkg.go.dev/github.com/volcengine/ark-runtime-go/arkruntime/model/chat) lists both `thinking` and `max_tokens`. However, [Volcengine distinguishes the Coding Plan endpoint from its ordinary Chat API](https://developer.volcengine.com/articles/7615528054736945158), and its `ark-code-latest` alias can point to a changing model. Support for this exact parameter combination on this alias was therefore a diagnostic question, not a guaranteed fix.

After **182 offline tests passed**, `provider_contract_smoke.py` was run **once**. A ninth offline contract test was added afterward; the final full suite is **183 passed**. The smoke compiled a 246-character context and 533-character prompt, made one application/provider request, and stopped on HTTP 400 after 0.324 seconds. No Chat Completions choices envelope was available, so the parser was not reached and no proposal was produced. Safe observed values:

| Field | Phase 6.5A contract attempt |
| --- | --- |
| Requested model / API mode | `ark-code-latest` / Chat Completions |
| Thinking / max output setting | `disabled` / `max_tokens=128` |
| HTTP status | `400` |
| Application / provider requests | `1 / 1` |
| Returned model, response ID, choices count | unavailable; no completion envelope |
| Finish reason, final-content type/characters | unavailable; **not** measured as zero |
| Reasoning/refusal presence and characters, tool calls | unavailable; no completion message |
| Input/output/total/reasoning tokens | unavailable |
| Request start/end (UTC) | `2026-09-16 09:54:35.002158` / `09:54:35.326228` |
| Decision latency | `0.324` seconds |
| Parser reached | No |
| Contract smoke | **FAIL — HTTP 400 provider rejection** |
| Real lunch rerun | **NOT RUN**; contract did not pass |

The observed HTTP 400 proves only that this request was rejected. It does **not** identify whether `thinking=disabled`, the 128-token setting, the dynamic model behind the alias, or another request constraint caused the rejection. The attempt did not retain a safe provider error code/type/parameter, and the response body must not be inferred from its status. After this run, the adapter was improved to retain only short, enum-like error identifiers (never the provider error message) for a future separately authorized request; that post-run edit does not retroactively supply this attempt's missing fields. The minimal next action is to inspect those safe identifiers on a **newly authorized single contract request** or the provider's own diagnostic record, then adjust only the confirmed incompatible adapter parameter. Do not run the lunch loop until the contract smoke passes. No further real-provider request, commit, push, or upstream edit occurred in Phase 6.5A.

## Minimal Provider Contract (Phase 6.5B)

The following is a later result; the preceding Phase 6.5/6.5A sections preserve what was known at those earlier times. The effective decision base URL was already the Coding Plan endpoint `https://ark.cn-beijing.volces.com/api/coding/v3`, so no endpoint mismatch was found. Credential provenance could not be verified locally and remains `UNKNOWN`. AgentSociety's own configuration was not changed; the decision adapter now supports dedicated `DECISION_LLM_*` variables with a legacy fallback.

One minimal request sent **only `model` and `messages`**—no thinking, temperature, output cap, stream, tools, or other optional body fields. It returned HTTP 200 with one choice, `finish_reason=stop`, 31 final-content characters, and a valid `WAIT` proposal. The requested alias was `ark-code-latest`; the returned model was `glm-5.3`. Latency was 4.119 seconds; usage was 44 input, 147 output, and 136 reasoning tokens. The reasoning field was present (656 characters), but its text was neither logged nor parsed. The parser passed. This establishes basic endpoint/model/auth/final-text compatibility for that minimal contract; it does not identify which optional field caused the earlier HTTP 400. The real lunch was not run in Phase 6.5B.

## Real Lunch Attempt (Phase 6.5C)

**PHASE 6.5 REAL CLOSED LOOP COMPLETE. This is the first real-model-driven closed-loop acceptance.** The existing `OpenAICompatibleDecisionClient` used the previously proven minimal `model`+`messages` request body, with no optional provider parameters. `CompactDecisionService`, `ClosedLoopStep`, `LunchScenarioRunner`, the rules, reducer, and event log were the same components used by the scripted brain. The model saw only the short goal, local observations, the `MOVE`/`BUY`/`EAT` capabilities, compact target IDs, and up to three compact events—not a prescribed action order or rule preconditions.

This Phase 6.5C run deliberately superseded the **request settings** in the historical Phase 6.5A section: no thinking switch, temperature, or token cap was sent. It also narrowed the historical five-action set by removing the unimplemented `WAIT` and `REST` capabilities; the RuleEngine itself was not changed.

`Observation → Real LLM → Proposal → Deterministic Rule → State → Event → New Observation`

The full offline suite passed before the sole Phase 6.5C real run: **210 passed**. The initial state was Alice at `home`, money `100.0`, hunger `0.8`, meal inventory `0`; restaurant meal price `20.0`, stock `10`. The bounded real run ended after three decisions, before the five-decision cap:

| Step | Observation before | Proposal | Rule / event | Changed fields | World after |
| --- | --- | --- | --- | --- | --- |
| 1 | `home`, money 100, hunger 0.8, meal 0 | `MOVE restaurant` | accepted / `MOVED` | location only | `restaurant`, money 100, hunger 0.8, meal 0, stock 10 |
| 2 | `restaurant`, money 100, hunger 0.8, meal 0; recent `MOVED:restaurant` | `BUY meal` | accepted / `PURCHASED` | money, inventory, restaurant stock | `restaurant`, money 80, hunger 0.8, meal 1, stock 9 |
| 3 | `restaurant`, money 80, hunger 0.8, meal 1; recent `MOVED:restaurant`, `PURCHASED:meal` | `EAT meal` | accepted / `ATE` | hunger, inventory | `restaurant`, money 80, hunger 0.2, meal 0, stock 9 |

All three response envelopes had HTTP 200, one choice, returned model `glm-5.3`, and `finish_reason=stop`. Safe per-step measurements, in decision order:

| Metric | Steps 1, 2, 3 |
| --- | --- |
| Context characters | `232, 301, 334` |
| Prompt characters | `519, 588, 621` |
| Decision latency, seconds | `3.911, 5.192, 3.919` |
| Input tokens | `155, 176, 188` |
| Output tokens | `98, 136, 167` |
| Reasoning tokens | `87, 125, 155` |
| Reasoning field characters (metadata only) | `362, 580, 679` |
| Visible final-content characters | `39, 32, 32` |

The world-mutation audit found exactly the action-specific fields shown in the step table and no extra changes. Each next observation matched `ObservationBuilder`'s local projection of the newly reduced `WorldState`; compact events reached the next decision context. The final observation showed hunger `0.2` and meal inventory `0`. Python—not the model—evaluated the terminal condition and stopped without a fourth request. World feedback: **PASS**.

This safe condensed transcript summarizes the sole real run's terminal output (the `STEP` lines combine several original log lines):

```text
REQUEST_CONTRACT=model+messages only
STEP 1: MOVE restaurant | ACCEPTED | MOVED | CHANGED_FIELDS=["location"]
STEP 2: BUY meal        | ACCEPTED | PURCHASED | CHANGED_FIELDS=["inventory","money","restaurant_stock"]
STEP 3: EAT meal        | ACCEPTED | ATE | CHANGED_FIELDS=["hunger","inventory"]
PHASE 6.5 REAL CLOSED LOOP COMPLETE
GOAL_REACHED=YES
WORLD_FEEDBACK=PASS
AGENTSOCIETY_CLOSE_OK
TOTAL_DECISIONS=3
APPLICATION_LLM_CALLS=3
PROVIDER_ATTEMPTS=3
FINAL_STATE={"location":"restaurant","money":80.0,"hunger":0.2,"meal":0,"restaurant_stock":9}
EVENT_COUNT=3
ENV_LLM_CALLS=0
RULE_LLM_CALLS=0
REDUCER_LLM_CALLS=0
EVENT_LLM_CALLS=0
```

The existing `ObservationBuilder` projects local offer **price and availability**, not numeric stock. The restaurant stock `9` above was checked against objective `WorldState` after BUY; the model's next local observation showed the meal remained available, alongside money `80` and meal inventory `1`. No observation semantics were changed for this smoke.

Application decision calls = **3**; provider POST attempts = **3**; event count = **3**; environment, rule, reducer, and event-generation LLM calls = **0, 0, 0, 0**. AgentSociety init and close both succeeded. No `society.ask()`, PersonAgent execution, ReAct, CodeGenRouter, extra model summary, retry, commit, push, or upstream edit occurred. The older empty-content and HTTP 400 diagnoses above remain historical observations; the successful minimal contract and this real loop do not prove which earlier optional parameter caused the HTTP 400.
