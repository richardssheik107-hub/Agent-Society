# AgentSociety 2 Bootstrap

## Repository

- Official repository: https://github.com/tsinghua-fib-lab/AgentSociety.git
- Checkout: `third_party/AgentSociety` (Git submodule)
- Branch: submodule detached HEAD at `main`; local `main` and `origin/main` match the checkout. `git ls-remote` confirmed the upstream `main` ref at the same commit.
- Commit: `670c94fff7c64c4f79b632125f2ccf968155e746` (`Merge branch 'release/2.8.7' into 'main'`)
- Package: `agentsociety2` 2.8.7 from `packages/agentsociety2/`; the `__init__.__version__` literal still says 2.8.3, so use package metadata/`pyproject.toml` as the distribution version.
- Python requirement: `>=3.11,<3.14`. Repository root is a uv workspace with only `packages/agentsociety2` as a member. The old v1 package was not installed as the target.

## Environment

- OS: Microsoft Windows 10.0.26200, native Windows (not WSL2); x64 CPU/process.
- Shell: PowerShell 7.6.5.
- Git: 2.54.0.windows.1.
- `python --version`: 3.11.9; `python3 --version`: no usable version from the WindowsApps alias.
- Selected uv environment: CPython 3.12.10 at `third_party/AgentSociety/.venv/Scripts/python.exe`.
- uv: 0.12.5 (Windows x86_64).
- WSL: no Linux distribution installed (`wsl.exe --status` / `--list --verbose`).

## Installation

Commands actually executed (PowerShell, from the integration root unless noted):

```powershell
git init
git submodule add https://github.com/tsinghua-fib-lab/AgentSociety.git third_party/AgentSociety
git submodule update --init --recursive third_party/AgentSociety
git -C third_party/AgentSociety remote -v
git -C third_party/AgentSociety branch --show-current
git -C third_party/AgentSociety rev-parse HEAD
git ls-remote https://github.com/tsinghua-fib-lab/AgentSociety.git refs/heads/main
cd third_party/AgentSociety
uv sync --python 3.12 --frozen
```

The uv sync completed with exit code 0 and installed 176 packages, including editable `agentsociety2==2.8.7` from this checkout. The frozen lock was not updated. The `uv run --frozen` checks below may resync the editable wheel but did not change tracked upstream files.

Source check without importing the credential-gated package:

```powershell
uv run --frozen python -c "import importlib.metadata as m, importlib.util as u; d=m.distribution('agentsociety2'); s=u.find_spec('agentsociety2'); print('version='+d.version); print('origin='+str(s.origin)); print('ray_available='+str(u.find_spec('ray') is not None))"
```

Observed: version `2.8.7`; origin `C:\Users\Fergeson\Desktop\Agent Society\third_party\AgentSociety\packages\agentsociety2\agentsociety2\__init__.py`; `ray_available=False`. The distribution's `direct_url.json` reports `editable:true` and the same source path. This proves the installation/source mapping, **not a successful `import agentsociety2`**.

## LLM Configuration

The upstream `.env.example` was copied to the upstream root `.env`; placeholder API keys were cleared in this ignored local file. No secret was printed or committed. The smoke entrypoint explicitly loads it *before* importing AgentSociety 2 (the regular package entrypoint does not automatically call `load_dotenv`). Environment variables, if present, take precedence.

- `AGENTSOCIETY_LLM_API_KEY`: **MISSING** (required; no real credential supplied).
- `AGENTSOCIETY_LLM_API_BASE`: template value `https://api.openai.com/v1` (set in the local `.env`; override to match the provider).
- `AGENTSOCIETY_LLM_MODEL`: template value `gpt-5.5` (set in the local `.env`; override to an accessible model).
- Coder/embedding API keys: optional; the source falls back to the default key.

The source validates the default API key at import. A syntactically populated key is not evidence that the provider accepts it; only a real `ask()` can verify that.

## Smoke Test

Own file: `smoke/agentsociety2_smoke.py`. It uses one Alice spec, `SimpleSocialSpace`, `CodeGenRouter`, `AgentSociety`, `init()`, `ask("What's your name?")`, and `close()` in `finally`, matching the current root/package Quick Start. Its output is directed to the integration root `run/agentsociety2_smoke/`, not the submodule.

Commands actually run from `third_party/AgentSociety`:

```powershell
uv run --frozen python -m py_compile ../../smoke/agentsociety2_smoke.py
uv run --frozen python ../../smoke/agentsociety2_smoke.py
```

Syntax check: PASS. Runtime smoke: exit code 1, expected guard message `AGENTSOCIETY_LLM_API_KEY is missing; configure the ignored upstream .env`. No package import, `init`, LLM request, response, or `close` was claimed. The `run/agentsociety2_smoke/` directory was not created.

The ordinary import check `uv run --frozen python -c "import agentsociety2; print(agentsociety2.__file__)"` was **not** run with a fabricated key: a real credential must be supplied first. `importlib.util.find_spec` and distribution metadata are separately reported, not substituted for this acceptance check.

