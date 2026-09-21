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
if [ ! -d "$ENV" ]; then
    python3 -m venv "$ENV"
fi
test -f "$ENV/pyvenv.cfg"
test -x "$ENV/bin/python"
# Python 3.11/3.12 venv 不保证自动创建 .gitignore。
if [ ! -e "$ENV/.gitignore" ]; then printf '*\n' > "$ENV/.gitignore"; fi
"$ENV/bin/python" -m pip install --disable-pip-version-check -r requirements-q61-runtime.txt
"$ENV/bin/python" -m pip check
mkdir -p run/evaluation/q6_1_runtime_environment
"$ENV/bin/python" -m pip freeze > run/evaluation/q6_1_runtime_environment/resolved-requirements.txt
"$ENV/bin/python" scripts/check_q6_1_provider_runtime.py --check-only
printf 'Q61_RUNTIME_SETUP_DONE\nREAL_PROVIDER_REQUESTS=0\n'
