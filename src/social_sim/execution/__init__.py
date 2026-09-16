"""Action execution orchestration; rules remain the source of behavior."""

from .executor import ActionExecutor, ExecutionOutcome

__all__ = ["ActionExecutor", "ExecutionOutcome"]
