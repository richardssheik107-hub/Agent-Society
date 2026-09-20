# 历史 smoke 入口

此目录以 Phase/A1/A2 复现入口为主，不是当前任务清单。请从 `docs/current/README.md` 与 `scripts/run_continuity.py` 开始。

原 `behavior_prior_corpus_resume_remaining.py` 和 `behavior_prior_corpus_finalize_existing.py` 写死了已完成的 A2-Fast 实验编号，已归档到 `archive/legacy_tools/`。原入口只解释停用原因，不再自动调用模型或回填旧产物。

其他仍被历史实验、回归或人工复核使用的脚本保留；需要真实 provider 的入口不在默认 CI 执行。
