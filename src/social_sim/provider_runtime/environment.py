"""在接触凭据之前检查一个完整的 Python 环境，不拼接 uv cache。"""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import os
import site
import subprocess
import sys
from pathlib import Path

from .safety import atom, exception_type

PACKAGES = {
    "httpx": "httpx", "httpcore": "httpcore", "anyio": "anyio",
    "typing_extensions": "typing_extensions", "h11": "h11", "idna": "idna",
    "certifi": "certifi", "dotenv": "python-dotenv",
}
UPSTREAM_SHA = "670c94fff7c64c4f79b632125f2ccf968155e746"
EXPECTED_BASE = "https://ark.cn-beijing.volces.com/api/coding/v3"
EXPECTED_MODEL = "ark-code-latest"


def git_value(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True,
                                       stderr=subprocess.DEVNULL, timeout=10).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def repository_info(root: Path) -> dict:
    top = git_value(root, "rev-parse", "--show-toplevel")
    status = git_value(root, "status", "--porcelain")
    upstream = git_value(root, "rev-parse", "HEAD:third_party/AgentSociety")
    valid = bool(top and Path(top).resolve() == root.resolve()
                 and (root / "src/social_sim/continuity/q6_1.py").is_file())
    return {"parent_repository": valid, "git_commit": git_value(root, "rev-parse", "HEAD"),
            "branch": git_value(root, "branch", "--show-current"),
            "worktree_clean": status == "", "upstream_sha": upstream,
            "upstream_matches": upstream == UPSTREAM_SHA}


def code_fingerprint(root: Path) -> str:
    """绑定本次代码，不包含 .env、运行产物或用户文件。"""
    paths = list((root / "src/social_sim").rglob("*.py"))
    paths += [root / "scripts/check_q6_1_provider_runtime.py", root / "requirements-q61-runtime.txt"]
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def inspect_runtime() -> dict:
    problems = []
    if sys.prefix == sys.base_prefix:
        problems.append("VIRTUAL_ENVIRONMENT_REQUIRED")
    if os.environ.get("PYTHONPATH"):
        problems.append("PYTHONPATH_MUST_BE_EMPTY")
    if os.environ.get("PYTHONHOME"):
        problems.append("PYTHONHOME_MUST_BE_EMPTY")
    if site.ENABLE_USER_SITE:
        problems.append("USER_SITE_ENABLED")
    if sys.version_info < (3, 11):
        problems.append("PYTHON_3_11_REQUIRED")
    packages = {}
    for name, distribution in PACKAGES.items():
        try:
            module = importlib.import_module(name)
            path = Path(module.__file__).resolve()
            version = importlib.metadata.version(distribution)
            inside = path.is_relative_to(Path(sys.prefix).resolve())
            packages[name] = {"version": version, "path": str(path), "inside_environment": inside}
            if not inside:
                problems.append("PACKAGE_OUTSIDE_ENVIRONMENT:" + name)
        except Exception as error:
            packages[name] = {"exception_type": exception_type(error)}
            problems.append("IMPORT_FAILED:" + name)
    # 真实 asyncio 后端的 import + client construction + close 均执行，但没有 complete/HTTP。
    if not problems:
        try:
            import anyio
            from social_sim.decision import OpenAICompatibleDecisionClient
            async def lifecycle():
                client = OpenAICompatibleDecisionClient(base_url="https://offline.invalid/v1",
                    model="offline", api_key="offline-placeholder", minimal_request=True)
                await client.aclose()
            anyio.run(lifecycle)
        except Exception as error:
            problems.append("LOCAL_CLIENT_LIFECYCLE_FAILED")
            packages["local_lifecycle"] = {"exception_type": exception_type(error)}
    return {"result": "PASS" if not problems else "FAIL", "issues": problems,
            "python_executable": sys.executable, "python_version": sys.version.split()[0],
            "prefix": sys.prefix, "packages": packages, "provider_requests": 0}


def load_provider_config(env_file: Path | None = None) -> dict:
    """只读明确指定的文件，dotenv 解析不执行 shell、不插值、不修改环境。"""
    names = ("CONTINUITY_BASE_URL", "CONTINUITY_MODEL", "CONTINUITY_API_KEY")
    values = {key: os.environ.get(key, "") for key in names}
    if env_file is not None:
        from dotenv import dotenv_values
        saved = dotenv_values(env_file, interpolate=False)
        if not env_file.is_file():
            raise ValueError("ENV_FILE_MISSING")
        values[names[0]] = values[names[0]] or saved.get(names[0]) or EXPECTED_BASE
        values[names[1]] = values[names[1]] or saved.get(names[1]) or EXPECTED_MODEL
        values[names[2]] = values[names[2]] or saved.get(names[2]) or saved.get("AGENTSOCIETY_LLM_API_KEY") or ""
    if not all(isinstance(values[n], str) and values[n].strip() for n in names):
        raise ValueError("PROVIDER_CONFIG_MISSING")
    if values[names[0]].rstrip("/") != EXPECTED_BASE or values[names[1]] != EXPECTED_MODEL:
        raise ValueError("PROVIDER_CONFIG_DIFFERS_FROM_FROZEN_PROTOCOL")
    secret = values[names[2]]
    if any(c in secret for c in "\r\n") or not atom(values[names[1]], secret):
        raise ValueError("PROVIDER_CONFIG_INVALID")
    return {"base_url": EXPECTED_BASE, "model": EXPECTED_MODEL, "api_key": secret}
