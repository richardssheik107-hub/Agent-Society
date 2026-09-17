"""Short neutral display of aggregate activities, never diary text or weights."""

from __future__ import annotations

from .query import PriorResult


def format_prior(result: PriorResult) -> str:
    if not result.activities:
        raise ValueError("empty prior must not be silently formatted")
    prefix = f"prior: common around now after {result.previous_activity or 'unknown'} -> "
    hint = prefix + ",".join(result.activities)
    if len(hint) > 180:
        raise ValueError("prior exceeds hard 180-character budget")
    return hint
