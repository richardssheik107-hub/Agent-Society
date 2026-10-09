#!/usr/bin/env python3
"""M5 多日持久生活：默认离线、零真实请求；real 须独立批准的新会话。"""
# ruff: noqa: E402 -- standalone source path
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.longrun.config import LongRunConfig
from social_sim.longrun.provider import (
    AuthorizationError, M5ProviderClient, load_provider_environment, validate_real_authorization,
)
from social_sim.provider_runtime.environment import git_value
from social_sim.provider_runtime.safety import exception_type, write_json

DEFAULT_PROTOCOL = ROOT / "config/experimental/m5_longrun_v1.json"
REGISTRY = ROOT / "run/evaluation/m5_longrun"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("offline", "real"), default="offline",
                   help="默认 offline：合成自适应策略，不加载凭据或构造真实 client")
    p.add_argument("--session-id", help="全新唯一会话 ID；offline 省略时自动生成")
    p.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL,
                   help="冻结 JSON 配置；real 必须使用独立的 mode=real 正预算协议")
    p.add_argument("--sim-days", type=int, help="1..30；real 必须等于冻结配置")
    p.add_argument("--max-decisions", type=int, help="高层决策预算；real 必须等于冻结配置")
    p.add_argument("--max-provider-requests", type=int,
                   help="真实 POST 预算；默认 0，正预算仍需独立授权文件")
    p.add_argument("--max-wall-seconds", type=float,
                   help="本轮墙钟上限；real 必须等于冻结配置")
    p.add_argument("--allow-provider", action="store_true", help="明确 real opt-in，不能替代授权文件")
    p.add_argument("--execution-commit", help="与授权/验收记录及干净 HEAD 完全一致的40位提交")
    p.add_argument("--protocol-hash", help="与冻结 LongRunConfig 规范 JSON SHA256 完全一致")
    p.add_argument("--authorization-path", type=Path,
                   help="本轮独立批准的 JSON：session/commit/hash/budget/acceptance/request_policy")
    p.add_argument("--env-file", type=Path, help="仅全部 real 门禁通过后只读解析，不 source")
    p.add_argument("--resume", type=Path, metavar="SESSION_DIR",
                   help="显式恢复；real 需独立 resume:true 授权，同提交/协议/总预算且无 UNKNOWN")
    p.add_argument("--export-only", type=Path, metavar="SESSION_DIR",
                   help="只读导出：不加载凭据、不构造 client、不运行世界动作")
    p.add_argument("--output", type=Path, help="export-only 的全新目标目录，禁止覆盖历史")
    p.add_argument("--output-root", type=Path,
                   help="offline 新会话注册目录；real 固定使用仓库注册目录")
    return p


def _resolve(path: Path | None) -> Path | None:
    return path if path is None or path.is_absolute() else ROOT / path


def _config(args) -> LongRunConfig:
    path = _resolve(args.protocol)
    if path.suffix != ".json" or path.resolve().suffix != ".json":
        raise AuthorizationError("FROZEN_PROTOCOL_JSON_REQUIRED")
    frozen = LongRunConfig.load(path)
    overrides = {name: getattr(args, name) for name in
                 ("sim_days", "max_decisions", "max_provider_requests", "max_wall_seconds")
                 if getattr(args, name) is not None}
    if args.mode == "real":
        # The current default protocol's budget is zero. Reject before credential
        # loading even if a key happens to be present or --allow-provider is used.
        if frozen.max_provider_requests == 0:
            raise AuthorizationError("ZERO_PROVIDER_BUDGET_NOT_AUTHORIZED")
        if frozen.mode != "real":
            raise AuthorizationError("FROZEN_REAL_PROTOCOL_REQUIRED")
        if any(value != getattr(frozen, name) for name, value in overrides.items()):
            raise AuthorizationError("REAL_PROTOCOL_OVERRIDE_FORBIDDEN")
        return frozen
    if frozen.mode != "offline":
        raise AuthorizationError("OFFLINE_PROTOCOL_REQUIRED")
    return replace(frozen, **overrides)


