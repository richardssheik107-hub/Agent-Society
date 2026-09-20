"""测试进程使用离线占位配置，所有测试禁止真实网络。"""
import os
import socket

import pytest

# 上游在导入时检查配置；这些不是凭据，不从用户 .env 加载模型配置。
os.environ["AGENTSOCIETY_LLM_API_KEY"] = "offline-placeholder-not-a-secret"
os.environ["AGENTSOCIETY_LLM_API_BASE"] = "http://127.0.0.1:9/v1"
os.environ["AGENTSOCIETY_LLM_MODEL"] = "openai/offline-placeholder"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("unit tests must not access the network")
    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
