# 运行手册：主线、环境与实验入口

更新：2026-10-09。Q6.2、M1.5、M2 已合入 main；本轮 D-02/D-09 追加批准 M5 的限定 opt-in 能力与三层评价，真实预算仍为 0。旧 `q62-panel-real-v2-01` 已完成且许可用尽，禁止重跑或复用。所有真实调用均须新协议和明确授权。[现行计划](plan.md)。

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

现有`scripts/run_q6_2_real_ab.py`是两条自主短链，不是已经实现的独立固定状态面板。它支持session-id、AB/BA顺序、输出目录和显式allow-provider；**没有env-file参数**。

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

入口为 `scripts/run_q6_2_fixed_state_panel.py`；`--help` 实际列出 protocol(v1/v2，默认v1)、mode、session-id、export-only、output、allow-provider、execution-commit、protocol-hash、max-requests、env-file、offline-case。普通运行注册根固定为 `run/evaluation/q6_2_fixed_state_panel/`，`--output` **仅可用于新恢复报告目录**，不能换目录绕过 session 身份。已有 ID 排他拒绝，不删除后重跑。

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

### v1轮历史示例：当时尚未授权，不执行

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

v1工程轮真实 provider 请求0、未读取实际 `.env`，这段历史不因v2获授权并执行而改写。两轮均未重跑Q6.1/旧双短链，不自动merge。离线环境中缺完整AS2依赖应单列收集错误，由完整CI验收，不能冒充通过。

### v2预注册与执行命令历史：已执行，不再运行

上述零授权/零请求段落为v1轮历史。本轮仅 `q62-panel-real-v2-01` 获准最多48尝试，现已完成这唯一session；额外探针/真实smoke/旧联调0。D-01记录的许可不是未来永久许可。以下是执行前预注册及原命令留档，不是再次运行指引：v2单次安全终结超时继续下一cell，连续两次停；默认v1仍一次停。正式ID已存在，只能只读核对，不能删除、换ID或执行第二次。

以下v2离线入口已实测；再次使用新的**离线**ID，不删除已有目录：

```bash
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_fixed_state_panel.py --protocol v2 \
  --session-id q62-panel-offline-v2-next --mode offline
```

执行前要求且已核对：新HEAD所有CI/AS2通过、工作树clean、环境和配置安全检查通过后，在同一WSL shell用可检查脚本冻结 `EXECUTION_COMMIT` 与 `digest(load_protocol(version="v2"))`。协议使用规范JSON摘要，不用配置原始字节sha256；当次生效地址为 `https://ark.cn-beijing.volces.com/api/coding/v3`、请求别名 `ark-code-latest`，仅现有load_provider_config解析 `third_party/AgentSociety/.env`，未source/cat/回显key；环境覆盖不匹配必须停止，未为测key发额外请求。分析与只读恢复不读取配置。

```bash
# 已执行命令的历史记录；正式ID已存在，禁止再次执行或换ID重跑
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_fixed_state_panel.py --mode real --allow-provider --protocol v2 \
  --session-id q62-panel-real-v2-01 --max-requests 48 \
  --execution-commit "$EXECUTION_COMMIT" --protocol-hash "$PROTOCOL_HASH" \
  --env-file third_party/AgentSociety/.env
```

当次执行遵守：超时占预算，取消未完成不启动下一请求；串行、无重试、无repair/fallback、未换provider/状态/提示。增量进度区分已处理与活动完成，含CALLS/VALID/ACTIVITIES/REJECTED/TIMEOUTS/STREAK/PAIRS。真实窗口未改tracked文件/commit/环境、未merge。若未来遇中断，先查原进程，原进程未停不并发导出；确认停止后才只读恢复，不恢复实验或补发。本次实际结束标记与验收范围见[验收账本](acceptance.md)。

### v2当前状态：只读复核与结果交接

