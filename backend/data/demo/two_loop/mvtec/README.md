# MVTec AD 玻璃瓶：用区域偏心区分掩膜形态

这个非商业演示使用一张公开原图。PatchCore 找到异常区域；统一条件溯因检查该区域是否较大、包围框不细长且像素分布不显著沿单轴拉伸。包围框接近方形，也可能包含对角狭带；加入主轴离心率就是为了排除这种形态，而不是判定工艺根因。

## 选择入口

| 文件 | 怎么用 |
| --- | --- |
| [material.md](material.md) | 在「素材与构图」上传、提取，用配置的文本模型制作新工作图。 |
| [working-graph.v2.json](working-graph.v2.json) | 不重新制作时，在「根因与图谱」导入并启用这个完整 v2 包；导入会分配新的登记 ID。 |
| [sample_006.png](sample_006.png) | 从已启用图点「用这张图分析」，选原始样本、`bottle`、PatchCore，关闭 ROI 语义（`semantic_mode=disabled`）。 |
| [evidence.json](evidence.json) | 选「中间 Evidence」，上传原生文件，用同图、统一条件溯因、Top K = 8 复算。不需要权重或远程模型。 |

第三方 Bottle PatchCore 权重不随包分发，上游未声明明确的权重许可；如有权使用，可从[固定上游文件](https://huggingface.co/micguida1/mvtec-anomaly-checkpoints/blob/17e6b9b9bbb42f2f0ccda588bd088724520b8348/Patchcore/MVTecAD/bottle/latest/weights/lightning/model.ckpt)准备。新实例普通上传 Evidence 可以复算，但不一定有关联媒体；「公开演示样本」的 Evidence 入口绑定随包原图。原图入口才会重新生成掩膜和热图。

## 哪些字段参与了这次推理？

| 字段 | 本次用途 |
| --- | --- |
| 异常布尔量 | 检测前置门控；为真不等于具体形态或根因成立。 |
| 面积占比、包围框长短比、主轴离心率 | 同一区域须分别满足 **≥ 0.10、≤ 2、≤ 0.90**。三个阈值都是作者声明的演示启发式。 |
| 连通分量数、粗形态标签 | 不入规则。每个本机连通 ROI 的分量数固定为 1；粗形态已由长短比和离心率分桶。 |
| 区域位置、像素框 | 图像坐标用于展示和回到 ROI；位置标签来自图像网格质心，不足以识别瓶口等部位。 |
| 外观候选、外观缺陷判定 | VLM 未运行，这两项缺测，不填入推理。 |

## 真实结果和单值对照

新资料解析为 1 个片段，经 1 次文本模型调用生成 20 节点、23 条关系的图。GUI 修改对象名称和别名、保存、回读并确认启用；随包图是编辑后实际导出的版本，三条几何规则未改。

原图经 CPU PatchCore 得到 1 个 ROI，实测面积占比 **22.84%**、长短比 **1.1173**、离心率 **0.7970**，三项均通过。**本工位取放接触扰动**与**进入工位前已有局部表面损伤**并列第一，代价 J = 0.25、排序分 −0.25，保存 8 条路径（12 条不同源边）。离心率条件可以定位到实际源边和同一 ROI。原生下载的 Evidence 经同图普通上传后，Frame、图快照和完整结果逐项相同。

只把副本的离心率改为 **0.94**，异常门、面积、长短比仍成立，离心率却与该联合分支不符。严格榜仍无入选，完整路径从 8 条变为 0；两候选另列为**待验证**，结果显示证据不足。三项可判诊断量中两项支持、一项反证，待验证代价 `J = 1/3 + 2 × 1/3 + 0.25 × 1 = 1.25`。它是这条分支的代价，不是工艺原因的概率，也不与严格榜比较。

**图像仍被检测为异常**，两工艺假设仍未区分。数值对照不是另一张图的测量，不随原生 Evidence 发布。原严格 `no_match` 对照及后来隔离 API 的待验证检查均在 [verification.json](verification.json) 中。

## 样本署名和许可

- `sample_006.png`：MVTec AD，原路径 `bottle/test/broken_large/006.png`。© 2019 MVTec Software GmbH。创作者：Paul Bergmann、Michael Fauser、David Sattlegger、Carsten Steger。参见 [MVTec AD 官方数据页](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)及[数据集论文](https://www.mvtec.com/fileadmin/Redaktion/mvtec.com/company/research/datasets/mvtec_ad.pdf)。
- 文件来自[保留原路径与署名通知的固定镜像](https://huggingface.co/datasets/foersben/mvtec-ad/tree/4e0e64896390500eb67720e1ceef16e160bb2a8d/bottle)。旧官方 Bottle 归档链接在首次验收时返回 404。镜像 PNG 与先前公开 DS-MVTec 副本逐字节一致（900 × 900 RGB，523,230 字节）；未重新编码、裁剪或改像素，只换为中性文件名。原目录类别只用于溯源，不参与推理。
- 原图及随包图像派生测量按 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 提供：署名、非商业使用，改编后再分发须使用相同许可。自著演示文字和工作图不是 MVTec 或第三方厂商提供的规则。
