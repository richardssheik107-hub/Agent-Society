# Social Simulation Project

Current foundation: AgentSociety 2. This repository is an integration workspace; the official source is kept as a Git submodule under `third_party/AgentSociety`.

Future architecture may use AgentSociety 2's PersonAgent, memory, environment, simulation scheduler, and replay/trace. Custom WorldState, ActionIntent, RuleEngine, StateReducer, and event model are planned for later phases; none is implemented here.

LLM proposes actions. Deterministic rules govern consequences.

Current phase: Phase 0 — bootstrap AgentSociety 2 only. See [the verified bootstrap record](docs/agentsociety2_bootstrap.md) for actual commands and blockers.

To obtain the pinned official source after cloning this workspace:

```sh
git submodule update --init --recursive third_party/AgentSociety
```