执行commit为 `ae2123f50beaaca6bcac2dcca8e34659bd0a8b24`，规范协议hash为 `b66217fa18ce8740deec38334b157ff35f00455d8d2b431dd0b48531debffcc6`。执行前CI [37744586404](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37744586404) 全库950 passed、8 skipped，核心394 passed及AS2通过；文档CI [37744586620](https://github.com/richardssheik107-hub/Agent-Society/actions/runs/37744586620)通过。临时merge `c7e41519c3dc73373d442e9aa336a20f040ea954` 与执行HEAD整树相等，但不是实际执行commit。本页不把这些CI结果说成本机完整AS2验收或结果文档提交的新CI结果。

正式session最终为 `PANEL_COMPLETED`，cleanup为 `CLOSED`。计划48/48已处理、客户端计数48；HTTP与有效完成活动46，A/B各23；各臂一次孤立安全超时，max streak1。可评分覆盖为 `PARTIAL`：46/48单元、22/24完整同后端配对；两次超时没有输出可评分行为，未补齐。研究解释为 `NO_CLEAR_DIFFERENCE`，并非统计等价或长期效果证明。

|安全产物|当前位置|本次操作|
|---|---|---|
|原session|`run/evaluation/q6_2_fixed_state_panel/q62-panel-real-v2-01/`|已结束；禁止覆盖或重新运行|
|只读恢复|`run/evaluation/q6_2_fixed_state_panel_recovery/q62-panel-real-v2-01/`|已执行；297个源文件hash前后相同、阶段计数及原终止原因一致、新增请求0；不得覆盖此目录|
|确定性分析|`run/evaluation/q62_v2_analysis/q62-panel-real-v2-01/`|`safe_metrics.json`、`result_fragment_zh.md`、`source_integrity.json`；重算与原安全记录一致，新增请求0|

原只读恢复命令保留如下，**输出目录已经存在，不能再次执行并覆盖**；若将来有独立复核需要，先确认原进程停止，另选未使用的新恢复目录，不改变原session：

```bash
# 本次已执行的只读恢复记录，不重用已有output
env -u PYTHONPATH -u PYTHONHOME .venv-q61-runtime/bin/python \
  scripts/run_q6_2_fixed_state_panel.py \
  --export-only run/evaluation/q6_2_fixed_state_panel/q62-panel-real-v2-01 \
  --output run/evaluation/q6_2_fixed_state_panel_recovery/q62-panel-real-v2-01
```

分析只看安全字段和明确分母，不打开原prompt/completion/隐藏推理。已知reasoning token存在，minimal_request不能解释为关闭了思考，也不等于完成小模型对照。不得把runner的自动 `NOT_TESTED` 字段改成收益成功；独立解释及成本/行为局限见[Q6.2问题档案](../studies/q62_action_projection.md)。本轮收束，无追加请求、自动merge、采购功能或长链授权。

## 文档检查

在带pytest的测试环境执行：

```bash
python scripts/audit_repository.py --check
python scripts/audit_documentation.py --check
python -m pytest -q tests/test_documentation_navigation.py tests/test_repository_quality.py
```

需要完整Git历史；浅克隆缺对象必须报告不能完成，不能忽略。文档审计只读、零模型。旧文件检索见[清理映射](../reference/cleanup.md)。


## M2 独立离线获取闭环

在最新 `main` 的独立 Python 运行环境执行以下离线命令；每次必须使用新 session，不能覆盖已存在目录：

```bash
python scripts/run_m2_acquire_validation.py --mode offline --session <新的离线唯一ID>
python -m pytest -q tests/test_m2_acquire*.py
```

默认也是 offline，没有 real 模式，不读取 `.env`，不构造 provider。输出位于 `run/evaluation/m2_acquire/<session>/`，保存所有成功、拒绝、失败及恢复证据。新 world 显式启用 ACQUIRE，生产默认仍禁用；完成获取不自动 PLAY。完整机制和事务边界见[M2](../studies/m2_object_acquisition.md)，本轮实际结果见[验收账本](acceptance.md)。


**此命令只执行合成世界的离线工程测试，M2 `ACQUIRE` 默认关闭；原真实 Q6.2 目录严禁重用。**

## M5 多日生活、停止与恢复

以下入口复用旧世界规则；默认是合成自适应策略、零真实请求，不读 `.env`。从父仓库使用已建好的 Python 3.12 环境，每次新运行必须给未使用的 session ID：

```bash
.venv/bin/python scripts/run_m5_long_horizon.py --help
.venv/bin/python scripts/run_m5_long_horizon.py --mode offline --session-id <全新七天ID> --sim-days 7
.venv/bin/python scripts/run_m5_long_horizon.py --mode offline --session-id <全新三十天ID> --sim-days 30
```

上面的尖括号是待替换说明，不是可直接执行的 shell 参数。默认协议为 `config/experimental/m5_longrun_v1.json`，其中 `acquire_enabled=true` 只对该协议新建的 M5 实验世界明确 opt-in，不修改全局默认或旧世界。高层决策最多1000、provider预算0、累计运行墙钟600秒、微步骤15分钟、每活动最多1000微步骤、上下文字符/token上界各12000。资源预算先到则保留实际时间，不补足七天。独立完整验收及多次重启对照：

```bash
.venv/bin/python scripts/check_m5_longrun.py --session-id <全新验收ID>
```

产物位于 `run/evaluation/m5_longrun/<session>/`：`world.sqlite3` 为持久事实，`summary.json` 为评价与总计，`requests.jsonl`、`activities.jsonl`、`checkpoints.jsonl` 分开记录请求、活动和快照；`daily/dayNNN.json` 与中文日报在午夜 checkpoint 后即时生成。多次重启对照的四个子目录另有真实墙钟、数据库大小和 RSS 观测 `resources.json`。输出目录已存在时禁止覆盖。

停止使用一次 Ctrl+C，等待程序退出并检查摘要/收据，不要在原进程仍持锁时启动第二个写入进程。恢复已有离线会话：

```bash
.venv/bin/python scripts/run_m5_long_horizon.py --mode offline --resume run/evaluation/m5_longrun/<原会话ID>
```

恢复读取原协议与预算，不接受新的天数或预算 override，不重新 seed。有 ACTIVE 活动先继续确定性步骤，不重新问同一意图；世界活动若被显式 PAUSED 则不擅自 RESUME。请求登记后发送不明则停在 `UNCERTAIN_REQUEST_STATE`，不能用恢复重发。终点处尚未完成的活动仍保持真实承诺。只核对和导出时使用全新目标目录：

```bash
.venv/bin/python scripts/run_m5_long_horizon.py --export-only run/evaluation/m5_longrun/<原会话ID> --output run/evaluation/m5_longrun/<全新只读导出ID>
```

只读模式以 SQLite `mode=ro` 打开源事实，不读取凭据、不构造 provider、不执行世界动作；即使源会话不可安全继续，也能保留 UNKNOWN 和真实终止原因。

### 未来真实七天：目前不可执行

当前付费请求授权为 **0**。接口已经实现，但不能因为密钥存在就运行。将来必须先批准新的 session、已验收的干净执行 commit、冻结的独立 `mode=real` JSON 协议及其规范 `LongRunConfig.protocol_hash`、总请求预算和本次执行授权。不要改默认离线协议来绕过门禁。预算建议为七天上限、最多256高层决策/256请求、累计墙钟7200秒、每次60秒、上下文上限12000；这只是有限资源建议，不是授权，也不保证真实模型能到达10080分钟。

授权文件无密钥，合同字段必须严格为实际批准值：`authorization_type=EXPLICIT_USER_SESSION_AUTHORIZATION`、`approved=true`、`session_id`、`execution_commit`、`protocol_hash`、`max_provider_requests`、`acceptance={execution_commit,result:PASS}`、`request_policy={retry:false,fallback:false}`、`resume=false`。协议内容必须匹配这些值及 CLI，不能临时 override。环境文件必须为既有受保护配置，沿用原 alias/endpoint/思考设置；minimal request **不等于关闭深度思考**。未来获批后才可使用以下参数形态（本轮未执行）：

```bash
.venv/bin/python scripts/run_m5_long_horizon.py --mode real --allow-provider \
  --session-id <独立新ID> --protocol <已冻结real协议.json> \
  --sim-days 7 --max-decisions 256 --max-provider-requests 256 --max-wall-seconds 7200 \
  --execution-commit <已验收且干净的40位SHA> --protocol-hash <规范协议SHA256> \
  --authorization-path <本轮独立授权.json> --env-file <受保护环境文件>
```

真实暂停后的继续执行需要新的 `resume:true` 执行授权，绑定原 session/commit/hash/**原总预算**，不能充值预算。用 `--resume <原会话目录>` 替代 `--session-id`，保留 real/allow-provider、原冻结协议与授权参数，不附加预算 override。UNKNOWN、服务错误和不可恢复终态不继续请求；只读导出仍可用。所有 timeout、错误、非法输出按协议记录，没有 retry、JSON repair、fallback WAIT、自动换模型或自动切思考参数。

L1不变量错误立即停止；L2分开记录需求、资金和任务后果；L3仍由人审核。预警只记录，不替人物吃饭、睡觉或工作。具体实现与实际证据见[M5问题档案](../studies/m5_long_horizon_autonomy.md)和[验收账本](acceptance.md)。
