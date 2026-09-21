"""只保留枚举、计数和版本；异常正文不是诊断产物。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

EXCEPTION_TYPES = frozenset({
    "ImportError", "ModuleNotFoundError", "AttributeError", "RuntimeError",
    "TypeError", "ValueError", "JSONDecodeError", "OSError", "PermissionError",
    "TimeoutError", "CancelledError", "ConnectError", "ConnectTimeout",
    "ReadError", "ReadTimeout", "WriteError", "WriteTimeout", "PoolTimeout",
    "CloseError", "RemoteProtocolError", "LocalProtocolError", "ProxyError",
    "UnsupportedProtocol", "NetworkError", "SSLError", "gaierror",
    "DecisionClientError", "ProviderContractError", "AssertionError",
})


def exception_type(error: BaseException) -> str:
    name = type(error).__name__
    return name if name in EXCEPTION_TYPES else "OtherException"


def atom(value: object, secret: str = "") -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,80}", value):
        return None
    if secret and secret in value:
        return None
    # ark-code-latest 是公开模型别名，不应被泛化的 ark- 规则屏蔽。
    if value.startswith("sk-") or (value.startswith("ark-") and value != "ark-code-latest"):
        return None
    return value


def counter(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def metadata(client: object) -> dict:
    source = getattr(client, "last_metadata", None)
    secret = getattr(client, "_redaction_secret", "")
    data = {}
    status = getattr(source, "http_status", None)
    data["http_status"] = status if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599 else None
    for name in ("provider_model", "finish_reason", "http_error_code", "http_error_type", "http_error_param"):
        data[name] = atom(getattr(source, name, None), secret)
    for name in ("input_tokens", "output_tokens", "reasoning_tokens"):
        data[name] = counter(getattr(source, name, None))
    return data


def failure_stage(error: BaseException, client: object | None = None) -> str:
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return "PYTHON_ENVIRONMENT"
    status = metadata(client).get("http_status")
    if status is not None and status != 200:
        return "HTTP_ERROR"
    if type(error).__name__ == "ProviderContractError":
        return "PROVIDER_CONTRACT"
    if exception_type(error) in {
        "ConnectError", "ConnectTimeout", "ReadError", "ReadTimeout", "WriteError",
        "WriteTimeout", "PoolTimeout", "RemoteProtocolError", "LocalProtocolError",
        "ProxyError", "NetworkError", "SSLError", "gaierror", "TimeoutError",
    }:
        return "NETWORK_RUNTIME"
    return "UNKNOWN_TRANSPORT"


def write_json(path: Path, data: dict) -> None:
    """同目录临时文件原子替换；调用者只可写本次新建 session。"""
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_event(path: Path, data: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
