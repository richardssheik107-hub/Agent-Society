# Phase 1 — Custom Read-Only World

## Goal

Introduce a minimal deterministic source of world facts for one Alice and a read-only AgentSociety environment adapter. The original Phase 1 smoke attempted to obtain Alice's natural-language account through `CodeGenRouter` and upstream `PersonAgent`; that acceptance path was stopped after diagnosing LLM latency during router initialization. Phase 1B replaces environment-side LLM work with a deterministic observation path, verified by a separate zero-LLM runtime smoke.

## Files added

- `src/social_sim/world/state.py`: `PersonWorldState` and `WorldState`.
- `src/social_sim/world/env.py`: `RuleWorldEnv`.
- `tests/test_world_observation.py`: seven local unit cases (including three validation parameter cases).
- `smoke/custom_world_smoke.py`: the original CodeGenRouter-based diagnostic smoke, retained as evidence, not the Phase 1B acceptance smoke.

Phase 1B adds `ObservationBuilder`/`LocalObservation`, `DeterministicRouter`, `ContextCompiler`, their tests, and `smoke/deterministic_world_smoke.py`. See [8B architecture](architecture_8b.md) for the design and phase boundary.

## World model

The fixture time is `2026-01-01T00:00:00+00:00`. Alice has `agent_id=1`, `location="home"`, `money=100.0`, and `hunger=0.8`. `PersonWorldState` is frozen and rejects negative money or hunger outside `[0, 1]`. `WorldState` is frozen, stores person records privately, returns a copy of its `people` mapping, and raises `ValueError` for an unknown ID. It is the objective source of truth; Alice's profile contains only her name and does not duplicate these world facts.

## EnvBase integration

`RuleWorldEnv` derives from upstream `EnvBase`. The Phase 1 adapter has one `@tool(readonly=True, kind="observe")` method, `observe_person(agent_id)`. It has no mutation API or statistics tool. Its `step` updates only the adapter's time field, not `WorldState`. The original method read a single person from `WorldState`; Phase 1B routes selection through `ObservationBuilder` so the environment does not assemble model-visible state directly. No upstream `EnvBase` or router source is changed.

## Observation schema

The direct Phase 1 observation for Alice is:

```json
{"agent_id":1,"time":"2026-01-01T00:00:00+00:00","location":"home","money":100.0,"hunger":0.8}
```

The original adapter returns a structured `unknown_agent_id` error for an unknown request; `WorldState.get_person()` itself raises `ValueError`. Phase 1B's `ObservationBuilder` is specified to fail explicitly for an unknown ID. No full `people` mapping, RuleSet, memory, history, or debug metadata belongs in a `LocalObservation`.

## Unit tests

The pre-Phase 1B run passed **7 tests**: Alice initialization, exact structured observation, observation without world mutation, explicit unknown-agent behavior, and three invalid money/hunger parameter cases. These tests are local and do not make an LLM request. They were preserved in the Phase 1B suite. The final unified Phase 1B run passed **25 tests** in **3.98 seconds** (exit `0`), with three upstream SWIG deprecation warnings and no failing tests.

## Smoke test

The original `smoke/custom_world_smoke.py` created a real `AgentSociety` with one Alice, `RuleWorldEnv`, and `CodeGenRouter`. Its direct observation assertion passed and printed `DIRECT_OBSERVE_OK`; the snapshot was equal immediately before and after this direct call. It then entered `society.init()` and never reached `INIT_OK` or `society.ask()`. The call was actively interrupted after the slow statistics-generation request; the `finally` block ran `society.close()` and printed `CLOSE_OK`. Therefore this run cannot prove Alice's environment tool use, her natural-language answer, or full-society before/after equality.

The Phase 1B acceptance smoke is instead `smoke/deterministic_world_smoke.py`: real `AgentSociety` initialization and close with `DeterministicRouter`, direct observation, deterministic statistics, fixed world description, zero router LLM calls, and a before/after world snapshot. It deliberately does **not** invoke `society.ask()` or upstream ReAct. The run exited **0** and printed `WORLD_INIT_OK`, `ROUTER_INIT_OK`, `AGENTSOCIETY_INIT_OK`, `DIRECT_OBSERVE_OK`, `STATISTICS_OK`, `WORLD_DESCRIPTION_OK`, `COMPACT_CONTEXT_CHARS: 107`, `ROUTER_LLM_CALLS: 0`, `ZERO_ROUTER_LLM_CALLS_OK`, `WORLD_STATE_UNCHANGED`, and `CLOSE_OK`. This verifies the deterministic environment path without a model request; it does not verify a future local-8B decision agent.

