# 运行与验收

## 1. 从这里开始

使用 Python 3.11+，切到 `integration/continuity-cleanup`。先检查 `git status --short`，不要 reset/clean 未提交工作。纯 Q6 脚本只需要标准库：

```bash
python scripts/run_continuity.py
```

包括历史 Router 的全库回归需要固定上游及测试依赖：

```bash
git submodule update --init --recursive third_party/AgentSociety
python -m pip install -c requirements-as2-constraints.txt -r requirements-test.txt -e third_party/AgentSociety/packages/agentsociety2
python -m pytest -q -rs
```

上游 `670c94` 使用 MCP v1 FastMCP 接口。兼容文件限定 `mcp<2`，不修改上游源码。安装依赖会联网下载软件；离线测试和模拟不向模型 provider 发请求。

## 2. 全库回归不等于完整历史实证复现

有 8 项原有测试直接读取未入库的真人日记产物。新 checkout 缺少以下文件时，逐测试明确 SKIP，不生成假语料、不删除旧测试、不把跳过算作通过：

```text
run/calibration/neutral_day_v1/calibration_manifest.json
run/calibration/neutral_day_v1/behavior_days_core7_candidate.jsonl
```

它们只涉及 `test_a2_final.py`、`test_behavior_prior_context.py`、`test_behavior_prior_index.py` 中登记的 8 项，其他测试仍执行。真实文件存在时，原 loader 继续检查 hash、7341 份成人日记和 3215 份在职工作日日记；文件错误仍然失败，不会跳过。

已准备原真实产物的本机使用：

```bash
python -m pytest -q --require-historical-data
```

该开关在缺文件时直接失败，禁止静默跳过。不能把普通 CI 的绿色结果写成“已复现全部历史语料结果”。

## 3. 长期状态与持久化

```bash
python -m pytest -q tests/test_continuity*.py tests/test_repository_quality.py
python scripts/run_continuity.py
```

默认分别执行 7、30 天，每档各跑不停机基线和反复关闭/恢复、重复提交命令的版本。新建唯一目录，不覆盖旧试验。

产物在 `run/evaluation/continuity/q6_<时间>/`：`summary.json`、中文 `报告.md`、`progress.jsonl`，以及两个版本的 SQLite 世界。程序输出 `CONTINUITY_RESULT`，含实际天数、重启数、重复命令数、状态哈希、上下文长度与最终等价性，最后才输出 `CONTINUITY_CONTRACT_PASS`。

验收范围是余额、库存、热量、媒体进度与活动生命周期的一致性。脚本安排这些活动，**不是模型自主生活实验**。CI 在 Actions artifact 中保留 JSON、中文报告和测试记录；具体数字以对应提交实测为准。

## 4. AS2 真实代码适配专项

```bash
python scripts/check_continuity_as2.py
```

直接实例化固定上游的 EnvBase/Router 路径并验证 workspace 恢复，不调用 PersonAgent、CodeGenRouter 或模型。使用无服务本地地址和占位配置，并禁止 socket 连接。此专项不是完整 Ray 社会、多机并发或 distributed replay 验收。

## 5. 代码和清理审计

```bash
python -m ruff check src/social_sim/continuity tests/test_continuity*.py tests/test_repository_quality.py tests/conftest.py scripts/run_continuity*.py scripts/check_continuity_as2.py scripts/audit_repository.py
python scripts/audit_repository.py --check
```

基础静态检查集合在 `pyproject.toml` 明示为 E4/E7/E9/F/B，避免 Ruff 升级改变默认规则口径。这不是所有 Ruff 规则或完整安全审计。原始 CI 曾因新版默认风格/接口检查报错，失败记录保留。归档检查逐文件比对冻结提交，校验历史代码、其他成员 delivery 文件和上游版本未被意外覆盖。

## 6. 小预算真实模型入口（本轮未执行）

从安全环境映射 `CONTINUITY_BASE_URL`、`CONTINUITY_MODEL`、`CONTINUITY_API_KEY`，不把 key 写进命令或文档。只有明确批准真实调用后执行：

```bash
python scripts/run_continuity_real.py --allow-provider --max-decisions 4
```

每次高层决策最多一个客户端调用；活动微步骤不调用模型。CLI 最多 12 次；预算在 SQLite 事务里核对，多个 runner 不能使用各自旧计数超发。调用开始先记持久 attempt，超时、取消、无效输出不自动重试。HTTP 超时与输出契约错误分别分类，未知 token 保持 null。

产物只保存经过解析的意图、安全元数据和执行结果，不保存原始 prompt/completion、隐藏推理或密钥。活动后续步骤失败也会停止并记录 `COMMITMENT_FAILED`，不只检查模型是否返回了 JSON。

## 7. 失败含义

`ALREADY_COMPLETED` 表示不能将已看集数伪装成新完成，明确 rewatch 仍可重看；`STALE_STATE` 表示提案依据过期状态；`REQUEST_ID_REUSE` 表示同一 ID 被换参数；`PROVIDER_TIMEOUT` 不能算行为性 idle。

未提交事务失败不会留下半扣款。宏活动已经完成的步骤是事实，例如到餐厅后没钱买饭，会保留移动但不声称吃完。SQLite 单机事务不是对真实外部交易或多机一致性的保证。
