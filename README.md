# 有状态社会行为模拟研究

目标是在短上下文与受限模型预算下，构建可审计、可恢复的行为生成环境。模型提出行为，确定性规则校验并执行；世界事实不依赖模型“记得”。

**当前入口：[中文文档与计划](docs/current/README.md)**

当前重点已从独立单步基准转向长期状态与持续活动：对象进度、所有权、库存、事务、暂停恢复、幂等请求，以及 7/30 天工程验收。

```text
正式对象和参数 + 人物/人物—对象状态
                 ↓ 有界观察
             模型提出当前活动
                 ↓
       滚动控制器 → 参数化规则
                 ↓
         事务提交状态 + 领域事件
                 ↓
          下一次观察 / 故障恢复
```

## 直接运行

Q6 离线工程验收只需 Python 3.11+ 标准库：

```bash
python scripts/run_continuity.py
```

包括历史 Router 的全量回归需要固定的上游依赖：

```bash
git submodule update --init --recursive third_party/AgentSociety
python -m pip install -r requirements-test.txt -e third_party/AgentSociety/packages/agentsociety2
python -m pytest -q
```

默认没有模型调用。真实 provider 必须显式授权，见 [运行手册](docs/current/runbook.md)。

## 不混淆证据

Q3 支持 Catalog + Top-K 作为当前一步接口参考；Q4 尚未找到最小可见状态集合；Q5 仅验证虚拟地址空间上的共享规则索引，**不等于真实千万对象数据库或完整后果执行**。Q6 离线脚本通过也不等于模型自主生活正常。

历史报告在 `docs/archive/2026-09-20/`，原路径有跳转，不再作为当前待办。历史实验包与测试保留复现；其他成员的 delivery 数据原样保留。官方 AgentSociety 2 固定在 `third_party/AgentSociety`，本轮不修改或自动升级上游。
