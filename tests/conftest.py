"""测试默认禁止真实网络，避免历史 smoke/新适配误调用 provider。"""
import socket

import pytest


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("unit tests must not access the network")
    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
