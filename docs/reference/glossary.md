# 术语与指标：怎么读才不会误解

| 术语/标签 | 中文含义 | 不能误读为 |
|---|---|---|
| Object / Catalog | 具体对象与正式目录 | 对象只要存在就能使用 |
| Type / Capability | 类型与通用能力 | 代替钱、位置和库存检查 |
| Rule Template | 共享规则/参数化公式 | 所有对象产生同样数值 |
| ResourceTruth / 可见投影 | 后台状态真值/给模型展示的一部分 | R8 世界真的只有八个事实 |
| Agent×Object State | 某个人与某个对象的持久关系 | 只有模型聊天记忆 |
| Activity Commitment | 一段持续活动及其生命周期 | 提议后立即算完成 |
| Feasible / executable_options | 当前检查可执行的活动和目标 | 未来库存不会改变，或行为最优 |
| Top-K | 返回有限候选的一般形式 | 必然是语义检索；Q5 只是确定性虚拟 ID 候选 |
| Matched cases | 各实验臂同时有成功结果的同场景样本 | 已消除所有超时选择偏差 |
| Runtime executable（Q3） | 对象和效果字段满足本基准检查 | 已验证长期真人活动执行 |
| Resource alignment（Q4） | 属于预先设定的可接受动作集合 | 真人唯一正确答案 |
| Critical miss（Q4） | 本实现中为 alignment 的补数 | 第二个独立改善证据 |
| Held-out share | 选择动作在独立日记参考分布中的占比 | 某人的合理行为概率/准确率 |
| NA / NOT EXERCISED | 无法对应评分/没有触发场景 | 自动成功或失败 |
| STATE_FEEDBACK_VISIBLE | 已记录的观察摘要跨步衔接 | 因果证明模型利用了每个字段 |
| Invariant | 程序定义的状态约束 | 整体行为像人 |
| SCRIPTED | 脚本安排的工程验收 | 模型自主生活 |
| CLOSED_ENGINEERING | 满足该阶段明确工程门槛 | 项目所有问题已经解决 |
| provider requests | 代码记录的客户端请求尝试计数 | 无响应时也能证明服务端收到 |
| input tokens / prompt chars | 模型计费输入单位/字符串字符数 | 同一个指标，或稳定延迟预测 |

金额分、时间分钟、需求 0—1000 是 Q6 小世界的单位；Q4 的影子 Resource 值使用 0—1，方向随字段不同，不混在一张表里当同一量纲。

查原问题：[问题索引](../current/research_status.md)。需人工确认的评分与概念边界：[审核专区](../review/README.md)。
