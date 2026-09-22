# Q6.1：独立运行时预检与 Attempt 3

当前交付状态：**代码及离线验收已完成，真实预检和 Attempt 3 未执行**。准确测试结果、代码版本与 CI 链接见 [本轮验收记录](q6_1_provider_runtime_acceptance.md)。原 [Q6.1 报告](q6_1_real_continuity_pilot.md) 中 Attempt 1/2 保留原样。

## 1. 为什么增加这一步

Attempt 2 只得到一次客户端请求尝试，没有 HTTP 响应或模型提案；关闭客户端时另有 typing_extensions.sentinel 导入错误。它提示依赖可能混用，但不等于已证实首次失败原因。

现在分别检查：单一环境导入、客户端构造/关闭、本机真实 HTTP 栈、火山服务的真实响应。首次失败和清理失败分别保存，不再只有一个没有解释的 PROVIDER_ERROR。

## 2. 已有脚本及职责

| 文件 | 职责 | 是否调用火山 |
|---|---|---|
| `scripts/setup_q6_1_runtime.sh` | 创建父仓库独立 venv、安装已验收依赖、pip check、离线生命周期检查 | 否 |
| `scripts/check_q6_1_local_transport.py` | 对 127.0.0.1 完成一次实际 HTTP POST、读取与关闭 | 否 |
| `scripts/check_q6_1_provider_runtime.py --check-only` | 检查依赖来源与客户端构造/关闭 | 否 |
| `scripts/check_q6_1_provider_runtime.py --allow-provider ...` | 一次真实预检 | 最多一次 |
| 同上加 `--with-pilot` | 预检成功后进入一次四决策 Attempt 3 | 总计最多五次 |

正式部分仍使用原 Q61PilotRunner、原行为提示、原 seed_demo 和确定性世界规则。没有新增行为先验、脚本替代或模型修复请求。

## 3. 安装及零凭据本机验证

先在正确父仓库切到 `research/q6-real-continuity-pilot` 并正常拉取；工作区有改动时不要 reset/clean。不要在官方子模块中查找项目分支。

在 WSL 中执行：

```bash
cd /home/fergeson/projects/agent-society
bash scripts/setup_q6_1_runtime.sh
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python scripts/check_q6_1_local_transport.py
```

安装步骤允许从软件源下载依赖，但不读取密钥、不发模型请求。Python 的 venv 组件缺失或包安装失败时修复环境，不拼接 uv 缓存目录。

在 PowerShell 里也可以直接把完整脚本路径交给 WSL，避免 `$(...)` 被外层展开：

```powershell
wsl.exe -d Ubuntu -- bash /home/fergeson/projects/agent-society/scripts/setup_q6_1_runtime.sh
```

环境应显示 result=PASS，回环应显示 loopback_http_stack=PASS、remote_provider_requests=0。实际 import 路径必须位于同一 `.venv-q61-runtime`，而不是多个 uv archive。单个正确环境通过安装使用缓存没有问题，禁止的是手工把多个版本加入 PYTHONPATH。

## 4. 真正调用前：只选择一种模式，执行一次

配置可以来自现有 CONTINUITY_BASE_URL/MODEL/API_KEY，或明确指定的受保护 `.env`。加载采用只读 dotenv 解析、不执行 shell、不插值、不修改原文件、不回显 key。缺少 CONTINUITY_API_KEY 时可从 AGENTSOCIETY_LLM_API_KEY 映射。

地址和模型固定为此前约定的 Coding Plan 地址与 `ark-code-latest`。不自动换 endpoint、模型或凭据测试。官方子模块本身不修改。

**模式一：只做一次真实预检，不运行正式 pilot。**

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/check_q6_1_provider_runtime.py --allow-provider \
  --session-id q61-runtime-01 --env-file third_party/AgentSociety/.env
```

**模式二：授权一次预检，只有通过后才运行一次四决策 Attempt 3。**

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/check_q6_1_provider_runtime.py --allow-provider --with-pilot \
  --session-id q61-runtime-01 --env-file third_party/AgentSociety/.env
```

两条是互斥选择，不是先后依次执行。模式二的总预算是 **1 次独立预检 + 最多 4 次正式决策**。活动微步骤零模型调用，没有扩到 12 次的选项。

