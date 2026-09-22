#!/usr/bin/env bash
# 仅安装依赖和离线检查；不读取密钥、不修改上游、不请求模型。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
test "$(git rev-parse --show-toplevel)" = "$ROOT"
test -f src/social_sim/continuity/q6_1.py
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1
ENV="$ROOT/.venv-q61-runtime"
PYTHON_BIN=""
if command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
elif command -v uv >/dev/null 2>&1; then
    PYTHON_BIN="$(uv python find 3.12 2>/dev/null || true)"
    if [ -z "$PYTHON_BIN" ]; then
        uv python install 3.12
        PYTHON_BIN="$(uv python find 3.12)"
    fi
fi
if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
    printf 'Q61_RUNTIME_SETUP_FAILED\nFAILURE_STAGE=PYTHON_312_UNAVAILABLE\n' >&2
    exit 1
fi
if [ -d "$ENV" ]; then
    if ! "$ENV/bin/python" -c \
        'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' \
        >/dev/null 2>&1 \
        || ! "$ENV/bin/python" -m pip --version >/dev/null 2>&1; then
        quarantine="${ENV}.invalid.$$"
        mv -- "$ENV" "$quarantine"
    fi
fi
if [ ! -d "$ENV" ]; then
    if command -v uv >/dev/null 2>&1; then
        uv venv --seed --python "$PYTHON_BIN" "$ENV"
    else
        "$PYTHON_BIN" -m venv "$ENV"
    fi
fi
test -f "$ENV/pyvenv.cfg"
test -x "$ENV/bin/python"
if ! "$ENV/bin/python" -c \
    'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' \
    >/dev/null 2>&1; then
    printf 'Q61_RUNTIME_SETUP_FAILED\nFAILURE_STAGE=PYTHON_312_UNAVAILABLE\n' >&2
    exit 1
fi
# Python 3.11/3.12 venv 不保证自动创建 .gitignore。
if [ ! -e "$ENV/.gitignore" ]; then printf '*\n' > "$ENV/.gitignore"; fi
"$ENV/bin/python" --version
"$ENV/bin/python" -m pip --version
"$ENV/bin/python" - <<'PY'
import sys
assert sys.version_info[:2] == (3, 12), sys.version
print("Q61_PYTHON_VERSION_OK")
print(sys.executable)
PY
"$ENV/bin/python" -m pip install --disable-pip-version-check -r requirements-q61-runtime.txt
"$ENV/bin/python" -m pip check
mkdir -p run/evaluation/q6_1_runtime_environment
"$ENV/bin/python" -m pip freeze > run/evaluation/q6_1_runtime_environment/resolved-requirements.txt
"$ENV/bin/python" scripts/check_q6_1_provider_runtime.py --check-only
printf 'Q61_RUNTIME_SETUP_DONE\nREAL_PROVIDER_REQUESTS=0\n'
