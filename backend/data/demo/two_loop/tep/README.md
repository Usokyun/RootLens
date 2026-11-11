# Tennessee Eastman：区分「温度上升」和「控制努力上升」

反应器冷却水调节量明显上移，反应器温度却仍接近正常参考。这个样例用同一窗口的实测数据解释为什么两者可以并存，以及为什么仅凭这些观测无法区分供冷侧和过程放热侧。

## 从哪里开始

| 文件 | 用途 |
| --- | --- |
| [working-graph.v2.json](working-graph.v2.json) | 在「根因与图谱」导入、检查并启用完整工作图；导入创建新登记图，不替换既有图。 |
| [evidence.json](evidence.json) | 从图页点「用这张图分析」，选「中间 Evidence」普通上传。选择统一条件溯因或 RootKGD，Top K = 8。不需要原始序列、权重或模型密钥。 |
| [material.md](material.md) | 从「素材与构图」上传、提取，使用已配置的文本模型制作初始图；原始规则要求冷却水调节量和出口温度都正偏移。 |
| [expert-refinement.md](expert-refinement.md) | 人工补充串级控制观测模式的依据与边界。最终图显式引用这份补充；它不是额外一次模型构图。 |
| [verification.json](verification.json) | 实际任务、三窗精确数值、初版图与修订图的结果、同窗口路径及单值对照。 |

使用现成图和 Frame 可直接复算。新的服务若没有原始附件，会如实显示曲线未关联；准备原件后可在公开演示入口关联每个窗口的真实曲线。详见[操作手册](../../../../docs/two-loop-demo.md)。

## 原始输入和正常参考

输入是同一固定版本的 [d04_te.dat](https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/0643318858ce7c87292bd59820b459e12a13d009/d04_te.dat) 和独立 [d00.dat](https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/0643318858ce7c87292bd59820b459e12a13d009/d00.dat)。上游见 [Russell、Chiang、Braatz 维护的闭环过程与数据](https://github.com/camaramm/tennessee-eastman-profBraatz/tree/0643318858ce7c87292bd59820b459e12a13d009)（过程原模型：Downs、Vogel）。镜像[许可声明](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/LICENSE)没有单独说明这些原始记录的再分发条件；DAT 文件及其曲线附件不随仓库分发。

在 `backend/` 执行 `uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset tep --download`，或从上述固定版本获取两份文件。用「原始样本」分别上传过程记录和正常参考；按一基、两端含边界输入 `1–100`、`161–260`、`261–360`，采样间隔 **180 秒**。序列是 960 × 52；参考原文件 52 × 500，适配器转为 500 × 52 后拟合。文件名和故障编号不参与推理。

## 同一规则如何区分三个窗口

异常门成立，且同窗同参考的 `XMV10` 有符号均值偏移 ≥ +2；然后需要满足「冷却水出口 `XMEAS21` ≥ +2」或「反应器温度 `XMEAS9` 在 [−2, +2]」。阈值是演示作者声明的启发式，不是设备报警值。冷凝器有独立的 `XMV11` 与 `XMEAS22` 联合规则。

| 样本窗口 | 异常门 | XMV10 | XMEAS9 | XMEAS21 | 统一条件溯因 |
| --- | --- | ---: | ---: | ---: | --- |
| 1–100 | 关 | +0.056 | −0.029 | −0.054 | 不入榜，无路径 |
| 161–260 | 开 | +7.172 | −0.077 | +0.086 | 补偿分支成立，两个候选并列 |
| 261–360 | 开 | +7.060 | +0.051 | +0.279 | 补偿分支成立，两个候选并列 |

暖出口分支始终不成立。最初只使用这条分支时，161–260 的实际结果是不匹配；后续人工补的是控制架构支持的另一种响应，不是降低原门槛。两个异常窗口均支持**反应器供冷侧入口冷却水偏暖**与**反应器过程侧放热负荷增加**，各 J = 0.25、排序分 −0.25。现有观测不直接测量入口温度或放热，不能从并列中断定真实原因。

原始 Run 下载的 Frame 普通上传后，三窗 Frame、图快照、完整结果和各窗 52 条曲线逐项相同。RootKGD 使用同一 Frame 的 52 维残差贡献与图传播比较，不执行上面的 ±2 条件；两个异常窗仍为反应器候选并列。正常门关闭时两引擎均不排序。[实际任务、曲线与路径验收](../../../../docs/tep-public-demo-acceptance.md)保留了原失配规则、后续窗口和离线单值对照。