## Actual Alice response

No Alice response was obtained in the custom-world smoke: initialization did not complete. The earlier Phase 0 Alice name response used `SimpleSocialSpace`, not this custom world, and is not evidence for custom-world observation.

## State before/after

For the verified original direct observation, the before and after snapshots were equal: time `2026-01-01T00:00:00+00:00`, Alice at `home`, money `100.0`, hunger `0.8`. The original full smoke stopped before Alice's answer, so it does not provide a full-run state-equality result. The Phase 1B smoke independently asserted `snapshot_before == snapshot_after` across deterministic router use and AgentSociety initialization/close. Both snapshots held time `2026-01-01T00:00:00+00:00`, Alice id `1` at `home`, money `100.0`, hunger `0.8`; `WORLD_STATE_UNCHANGED` printed.

## Problems

### CodeGenRouter initialization latency

- **Symptom:** `society.init()` did not return. The last successful business log was `Generated observe code using LLM` at approximately 16:20:31 Beijing time. The process was interrupted during statistics code generation; it then printed `CLOSE_OK`.
- **Root cause / call chain:** `society.init() -> CodeGenRouter.init() -> statistics code generation -> LLMClient(coder) -> network read wait`. This occurred before PersonAgent's LLM call, `ask_env`, Alice's tool execution, or `society.ask()`.
- **Observed attempts:** Two logical router LLM calls were identified: observe-code generation completed between approximately 16:19:53 and 16:20:31; statistics generation began around 16:20:32. Its first attempt timed out after approximately 300.1 seconds, logged as `attempt 1/11`; a second attempt began at 16:25:32 and was interrupted around 16:26:06. This proves at least three application-level attempts, not an exact count of underlying HTTP requests. No 429 was observed. LiteLLM separately warned that downloading its public model-cost map timed out and fell back to a local copy.
- **Fix / architectural decision:** Do not continue waiting for or modifying upstream code generation. Replace environment routing with a deterministic integration-owned router, observation builder, and fixed world description. Keep CodeGenRouter available upstream.
- **Verification:** The blocked process exited after deliberate interruption, with `finally` cleanup and `CLOSE_OK`; the seven original unit tests and `DIRECT_OBSERVE_OK` remained valid. The separate Phase 1B deterministic smoke subsequently passed with zero router LLM calls; the expanded unified suite passed 25 tests.

The smoke's `max_react_turns` configuration was `3`, but Alice never entered ReAct. During the network wait, the process had an established HTTPS connection and low cumulative CPU use; the collected evidence did not prove continuous data transfer.

## CodeGenRouter evaluation

| Item | Result |
| --- | --- |
| `WorldState` | PASS in local unit tests |
| Direct read-only observation | PASS (`DIRECT_OBSERVE_OK`, state unchanged for direct call) |
| Phase 1 unit tests | PASS (7) |
| Custom-world CodeGenRouter smoke | INCOMPLETE before `society.init()` returned |
| Final environment architecture | CodeGenRouter rejected for this target; deterministic router selected |

CodeGenRouter is **valid upstream behavior but unsuitable for our target constraints**. Its environment initialization uses LLM-generated observe and statistics code, and its default world-description path can use an LLM. This latency and multiplicity of model calls are incompatible with a slow local 8B target and the architecture's at-most-one-LLM-call-per-decision rule. It is not described as broken, deleted, or patched. Upstream PersonAgent ReAct is likewise a valid capability but not the selected final local-8B decision path.

## Final status

Original Phase 1 custom-world smoke: **incomplete due to router LLM latency**. `WorldState`, direct observation, and seven original local tests passed. The separate **Phase 1B deterministic path is complete**: 25 unified tests passed; AgentSociety init/close worked; router LLM calls were `0`; compiled context was `107` characters; and the full smoke's world snapshot was unchanged. `git -C third_party/AgentSociety status --short` and `git -C third_party/AgentSociety diff --stat` produced no output, confirming upstream tracked code remained clean. RuleEngine, ActionIntent execution, StateReducer, and the local-8B decision agent are not started in this phase.
