"""Optional real-provider Object Set A/B/C pilot.

The runner stores parsed selections and safe numeric metadata, never raw prompts,
raw completions, credentials, or hidden reasoning text.
"""

from __future__ import annotations

import asyncio
from collections import Counter
import time
from dataclasses import dataclass

import httpx

from social_sim.decision.client import DecisionModelClient

from .benchmark import ObjectChoiceEvaluator, build_choice_prompt, parse_object_choice, summarize_rows
from .catalog import ObjectCatalog, build_scenarios
from .models import ArchitectureArm


@dataclass(frozen=True)
class PilotConfig:
    repetitions: int = 2
    top_k: int = 10
    max_scenarios: int | None = None
    attempt_id: str = "attempt_2"

    def __post_init__(self) -> None:
        if self.repetitions <= 0 or self.top_k <= 0:
            raise ValueError("repetitions/top_k must be positive")
        if self.max_scenarios is not None and self.max_scenarios <= 0:
            raise ValueError("max_scenarios must be positive")
        if not self.attempt_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in self.attempt_id):
            raise ValueError("attempt_id must be a simple artifact-safe label")


def pilot_schedule(config: PilotConfig) -> list[tuple[int, object, ArchitectureArm]]:
    scenarios = build_scenarios()
    if config.max_scenarios is not None:
        scenarios = scenarios[: config.max_scenarios]
    arms = tuple(ArchitectureArm)
    schedule: list[tuple[int, object, ArchitectureArm]] = []
    for repetition in range(1, config.repetitions + 1):
        for index, scenario in enumerate(scenarios):
            offset = (index + repetition - 1) % len(arms)
            for step in range(len(arms)):
                schedule.append((repetition, scenario, arms[(offset + step) % len(arms)]))
    return schedule


