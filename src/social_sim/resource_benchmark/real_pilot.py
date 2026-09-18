"""Single-request-per-cell real provider pilot with incremental safe progress."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import httpx

from social_sim.decision.client import DecisionClientError, DecisionModelClient, ProviderContractError

from .benchmark import parse_resource_proposal
from .context import build_resource_prompt, context_without_resources
from .models import ResourceScenario, ScheduleEntry
from .scorer import score_proposal, summarize_resource_rows


def _safe_metadata_fields(client: DecisionModelClient) -> dict[str, object]:
    metadata = getattr(client, "last_metadata", None)
    return {
        "http_status": getattr(metadata, "http_status", None),
        "http_error_code": getattr(metadata, "http_error_code", None),
        "http_error_type": getattr(metadata, "http_error_type", None),
        "http_error_param": getattr(metadata, "http_error_param", None),
        "request_id": getattr(metadata, "request_id", None),
        "sanitized_error_message": getattr(metadata, "sanitized_error_message", None),
    }


def _safe_provider_model(value: object) -> str | None:
    if isinstance(value, str) and len(value) <= 128 and all(c.isalnum() or c in "._:-/" for c in value):
        return value
    return None


def _base_row(entry: ScheduleEntry, scenario: ResourceScenario, prompt: object) -> dict[str, object]:
    projection = scenario.truth.project(entry.level)
    return {
        "case_id": entry.case_id,
        "scenario_id": scenario.scenario_id,
        "family": scenario.family,
        "repetition": entry.repetition,
        "level": entry.level.value,
        "resource_level": entry.level.value,
        "visible_resources": dict(projection.values),
        "truth_values": dict(scenario.truth.values),
        "resource_truth_sha256": hashlib.sha256(json.dumps(dict(scenario.truth.values), sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "fixed_context_hash": hashlib.sha256(context_without_resources(prompt.context).encode()).hexdigest(),
        "context_chars": len(prompt.context),
        "prompt_chars": prompt.prompt_chars,
        "strict_parse_valid": False,
        "resource_projection_valid": tuple(projection.values) == tuple(scenario.truth.values)[:len(projection.values)],
        "action": None,
        "target": None,
        "provider_status": "UNKNOWN",
        "provider_model": None,
        "raw_output_chars": None,
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "latency_seconds": None,
    }


async def run_real_pilot(
    client: DecisionModelClient,
    scenarios: Sequence[ResourceScenario],
    schedule: Sequence[ScheduleEntry],
    *,
    progress_path: Path | str | None = None,
    heldout_distributions: Mapping[str, object] | None = None,
    on_progress: Callable[[dict[str, object]], None] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    if len(by_id) != len(tuple(scenarios)):
        raise ValueError("scenario IDs must be unique")
    if len({entry.case_id for entry in schedule}) != len(schedule):
        raise ValueError("schedule case IDs must be unique")
    progress = Path(progress_path) if progress_path is not None else None
    if progress is not None:
        progress.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for entry in schedule:
        scenario = by_id.get(entry.scenario_id)
        if scenario is None:
            raise ValueError(f"schedule references unknown scenario: {entry.scenario_id}")
        projection = scenario.truth.project(entry.level)
        resource_prompt = build_resource_prompt(scenario, projection)
        row = {
            **_base_row(entry, scenario, resource_prompt),
        }
        started = time.perf_counter()
        before_requests = getattr(client, "provider_request_count", None)
        try:
            reply = await client.complete(resource_prompt.system, resource_prompt.user)
            row["raw_output_chars"] = len(reply.raw_text)
            row["provider_model"] = _safe_provider_model(reply.provider_model)
            row["input_tokens"] = reply.input_tokens
            row["output_tokens"] = reply.output_tokens
            row["reasoning_tokens"] = reply.reasoning_tokens
            proposal, parsed = parse_resource_proposal(reply.raw_text, scenario)
            row.update({
                "strict_parse_valid": parsed.strict_valid,
                "parse_failure_type": parsed.failure_type,
                "parse_failure_category": parsed.failure_category,
                "recoverable_valid": parsed.recoverable_valid,
                "provider_status": "SUCCESS" if proposal is not None else "PARSE_ERROR",
            })
            if proposal is not None:
                row["action"] = proposal.action.value
                row["target"] = proposal.target
                row.update(score_proposal(
                    scenario, proposal.action, proposal.target,
                    (heldout_distributions or {}).get(scenario.scenario_id),
                ))
            row.update(_safe_metadata_fields(client))
        except (httpx.TimeoutException, asyncio.TimeoutError):
            row["provider_status"] = "TIMEOUT"
            row.update(_safe_metadata_fields(client))
        except ProviderContractError as exc:
            row["provider_status"] = "PARSE_ERROR"
            row["provider_contract_category"] = exc.category
            row.update(_safe_metadata_fields(client))
        except (DecisionClientError, httpx.HTTPError) as exc:
            row["provider_status"] = "HTTP_ERROR"
            row["error_type"] = type(exc).__name__
            row.update(_safe_metadata_fields(client))
        except Exception as exc:  # pragma: no cover - real-provider safety net
            row["provider_status"] = "ARCHITECTURE_ERROR"
            row["error_type"] = type(exc).__name__
        row["latency_seconds"] = round(time.perf_counter() - started, 6)
        after_requests = getattr(client, "provider_request_count", None)
        if isinstance(before_requests, int) and isinstance(after_requests, int):
            row["provider_request_count"] = after_requests - before_requests
        else:
            row["provider_request_count"] = 1
        rows.append(row)
        if progress is not None:
            with progress.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        if on_progress is not None:
            on_progress(row)
    return rows, summarize_resource_rows(rows)
