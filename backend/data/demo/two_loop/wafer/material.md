# WM811K 晶圆图案：空间证据校验

这是 RootLens 自著的演示说明，可随项目分发。输出是晶圆失效**图案类型**，不是制造根因。对同一张晶圆（对象 `wafer`），原始网格编码 `0` 为背景、`1` 为正常 die、`2` 为失效 die；背景不进密度分母。图案词是 ResNet 的 `classifier.pattern`，不是数据集原生标签。检测到失效只是前置条件，不足以判断图案。

## 测量口径

`spatial.failure_density` 是失效 die 数除以有效 die 数，单位 `1`。`all_valid` 为全片有效区；按有效 die 包围框中心与各轴半径归一，`center` 是半径 ≤ 0.4，`edge` 是半径 ≥ 0.8。空区域视为缺失。`spatial.largest_component_ratio` 是最大八邻域失效连通分量大小除以全片失效 die 数，作用域 `all_valid`，单位 `1`。分类器和这些确定性测量都使用原始网格，但空间统计不从分类器标签推导。

## 两个候选图案，每个只用自己的联合条件

**近全片失效（`nearfull`）**。中间空间状态：全片高密度且失效成片。以下条件须在同一张晶圆同时满足：

- `classifier.pattern` 在 `all_valid` 等于 `nearfull`。
- `spatial.failure_density`：`all_valid` ≥ **0.75**，`center` ≥ **0.60**，`edge` ≥ **0.60**。
- `spatial.largest_component_ratio` 在 `all_valid` ≥ **0.70**。

**边缘环状失效（`edge_ring`）**。中间空间状态：边缘聚集、中心较低。以下条件须在同一张晶圆同时满足：

- `classifier.pattern` 在 `all_valid` 等于 `edge_ring`。
- `spatial.failure_density`：`edge` ≥ **0.55**，`center` ≤ **0.30**。

数值都是作者声明的**演示启发式**（`declared_demo_heuristic`），不是 WM811K 原标注、模型概率阈值或产线规范。类别与空间条件不一致时保留冲突或不足，不能只按分类器输出补结论。本说明没有工序、设备或失效机理记录，不能用来判定制造原因。
