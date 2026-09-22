# Q6.1 独立运行时：代码交付与离线验收

日期：2026-09-21。分支：`research/q6-real-continuity-pilot`；继续使用 PR #4，不自动合并 main。

## 1. 实际执行到哪一步

本轮已经完成运行时代码、一次预检、条件性四决策调度、异常诊断、测试和中文说明，并在 GitHub Actions 实际执行了离线验收。

**没有读取用户本机 API key，没有发送火山模型请求，真实 Provider Runtime Preflight 和 Attempt 3 均尚未运行。** 下载依赖和本机 HTTP 回环不是火山模型调用。

已验收代码提交：`bc7d4ff6d1c7a092d19beb36c3dc692df3c9a2f3`。本文件属于后续文档回填，不把文档提交当成上述运行的代码提交。

## 2. CI 结果及证据

[独立运行时验收 35582023492](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35582023492) 在上述分支提交上运行；[仓库回归 35582027992](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35582027992) 在该提交与当时 main 的预合并版本上运行，预合并 SHA 为 `ecd9b3d325cacda2423d3c6fee52d387d1455649`。这不是实际合并 main。

| 验收项 | 结果 | 范围 |
|---|---|---|
| 独立 venv 安装、导入及客户端构造/关闭 | PASS | 清除 PYTHONPATH/PYTHONHOME，不混用 uv 缓存 |
| pip check | PASS | 已安装依赖没有声明冲突 |
| 实际 HTTP 栈回环 | PASS | 仅 127.0.0.1，1 次本机请求，0 次远端模型请求 |
| 运行时、Q6.1、continuity、仓库联合专项 | 109 passed | 包含本轮新增 37 项参数化测试案例 |
| 全库回归 | 609 passed，8 skipped | 八项缺少未入库的历史真人语料，未计入通过 |
| Ruff 已配置检查范围 | PASS | 不声称等同于全面安全审计 |
| 原文归档、受保护文件及链接审计 | PASS | 原有 32 份原文仍逐份核验 |
| 实际固定上游 AS2 适配器 | PASS | 时钟、观察、checkpoint/restore，无模型调用 |
| 七天/三十天脚本一致性 | PASS | SCRIPTED 工程测试，不是模型自主行为 |

专项产物：[q61-runtime-offline-evidence](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35582023492/artifacts/10630084352)，包括精确依赖清单、JUnit 与审计 JSON。

回归产物：[continuity-regression-evidence](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/35582027992/artifacts/10630603128)，包括全库 JUnit、依赖版本、上游版本。Actions 产物可能按服务保留策略过期，关键结果与运行 ID 保留在本页。

八项跳过涉及 `tests/test_a2_final.py`、`tests/test_behavior_prior_context.py`、`tests/test_behavior_prior_index.py`。它们需要本地的 `run/calibration/neutral_day_v1/calibration_manifest.json` 和 `behavior_days_core7_candidate.jsonl`。拥有原始数据的机器可使用 `--require-historical-data`；缺失时不允许伪造或当作通过。

## 3. 这轮补齐了什么

一个独立 `.venv-q61-runtime` 就能运行该预检和四决策实验，不要求重装整个 AS2/Ray。`requirements-q61-runtime.txt` 固定实际验收过的组合：HTTPX 0.28.1、httpcore 1.0.9、AnyIO 4.15.1、typing_extensions 4.16.0、python-dotenv 1.1.1，以及其余三个运行依赖。

新会话先检查父仓库、工作树、固定上游和依赖来源；从明确指定的本地 `.env` 只读解析配置，不执行 shell，不输出密钥。请求失败仅保存安全异常类型；首次失败和关闭客户端失败分开记录。

预检只有一次请求，HTTP 200、严格 JSON、指定 SLEEP 提案和正常 close 必须全部满足。即使拿到合法响应，只要 close 失败，也不进入正式 pilot。代码或提交在两阶段之间变化时，停止交接。

额外提供 `--with-pilot` 才授权预检通过后执行四次高层决策。总上限是 **1 次预检 + 4 次正式决策 = 5 次客户端请求尝试**，不是总共四次。正式部分复用原 Q61PilotRunner、提示、初始世界与规则；活动微步骤不请求模型。

