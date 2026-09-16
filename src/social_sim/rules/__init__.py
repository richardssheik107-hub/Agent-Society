"""Deterministic action validation; this package never mutates WorldState."""

from .base import ReasonCode, Rule, RuleResult
from .eating import EatRule
from .engine import RuleEngine
from .movement import MoveRule
from .purchasing import BuyRule

__all__ = ["BuyRule", "EatRule", "MoveRule", "ReasonCode", "Rule", "RuleEngine", "RuleResult"]
