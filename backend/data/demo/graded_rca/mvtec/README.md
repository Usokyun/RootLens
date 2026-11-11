# 玻璃瓶：块状、细长与结构复查

**先看形态，再查原因。** PatchCore 的异常掩膜能区分较大块状响应与细长响应；这次的公开表面对照也得到块状响应，说明几何不能区分材料缺口、表面对比或工位成因。工作图保留两项结构复查，不把未测量的物理情况计入排名。

## 运行这个演示

1. 在「素材与构图」上传并提取 [material.md](material.md)，可用配置的文本模型制作初稿。先检查模型有没有把实际缺项编成代理条件、有没有保留细长形态的两个替代分支；给当前图加分级比较预算后再启用。直接演示时，导入并启用已经复核的 [working-graph.v2.json](working-graph.v2.json)，不需要文本模型。
2. 在该图点击「用这张图分析」，选**分级解释溯因**（`graded_abduction`）。用 [原生 Evidence](evidence.json) 可直接复算，不需要任何模型或权重。也可上传[同一张公开 006 原图](../../two_loop/mvtec/sample_006.png)，选择 `bottle`、PatchCore、关闭 ROI 外观语义，现场生成原图、掩膜、热图及 ROI 对照。第三方权重不随包分发；有权使用时按[固定上游文件](https://huggingface.co/micguida1/mvtec-anomaly-checkpoints/blob/17e6b9b9bbb42f2f0ccda588bd088724520b8348/Patchcore/MVTecAD/bottle/latest/weights/lightning/model.ckpt)配置。
3. 保留候选数为 8，打开「推理」查看每项实测、正／负贡献和来源，点离心率回到同一 ROI。可下载本次 Evidence，再按同图、同引擎、同候选数普通上传。普通重传不调用 Backbone；仅拿随包 Frame 在新实例复算时，旧实例的媒体路径不会自动恢复。

对照用 [A 原图](contrast-a.png)／[Frame](contrast-a.evidence.json) 与 [B 原图](contrast-b.png)／[Frame](contrast-b.evidence.json)。两张原图都由同一 CPU PatchCore 测量后交给同一 adapter；没有使用目录类别或像素标注作为输入。A 未触发异常门，不出形态候选；B 触发异常门，实测面积 **10.19%**、长短比 **1.0753**、离心率 **0.7125**，块状分支的两个解释仍并列，`S=0.6795`。

## 怎么读结果

006 一个 ROI 的面积 **22.84%**、长短比 **1.1173**、离心率 **0.7970**。三个等权几何槽均充分支持较大块状响应，`P=1`、`C=0`、`S=1`、`V=1`。**本工位取放接触扰动**和**进站前已有局部表面损伤**共用同一机理和响应，仍并列。这里的 `expected` 表示形态不符会降低该形态解释的分数，不表示已证实工位原因。

[单值对照](controlled-comparison.json)只改既有 006 Frame 的离心率：改为 **0.94** 时，块状分支的面积、长短比仍支持，离心率的加权反证为 **1/6**，同一分支转为待核验，`S=0.5`。细长分支选择「面积下限 AND 主轴拉伸」而不是轴对齐长短比，两个方向性解释并列有支持，`S=0.5`。这不是另一张图的测量；分组状态和实际分支不能只看同一个分数。

| 观测 | 作用 |
| --- | --- |
| 异常布尔量 | 仅是前置门控。 |
| 面积、长短比、离心率 | 同一掩膜的三个等权槽；同一量的相反比较共用一个槽。 |
| 分量数、粗形态、位置、图像框 | 分量数对单连通 ROI 恒为 1；粗形态重复分桶；位置和框用于显示，不识别瓶口等部位。 |
| 外观语义、外轮廓缺口、表面沉积、工位履历 | 本次没有可核验的值，不用于排名。 |

[外轮廓叠加与偏差曲线](reference-outline-comparison.png)中的金色框是 006 的检测 ROI，控制图上的同框只是固定比较区域，不是它们各自的模型 ROI。用三张正常参考配准后，006 相对两张对照的局部外轮廓偏差差值仅 **0.91–0.95% R**，低于事先冻结的 **2% R**。[参数和实测](reference-checks.json)也保留了环带探针：名义比例差 26.21 个百分点，但内边界敏感性下最小差 20.12，低于冻结的 25；都没有加入评分。下一步用匹配视角／背光确认缺口，再换光复查内部反差，或比较同瓶进站前后图像。

## 来源与许可

- 006 原图沿用[旧包中的已署名公开文件](../../two_loop/mvtec/README.md#样本署名和许可)。A、B 原图分别为 `bottle/test/good/001.png`、`bottle/test/contamination/000.png`，来自[固定镜像](https://huggingface.co/datasets/foersben/mvtec-ad/tree/4e0e64896390500eb67720e1ceef16e160bb2a8d/bottle)，仅改文件名，不修改像素。配准参考为同版本 `bottle/train/good/{000,001,002}.png`，不在包中重复分发。
- MVTec AD © 2019 MVTec Software GmbH；创作者 Paul Bergmann、Michael Fauser、David Sattlegger、Carsten Steger。[官方数据页](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)。原图、图像派生 Frame、测量与叠加图按 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 提供；叠加图标出拟合轮廓与比较区域，并附曲线。
- 材料与工作图是 RootLens 的演示说明，引用 Emhart 和 Basler 的公开资料，不再分发原文 PDF；几何规则不是厂商或数据集提供的工艺标准。

完整闭环与实际编辑见 [MVTec 验收](../../../../docs/mvtec-graded-demo-acceptance.md)；[机器摘要](verification.json)保留 Run、源边与原始观测 ID。