## Runtime Outputs

- Agent workspace: none.
- `AGENT.json`, config, state: none.
- Replay / trace: none.
- Society state: none.
- The only generated artifacts are the ignored upstream `.venv`, ignored local `.env`, and ignored Python bytecode cache from the syntax check.

## Problems Encountered

### Previous task interruption

- Symptom: an earlier, superseded two-repository request was interrupted after the AgentSociety submodule was indexed while an eliza clone had started in the background.
- Root cause: user replaced that request with this AgentSociety-only Phase 0 task mid-command.
- Minimal fix: stopped only the identified old eliza Git process chain, restored `.gitmodules` from the index, and finished the AgentSociety submodule checkout. No eliza worktree or submodule entry is present in the current workspace; an incomplete internal `.git/modules/third_party/eliza` cache from the interrupted clone may remain, but is not tracked or used. No directories were deleted.
- Verification: `.gitmodules` has only AgentSociety; `third_party/` contains only `AgentSociety`.

### Missing LLM credentials

- Symptom: smoke preflight raises `AGENTSOCIETY_LLM_API_KEY is missing` before import.
- Root cause: no actual key was supplied in the process environment or ignored `.env`.
- Minimal fix: prepared ignored `.env` from the upstream example and added a guard so template placeholders cannot trigger an accidental request. User must supply a real key and confirm provider base/model.
- Verification: local key presence is `MISSING`; smoke exit code 1 at the guard. No fake key was used.

### Native Windows Ray exclusion

- Symptom: `ray_available=False` after successful frozen sync.
- Root cause: upstream `packages/agentsociety2/pyproject.toml` line 81 declares `ray>=2.0.0; sys_platform != 'win32'`, while `AgentSociety.init()` calls `init_dispatchers()`, which unconditionally imports `ray` at the start of initialization. Therefore this native Windows dependency set cannot reach `init()` even after credentials are added.
- Minimal fix applied: none; no upstream dependency or runtime code was changed. The appropriate next environment is a unified WSL2 + Ubuntu checkout with Linux Python/uv and a real LLM credential. WSL2 was not installed or the Windows project/venv mixed into Linux.
- Verification: package marker, installed environment's `ray_available=False`, and `init_dispatchers()` source at `config/llm_dispatcher.py` were inspected. Because credentials are missing, this is a source/dependency diagnosis rather than an executed post-credential `init()` traceback.

## Final Status

**INCOMPLETE**: official source, current main commit, Python/uv environment, editable installation, script syntax, and source mapping are verified. Actual package import, PersonAgent workspace, Environment and AgentSociety initialization, LLM `ask()`/response, `close()`, replay and trace are unverified. There are two independent blockers: real LLM credentials and the upstream Ray dependency exclusion on native Windows. This is not the credentials-only status.

Final checks: `uv run --frozen ruff check ../../smoke/agentsociety2_smoke.py` passed; `git -C third_party/AgentSociety status --short` produced no output. Parent `git status --short` shows staged `.gitmodules` and `third_party/AgentSociety`, plus untracked `.gitignore`, `README.md`, `docs/`, and `smoke/`. No commit was made, and Git lists no unignored `.env` or `run/` files.

Once WSL2 + Ubuntu is available, use a Linux checkout and Linux uv environment, set the real `AGENTSOCIETY_LLM_API_KEY` and matching `AGENTSOCIETY_LLM_API_BASE` / `AGENTSOCIETY_LLM_MODEL` in its ignored `.env`, then rerun frozen sync, real import/source check, the same smoke script, and inspect `run/agentsociety2_smoke/`. Do not reuse the Windows `.venv`. No Phase 1 modules were started.

# Phase 0B-1 — WSL2 Ray Verification

