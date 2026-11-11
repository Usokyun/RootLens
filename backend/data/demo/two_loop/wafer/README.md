# WM811K 晶圆 248536：用空间证据校验图案

[短资料](material.md)给出两个图案的可复算规则。两条路线均用**统一条件溯因**，输出图案类型，不是制造根因。

- **无密钥复算**：在「根因与图谱」导入、启用 [v2 工作图](working-graph.v2.json)。点「用这张图分析」，普通上传 [实际导出的 Evidence](evidence.json)，或选择公开样例的「中间 Evidence」。Frame 只含观测与资产引用，不含原网格；尚未准备或绑定网格时仍能推理。
- **原始网格**：按[现场手册](../../../../docs/two-loop-demo.md)准备本机权重及原始行后，选择同一图和「原始样本」。JSONL 只含 `wafer_id`、`case_id`、`waferMap`（0 背景／1 正常／2 失效）；不传原生标签。运行后下载该次 Evidence 可普通上传复算。
- **从资料制作新图**：上传 `material.md`、提取、选择 Wafer 构图。此步骤调用配置的文本模型；完成后检查两类实际联合条件和来源，再编辑、启用。它不是导入预制包。

## 来源与分发

原始网格取自 [WM811K 镜像固定版](https://huggingface.co/datasets/lslattery/wafer-defect-detection/tree/903fe28851d02a976db7a3a4bc12b6cfa2f5443c) `test.pkl` 索引 248536。该镜像没有明示网格再分发许可；仓库不包含原始网格或其图片。原始数据论文：[Wu、Jang、Chen，2015](https://doi.org/10.1109/TSM.2014.2364237)。

[RadAI ResNet34 固定版](https://huggingface.co/radai-agent/radai-wm811k-defect-detection/blob/61747cac7cba3eee3714fee86ab99f8250dd2e08/best_radai_resnet.pt)另行本机下载。模型仓库标示 MIT，不涵盖 WM811K 原始数据。发布的短材料、图与派生 Frame 均不含原始 die 网格；来源材料为 RootLens 自著演示规则，不代表作者或厂商的诊断规范。

[验收摘要](verification.json)与[三页实跑记录](../../../../docs/wafer-public-demo-acceptance.md)列出真实运行和单值反事实。反事实不进入发布 Frame，也不是第二个真实晶圆样本。
