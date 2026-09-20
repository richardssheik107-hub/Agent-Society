# 运行与验收

## 1. 环境

Python 3.11+。从集成分支执行，先看 `git status --short`，不要 reset/clean 未提交工作。

```bash
python -m pip install -r requirements-test.txt
python -m pytest -q
python -m ruff check src/social_sim/continuity tests/test_continuity*.py scripts/run_continuity*.py scripts/audit_repository.py
```

Q6 默认只用 Python 标准库；旧实验测试还需要 requirements-test.txt 中的依赖。AS2 适配器是独立可选依赖，见下面专项命令。

## 2. 七天与三十天离线验收

```bash
python scripts/run_continuity.py
```

默认分别执行 7、30 天，每档各跑一次不停机基线和一次反复关闭/恢复并重复提交命令的版本。新建唯一输出目录，不覆盖旧试验。

产物在 `run/evaluation/continuity/q6_<时间>/`：`summary.json`、中文 `报告.md`、增量 `progress.jsonl`、不停机与恢复版本的 SQLite 世界。

应出现 `CONTINUITY_CONTRACT_PASS`。判断依据包括事件账本与余额/库存/热量一致，媒体进度合法，恢复前后最终状态哈希和事件数相同。

本轮本地验证：47 项新增核心测试通过；7 天恢复 561 次、重复命令 560 次；30 天恢复 2401 次、重复命令 2400 次；两档均与不停机运行一致。观察上下文最大分别 1011、1017 字符。所有值只是这组脚本的结果，最终 CI 可能增加适配器专项测试数量。

曾有一次本地 40 秒执行窗口在 30 天恢复测试中截断。随后优化了全账本校验频率：每个模拟日及终态校验，不再每一小步重读全部历史；未修改世界语义。重新运行于独立目录并完成，不把中断结果标记为成功。

**这些结果不是 7/30 天真实模型自主行为结果。**

## 3. AS2 薄适配专项

```bash
git submodule update --init --recursive third_party/AgentSociety
python -m pip install -e third_party/AgentSociety/packages/agentsociety2
python scripts/check_continuity_as2.py
```

专项直接实例化真实上游 EnvBase/Router 路径并验证 workspace 恢复，不调用 PersonAgent 或外部模型。导入上游可能需要符合其配置检查的环境变量；CI 使用本地无服务地址和占位 key，绝不能向该地址发送真实决策请求。

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
