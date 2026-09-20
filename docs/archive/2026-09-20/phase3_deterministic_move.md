# Phase 3 — Deterministic MOVE Execution

## Goal and boundary

Phase 3 connects the Phase 2 `DecisionProposal` to one deterministic state transition. The only executable action is `MOVE`; the model's responsibility ends at the proposal. Python supplies the actor identity, checks the rule, declares an effect, and applies it through one state-writing boundary.

```text
DecisionProposal
  -> proposal_to_intent -> ActionIntent
  -> RuleEngine -> MoveRule -> RuleResult
  -> MoveEffect (only when accepted)
  -> StateReducer -> new WorldState
```

`WAIT` and `REST` remain in the Phase 2 action enum but have no Phase 3 execution rule. `RuleEngine` rejects them with `UNSUPPORTED_ACTION`. This phase does not implement purchase, eating, work, chat, economy, inventory, event logging, multi-agent conflict, maps, travel costs, or clock advancement.

## Models and contracts

| Model | Phase 3 contract |
| --- | --- |
| `DecisionProposal` | LLM-facing `{action, target}` from Phase 2; not proof that an action succeeds. Its schema is unchanged. |
| `ActionIntent` | Internal, frozen request with `actor_id`, `action`, `target`, and an empty `params` mapping by default. `proposal_to_intent(actor_id, proposal)` adds the Python-owned actor identity; the LLM never supplies it. |
| `RuleResult` | Frozen audit record with `actor_id`, `action`, `allowed`, machine-readable `reason_code`, and declared `effects`. Rejected results have no effects. |
| `MoveEffect` | Frozen declaration of `agent_id`, `from_location`, and `to_location`; it does not mutate state. |
| `WorldState` | Source of truth for people and valid destination IDs. `WorldState.locations` is the only list consulted by `MoveRule` and `StateReducer`; no duplicate location registry exists in the rule. |

The registered rules are a small explicit mapping: `MOVE -> MoveRule`. There is no dynamic registry, NLP matching, or LLM fallback. `MoveRule` checks that the actor exists, the target is a nonempty location ID, the target occurs in `world.locations`, and it differs from the actor's current location. It returns `ACCEPTED` and one `MoveEffect` when all checks pass; otherwise it returns `ACTOR_NOT_FOUND`, `MISSING_TARGET`, `UNKNOWN_DESTINATION`, or `ALREADY_AT_DESTINATION`. Unsupported actions return `UNSUPPORTED_ACTION` from `RuleEngine`.

Rule evaluation is read-only. For the same `WorldState` and `ActionIntent`, it must return the same `RuleResult` and effects without randomness, wall-clock reads, network access, or model calls. A proposal, intent, rule, result, or effect cannot itself change the world.

## StateReducer and conflict guard

`StateReducer.apply(world, effects)` is the sole Phase 3 state-writing boundary. It returns a new `WorldState` when a move effect is applied, leaving the input world unchanged. It replaces only the moved person's `location`; `money`, `hunger`, other person fields, time, and valid locations are preserved. With no effects, it returns the unchanged world.

Before applying a `MoveEffect`, the reducer checks that the actor still exists, `effect.from_location` equals the person's current location, and `effect.to_location` is a valid, different world location. A stale or invalid effect raises `StateConflictError` with the machine-readable code `STATE_CONFLICT` instead of silently changing state. This guards the validate-then-apply boundary even though Phase 3 does not introduce concurrency.

## Accepted and rejected examples

Given Alice at `home`, with `money=100.0`, `hunger=0.8`, and world locations `home`, `park`, and `restaurant`:

| Request | Rule decision | Reducer result |
| --- | --- | --- |
| `MOVE restaurant` | `allowed=True`, `ACCEPTED`, `MoveEffect(1, home, restaurant)` | Old world: Alice at `home`. New world: Alice at `restaurant`; money and hunger unchanged. |
| `MOVE moon` | `allowed=False`, `UNKNOWN_DESTINATION`, no effects | Reducer is not called. Alice remains at `home`; the world is unchanged. |

The action target is an exact location ID. A phrase such as `the restaurant near my home` is not resolved or normalized by the rule layer.

## Tests and smoke

The intended automated checks cover proposal-to-intent conversion, every `MoveRule` precondition, unsupported-action dispatch, deterministic repeated evaluation, read-only rule behavior, reducer-only mutation, old/new state separation, unchanged numeric fields, empty effects, invalid effect rejection, and `STATE_CONFLICT` for a stale source location. The pipeline check must include both accepted `home -> restaurant` and rejected `home -> moon` cases.

The deterministic smoke constructs `DecisionProposal` directly, without a provider or API key. The full integration suite, including Phase 1/2 regressions, completed with **106 passed, 3 warnings in 4.05s**. The deterministic smoke exited successfully and reported:

```text
WORLD_INIT_OK
PROPOSAL_OK
INTENT_OK
RULE_ACCEPTED
EFFECT_CREATED
REDUCER_APPLIED
OLD_LOCATION=home
NEW_LOCATION=restaurant
MONEY_UNCHANGED
HUNGER_UNCHANGED
INVALID_MOVE_REJECTED
REASON=UNKNOWN_DESTINATION
WORLD_UNCHANGED_AFTER_REJECT
ZERO_LLM_CALLS
PHASE3_MOVE_OK
```

The smoke also asserts the old world snapshot remains unchanged after the accepted rule evaluation and after reduction. It invokes no real LLM. Upstream cleanliness is checked separately in the final repository audit.

## LLM usage and upstream scope

The Phase 3 rules, effects, and reducer use **zero LLM calls** by design. The deterministic smoke must not invoke `DecisionClient`, PersonAgent, CodeGenRouter, ReActRouter, or the remote provider. A later optional end-to-end test may connect one compact decision call to this pipeline, but it is not needed to validate MOVE execution and must not retry to force a particular proposal.

All integration changes stay under `src/social_sim/`, `tests/`, `smoke/`, and `docs/`. The pinned `third_party/AgentSociety` upstream is not modified.
