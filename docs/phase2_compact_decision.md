# Phase 2 — Compact Single-Call Decision

## Goal

Verified one manually triggered, compact decision: `WorldState -> ObservationBuilder -> ContextCompiler -> DecisionClient -> DecisionParser -> DecisionProposal`. The proposal records what Alice wants to do; it is not an action result. The model did not modify Alice's `location`, `money`, or `hunger`, or any other world fact.

This phase tests the decision layer directly. It does not call `PersonAgent.ask()`/`step()`, use ReAct or `CodeGenRouter`, or replace the Phase 1B `AgentSociety` + `RuleWorldEnv` + `DeterministicRouter` environment path. Environment routing and future rule validation use zero LLM calls.

## Architecture

`ObservationBuilder` selects Alice's local facts from `WorldState`. `ContextCompiler` serializes those facts, a tiny profile, and whitelisted available actions/target IDs into deterministic JSON. A thin `DecisionModelClient` interface takes the assembled compact prompt and returns raw model text. The current `OpenAICompatibleDecisionClient` is only a remote test adapter; its transport details do not belong in world, observation, context, or future rule code. `DecisionParser` deterministically validates the response and produces `DecisionProposal`. Parsing errors end the decision with an error, without another LLM request or a hidden `WAIT` fallback.

The adapter must remain replaceable by an OpenAI-compatible local server, vLLM, llama.cpp, Ollama, or another local inference endpoint without changing `WorldState`, `ObservationBuilder`, `ContextCompiler`, or future `RuleEngine` code. The Phase 2 smoke uses the existing Volcengine endpoint only to test this interface; it is not the target deployment architecture.

## Decision schema and action enum

The first version allows only `WAIT`, `REST`, and `MOVE`. `DecisionProposal` contains only `action` and optional `target: str | None`; there are no reasoning, plan, tool-call, world-update, or execution fields. A compact valid example is `{"action":"MOVE","target":"park"}`. `MOVE` requires a nonempty target ID from the available candidates; `WAIT` and `REST` require `target=null` or an omitted target. Unknown actions, extra fields, and malformed structures fail validation. `{"action":"REST","target":null}` expresses a wish, not a change in hunger.

## Context budget

The final local ~8B deployment targets approximately **2K input tokens or less**, but the model/tokenizer is not yet selected. Phase 2 therefore uses a model-independent character-count guard: the service configures `ContextCompiler` with a **2,000-character cap**, and the one-person smoke additionally checks **under 1,000 characters**. Oversize input is clipped only in documented noncritical free-text fields or rejected; it never silently expands into a long prompt. The smoke measured `context_chars=166`. A tokenizer-specific guard will be added when the deployment model is chosen.

## Prompt budget

The total `prompt_chars` counts system instruction, user prompt, schema instruction, and compiled context. Preferred length is **under 1,500 characters**; the hard implementation guard rejects **3,000 characters or more**. The prompt uses a short instruction to select one next action, return JSON only, and not explain. It contains no complete `WorldState`, `RuleSet`, tool schema, long memory, runtime description, environment source, or chain-of-thought request. The smoke measured `prompt_chars=445`.

## Output budget

Request a tiny JSON response such as `{"action":"WAIT","target":null}`. Preferred raw response is **under 100 characters**; an output above 500 characters is an `OUTPUT_TOO_VERBOSE_WARNING` even if parsable. The test adapter uses `max_tokens=64` and `temperature=0`; the smoke response was **39 characters**. The parser trims whitespace and accepts one simple JSON code fence; it does not infer actions from prose or ask the model to repair invalid JSON.

## Call-count rule

One `CompactDecisionService.decide(...)` invocation has exactly one application-level model call path and at most one logical LLM call. No parse-error repair call, model retry loop, ReAct turn, or tool-calling loop is allowed. The `httpx` adapter sends one Chat Completions POST with explicit **60-second timeout** and `AsyncHTTPTransport(retries=0)`; it does not add application retries. A failed or timed-out response remains a failure. Unit tests use a counting fake client and zero network calls. The real smoke triggered exactly one decision, not one decision per simulation tick.

## Unit test results

The unified local suite passed **69 tests** in **8.12 seconds**, with **3 warnings** and no failures. Coverage includes proposal validation, strict parser behavior, bounded deterministic context, one-call success and parser-failure paths, rejection of malformed target candidates before a model call, and the full fake-client pipeline with unchanged `WorldState`. The unit tests make **zero network requests**.

## Real smoke result

`smoke/compact_decision_smoke.py` exited **0** using the existing ignored `.env`. It printed `OBSERVATION_OK`, `CONTEXT_COMPILED_OK`, `DECISION_CALLS=1`, `DECISION_VALID`, `ENVIRONMENT_LLM_CALLS=0`, `WORLD_STATE_UNCHANGED`, and `PHASE2_SMOKE_OK`. The model proposed `MOVE` to `restaurant`; that result was validated, not executed. The smoke does not prescribe a preferred action: `WAIT`, `REST`, or a valid `MOVE` target may all pass.

| Measure | Actual result |
| --- | --- |
| `context_chars` | 166 |
| `prompt_chars` | 445 |
| `decision_call_count` (application level) | 1 |
| `decision_latency_seconds` | 2.872 |
| Raw output characters | 39 |
| Decision proposal | `{"action":"MOVE","target":"restaurant"}` |
| Provider input/output tokens | 134 / 64, as reported by provider |
| Environment LLM calls | 0 |
| Smoke exit code | 0 |

If model output is invalid, the smoke reports `INVALID_MODEL_OUTPUT` with only a safe short summary, performs no repair call, and fails. A parse failure must not be misreported as a successful fallback.

## World before / after

Both actual snapshots have time `2026-01-01T00:00:00+00:00` and Alice (`id=1`) at `home`, money `100.0`, hunger `0.8`. **Before == after: YES.** The smoke compared objective snapshots rather than inferring immutability from the model's text. No proposal was executed in this phase.

## Phase boundary

RuleEngine, ActionIntent execution, Effect, StateReducer, conflict resolution, inventory, economy, relationships, multi-agent interaction, and long-horizon planning are **not started**. Phase 3 may define deterministic execution separately; Phase 2 acceptance stopped after a valid tiny proposal from one call with an unchanged world.
