# 运行与验收

## 1. 环境

Python 3.11+。从集成分支执行，先看 `git status --short`，不要 reset/clean 未提交工作。

纯 Q6 代码使用 Python 标准库；只跑新增核心测试可以先安装 pytest。包括历史 Router 的全量回归需要固定上游和完整测试依赖：

```bash
git submodule update --init --recursive third_party/AgentSociety
python -m pip install -c requirements-as2-constraints.txt -r requirements-test.txt -e third_party/AgentSociety/packages/agentsociety2
python -m pytest -q
python -m ruff check src/social_sim/continuity tests/test_continuity*.py scripts/run_continuity*.py scripts/audit_repository.py
```

上游 `670c94` 使用 MCP v1 的 FastMCP 接口；无约束安装到 MCP v2 会导入失败。`requirements-as2-constraints.txt` 限定 `mcp<2`，不修改上游。依赖安装可以联网下载软件，测试与离线模拟不得向模型 provider 发请求。

## 2. 七天与三十天离线验收

```bash
python scripts/run_continuity.py
```

默认分别执行 7、30 天，每档各跑一次不停机基线和一次反复关闭/恢复并重复提交命令的版本。新建唯一输出目录，不覆盖旧试验。

产物在 `run/evaluation/continuity/q6_<时间>/`：`summary.json`、中文 `报告.md`、增量 `progress.jsonl`、不停机与恢复版本的 SQLite 世界。

应出现 `CONTINUITY_CONTRACT_PASS`。判断依据包括事件账本与余额/库存/热量一致，媒体进度合法，恢复前后最终状态哈希和事件数相同。

本轮本地验证：47 项新增核心测试通过；7 天恢复 561 次、重复命令 560 次；30 天恢复 2401 次、重复命令 2400 次；两档均与不停机运行一致。观察上下文最大分别 1011、1017 字符。所有值只是这组脚本的结果，完整远端回归以 CI 结果为准。

曾有一次本地 40 秒执行窗口在 30 天恢复测试中截断。随后优化了全账本校验频率：每个模拟日及终态校验，不再每一小步重读全部历史；未修改世界语义。重新运行于独立目录并完成，不把中断结果标记为成功。

**这些结果不是 7/30 天真实模型自主行为结果。**

## 3. AS2 薄适配专项

```bash
python scripts/check_continuity_as2.py
```

使用上面安装的真实固定上游，专项直接实例化 EnvBase/Router 路径并验证 workspace 恢复，不调用 PersonAgent 或外部模型。CI 使用本地无服务地址和占位 key，并禁止 socket 连接。

## 4. 小预算真实模型入口（本轮未执行）

仅在操作者明确批准真实调用后，从安全环境映射 `CONTINUITY_BASE_URL`、`CONTINUITY_MODEL`、`CONTINUITY_API_KEY`，不把 key 写进命令或文档。

```bash
python scripts/run_continuity_real.py --allow-provider --max-decisions 4
```

每次高层决策最多一个客户端调用；活动微步骤不调用模型。整个 await 有硬墙钟超时。请求开始前写持久 attempt，失败/中断不自动重试；默认不续跑旧实验。CLI 最多允许 12 次请求，缺 key 或没有 opt-in 时为零请求。

结果含已解析意图、token 数、模型标识、安全 HTTP 状态和终止原因，不保存原始 prompt/completion、隐藏推理或 key。真实接口尚未在本轮验证，不把 fake client 测试标成真实模型成功。

## 5. 故障解释

`ALREADY_COMPLETED` 不是禁止正常重看：宿主可以明确提交 rewatch。`COMMITMENT_FAILED` 表示已接纳活动但某阶段不可执行，必须读 failure_reason。`STALE_STATE` 表示提案基于过期事实。`PROVIDER_TIMEOUT` 与行为性 idle 分开，不能让脚本替模型补动作。

模型失败不回滚此前合法完成的世界事实；未提交事务失败不能留下半扣款或半更新进度。SQLite 单写者与真实多机并发是不同层级，本轮没有分布式一致性结论。
