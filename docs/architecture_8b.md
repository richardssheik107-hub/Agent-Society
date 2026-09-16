# 8B / Short-Context Architecture

## Status and scope

This is the target architecture for a local, approximately 8B-parameter model with limited context and inference speed. Phase 1B implemented the deterministic path from `WorldState` to a compact observation, plus a bounded `ContextCompiler`. Phase 2 verified a manually triggered, compact single-call decision that ends at a proposal; it does **not** implement rules, effects, or a replacement decision agent.

AgentSociety 2 remains the simulation runtime, clock, Ray execution, workspace, and replay infrastructure. Integration code lives under `src/social_sim/`; upstream `third_party/AgentSociety/` is not modified.

## Permanent constraints

1. One decision uses **at most one LLM call**. A tick without a new decision uses zero.
2. Target each model input at approximately **2K tokens or less**. Until the local model and tokenizer are selected, a model-independent character or UTF-8 byte cap is enforced; the minimal Phase 1B context should be below 1,500 characters.
3. Never put the full `WorldState` in the model context.
4. Never put the full `RuleSet` in the model context.
5. All real state mutation is performed by deterministic Python, never by an LLM response itself.

Observation, environment routing, statistics, action validation, state transitions, conflict resolution, clock advancement, and numeric updates must also be deterministic. The eventual model's only responsibility is to propose what to do next from a bounded local context.

## Target data flow

```text
WorldState (source of truth)
  -> ObservationBuilder -> LocalObservation
  -> DecisionTrigger (future; deterministic)
       no decision: 0 LLM calls
       new decision: ContextCompiler -> local 8B (<= 1 LLM call)
  -> tiny Decision Proposal (Phase 2; no execution)
  -> RuleEngine (future; deterministic validation)
  -> Effects (future; deterministic application)
  -> WorldState
```

This is **not** `every tick -> LLM`. A future trigger will decide deterministically whether a fresh decision is needed; Phase 2 triggers one decision manually. The response is small structured data such as `{"action":"REST","target":null}`. Free-text reasoning and chain-of-thought are neither requested nor exposed.

## Decision Contract

| Item | Contract |
| --- | --- |
| Input | A bounded compact context compiled from selected local observation, a tiny profile, and short action/target IDs; never the complete `WorldState`, `RuleSet`, or tool schema. |
| Output | `DecisionProposal` with only `action` (`WAIT`, `REST`, or `MOVE`) and optional `target`; this is a proposal, not an executed action. |
| LLM calls per decision | At most **1** application-level model call; no LLM-based output repair, application retry, ReAct, or tool-calling loop. |
| Environment LLM calls | **0**, including routing, observation, statistics, and world description. |
| Rule LLM calls | **0**; later validation and execution remain deterministic. |

The target deployment input is approximately **2K tokens or less**. Because the final tokenizer is unknown, Phase 2 guards input by character count: `CompactDecisionService` uses a **2,000-character context cap**, and the entire prompt—including system, user, and schema instructions—is preferably **under 1,500 characters**, with a hard guard rejecting 3,000 characters or more. When the local model is selected, add a tokenizer-specific check. The preferred decision response is **under 100 characters** of JSON only, with a small output-token limit. The prompt says not to explain and never requests chain-of-thought. The Phase 2 smoke measured **166 context characters**, **445 prompt characters**, and a **39-character** response.

`DecisionClient` isolates the backend. The current Volcengine OpenAI-compatible endpoint is a **remote test provider only**. A future OpenAI-compatible local server, vLLM, llama.cpp, Ollama, or another local endpoint must be substitutable without changing `WorldState`, `ObservationBuilder`, `ContextCompiler`, or the future `RuleEngine`. The decision path has a 60-second timeout and zero configured transport retries; parsing or provider failure ends the attempt rather than invoking another model call. The Phase 2 smoke observed **one application-level request**, a valid `MOVE` proposal, and unchanged world state; see the [Phase 2 verification record](phase2_compact_decision.md) for full measurements.

## Phase 1B environment path

```text
WorldState -> ObservationBuilder -> RuleWorldEnv
           -> DeterministicRouter -> compact observation string
```

The entire path must make **zero LLM calls**, including router initialization, `<observe>`, `<statistics>`, and world description. `ObservationBuilder` selects only the requesting person's `agent_id`, `time`, `location`, `money`, and `hunger`; the agent never receives the world object or another person's full state. Unknown IDs fail explicitly. `RuleWorldEnv` exposes read-only observation only; its `step` remains a no-op or clock-only update. No environment action or state mutation is available in this phase.

`DeterministicRouter` is an integration adapter for AgentSociety's router contract. It serializes the selected observation to stable, compact JSON; returns an empty deterministic statistics result if requested; returns a fixed short world description; and explicitly rejects unsupported instructions. It must not fall back to a language-model router. The Phase 1B smoke initializes and closes a real `AgentSociety` instance with this router, without calling `society.ask()`.

## Compact context and budget

`ContextCompiler` converts the selected profile and local observation into a compact structure, for example:

```json
{"p":{"name":"Alice"},"s":{"id":1,"t":"2026-01-01T00:00:00+00:00","loc":"home","money":100.0,"hunger":0.8}}
```

The compiler performs no model request. Its policy allows at most four whitelisted profile fields, three relevant memories, three events, six available actions, and five candidate target IDs. Strings are truncated at documented field limits; excessive collection counts or total serialized length raise an error. Its general hard output cap is 6,000 characters, while the Phase 2 decision service applies a stricter 2,000-character cap. The final model's tokenizer is unknown, so the first hard limit is model-independent; the 2K-token target remains a design target to re-check with the chosen tokenizer.

Future memory retrieval may contribute only a few recent or relevant memories (roughly 3–5), not the entire history. Future actions should be represented by compact names such as `MOVE(target)`, `WORK`, `REST`, and `CHAT(target)`, not complete JSON tool schemas. These are design constraints, not Phase 1B implementations.

## Deliberate exclusions and next stage

`CodeGenRouter` is valid upstream behavior but is **not used in the final deterministic environment path**: its initialization can use LLM-generated observe/statistics code and its default world description can use an LLM. The Phase 1 custom-world run reached statistics code generation and timed out after a 300-second first attempt, then retried. This is a fit-to-constraints decision, not a claim that upstream is broken.

Upstream `PersonAgent` ReAct remains an available capability, but it is **not selected as the final local-8B decision architecture** because a decision cannot rely on multi-turn tool use or multiple model calls. The future `CompactDecisionAgent` or equivalent single-call decision path is outside Phase 1B. RuleEngine, ActionIntent execution, StateReducer, Effects, conflict resolution, economy, relationships, and multi-agent behavior are also outside this phase.

Phase 2 verified `Compact Context -> exactly one LLM call when manually triggered -> tiny structured proposal`, stopping before state mutation. A later phase will address `Decision Proposal -> deterministic RuleEngine -> Effects`. Phase 2 has separate tests and a real single-call smoke; Phase 1B's runtime smoke alone did not establish this decision path.
