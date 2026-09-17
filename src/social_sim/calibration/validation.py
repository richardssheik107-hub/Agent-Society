"""Fail-closed checks for research-only calibration outputs."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from .ontology import CORE5, DOMAIN_ORDER, TARGET_MINUTE_COVERAGE


def validate_coverage(core5: dict[str, object], core7: dict[str, object], source_coverage: dict[str, object]) -> None:
    if int(core5["episodes"]) != int(source_coverage["total_episodes"]) or int(core5["covered_episodes"]) != int(source_coverage["mapped_to_core_count"]):
        raise ValueError("Core5 episode counts disagree with B1.1 artifact")
    if int(core5["minutes"]) != int(source_coverage["total_minutes"]) or int(core5["covered_minutes"]) != int(source_coverage["mapped_to_core_minutes"]):
        raise ValueError("Core5 minute counts disagree with B1.1 artifact")
    if not 0 <= float(core5["minute_coverage"]) <= float(core7["minute_coverage"]) <= 1:
        raise ValueError("ontology minute coverage not monotone")
    if int(core7["covered_minutes"]) + int(core7["OTHER_remaining_minutes"]) != int(core7["minutes"]):
        raise ValueError("coverage minutes do not reconcile")


def validate_profile(profile: dict[str, object], source_sha: str, recommendation: str) -> None:
    if profile["source"]["archive_sha256"] != source_sha or profile["source"]["dataset"] != "NHAPS_AHTUS_1992_94":
        raise ValueError("candidate provenance differs from source archive")
    activities = profile["ontology"]["activities"]
    if activities != [*CORE5, *DOMAIN_ORDER] or profile["ontology"]["status"] != "EXPERIMENTAL":
        raise ValueError("experimental ontology incomplete")
    if recommendation == "RECOMMENDED_FOR_NEXT_EXPERIMENT" and profile["coverage"]["all_adults"]["minute_coverage"] < TARGET_MINUTE_COVERAGE:
        raise ValueError("recommendation falls below target")
    for activity in activities:
        if not isinstance(profile["duration_candidates"][activity], int) or profile["duration_candidates"][activity] <= 0:
            raise ValueError(f"invalid experimental duration: {activity}")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_unchanged(paths: dict[Path, str]) -> None:
    for path, original in paths.items():
        if file_sha256(path) != original:
            raise ValueError(f"production file modified: {path}")
