# Tennessee Eastman：反应器与冷凝侧的两类冷却响应

这是 RootLens 自著的过程诊断材料。回路与变量身份以固定版本的 [Downs、Vogel 原过程程序](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/teprob.f#L100-L132)和 [Russell、Chiang、Braatz 闭环程序](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f)为依据。以下可执行观测模式为演示规则，不是源程序的故障分类器。

## 反应器：控制努力上移有两种可见表现

`CONTRL18` 读反应器温度 `xmeas_9` 并写内环给定 `SETPT(10)`；`CONTRL10` 用冷却水出口温度 `xmeas_21` 对给定的偏差调整反应器冷却水调节量 `xmv_10`。控制量上移可与反应器温度仍受控制同时出现，不能把冷却水出口温度当入口温度。见 [外环程序 1192–1204 行](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f#L1192-L1204)和[内环程序 905–917 行](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f#L905-L917)。

在同一异常窗口及独立正常参考中，保留下列两个可观测签名。它们是**替代表现**，不是同时出现的两条反证义务：

1. **调节上移且出口变暖**：`xmv_10 statistics.mean_z >= 2` AND `xmeas_21 statistics.mean_z >= 2`。
2. **调节上移且反应器温度近参考**：`xmv_10 statistics.mean_z >= 2` AND `xmeas_9 statistics.mean_z >= -2` AND `xmeas_9 statistics.mean_z <= 2`。

两个签名共享一个反应器冷却热平衡机理和同样的两个待排查解释、同等 `expected` 强度：**反应器供冷侧入口冷却水偏暖**，或 **反应器过程侧放热负荷增加**。两支温度模式不能区分这两个上游解释。需另测入口水温或独立过程热负荷。

## 冷凝侧：调节、出口和分离器温度波动联合检查

`xmv_11` 是冷凝器冷却调节量，`xmeas_22` 是分离器侧冷却水出口温度，`xmeas_11` 是产品分离器温度。`CONTRL11` 读汽提塔底物流量 `xmeas_17` 后更新 `xmv_11`，并非照搬反应器的冷却水出口温度内环；`xmeas_17` 只作上下文。见[闭环程序 944–958 行](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f#L944-L958)。

**冷凝侧负荷响应**：同一异常窗、同一参考下，`xmv_11 statistics.mean_z >= 0.5` AND `xmeas_22 statistics.mean_z >= 0.5` AND `xmeas_11 statistics.std_z >= 1.5`。以「冷凝及分离侧热平衡响应」为机理，比较 **冷凝侧供冷能力变化** 与 **冷凝及分离侧热负荷增加** 两个同等 `expected` 的候选。这三个观测不直接测量入水温度、流量或换热能力。程序将命令 `XMV`、经过阀约束的 `VCV` 与实际阀位状态 `VPOS` 分开，[原过程程序 791–805 行](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/teprob.f#L791-L805)可核；仅凭本规则不提出阀卡滞诊断，需补实际阀位、流量与命令的比较。

`statistics.mean_z` 是有符号窗口均值偏移，`statistics.std_z` 是同一标准化窗内波动（单位均为 `1`）。所有阈值属于 `declared_demo_heuristic`，不是设备报警值或显著性检验。保持签名内的 AND、跨反应器签名的替代关系以及实际异常门；不能用单通道、文件名或故障编号推出原因。
