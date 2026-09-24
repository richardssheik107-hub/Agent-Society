# 分支状态与主线约定

核对日期：2026-09-24。

## 当前远端状态

| 分支 | 状态 | 用途 |
|---|---|---|
| `main` | **唯一现行开发基线**；Q6.1/Q6.2 已合入，merge `cce3e7bd850f72faf0efa41017491d392b00ee11` | 后续所有新研究、修复和实验从这里开分支 |
| `research/q6-real-continuity-pilot` | PR #4 已合并；历史 ref | 保留 Q6.1/Q6.2 提交顺序与实验审计，不继续开发 |
| `docs/research-navigation-zh` | PR #5 已合并；历史 ref | 保留文档整理过程，不继续开发 |

旧 Q3/Q4/Q5、ATUS 和 integration 分支已经从远端移除；其提交仍在 Git 历史中。

## 本次合并记录

Q6 研究分支先与最新 main 做显式双父合并，保留 main 的中文文档体系，只带入 Q6.1/Q6.2 的业务代码、运行时、测试和 CI。第一次集成 CI 暴露一个旧文档保护测试与新退役策略不兼容；修复提交 `bea7dbf64fd8a61eced09820503b46ae3f56ad59` 后，最终 CI `35951841827` 全绿，再合并 PR #4。

最终 merge commit：

```text
cce3e7bd850f72faf0efa41017491d392b00ee11
```

## 以后怎么开工

统一规则：

```text
main
  ↓
feature/<topic>
research/<new-question>
fix/<problem>
```

不要从已合并的 docs/Q6 历史分支继续开发，也不要 force push 或改写旧实验提交。真实 Q6.2 A/B 仍需新的明确授权；代码入 main 不等于自动授权请求。