async def run_real_pilot(
    client: DecisionModelClient,
    catalog: ObjectCatalog,
    config: PilotConfig | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    cfg = config or PilotConfig()
    evaluator = ObjectChoiceEvaluator(catalog, top_k=cfg.top_k)
    rows: list[dict[str, object]] = []
    for case_number, (repetition, scenario, arm) in enumerate(pilot_schedule(cfg), 1):
        candidates = catalog.retrieve(scenario, k=cfg.top_k) if arm is not ArchitectureArm.LLM_ONLY else ()
        system, user = build_choice_prompt(scenario, arm, candidates)
        started = time.perf_counter()
        try:
            reply = await client.complete(system, user)
            elapsed = time.perf_counter() - started
        except (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException):
            row = {
                "case_number": case_number,
                "scenario_id": scenario.scenario_id,
                "domain": scenario.domain.value,
                "arm": arm.value,
                "repetition": repetition,
                "provider_status": "TIMEOUT",
                "latency_seconds": round(time.perf_counter() - started, 6),
            }
            row.update(_safe_metadata_fields(client))
            rows.append(row)
            continue
        except Exception as exc:
            row = {
                "case_number": case_number,
                "scenario_id": scenario.scenario_id,
                "domain": scenario.domain.value,
                "arm": arm.value,
                "repetition": repetition,
                "provider_status": "HTTP_ERROR" if type(exc).__name__ == "DecisionClientError" else type(exc).__name__,
                "latency_seconds": round(time.perf_counter() - started, 6),
            }
            row.update(_safe_metadata_fields(client))
            rows.append(row)
            continue
        try:
            choice = parse_object_choice(reply.raw_text)
        except ValueError as exc:
            row = {
                "case_number": case_number,
                "scenario_id": scenario.scenario_id,
                "domain": scenario.domain.value,
                "arm": arm.value,
                "repetition": repetition,
                "provider_status": str(exc),
                "latency_seconds": round(time.perf_counter() - started, 6),
                "raw_output_chars": len(reply.raw_text),
                "provider_model": reply.provider_model,
            }
            row.update(_safe_metadata_fields(client))
            rows.append(row)
            continue
        try:
            row = evaluator.evaluate(scenario, arm, choice)
            row.update(
                case_number=case_number,
                repetition=repetition,
                provider_status="SUCCESS",
                latency_seconds=round(elapsed, 6),
                input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens,
                reasoning_tokens=reply.reasoning_tokens,
                provider_model=reply.provider_model,
                prompt_chars=len(system) + len(user),
                raw_output_chars=len(reply.raw_text),
            )
        except Exception as exc:  # provider/architecture taxonomy is intentionally compact
            row = {
                "case_number": case_number,
                "scenario_id": scenario.scenario_id,
                "domain": scenario.domain.value,
                "arm": arm.value,
                "repetition": repetition,
                "provider_status": "ARCHITECTURE_ERROR",
                "error_type": type(exc).__name__,
                "latency_seconds": round(time.perf_counter() - started, 6),
            }
            row.update(_safe_metadata_fields(client))
        rows.append(row)
    successful = [row for row in rows if row.get("provider_status") == "SUCCESS"]
    return rows, summarize_pilot_rows(rows, successful)


def _safe_metadata_fields(client: DecisionModelClient) -> dict[str, object]:
    """Copy only redacted envelope metadata into a failed row."""
    metadata = getattr(client, "last_metadata", None)
    return {
        "http_status": getattr(metadata, "http_status", None),
        "http_error_code": getattr(metadata, "http_error_code", None),
        "http_error_type": getattr(metadata, "http_error_type", None),
        "http_error_param": getattr(metadata, "http_error_param", None),
        "request_id": getattr(metadata, "request_id", None),
        "sanitized_error_message": getattr(metadata, "sanitized_error_message", None),
    }


def summarize_pilot_rows(
    rows: list[dict[str, object]], successful: list[dict[str, object]] | None = None
) -> dict[str, object]:
    """Return safe status, backend, arm metrics, and matched-triple facts."""
    success_rows = successful if successful is not None else [
        row for row in rows if row.get("provider_status") == "SUCCESS"
    ]
    statuses = Counter(str(row.get("provider_status", "UNKNOWN")) for row in rows)
    failed_rows = [row for row in rows if row.get("provider_status") != "SUCCESS"]
    http_status_counts = Counter(
        str(row["http_status"])
        for row in failed_rows
        if isinstance(row.get("http_status"), int)
    )
    http_error_code_counts = Counter(
        str(row["http_error_code"])
        for row in failed_rows
        if isinstance(row.get("http_error_code"), str) and row.get("http_error_code")
    )
    backend_models = Counter(
        str(row["provider_model"])
        for row in success_rows
        if isinstance(row.get("provider_model"), str) and row.get("provider_model")
    )
    arm_metrics = summarize_rows(success_rows)
    by_key: dict[tuple[str, int], dict[str, dict[str, object]]] = {}
    for row in success_rows:
        key = (str(row["scenario_id"]), int(row["repetition"]))
        by_key.setdefault(key, {})[str(row["arm"])] = row
    matched = [group for group in by_key.values() if set(group) == {arm.value for arm in ArchitectureArm}]
    matched_rows = sum(len(group) for group in matched)

    def matched_mean(arm: ArchitectureArm, field: str) -> float | None:
        values = [
            float(group[arm.value][field])
            for group in matched
            if isinstance(group[arm.value].get(field), (int, float))
        ]
        return round(sum(values) / len(values), 6) if values else None

    matched_metrics = {
        arm.value: {
            field: matched_mean(arm, field)
            for field in (
                "runtime_executable",
                "usable_effect_coverage",
                "authoritative_effect_coverage",
                "model_estimated_field_rate",
                "latency_seconds",
                "prompt_chars",
                "input_tokens",
            )
        }
        for arm in ArchitectureArm
    }

    def delta(field: str, left: ArchitectureArm, right: ArchitectureArm) -> float | None:
        left_value = matched_metrics[left.value][field]
        right_value = matched_metrics[right.value][field]
        if left_value is None or right_value is None:
            return None
        return round(left_value - right_value, 6)

    ab_deltas = {
        field: delta(field, ArchitectureArm.LLM_ONLY, ArchitectureArm.CATALOG_TOPK)
        for field in (
            "runtime_executable",
            "usable_effect_coverage",
            "authoritative_effect_coverage",
        )
    }
    if not matched:
        necessity_signal = "UNRESOLVED"
    elif any(
        value is not None and value <= -0.15
        for value in (ab_deltas["runtime_executable"], ab_deltas["usable_effect_coverage"])
    ):
        necessity_signal = "STRONG"
    elif (
        any(
            value is not None and value <= -0.05
            for value in (ab_deltas["runtime_executable"], ab_deltas["usable_effect_coverage"])
        )
        or (ab_deltas["authoritative_effect_coverage"] is not None
            and ab_deltas["authoritative_effect_coverage"] <= -0.05)
    ):
        necessity_signal = "MODERATE"
    else:
        necessity_signal = "WEAK"
    hybrid_success = [
        row for row in success_rows if row.get("arm") == ArchitectureArm.HYBRID.value
    ]
    hybrid_signal = (
        "SUPPORTED"
        if matched
        and matched_metrics[ArchitectureArm.HYBRID.value]["runtime_executable"] is not None
        and matched_metrics[ArchitectureArm.CATALOG_TOPK.value]["runtime_executable"] is not None
        and matched_metrics[ArchitectureArm.HYBRID.value]["runtime_executable"]
        >= matched_metrics[ArchitectureArm.CATALOG_TOPK.value]["runtime_executable"] - 0.05
        and any(bool(row.get("novel_created")) for row in hybrid_success)
        else "UNRESOLVED"
    )

    def mean_for(arm_name: ArchitectureArm, field: str) -> float | None:
        values = [
            float(row[field])
            for row in success_rows
            if row.get("arm") == arm_name.value and isinstance(row.get(field), (int, float))
        ]
        return round(sum(values) / len(values), 6) if values else None

    costs = {
        arm.value: {
            "mean_input_tokens": mean_for(arm, "input_tokens"),
            "median_input_tokens": _median_for(success_rows, arm, "input_tokens"),
            "mean_prompt_chars": mean_for(arm, "prompt_chars"),
            "mean_latency_seconds": mean_for(arm, "latency_seconds"),
        }
        for arm in ArchitectureArm
    }
    return {
        "scheduled": len(rows),
        "success": len(success_rows),
        "timeout": statuses.get("TIMEOUT", 0),
        "http_error": statuses.get("HTTP_ERROR", 0),
        "parse_error": sum(
            count for status, count in statuses.items()
            if status.startswith("INVALID_")
        ),
        "architecture_error": statuses.get("ARCHITECTURE_ERROR", 0),
        "status_counts": dict(sorted(statuses.items())),
        "http_status_counts": dict(sorted(http_status_counts.items())),
        "http_error_code_counts": dict(sorted(http_error_code_counts.items())),
        "backend_model_counts": dict(sorted(backend_models.items())),
        "arms": arm_metrics,
        "costs": costs,
        "matched_abc": len(matched),
        "matched_rows": matched_rows,
        "matched_metrics": matched_metrics,
        "a_vs_b_deltas": ab_deltas,
        "object_set_necessity_signal": necessity_signal,
        "hybrid_open_world_signal": hybrid_signal,
    }


def _median_for(
    rows: list[dict[str, object]], arm: ArchitectureArm, field: str
) -> float | None:
    values = sorted(
        float(row[field])
        for row in rows
        if row.get("arm") == arm.value and isinstance(row.get(field), (int, float))
    )
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return round(values[middle], 6)
    return round((values[middle - 1] + values[middle]) / 2, 6)
