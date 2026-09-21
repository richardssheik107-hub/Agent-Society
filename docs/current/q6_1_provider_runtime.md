# Q6.1：独立运行时预检与 Attempt 3

本页是 Attempt 2 之后的执行入口。原 [Q6.1 实验报告](q6_1_real_continuity_pilot.md) 与 Attempt 1/2 数字不修改。本轮只补齐运行环境、诊断、预检和串行门禁，不改变提示、初始世界或业务规则。

## 1. 为什么加这一层

Attempt 2 只记录到一次客户端请求尝试，没有 HTTP 响应或模型提案；关闭客户端时另有 `typing_extensions.sentinel` 导入错误。它提示本地依赖可能混用，但不是已确认的首次失败根因。需要分别检查：环境导入、真实 HTTP 栈、provider 响应、关闭客户端。

旧的 `provider_request_count` 在调用 HTTP POST 之前递增。本轮保留其语义，明确标注为“客户端尝试”；不能凭这个计数证明服务器已收到请求。

## 2. 已写好的代码

- `scripts/setup_q6_1_runtime.sh`：创建或使用父仓库的 `.venv-q61-runtime`，不使用多个 uv 缓存路径，不改官方子模块；安装要求并执行 `pip check`，记录解析后的精确版本。
- `scripts/check_q6_1_local_transport.py`：只对 127.0.0.1 的模拟服务执行一次完整 HTTP POST、读取与关闭，验证实际 httpx/httpcore/anyio 路径。不是火山请求，不能冒充鉴权通过。
- `scripts/check_q6_1_provider_runtime.py`：默认不发请求；可执行环境检查、单次真实预检，或额外授权预检通过后的一次四决策 Attempt 3。
- `social_sim.provider_runtime`：安全异常类名、阶段分类、环境来源检查、结果落盘、首次异常与清理异常分开保存。
- `ActivityDecisionRunner`：仅增加安全异常类型及响应元数据诊断，不改变决策或状态规则。

## 3. Windows / WSL 最省事的操作

不要再把 Bash 的 `$(...)` 包在容易被 PowerShell 提前展开的命令里，也不要把 uv 的多个 cache 目录拼接到 PYTHONPATH。直接打开 WSL 后执行脚本，或从 PowerShell 直接传脚本路径。

```powershell
wsl.exe -d Ubuntu -- bash /home/fergeson/projects/agent-society/scripts/setup_q6_1_runtime.sh
```

该命令只安装依赖和检查环境，不读取 API key，不发送模型请求。先确保父仓库已切到并拉取本 PR 分支。

接下来在 WSL 中进行一次本机网络栈验证：

```bash
cd /home/fergeson/projects/agent-society
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python scripts/check_q6_1_local_transport.py
```

应输出 `loopback_http_stack=PASS`、`remote_provider_requests=0`。如果失败，只修环境，不启动正式 pilot。

## 4. 真正调用火山时，只选下面一种方式执行一次

已有三个 CONTINUITY 环境变量时，不传 `--env-file`。若使用现有子模块中的受保护 `.env`，以下命令只读解析，不执行 `.env` 里的 shell 内容，也不输出密钥。优先用现有 `CONTINUITY_*`，缺少 key 时可从 `AGENTSOCIETY_LLM_API_KEY` 映射；地址和模型仅使用已约定的 Coding Plan 地址/别名，不自动尝试其他 endpoint。

**只授权一次真实预检，不运行 Attempt 3：**

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/check_q6_1_provider_runtime.py --allow-provider \
  --session-id q61-runtime-01 --env-file third_party/AgentSociety/.env
```

**授权一次预检，并在通过后自动进行一次四决策 Attempt 3：**

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/check_q6_1_provider_runtime.py --allow-provider --with-pilot \
  --session-id q61-runtime-01 --env-file third_party/AgentSociety/.env
```

上面两条是互斥选择，不是先后依次执行。第二条总预算上限为 **预检 1 次 + 正式 pilot 4 次 = 5 次客户端尝试**。不提供扩展到 12 次的入口。

同一个 session ID 已有目录时一律拒绝重跑；不同 ID 也有进程独占锁，防止并发误启动。发生中断后，不自动续跑，不自动生成新 ID，不删除旧目录。先检查既有 session、请求日志和 SQLite，再由操作者决定新尝试。请求开始标记不代表已收到响应。

## 5. PASS 的含义

预检必须同时满足：一个实际客户端尝试、HTTP 200、有效响应契约、严格二字段 JSON 与指定 SLEEP 提案一致、客户端关闭无异常。HTTP 200 但 JSON 不合法，仍不通过。正确响应后 close 失败，也不会启动 Attempt 3。

异常分类包括 PYTHON_ENVIRONMENT、CLIENT_CONSTRUCTION、NETWORK_RUNTIME、HTTP_ERROR、PROVIDER_CONTRACT、MODEL_OUTPUT、UNKNOWN_TRANSPORT、CLIENT_CLEANUP。只记录白名单异常类名，不记录 `str(error)`、堆栈、原始响应或隐藏推理。首次失败与 `cleanup_exception_type` 分开保存。

正式 pilot 复用 Q61PilotRunner、相同提示和 seed_demo。每项活动中不再请求模型；逐步打印安全状态并保存进度。少于四次完整决策、清理失败或没有跨决策反馈均不能标为 SUPPORTED。已知不变量失败或反馈不一致单独标记；其他不足为 INSUFFICIENT_EVIDENCE。

`SUPPORTED` 只表示本次短链状态与观察相容，不证明模型在因果意义上依赖了某个字段，也不证明七天/三十天生活正常。未覆盖的媒体/所有权情境不计为成功证据。

## 6. 产物与历史

新产物统一位于：

```text
run/evaluation/q6_1_provider_runtime/<session-id>/
  environment.json
  session.json
  report_zh.md
  preflight/summary.json
  preflight/progress.jsonl
  preflight/report_zh.md
  attempt_3/world.sqlite3
  attempt_3/request_progress.jsonl
  attempt_3/progress.jsonl
  attempt_3/summary.json
  attempt_3/decisions.jsonl
  attempt_3/events.jsonl
  attempt_3/final_state.json
  attempt_3/environment.json
  attempt_3/report_zh.md
```

Attempt 3 子目录仅在预检通过且另有 `--with-pilot` 授权时创建。新路径不覆盖 Attempt 1/2。单机日志和事务可追溯，不声称断电/跨机 exactly-once；输出磁盘本身损坏时应读已有进度，不重发请求。

## 7. 本轮执行状态与后续

本页初版的状态是：代码与离线验收准备中，**真实 provider 预检和 Attempt 3 尚未执行**。以随后验收记录和 CI 为准，不填造 HTTP 200 或模型结果。

仓库 CI 只跑 MockTransport 和本机回环，不读取 GitHub secrets，不发火山请求。真实环境使用单独 venv，不需要为了这个 1+4 pilot 重新安装整个 AS2/Ray 依赖。原有 AS2 和全量测试继续使用原 CI。

参考接口：[Python venv](https://docs.python.org/3/library/venv.html)、[HTTPX transports](https://www.python-httpx.org/advanced/transports/)。MockTransport 的通过不等于 DNS/TLS/鉴权已通过，因此保留独立真实预检。
