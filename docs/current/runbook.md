# 运行手册：先看分支，再选环境

本页不是付费调用授权。真实实验需另行批准预算和停止条件，不能为检查配置再运行已用过的session。

## 主线可运行的工程验收

Q6脚本只需Python标准库，模型调用为0：

```bash
python scripts/run_continuity.py
```

完整回归需要固定AS2和测试依赖，在独立全栈环境安装，不混入轻量provider环境：

```bash
git submodule update --init --recursive third_party/AgentSociety
python -m pip install -c requirements-as2-constraints.txt -r requirements-test.txt -e third_party/AgentSociety/packages/agentsociety2
python -m pytest -q -rs
```

执行前确认所用Python及独立环境；不要在系统全局环境盲目安装。历史真人数据缺失显示SKIP，真正有数据可用 `--require-historical-data` 严格检查。

## Q6.2研究分支：已核验原文件，不需要默认重复

业务代码仍在 `research/q6-real-continuity-pilot`。父仓库 `/home/fergeson/projects/agent-society`，不是官方子模块。先看工作树状态，有改动不reset/clean。已有Python3.12.14的 `.venv-q61-runtime` 不因文档更新重建，不拼uv缓存。

原artifact核验已有成功报告。需要再次独立复核时可在有真实文件的研究分支运行：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_projection_offline.py \
  --source-artifact run/evaluation/q6_1_provider_runtime/q61-runtime-01
```

它只读原 `attempt_3/` 文件、写新目录，不调用模型。新报告不覆盖已有原文件和历史失败。

## A/B入口已准备，默认只能dry-run

研究分支 `e2d85c6` 已有 `scripts/run_q6_2_real_ab.py`。无凭据dry-run示例：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_real_ab.py --session-id <新的dry-run唯一ID> --schedule AB
```

尖括号为需要替换的占位，不要原样执行。已有dry-run产物可直接审阅，不必重复建设。默认provider请求0、真实A/B未执行；真实调用的allow-provider选项在本页不启用。现有每臂四次/总八次的代码上限不是新增授权。[人工D-01](../review/decisions.md#d-01)

不要重跑q61-runtime-01真实预检，不自动切换模型/endpoint，不插WATCH/MEAL，不因失败换ID补跑。

## 文档检查

```bash
python scripts/audit_repository.py --check
python scripts/audit_documentation.py --check
python -m pytest -q tests/test_documentation_navigation.py
```

需要完整Git历史；浅克隆缺对象必须报告不能完成，不忽略。审计只读、零模型。旧文件查找见[清理映射](../reference/cleanup.md)。
