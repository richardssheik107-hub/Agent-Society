#!/usr/bin/env python3
"""只连接 127.0.0.1：验证实际 httpx/httpcore/anyio 请求、读取和关闭。"""
from __future__ import annotations

import asyncio
import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    from social_sim.decision import OpenAICompatibleDecisionClient
    from social_sim.provider_runtime.safety import exception_type
    original_connect = socket.socket.connect
    def local_only(sock, address):
        if not isinstance(address, tuple) or address[0] != "127.0.0.1":
            raise RuntimeError("external network forbidden")
        return original_connect(sock, address)
    socket.socket.connect = local_only
    hits = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            hits.append(self.path)
            assert set(request) == {"model", "messages"}
            payload = {"model": "loopback-fixture", "choices": [{"finish_reason": "stop",
                       "message": {"role": "assistant", "content": '{"activity":"SLEEP","target":null}'}}]}
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    async def exercise():
        client = OpenAICompatibleDecisionClient(base_url=f"http://127.0.0.1:{server.server_port}/v1",
                                               api_key="offline-placeholder", model="loopback-fixture",
                                               minimal_request=True, timeout_seconds=5)
        try:
            reply = await asyncio.wait_for(client.complete("JSON only", "Return SLEEP"), timeout=5)
            assert json.loads(reply.raw_text) == {"activity": "SLEEP", "target": None}
            assert client.last_metadata.http_status == 200
            assert client.provider_request_count == 1
        finally:
            await asyncio.wait_for(client.aclose(), timeout=5)
    try:
        asyncio.run(exercise())
        assert len(hits) == 1
        result = {"loopback_http_stack": "PASS", "mode": "LOCAL_LOOPBACK_NOT_PROVIDER",
                  "loopback_requests": 1, "remote_provider_requests": 0}
    except Exception as error:
        result = {"loopback_http_stack": "FAIL", "exception_type": exception_type(error),
                  "loopback_requests": len(hits), "remote_provider_requests": 0}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        socket.socket.connect = original_connect
    print(json.dumps(result))
    return 0 if result["loopback_http_stack"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