def _real_resume_guard(saved: dict, args, config: LongRunConfig) -> int:
    """Inspect durable facts before key loading, repeated under the writable lock."""
    previous = saved["metadata"].get("execution_authorization", {})
    if (saved["manifest"]["protocol_hash"] != config.protocol_hash
            or saved["metadata"].get("execution_commit") != args.execution_commit
            or previous.get("approved") is not True
            or previous.get("session_id") != args.session_id):
        raise AuthorizationError("RESUME_ORIGINAL_AUTHORIZATION_MISMATCH")
    if any(row["phase"] in {"REQUEST_REGISTERED", "RESPONSE_OBSERVED"}
           for row in saved["requests"]):
        raise AuthorizationError("UNCERTAIN_REQUEST_STATE")
    state = saved["session"]["state"]
    active = any(c["status"] in {"ACTIVE", "PAUSED"} for c in saved["world"]["commitments"])
    allowed = state in {"PAUSED", "COMMITMENT_ACTIVE", "CHECKPOINTED", "RECOVERY_REQUIRED"}
    if state == "STOPPED_BY_BUDGET":
        allowed = active and saved["session"]["stop_reason"] == "REQUEST_BUDGET_REACHED"
    if not allowed:
        raise AuthorizationError("REAL_TERMINAL_STATE_RESUME_FORBIDDEN")
    if _resolve(args.resume).resolve() != (REGISTRY / args.session_id).resolve():
        raise AuthorizationError("REAL_RESUME_REGISTRY_MISMATCH")
    return previous.get("max_provider_requests")


async def _execute(args, config, authorization=None) -> dict:
    from social_sim.longrun.runner import LongRunRunner
    from social_sim.longrun.session import LongRunSession
    registry = _resolve(args.output_root) or REGISTRY
    provenance = {
        "execution_commit": git_value(ROOT, "rev-parse", "HEAD"),
        "protocol_hash": config.protocol_hash,
        "result_class": ("REAL_MODEL_AUTONOMOUS_LONG_RUN" if config.mode == "real"
                         else "SCRIPTED_OR_FAKE_LONG_RUN"),
    }
    if authorization is not None:
        provenance["execution_authorization"] = authorization
    session = (LongRunSession.open(_resolve(args.resume), resume=True) if args.resume is not None
               else LongRunSession.create(registry, args.session_id, config, provenance))
    with session:
        client = None
        primary_error = None
        run_number = session.load()["resume_count"]
        try:
            if session.config.mode == "offline":
                from social_sim.longrun.policy import FakeLongRunPolicy
                client = FakeLongRunPolicy(session.world, session.config)
            else:
                if args.resume is not None:
                    _real_resume_guard(session.export_data(), args, session.config)
                    receipt = session.dir / f"resume_authorization_{run_number:06d}.json"
                    if receipt.exists():
                        raise AuthorizationError("RESUME_AUTHORIZATION_RECEIPT_ALREADY_EXISTS")
                    write_json(receipt, {"stage": "EXECUTION_AUTHORIZATION_VERIFIED",
                                        "execution_authorization": authorization})
                from social_sim.provider_runtime.environment import repository_info
                info = repository_info(ROOT)
                if (info.get("git_commit") != args.execution_commit
                        or not all(info.get(key) is True for key in
                                   ("parent_repository", "worktree_clean", "upstream_matches"))):
                    raise AuthorizationError("REAL_REPOSITORY_GATE_FAILED")
                # Session creation holds its exclusive lock and has recorded
                # authorization before this first contact with credentials.
                provider = load_provider_environment(_resolve(args.env_file))
                for name in ("httpx", "httpcore", "anyio"):
                    logging.getLogger(name).setLevel(logging.CRITICAL)
                client = M5ProviderClient(provider, session.config)
            result = await LongRunRunner(session, client).run()
        except BaseException as error:
            primary_error = error
            raise
        finally:
            cleanup = {"cleanup_outcome": "NOT_REQUIRED", "exception_type": None,
                       "automatic_retry": False}
            cleanup_error = None
            if client is not None and hasattr(client, "aclose"):
                try:
                    await asyncio.wait_for(client.aclose(), timeout=5)
                    cleanup["cleanup_outcome"] = "CLOSED"
                except (Exception, asyncio.CancelledError) as error:
                    cleanup_error = error
                    cleanup.update(cleanup_outcome="FAILED", exception_type=exception_type(error))
            try:
                receipt = session.dir / f"cleanup_run_{run_number:06d}.json"
                if receipt.exists():
                    raise RuntimeError("CLEANUP_RECEIPT_ALREADY_EXISTS")
                write_json(receipt, cleanup)
            except Exception:
                if primary_error is None:
                    raise
            if cleanup_error is not None and primary_error is None:
                raise RuntimeError("CLIENT_CLEANUP_FAILED") from None
        from social_sim.longrun.reporting import export_reports
        report = export_reports(session)
        if report.get("evaluation", {}).get("L1", {}).get("status") != "PASS":
            # The final independent audit can invalidate a provisional horizon
            # result. Preserve world time/effects and export the durable failure.
            session.transition("STOPPED_BY_FAILURE", "INVARIANT_FAILED")
            result = session.summary()
            result["final_audit_failed"] = True
            export_reports(session)
        return result


