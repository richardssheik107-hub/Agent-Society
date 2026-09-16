"""Effects describe approved changes but never apply them to the world."""

from dataclasses import dataclass


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
