"""Effects describe approved changes but never apply them to the world."""

from dataclasses import dataclass
import math


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


Effect = MoveEffect | PurchaseEffect | EatEffect