def main(argv=None) -> int:
    p = parser()
    args = p.parse_args(argv)
    if args.export_only is not None:
        incompatible = (args.resume is not None or args.output is None or args.allow_provider
                        or args.env_file is not None or args.authorization_path is not None
                        or args.execution_commit or args.protocol_hash or args.session_id
                        or args.output_root is not None or args.mode != "offline")
        if incompatible:
            p.error("export-only 只接受源会话与全新的 --output")
        from social_sim.longrun.session import LongRunSession
        exported = LongRunSession.export_only(_resolve(args.export_only))
        output = _resolve(args.output)
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "export.json", exported)
        from social_sim.longrun.reporting import export_reports
        export_reports(exported, output_dir=output)
        print(f"ARTIFACT_DIR={output}\nREAD_ONLY_RECOVERY=PASS\nNEW_REAL_PROVIDER_REQUESTS=0")
        return 0
    if args.output is not None:
        p.error("--output 仅用于 export-only")
    if args.mode == "offline" and (args.allow_provider or args.env_file is not None
                                   or args.authorization_path is not None
                                   or args.execution_commit or args.protocol_hash):
        p.error("offline 不接受真实凭据或执行授权参数")
    if args.mode == "real" and args.output_root is not None:
        p.error("real 不能改变会话注册根目录")
    if args.resume is not None and args.session_id:
        p.error("resume 使用已有会话目录，不接受新 session-id")
    try:
        saved = None
        if args.resume is not None:
            from social_sim.longrun.session import LongRunSession
            saved = LongRunSession.export_only(_resolve(args.resume))
            # Validate mode before opening a writable world or reading a key.
            saved_config = LongRunConfig.from_dict(saved["manifest"]["config"])
            if saved_config.mode != args.mode:
                raise AuthorizationError("RESUME_MODE_MISMATCH")
            if any(getattr(args, name) is not None for name in
                   ("sim_days", "max_decisions", "max_provider_requests", "max_wall_seconds")):
                raise AuthorizationError("RESUME_PROTOCOL_OVERRIDE_FORBIDDEN")
            config = saved_config
            args.session_id = saved["session"]["session_id"]
            if args.mode == "real" and _config(args).protocol_hash != config.protocol_hash:
                raise AuthorizationError("RESUME_FROZEN_PROTOCOL_MISMATCH")
        else:
            config = _config(args)
        if args.session_id is None:
            if args.mode == "real":
                raise AuthorizationError("REAL_SESSION_ID_REQUIRED")
            args.session_id = ("offline_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                               + "_" + uuid.uuid4().hex[:12])
        authorization = None
        if args.mode == "real":
            previous_budget = (_real_resume_guard(saved, args, config)
                               if args.resume is not None else None)
            authorization = validate_real_authorization(
                root=ROOT, registry=REGISTRY, config=config, session_id=args.session_id,
                allow_provider=args.allow_provider, execution_commit=args.execution_commit,
                protocol_hash=args.protocol_hash, frozen_protocol_hash=config.protocol_hash,
                authorization_path=_resolve(args.authorization_path), resume=args.resume is not None,
                previous_authorized_budget=previous_budget,
            )
        result = asyncio.run(_execute(args, config, authorization))
    except AuthorizationError as error:
        print(f"M5_AUTHORIZATION_REFUSED={error}\nNEW_REAL_PROVIDER_REQUESTS=0")
        return 1
    except Exception as error:
        print(f"M5_STOPPED_EXCEPTION_TYPE={exception_type(error)}; REVIEW_SESSION", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    if args.mode == "offline":
        print("NEW_REAL_PROVIDER_REQUESTS=0")
    return 0 if result.get("stop_reason") == "SIMULATION_HORIZON_REACHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
