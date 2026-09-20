"""长期一致性运行层；默认离线，AS2 适配器和模型客户端按需导入。"""
from .engine import ContinuityWorld
from .models import ObjectDefinition, initial_actor
from .validation import validate_world

__all__ = ["ContinuityWorld", "ObjectDefinition", "initial_actor", "validate_world"]
