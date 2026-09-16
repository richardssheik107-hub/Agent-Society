"""Deterministic action requests derived from decision proposals."""

from .models import ActionIntent, proposal_to_intent

__all__ = ["ActionIntent", "proposal_to_intent"]
