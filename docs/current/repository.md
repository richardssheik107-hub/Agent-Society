# 仓库地图与清理记录

## 整理基线

2026-09-20 核对到：main=`bbebaf6720e8fadf25e4de0ee5b62021ae84c358`，Q3=`20f5f0c0e6f1aa830075981dc87f9852d356460d`，Q4=`9aa5d96b4339aac6affbb783a913c2f4a366c3ac`，Q5=`7e537cef22fca73c7e1cc6be22d55a829aed6d9a`。Q5 继承 Q4/Q3；main 另有会议记录和其他成员的两份 delivery 文件。

本次在 `integration/continuity-cleanup` 整合这些内容，不改写原研究分支，不 force push，不自动合并到 main。上游固定为 `670c94fff7c64c4f79b632125f2ccf968155e746`。

清理前对 267 个跟踪条目完成清单与 Python AST 导入扫描；这是仓库盘点，不表示逐行证明了全部代码正确。

## 模块定位

| 路径 | 现在的定位 |
|---|---|
| `src/social_sim/continuity/` | 新的长期状态与活动运行层，当前重点 |
| `world/ actions/ effects/ rules/ reducer/ execution/ events/ closed_loop.py` | 原有确定性世界和逐动作闭环，保留兼容与回归 |
| `router/ context/ decision/` | 原有确定性观察、短上下文及安全客户端，按需复用 |
| `daily/ evaluation/ a2_final/ a2_closure/` | 已完成阶段的实验与审计实现，不视为废代码直接删除 |
| `human_data/ calibration/ behavior_prior/` | 日记 ETL、标定和先验，保留原数据分割 |
| `object_benchmark/ resource_benchmark/ rule_scaling/` | Q3/Q4/Q5 冻结基准，不与 Q6 实际领域执行混称 |
| `scripts/run_continuity*.py` | 当前离线/显式授权真实运行入口 |
| `scripts/audit_repository.py` | 只读仓库与文档引用检查 |
| `smoke/` | 历史阶段入口；见该目录说明，不按旧计划自动补跑 |
| `archive/legacy_tools/` | 已完成、写死旧 experiment ID 的一次性脚本原文 |
| `docs/current/` | 当前中文说明与计划的唯一入口 |
| `docs/archive/2026-09-20/` | 旧报告原文，内容哈希保留 |
| `third_party/AgentSociety/` | 未修改的上游子模块 |
| `delivery.*.jsonl` | 其他成员上传数据，原样保留 |

## 本次清理动作

- 替换仍声称“Phase 0、规则尚未实现”的 README。
- 将原根目录 README 和全部旧 docs 原文归档；旧 docs 路径保留简短中文跳转，避免外部链接失效。研究证据没有被删除。
- 将写死 `real_20260917T085445574770Z` 的 A2-Fast 补跑、回填脚本移入 legacy_tools。原入口改为明确退出的停用说明，避免重新调用 provider 或覆盖旧结果。
- 不批量删除旧 Python 包、测试、校准配置和历史失败，因为它们仍用于复核和回归；未被导入也不代表 CLI 无用。
- 加入当前测试依赖、中文执行手册、有界真实请求入口、CI 和只读盘点工具。

机器可读清单位于 `docs/current/cleanup_manifest.json`。只读审计从冻结 Git 提交读取原始内容并核对 SHA256；受保护代码、delivery 文件与上游 gitlink 也会核对，不读取凭据或原始模型响应。

## 当前仍需注意

旧实验的数据目录 `run/` 和外部语料不在 Git 里。本轮未读取用户电脑上的隐藏运行产物，不填造它们的内容。历史 508 个测试与新增测试是否全通过，以最后 CI/运行记录为准。
