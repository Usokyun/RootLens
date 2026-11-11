# Tennessee Eastman Process：两条冷却回路的联合观测演示

这是 RootLens 自著的过程诊断演示说明。对象是 `Tennessee Eastman Process`。通道定义及冷却器能量平衡参考 [Downs/Vogel 原过程程序](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/teprob.f)和 [Russell、Chiang、Braatz 闭环程序](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f)。此处诊断规则不是原作者验证的故障分类器。

## 可观测量与范围

- `xmv_10` 是反应器冷却水回路调节量；`xmeas_21` 是同回路冷却水出口温度（°C）。`xmv_11` 是冷凝器冷却水回路调节量；`xmeas_22` 是冷凝器冷却水出口温度（°C）。调节量不是独立流量传感器。入口冷却水温度、反应放热量和换热阻力未在这四项中直接测量。
- 窗口统计使用独立正常参考。`statistics.mean_z` 是相对该参考的有符号标准化均值（单位 `1`）；正偏移不等于绝对偏移。`detection.anomaly_present=true` 只允许检查具体条件，不能代替它们。不同通道必须在同一个窗口、同一参考下共同成立。

## 两组可执行现象与待排查解释

1. **反应器冷却调节上移且出口变暖**：对同一窗口，`xmv_10` 的 `statistics.mean_z >= 2` **并且** `xmeas_21` 的 `statistics.mean_z >= 2`，再满足异常门控。两个并列的解释共享“反应器冷却热平衡受到额外负担”这一机制及相同的 `expected` 期望、同等假设代价：**反应器供冷侧入口水偏暖**，或者 **反应器过程侧放热负荷增加**。这两种机制来源方向不同，但这对通道不能区分它们；不能把出口温度当入口温度。
2. **冷凝器冷却调节上移且出口变暖**：对同一窗口，`xmv_11` 的 `statistics.mean_z >= 2` **并且** `xmeas_22` 的 `statistics.mean_z >= 2`，再满足异常门控。以“冷凝器冷却热平衡受到额外负担”为独立机制，比较一个替代假设：**冷凝器侧热负荷增加**；只对该组通道使用相同的 `expected` 期望。

两个回路的数值门槛 `+2` 皆由演示作者声明为 `declared_demo_heuristic`，不是设备报警值或实测故障标签。保持各组的两个条件为 ALL；任一条件缺测或方向相反，不得由另一条件或仅凭异常门控补足。不要从文件名、目录、故障编号或模拟标签读取推理输入；不要求回路上的其他变量都偏移。候选仅表示与现有证据的相容性，后续须补入口温度或过程热负荷测量才能区分。