The above record describes the historical native-Windows Phase 0A state. Phase 0B-1 subsequently moved the integration repository to `/home/fergeson/projects/agent-society` on Ubuntu 26.04.1 LTS, WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`, x86_64, user `fergeson`. The copy preserved Git index and untracked work while excluding the Windows `.venv`, bytecode caches, run outputs, and the unused interrupted eliza Git cache. Four upstream files whose committed blobs use CRLF despite `.gitattributes` requiring LF needed a Linux-local `.git/info/attributes` override; no tracked upstream file was changed.

- Commit: `670c94fff7c64c4f79b632125f2ccf968155e746`.
- Linux uv: `0.12.15`; uv-managed Python: `3.12.14`.
- Command: `uv sync --python 3.12 --frozen` from the Linux upstream root; exit code 0, 179 packages installed, including editable `agentsociety2==2.8.7` and `ray==2.55.1`.
- Independent command: `uv run --frozen python -c "import ray; ray.init(include_dashboard=False); print('RAY INIT OK'); ray.shutdown()"`.
- Result: `RAY INIT OK`, exit code 0. Upstream `git status --short` and `git diff --stat` had no output. No LLM configuration or smoke was performed in Phase 0B-1.

# Phase 0B-2 — Runtime Smoke Test

## Environment

- Ubuntu: 26.04.1 LTS under WSL2.
- Python: 3.12.14; uv: 0.12.15; Ray: 2.55.1 (independent init passed in Phase 0B-1).
- AgentSociety 2: package 2.8.7; commit `670c94fff7c64c4f79b632125f2ccf968155e746`.

## LLM

- API KEY: **SET** in the ignored Linux upstream `.env`, file mode `600`; the key value is deliberately omitted. `git check-ignore .env` succeeds and `git ls-files --error-unmatch .env` confirms it is not tracked.
- API BASE: `https://ark.cn-beijing.volces.com/api/coding/v3` (OpenAI-compatible Coding Plan gateway supplied by the user).
- MODEL: `ark-code-latest` (supplied by the user). AgentSociety's LiteLLM router adds the `openai/` prefix internally.
- Timeout: `AGENTSOCIETY_LLM_REQUEST_TIMEOUT=300` was read as 300.0 seconds.
- Retry limitation: the user supplied a zero-retry preference, but this checkout's `LLMClient.call()` applies `max(max_retries, 1)` and has no global environment setting to guarantee zero retries. The user subsequently authorized a real attempt under the upstream retry policy. No upstream code was altered.

## Import

Executed from the Linux upstream root:

```bash
uv run --frozen --env-file .env python -c "import agentsociety2; print('AGENTSOCIETY2 IMPORT OK'); print('PACKAGE SOURCE:', agentsociety2.__file__)"
```

Result: `AGENTSOCIETY2 IMPORT OK`, exit code 0. Package source: `/home/fergeson/projects/agent-society/third_party/AgentSociety/packages/agentsociety2/agentsociety2/__init__.py` (the current editable checkout). Effective configuration was checked without printing the key: key SET, specified public API base/model, coder-model fallback, and 300-second timeout. LiteLLM reported a timeout fetching its public remote model-cost map and fell back to its local copy; this did not fail import and was not a model request.

## Runtime

- Ray: independent recheck printed `RAY INIT OK` and exited 0 immediately before the smoke.
- Command from the Linux upstream root: `uv run --frozen --env-file .env python ../../smoke/agentsociety2_smoke.py`.
- First real run: process exited 0 and initialized the single-agent society, but the ambiguous question `What's your name?` made `AgentSocietyHelper` identify itself instead of Alice. It therefore **did not meet the Alice-response acceptance criterion**. Artifacts remain under `run/agentsociety2_smoke/`; they were not overwritten.
- Symptom/root cause/minimal fix/verification: the helper interpreted “your” as referring to itself because `society.ask()` is helper-mediated. After inspecting `society/helper.py` and the official quickstart's targeted-agent question, only the integration-owned smoke script was changed to explicitly ask Alice (id 1), assert that the non-empty response names Alice, print `INIT_OK` / `CLOSE_OK`, and write to a separate `run/agentsociety2_smoke_linux/` directory. Ruff check passed. No upstream source changed.
- Second real run: `INIT_OK` printed after `society.init()`. The helper planned one step to ask Alice directly; the tool result contained Alice's own answer, “My name is Alice.” The final response reported that answer and passed the Alice assertion. `CLOSE_OK` printed after `await society.close()`. Python exit code: **0**. Logs showed LLM-generated observation/statistics code and a world description for `SimpleSocialSpace`, confirming real provider requests rather than a mock.
- PersonAgent workspace: `run/agentsociety2_smoke_linux/agents/agent_0001/`; `AGENT.json` names Alice. Empty `state/` and present `memory/` directories were observed.

## Generated Files

Actual files in the successful second run (relative to `run/agentsociety2_smoke_linux/`):

```text
SOCIETY.json
agents/agent_0001/AGENT.json
agents/agent_0001/MEMORY.md
agents/agent_0001/TODO.json
agents/agent_0001/config.json
agents/agent_0001/memory/episodes.jsonl
agents/agent_0001/memory/state.json
replay/.core_agent_profile.99.lock
replay/_schema.json
replay/core_agent_profile.99.jsonl
```

The replay profile JSONL has one record; the lock and memory episodes file are empty. No `trace/` directory or `SOCIETY_STEP.json` was produced by this init/ask-only run. These absent optional outputs are not reported as failures.

## Final Verification

- `agentsociety2` import/source: PASS, current editable checkout.
- Ray/init/PersonAgent/SimpleSocialSpace/real LLM request/`society.ask()`/Alice response/`society.close()`/exit code 0: PASS in the second run.
- Upstream `git status --short` and `git diff --stat`: no output; tracked core unchanged.
- Ignored `.env`: mode `600`, not tracked. The key is omitted from this report and all tracked files.
- No commit, push, RuleEngine, or Phase 1 work.
- **PHASE 0 COMPLETE** for the defined one-agent runtime smoke.
