# 运行手册：先看分支，再选环境

本页不是新的模型调用授权。所有付费实验必须另行确认预算和停止条件；不要为检查配置再次运行已用过的 session。

## 主线能做什么

main 现有 Q6 脚本验收只需 Python 标准库：

```bash
python scripts/run_continuity.py
```

它验证工程状态，不请求模型。完整仓库测试需要固定 AS2 依赖，不能在轻量 provider 环境缺依赖时把收集错误称为业务失败。

```bash
git submodule update --init --recursive third_party/AgentSociety
python -m pip install -c requirements-as2-constraints.txt -r requirements-test.txt -e third_party/AgentSociety/packages/agentsociety2
python -m pytest -q -rs
```

这是安装测试环境的说明；不要在未经确认的本机全局环境盲目执行。优先使用独立全栈回归环境。八项历史语料依赖缺失应显示 SKIP，实际有语料可用 `--require-historical-data` 严格核验。

## Q6.1/Q6.2 分支能做什么

研究代码在 `research/q6-real-continuity-pilot`，不是只拉 main 就能运行。父仓库为 `/home/fergeson/projects/agent-society`，不要在官方子模块里切研究分支。先看 `git status --short`，有未提交内容不 reset/clean。

本机已经成功建立 `.venv-q61-runtime`（Python 3.12.14），不需要因文档更新再次重建，也不拼接 uv cache。运行时安装/预检已经通过的历史见[Q6.1](../studies/q61_real_pilot.md)。

在原产物确实存在且新离线脚本可用的研究分支，只读核验命令：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_projection_offline.py \
  --source-artifact run/evaluation/q6_1_provider_runtime/q61-runtime-01
```

该入口读取 `attempt_3/summary.json`、`decisions.jsonl` 和 `final_state.json`，输出新目录，模型请求 0。不存在原文件时不能标记 verified；有差异不能自动修原数据。

## 当前不要执行什么

不要重跑 `q61-runtime-01` 真实预检，不自动换 session，不自动授权十二次，不因模型未选 WATCH 就插入观看动作。新的真实 A/B 先完成[人工 D-01](../review/decisions.md#d-01)。

## 文档本身怎么检查

```bash
python scripts/audit_repository.py --check
python scripts/audit_documentation.py --check
python -m pytest -q tests/test_documentation_navigation.py
```

完整历史检查需要 `fetch-depth: 0` 的克隆；浅克隆缺 Git 对象应明确失败而不是忽略。审计只读，不下载密钥、不调用模型。历史文件查找见[清理映射](../reference/cleanup.md)。
