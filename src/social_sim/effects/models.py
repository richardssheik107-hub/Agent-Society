"""Effects describe approved changes but never apply them to the world."""

from dataclasses import dataclass
from datetime import datetime
import math

from social_sim.decision.models import ActionType


MEAL_HUNGER_REDUCTION = 0.6


@dataclass(frozen=True)
class MoveEffect:
    agent_id: int
    from_location: str
    to_location: str

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, int) or isinstance(self.agent_id, bool):
            raise ValueError("agent_id must be an integer")
        if not isinstance(self.from_location, str) or not self.from_location:
            raise ValueError("from_location must be a nonempty string")
        if not isinstance(self.to_location, str) or not self.to_location:
            raise ValueError("to_location must be a nonempty string")


def _nonnegative_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def _nonnegative_number(value: float, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be a finite nonnegative number")


@dataclass(frozen=True)
class PurchaseEffect:
    """One approved purchase with snapshots for reducer conflict detection."""

    agent_id: int
    location_id: str
    item_id: str
    quantity: int
    unit_price: float
    expected_money_before: float
    expected_stock_before: int
    expected_inventory_before: int

    def __post_init__(self) -> None:
        _nonnegative_int(self.agent_id, "agent_id")
        if not isinstance(self.location_id, str) or not self.location_id.strip():
            raise ValueError("location_id must be a nonempty string")
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a nonempty string")
        _nonnegative_int(self.quantity, "quantity")
        if self.quantity < 1:
            raise ValueError("quantity must be positive")
        _nonnegative_number(self.unit_price, "unit_price")
        _nonnegative_number(self.expected_money_before, "expected_money_before")
        _nonnegative_int(self.expected_stock_before, "expected_stock_before")
        _nonnegative_int(self.expected_inventory_before, "expected_inventory_before")


@dataclass(frozen=True)
class EatEffect:
    """One approved consumption with snapshots for reducer conflict detection."""

    agent_id: int
    item_id: str
    quantity: int
    expected_inventory_before: int
    expected_hunger_before: float
    new_hunger: float

    def __post_init__(self) -> None:
        _nonnegative_int(self.agent_id, "agent_id")
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a nonempty string")
        _nonnegative_int(self.quantity, "quantity")
        if self.quantity < 1:
            raise ValueError("quantity must be positive")
        _nonnegative_int(self.expected_inventory_before, "expected_inventory_before")
        _nonnegative_number(self.expected_hunger_before, "expected_hunger_before")
        _nonnegative_number(self.new_hunger, "new_hunger")
        if self.expected_hunger_before > 1 or self.new_hunger > 1:
            raise ValueError("hunger must be in [0, 1]")


@dataclass(frozen=True)
class StartActivityEffect:
    """Start one timed activity after a rule has validated its preconditions."""

    agent_id: int
    action: ActionType
    expected_location: str
    expected_time: str
    end_time: str

    def __post_init__(self) -> None:
        _nonnegative_int(self.agent_id, "agent_id")
        if isinstance(self.action, str):
            try:
                object.__setattr__(self, "action", ActionType(self.action))
            except ValueError as exc:
                raise ValueError("action must be a timed activity") from exc
        if self.action not in (ActionType.SLEEP, ActionType.WORK, ActionType.LEISURE,
                               ActionType.PERSONAL_CARE, ActionType.CHORES):
            raise ValueError("action must be a timed activity")
        if not isinstance(self.expected_location, str) or not self.expected_location.strip():
            raise ValueError("expected_location must be nonempty")
        try:
            start = datetime.fromisoformat(self.expected_time)
            end = datetime.fromisoformat(self.end_time)
        except (TypeError, ValueError) as exc:
            raise ValueError("activity times must be ISO datetime strings") from exc
        if end <= start:
            raise ValueError("activity end_time must follow expected_time")


Effect = MoveEffect | PurchaseEffect | EatEffect | StartActivityEffect
