# WM811K：分级比较四种晶圆图案

**先复算，再看原网格。** 在「根因与图谱」导入并启用 [工作图](working-graph.v2.json)，点「用这张图分析」。在「中间 Evidence」上传 [原生 Frame](evidence.json)，选「分级解释溯因」，保留 8 个候选。两份 Frame 来自同一次实际原始输入，不需要模型、密钥或原网格即可复算。

- **248536**：近全片失效获支持，边缘环仍为待核验。
- **31707**：边缘环和边缘局部都只是待核验；在「推理」里选边缘环，比较中心密度反证与扇区参与度正证。若原网格受管附件已关联，两条都能定位到对应区域；离线 Frame 只有资产引用，不补画网格。

## 可选：从原始样本或短资料开始

- 原始 **248536** 用[现有 Wafer 准备器](../../../../docs/two-loop-demo.md#原始入口按场景准备固定输入)取得网格和固定权重。在同一工作图选「原始样本」，上传准备好的 JSONL；下载本次 Evidence 后，可用同图、同解释器普通上传复算。**31707** 的真实原网格来自同一固定测试表索引；需要该原始对照时只用已校验表和现有受限数据读取器裁取对应行，不加载原生标签。默认准备器只裁 248536，发布的两份 Frame 都可直接分析。
- 从 [自著短资料](material.md) 开始，可真实上传、提取和调用配置的文本模型。构图完成后人工校核，再编辑连续宽度、测量预算、判别锚点与辅证关系。这个操作会形成新图；从文件导入已发布图不是重跑 LLM。

WM811K 两行来自[固定数据镜像](https://huggingface.co/datasets/lslattery/wafer-defect-detection/tree/903fe28851d02a976db7a3a4bc12b6cfa2f5443c)，没有明确原网格再分发许可，仓库不附原网格或网格截图。[RadAI ResNet34 固定权重](https://huggingface.co/radai-agent/radai-wm811k-defect-detection/blob/61747cac7cba3eee3714fee86ab99f8250dd2e08/best_radai_resnet.pt)另行本机准备，其模型许可不覆盖原网格。短资料是演示作者规则；结果只评估图案，不判定工序或设备原因。

[实跑验收](../../../../docs/graded-wafer-demo-acceptance.md) · [结果摘要](verification.json) · [独立测量对照](measurement-validation.json)
