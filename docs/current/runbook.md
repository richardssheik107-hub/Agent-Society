# 运行手册：主线、环境与实验入口

更新：2026-10-08。Q6.1/Q6.2已合入main；新固定状态面板在本轮分支实现并离线验收。本页不是付费请求授权；获取活动尚未实现。现行任务见[完整计划](plan.md)。

## 工作区与环境

父仓库为`/home/fergeson/projects/agent-society`，不是`third_party/AgentSociety`。先看`git status --short`；有用户改动不reset/clean。工作树干净后切main并使用`git pull --ff-only origin main`，新任务从main建短期分支。

已有Python3.12的`.venv-q61-runtime`通过检查就复用；不要因文档更新重建。系统默认Python可能不是目标版本，不拼接uv缓存。确实缺失或损坏时才使用仓库现有`bash scripts/setup_q6_1_runtime.sh`并检查依赖，任何安装失败不启动真实请求。

轻量runtime用于provider/连续性入口，不保证包含pytest或完整AS2依赖。完整回归在单独测试环境运行，不往系统全局或轻量环境盲目安装全部AS2/Ray依赖。

## 已有工程验收

Q6脚本只需Python标准库，模型请求为0；已验收且代码未变时不为重复留数字再跑：

```bash
python scripts/run_continuity.py
```

完整回归的既有命令（在独立完整测试环境中）：

```bash
git submodule update --init --recursive third_party/AgentSociety
python -m pip install -c requirements-as2-constraints.txt -r requirements-test.txt -e third_party/AgentSociety/packages/agentsociety2
python -m pytest -q -rs
```

执行前确认子模块固定版本；历史真人数据缺失显示SKIP，不计通过。有真实冻结语料时使用`--require-historical-data`严格检查。本文没有实际执行这些命令。

## Q6.1原产物：已有核验，不默认重跑

源产物已在WSL核验成功。只有需要独立复核时，在有原文件的父仓库使用：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_projection_offline.py \
  --source-artifact run/evaluation/q6_1_provider_runtime/q61-runtime-01
```

该命令只读原attempt_3文件、写新目录、不调用模型。不得覆盖旧结果，也不要把它换成重跑旧真实session。

## 当前Q6.2入口：默认零请求

现有`scripts/run_q6_2_real_ab.py`是两条自主短链，不是计划中新提出的固定状态面板。它支持session-id、AB/BA顺序、输出目录和显式allow-provider；**没有env-file参数**。

无凭据试运行示例（先把占位符替换为新的、批准使用的dry-run ID）：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_real_ab.py --session-id <新的dry-run唯一ID> --schedule AB
```

已有dry-run足够审阅时不用重复生成。默认provider请求0；真实分支只从当前进程读取`CONTINUITY_BASE_URL`、`CONTINUITY_MODEL`、`CONTINUITY_API_KEY`。Q6.1统一预检入口的env-file处理不能当成此脚本已有功能。

获得对应实验的明确授权后，配置映射必须在同一个Linux进程环境完成；只读解析既有受忽略保护的配置，密钥不回显、不进shell history、不写报告。不要cat整个.env，不靠跨PowerShell/Bash层的未转义变量展开检查仓库，也不重用此前混合uv缓存的方法。

真正运行前按[M0检查](plan.md#四m0下一轮先完成最小证据检查)确认版本、计数、停止和中断证据；本页不提供自动开启真实调用的命令。八请求是旧短链代码上限，不是本次新增授权。

## 中断与已有session

发现session已存在或上次执行是否发请求不清楚，先只读检查进程、summary、decision记录与SQLite；日志没有某行不能证明请求为0。不得删除目录、换ID或自动补跑。允许导出已存在记录，不重新发送请求。真实停止策略以批准的具体协议为准。

## 新固定状态面板：三个模式与只读恢复

入口为 `scripts/run_q6_2_fixed_state_panel.py`；`--help` 实际列出 mode、session-id、export-only、output、allow-provider、execution-commit、protocol-hash、max-requests、env-file、offline-case。普通运行注册根固定为 `run/evaluation/q6_2_fixed_state_panel/`，`--output` **仅可用于新恢复报告目录**，不能换目录绕过 session 身份。已有 ID 排他拒绝，不删除后重跑。

以下 dry-run、offline 和 export-only 均已通过离线测试；示例 ID 是本轮已用 ID 的形式，实际再次执行要换**新的离线 ID**，不要复用旧真实 session。默认不读密钥、不创建真实 client；offline 只使用显式脚本 client，报告为 OFFLINE_SYNTHETIC。

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_fixed_state_panel.py --session-id q62-panel-dry-next

env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_fixed_state_panel.py --session-id q62-panel-offline-next --mode offline

env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_fixed_state_panel.py \
  --export-only run/evaluation/q6_2_fixed_state_panel/q62-panel-offline-next \
  --output run/evaluation/q6_2_fixed_state_panel_recovery/q62-panel-offline-next
```

恢复源库 `mode=ro`、`query_only` 打开，不调用 StateStore/World 初始化，不迁移，不读凭据、不构造 client、不补动作；报告写新目录。session.sqlite3 记录完整计划与阶段；每个 `cells/cNNN/world.sqlite3` 的 commands、decision_attempts、events、state 是业务事实。意图后中断写发送 UNKNOWN/null；只有响应证据不编造提案；world 已提交从已提交事实恢复。不提供自动 resume/retry，保留中断 session。

离线脚本还可选 `--offline-case both-legal`、`b-worse`、`no-valid-proposal`；它们验证汇总器不保证 B 获胜，不构成模型证据。每单元一次决策，跨决策反馈/重复率/长期连续性为 NOT_APPLICABLE。

### 未来 real：尚未授权，不执行

只有独立批准冻结协议和48次预算后，才可将占位符换成已批准执行commit、配置规范JSON hash、新session和保护配置路径：

```bash
# 尚未授权，不执行；48是固定容量，不是本轮许可
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_fixed_state_panel.py --mode real --allow-provider \
  --session-id <待批准的新real-ID> --max-requests 48 \
  --execution-commit <待批准的干净HEAD> --protocol-hash <待批准的配置SHA256> \
  --env-file <显式指定的受保护配置文件>
```

无独立 allow-provider、版本/hash不匹配、环境无效或重复session均不发送请求。沿用 minimal_request，仅 model/messages；不添加 thinking/max_tokens/temperature。首个请求前冻结48计划和全部世界，每单元前再查冻结四项摘要；调用前占预算，逐单元增量输出完成数、cell、状态与累计尝试。规则拒绝和已知活动失败可继续；其余fatal停止整轮，剩余NOT_RUN附停止原因。

本轮真实 provider 请求0，不读取实际 `.env`，不重跑Q6.1/旧双短链，不自动merge。离线环境中缺完整AS2依赖应单列收集错误，由完整CI验收，不能冒充通过。

## 文档检查

在带pytest的测试环境执行：

```bash
python scripts/audit_repository.py --check
python scripts/audit_documentation.py --check
python -m pytest -q tests/test_documentation_navigation.py tests/test_repository_quality.py
```

需要完整Git历史；浅克隆缺对象必须报告不能完成，不能忽略。文档审计只读、零模型。旧文件检索见[清理映射](../reference/cleanup.md)。
