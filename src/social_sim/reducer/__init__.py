"""Deterministic application of validated effects to objective world state."""

from .state_reducer import StateConflictError, StateReducer

__all__ = ["StateConflictError", "StateReducer"]
