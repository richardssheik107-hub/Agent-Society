# Phases 4–6: deterministic lunch closed loop

## Scope and acceptance

The first single-person loop is `MOVE restaurant -> BUY meal -> EAT meal`. Its deterministic smoke uses three fixed decision replies, **not** the real provider. Each `ClosedLoopStep` makes exactly one decision-client call; rules, effects, reduction, event generation, and observation make zero LLM calls. This verifies the domain feedback loop, not an AgentSociety scheduler or a multi-agent simulation.

```text
WorldState(t) -> local Observation -> compact Context -> DecisionProposal
              -> ActionIntent -> RuleResult -> Effect -> StateReducer
              -> WorldState(t+1) -> DomainEvent -> EventLog
              -> next local Observation -> next Decision
```

The model can propose only `action` and `target`. Python adds `actor_id` and the one-unit `quantity` for `BUY`/`EAT`. A proposal neither approves an action nor changes objective state.

## Initial world and hunger convention

| Fact | Initial value |
| --- | --- |
| Alice | `agent_id=1`, `location=home`, `money=100.0`, `hunger=0.8`, `inventory={}` |
| Locations | `home`, `park`, `restaurant` |
| Restaurant offer | `meal`: `price=20.0`, `stock=10` |

`hunger ∈ [0,1]` is **degree of hunger**: `0.0` means satiated and `1.0` extremely hungry. Alice's initial `0.8` means she is hungry. Eating one meal reduces hunger by `0.6`, with `max(0.0, hunger - 0.6)` rounded to six decimals; in this run, `0.8 -> 0.2`. The field remains named `hunger`.

`PersonWorldState.inventory` defaults to an independent empty mapping, so older constructors still work. The `WorldState` restaurant offer is the **only source of truth** for price and stock; `BuyRule` contains no parallel menu or stock constant. The local observation exposes Alice's inventory and, only at her current venue, compact offer price and availability. It does not expose the full world or other venues' internal inventories.

## Deterministic contracts

`RuleEngine` dispatches `MOVE`, `BUY`, and `EAT`. `WAIT` and `REST` remain unsupported for execution. The LLM-facing `DecisionProposal(action,target)` is unchanged apart from the two new action enum members; it has no quantity or rule parameters.

- `BuyRule` requires an existing actor, nonempty known item, current location selling that item, positive stock, and enough money. Rejection codes include `ACTOR_NOT_FOUND`, `MISSING_TARGET`, `ITEM_NOT_FOUND`, `NOT_AT_SELLER`, `OUT_OF_STOCK`, and `INSUFFICIENT_FUNDS`. It reads current price and stock from `WorldState`, then declares a one-unit `PurchaseEffect`; it never changes the world.
- `EatRule` requires an existing actor, nonempty known item, and at least one owned item. Rejection codes include `ACTOR_NOT_FOUND`, `MISSING_TARGET`, `ITEM_NOT_FOUND`, and `ITEM_NOT_OWNED`. Consumption does not require remaining at the seller. It declares a one-unit `EatEffect` and the new hunger value; it never changes the world.
- Effects are immutable declarations. `PurchaseEffect` carries expected-before money, venue stock, and inventory count; `EatEffect` carries expected-before inventory and hunger. `StateReducer` is the sole world-write boundary and checks those values again before constructing a new immutable snapshot. A stale or otherwise invalid effect raises `STATE_CONFLICT`; old snapshots are not mutated. `MoveEffect` retains the Phase 3 source-location check.
- `ActionExecutor` is a thin coordinator: evaluate intent, apply allowed effects through the reducer, and return an `ExecutionOutcome`. A rejection skips the reducer and returns the identical `WorldState` with no effects.
- Each outcome has one deterministic `DomainEvent`: `MOVED`, `PURCHASED`, `ATE`, or `ACTION_REJECTED` with a machine-readable reason. The in-memory append-only `EventLog` provides predictable `event-000001`-style IDs, `all()`, and agent-scoped `recent_for_agent(limit=3)`. Only compact feedback such as `MOVED:restaurant` or `ACTION_REJECTED:NOT_AT_SELLER` enters the next decision context; no event summarization model or memory LLM is involved.

`ClosedLoopStep` builds the observation, compiles bounded context, makes one `CompactDecisionService` call, converts the proposal to an intent, executes it, and appends the event. `LunchScenarioRunner` feeds each returned world into the next step, stops when Python sees `hunger <= 0.2` and `meal inventory == 0`, and fails after at most five decisions. If the initial world already meets that condition, it returns the same world and its observation with zero steps, events, and decision calls. `LunchRunResult.events` contains only events produced by that run; preexisting `EventLog` history remains in the log but is not included in the result. This is domain orchestration, not a replacement simulation scheduler.

## Accepted audit trail

| Step | Intent and judgment | Declared effect and resulting state | Event |
| --- | --- | --- | --- |
| 1 | `MOVE restaurant`, `ACCEPTED` | Alice `home -> restaurant`; money `100.0`, hunger `0.8`, meal `0`, stock `10` unchanged | `event-000001 MOVED` |
| 2 | `BUY meal`, `ACCEPTED` | Money `100.0 -> 80.0`; restaurant stock `10 -> 9`; Alice meal inventory `0 -> 1`; location and hunger unchanged | `event-000002 PURCHASED` |
| 3 | `EAT meal`, `ACCEPTED` | Meal inventory `1 -> 0`; hunger `0.8 -> 0.2`; money `80.0`, stock `9`, and location unchanged | `event-000003 ATE` |

The event order is exactly `MOVED -> PURCHASED -> ATE`. The earlier world snapshots still show `home / 100.0 / 0.8`, `restaurant / 100.0 / 0.8`, and `restaurant / 80.0 / 0.8`, respectively; subsequent steps do not alter them.

The final `ObservationBuilder` call reads the resulting world and reports Alice at `restaurant`, `money=80.0`, `hunger=0.2`, `inventory["meal"]=0`. The local restaurant offer remains visible at `price=20.0` with `available=true`; underlying stock is `9`. This last observation is the evidence that consequences flow back into perception for a later decision.

## Rejection and bounded feedback

The separate rejected-path test proposes `BUY meal` while Alice is still at `home`. `BuyRule` returns `NOT_AT_SELLER`; there are no effects, the reducer is not invoked, and `ExecutionOutcome.new_world` is the same object. `EventLog` receives `ACTION_REJECTED:NOT_AT_SELLER`. The following observation still reads `home / 100.0 / hunger 0.8`; a subsequent decision receives the compact rejection feedback. The rule, not the model, decides whether a purchase occurred.

## Budget and verification

The scripted smoke's context lengths for the three decisions were **`[178, 247, 280]` characters**, all below the 2,000-character decision cap and the preferred 1,000-character scenario target. They contain compact local state, allowed action/target IDs, and up to three recent event strings, not the full `WorldState`, rules, effect definitions, or reason-code catalog. The script issued **3 scripted decision calls**, exactly one per step; environment, rule, reducer, and event LLM calls were **0**.

The deterministic lunch smoke passed with `LUNCH_CLOSED_LOOP_OK`, `WORLD_LOOP_CLOSED`, `FINAL_OBSERVATION_OK`, and `EVENT_COUNT=3`. The full suite passed: **168 tests passed, 3 warnings in 8.74 seconds** (exit code 0), including rejected-event feedback, pre-satisfied terminal condition, scenario-local event history, and fixed one-unit intent tests. The optional real-provider lunch attempt and AgentSociety lifecycle-wrapped lunch smoke were **NOT_RUN**; neither is required to accept this deterministic domain loop. The upstream `third_party/AgentSociety` source was not changed.
