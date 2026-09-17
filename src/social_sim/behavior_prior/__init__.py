"""Deterministic, aggregate-only NHAPS behavior priors (Research A2-Fast)."""

from .formatter import format_prior
from .index import BehaviorPriorIndex, load_nested_worker_corpora
from .query import PriorQuery, PriorResult, previous_activity_from_events

__all__ = (
    "BehaviorPriorIndex", "PriorQuery", "PriorResult", "format_prior",
    "load_nested_worker_corpora", "previous_activity_from_events",
)