每个会话有独占目录和进程锁，重复会话 ID 拒绝启动。请求开始、完成、状态与清理分别留痕。故障后不重试、不重新命名会话自动补跑、不插入脚本动作。

测试使用实际 OpenAICompatibleDecisionClient 搭配 MockTransport，覆盖 HTTP 错误/重定向、超时、错误 JSON、工具调用和拒绝混合响应、构造失败、清理失败、预检失败不调用 pilot、一次预检加四步、下一集状态反馈、首次失败停止，以及秘密字符串不进入输出。

## 4. 历史没有被改写

Attempt 1 的导入错误、Attempt 2 的一次请求尝试及无响应记录保留原样。没有把本机回环 PASS 改写成火山 HTTP 200，也没有把模拟响应标记为真实模型。

本轮早期 PR 检查发现：main 中已按用户要求翻译的 Q3/Q4/Q5 报告，与原文不可变哈希规则冲突。修复方式是保留中文阅读版，把翻译前准确字节另存 `docs/archive/2026-09-20/source_en/`，并通过三项显式映射继续对冻结版本核验。没有删除审计、跳过这三份报告或修改预期原始哈希。此前失败的 CI 历史保留。

## 5. 本机执行交接

只需拉取代码并运行已有脚本，执行者不需要再设计实验。

先确认当前在父仓库且工作树干净，再切到本分支，使用 `git pull --ff-only` 同步；不要 reset/clean 未提交改动。

```bash
cd /home/fergeson/projects/agent-society
bash scripts/setup_q6_1_runtime.sh
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python scripts/check_q6_1_local_transport.py
```

前两项检查通过，且操作者要执行一次预检和条件性 Attempt 3 时，执行下面这一条一次即可：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/check_q6_1_provider_runtime.py --allow-provider --with-pilot \
  --session-id q61-runtime-01 --env-file third_party/AgentSociety/.env
```

若该会话目录已存在，不删除、不自行换 ID 再发请求；先检查已有产物。只有预检已通过且没有停止条件，才会继续四步正式决策。仅做预检的操作方式见 [完整运行手册](q6_1_provider_runtime.md)，两种方式是互斥选择。

## 6. 当前结论

```text
RUNTIME_CODE_AND_OFFLINE_GATES = PASS
REAL_PROVIDER_PREFLIGHT_EXECUTED_THIS_DELIVERY = NO
REAL_PROVIDER_REQUESTS_THIS_DELIVERY = 0
Q6_1_ATTEMPT_3_EXECUTED = NO
SHORT_HORIZON_STATE_CONTINUITY_REAL_EVIDENCE = INSUFFICIENT_EVIDENCE
```

本轮已解决可在 GitHub 直接完成的代码和离线验证工作。用户 WSL 的实际 DNS/TLS、账户权限、provider 可用性及真实模型反馈必须由本地新会话验证。即使四步以后通过，也只支持受测短链，不证明模型因果利用了每个字段或能长期像真人生活。


## 7. 本地真实执行补充（2026-09-22）

此前“真实 Provider Runtime Preflight 尚未运行”属于交接前状态，保留其历史含义。本次提交 54ed48f93f452718e59bda1368e15737f173084c 使用 Python 3.12.14 独立 runtime 完成一次真实 session。

PYTHON_RUNTIME = PASS
LOCAL_HTTP_LOOPBACK = PASS
PROVIDER_RUNTIME_PREFLIGHT = PASS
PREFLIGHT_PROVIDER_REQUESTS = 1
PREFLIGHT_HTTP_STATUS = 200
PREFLIGHT_PROVIDER_MODEL = glm-5.3
ATTEMPT_3_EXECUTED = YES
ATTEMPT_3_PROVIDER_REQUESTS = 4
ATTEMPT_3_TERMINATION = RULE_REJECTED
SHORT_HORIZON_STATE_CONTINUITY = INSUFFICIENT_EVIDENCE

离线专项为 113 passed；Ruff、repository audit 通过。全库回归在 AS2 测试收集阶段因缺少 litellm 产生 2 个 collection errors；AS2 smoke 同样因该依赖缺失而阻塞。没有重跑真实 session。
