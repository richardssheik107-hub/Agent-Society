# 分支归档与主线约定

整理日期：2026-09-20。

从本次整理开始，**`main` 是唯一现行主线**。后续新研究、修复和实验都应从最新 `main` 创建新分支；下面列出的旧分支只保留历史审计价值，不再继续提交新功能。

## 当前分支状态

| 分支 | 主要内容 | 当前状态 |
|---|---|---|
| `main` | Q3/Q4/Q5、会议资料、delivery 数据、Q6 continuity 与中文现行文档 | **现行主线** |
| `integration/continuity-cleanup` | 本次仓库整理、长期状态、滚动活动、AS2 适配与验收 | 已通过 PR #3 合入 `main`，历史保留 |
| `research/object-set-necessity` | Q3 Object Set 必要性实验 | 已被集成分支完整包含，历史保留 |
| `research/resource-set-size` | Q4 Resource Set 大小实验 | 已被集成分支完整包含，历史保留 |
| `research/rule-engine-scaling` | Q5 10M RuleEngine scaling 实验 | 已被集成分支完整包含，历史保留 |
| `data/atus-2025` | 早期 ATUS/行为数据相关实现 | 已被集成分支完整包含，历史保留 |

GitHub compare 已确认：上面五个旧分支的 HEAD 都是集成分支的祖先，因此没有逐个重复 merge；一次合并 PR #3 即把它们统一收进 `main`。

## PR 归档

- PR #3：已合入 `main`，作为本轮统一归档入口。
- PR #1（Q3）：内容已通过 PR #3 进入 `main`，不再单独合并。
- PR #2（Q5）：内容已通过 PR #3 进入 `main`，不再单独合并。
- Q4 没有单独保留一个必须再合并的 PR；其 HEAD 已位于 Q5/集成历史链上。

## 为什么不直接删除旧分支

本轮目标是“归档到 main”，不是抹掉实验历史。保留旧 branch ref 有三个好处：

1. 能直接查看当时实验代码和提交顺序；
2. 能复核 Q3/Q4/Q5 的原始结果，而不依赖后续重构；
3. 避免删除后需要从 commit SHA 人工恢复历史上下文。

因此旧分支现在是**只读历史标签式用途**。如果以后确认不再需要 branch ref，可以单独做一次远端分支删除；删除前不应再产生新提交。

## 以后怎么开工

统一规则：

```text
main
  ↓
feature/<topic>
research/<new-question>
fix/<problem>
```

不要再从 Q3/Q4/Q5/data/integration 这些历史分支继续开发。

当前项目状态、架构和优先级以：

- `docs/current/README.md`
- `docs/current/research_status.md`
- `docs/current/architecture.md`
- `docs/current/plan.md`

为准。