相对 `--env-file` 路径始终基于父仓库。直接使用环境变量时可以省略该参数。

## 5. 门禁与失败处理

默认没有 `--allow-provider` 时不构造真实客户端，不读取凭据，不发请求。

真实运行要求正确父仓库、干净工作树、固定上游和通过的独立环境检查。全新会话目录以排他方式创建，已有 ID 拒绝重复启动；进程锁还限制不同 ID 的并发启动。

预检要求：恰好一次客户端尝试、HTTP 200、有效响应契约、严格二字段 JSON、指定 SLEEP 提案、关闭客户端无异常。工具调用或拒绝响应即使同时有合法 JSON，也不能通过。正确响应后的 close 失败会保留响应证据，但不会开始正式 pilot。

只有明确 `--with-pilot` 且预检 PASS，才在相同配置和 Python 进程中进入四步。交接前重新检查 HEAD、工作树和代码指纹；中途代码变化会停止。

超时、输出错误、规则拒绝、活动失败或不变量失败会停止，不 retry、不补动作、不改 prompt 后补跑。发生中断后不能直接假定没有发送请求；先核对本次目录和日志，不删除目录、不自动换 ID。

安全分类包括 PYTHON_ENVIRONMENT、CLIENT_CONSTRUCTION、NETWORK_RUNTIME、HTTP_ERROR、PROVIDER_CONTRACT、MODEL_OUTPUT、UNKNOWN_TRANSPORT、CLIENT_CLEANUP。只记录白名单异常类名与允许的响应元数据，不记录错误正文、原始提示、原始响应、堆栈或隐藏推理。

## 6. 计数与结论的含义

provider_requests 沿用现有客户端“准备调用 HTTP POST 时递增”的语义，因此表示客户端尝试，不保证服务器已经收到。没有 HTTP 响应时 server_receipt=UNKNOWN，不能据此断言服务端故障。

requested_model 保存公开请求别名，provider_model / observed_backend_models 保存实际返回的模型标识，二者不混淆。token 未知时为 null，不伪装成零。

正式结果只有四次决策全部完成、跨决策观察正确反映变化、终态不变量通过且清理正常时，才允许 SUPPORTED。部分运行或未形成反馈链为 INSUFFICIENT_EVIDENCE；明确反馈/不变量失败分别记录。没有触发的媒体或所有权场景不计为已验证。

即使 SUPPORTED，也只支持本次短链状态一致，不证明模型因果使用了每个状态字段，更不证明自主正常生活七天或三十天。

## 7. 产物

```text
run/evaluation/q6_1_provider_runtime/<session-id>/
  environment.json
  session.json
  report_zh.md
  preflight/
    summary.json
    progress.jsonl
    report_zh.md
  attempt_3/
    world.sqlite3
    request_progress.jsonl
    progress.jsonl
    execution_status.json
    summary.json
    decisions.jsonl
    events.jsonl
    final_state.json
    environment.json
    report_zh.md
```

只有预检通过并有额外授权才创建 attempt_3。每个请求开始和每个决策结束增量记录；首次结果先落盘，再处理客户端关闭。严重中断可能只有部分产物，应据实审计，不把缺少完整 summary 当成零请求。

运行时版本清单保存在 `run/evaluation/q6_1_runtime_environment/`。本轮 CI 不读取 GitHub secrets、不发火山请求；MockTransport 与回环只是离线证据。

参考：[Python venv](https://docs.python.org/3/library/venv.html)、[HTTPX transports](https://www.python-httpx.org/advanced/transports/)。实际完成情况见 [验收记录](q6_1_provider_runtime_acceptance.md)。


## 8. 本地执行结果（2026-09-22）

提交 54ed48f93f452718e59bda1368e15737f173084c 修复 setup，使其显式选择 Python 3.12。独立 runtime 为 Python 3.12.14，固定依赖全部来自 .venv-q61-runtime，typing_extensions.sentinel 可用，pip check 和本机 HTTP loopback 均通过。固定 session q61-runtime-01 已执行一次：预检 1 次请求通过，Attempt 3 使用 4 次请求，在第四次 PLAY game_a 因 ITEM_NOT_OWNED 规则拒绝停止。已有 session ID 不可重复执行。
