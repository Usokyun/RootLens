# MVTec AD 玻璃瓶：用几何证据解释局部异常

这个非商业演示使用一张公开玻璃瓶图像、一个以掩膜几何为输入的工作图。检测回答“哪里有异常响应”；推理展示哪些观测满足图中的条件、哪些解释仍无法区分。图中阈值是演示规则，不是工厂质检标准。

## 选一条入口

| 文件 | 怎么用 |
| --- | --- |
| [material.md](material.md) | 在「素材与构图」上传并解析，再用配置的文本模型制作新工作图。图中材料来源可回到这份原文。 |
| [working-graph.v2.json](working-graph.v2.json) | 不重新制作时，在「根因与图谱」导入并启用这个完整 v2 包；导入会分配新的登记 ID。 |
| [sample_006.png](sample_006.png) | 从已启用图点击「用这张图分析」，选原始样本、`bottle`、PatchCore、关闭 ROI 语义（`semantic_mode=disabled`）。 |
| [evidence.json](evidence.json) | 选「中间 Evidence」并上传，使用同图和统一约束推理。直接复算，不需要权重或远程模型。 |

原图入口使用已准备的 Bottle PatchCore。第三方权重不随包分发，来源仓库未声明明确的权重许可；仅在你有权使用时，从[固定的上游文件](https://huggingface.co/micguida1/mvtec-anomaly-checkpoints/blob/17e6b9b9bbb42f2f0ccda588bd088724520b8348/Patchcore/MVTecAD/bottle/latest/weights/lightning/model.ckpt)准备。重新制作工作图需要文本模型；导入现成图后上传 Evidence 不需要它。

`evidence.json` 是后端实际下载的原生文件，未重写观测或附件引用。新实例中，普通上传可复算，但不一定有关联媒体；选「公开演示样本」的 Evidence 入口会绑定随包原图。只有运行原图入口才重新生成掩膜和热图。

## 这一次实际验证了什么

1. 上传这份 Markdown，实际解析为 1 个片段，进行 1 次文本模型调用，无修复，生成 18 节点、21 条关系的工作图。在图谱页把实体名称改为「玻璃瓶 · Bottle」、更新别名后保存并明确启用；可执行条件、来源和源边标识不变。随包工作图是该次编辑后实际导出。
2. 从这张图进入普通原始样本上传。Bottle PatchCore 检出 1 个区域，异常门控为真。该区域在检测网格中的面积占比为 **22.84%**，包围框长短边比为 **1.1173**；同一区域的两项条件同时满足。ROI 外观语义未请求，未用图像目录标签补充观测。
3. 「本工位取放接触扰动」和「进入工位前已有局部表面损伤」并列第一，代价 **J = 0.25**，排序分 **−0.25**。保存了 6 条路径，涉及 11 条不同源边；面积条件可以定位到实际源边和同一 ROI。两候选共享观测，不能据此确认接触历史或瓶身部位。
4. 从该次运行下载 Evidence，普通上传到同一张图和同一引擎（Top K = 8）。Frame、图快照和完整推理结果逐项相同，未重跑 Backbone。原生运行及精确的观测、条件和源边 ID 见 [verification.json](verification.json)。

## 样本署名和许可

- `sample_006.png`：MVTec AD，原路径 `bottle/test/broken_large/006.png`。© 2019 MVTec Software GmbH。创作者：Paul Bergmann、Michael Fauser、David Sattlegger、Carsten Steger。参见 [MVTec AD 官方数据页](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)及[数据集论文](https://www.mvtec.com/fileadmin/Redaktion/mvtec.com/company/research/datasets/mvtec_ad.pdf)。
- 文件来自[保留原路径与署名通知的固定镜像](https://huggingface.co/datasets/foersben/mvtec-ad/tree/4e0e64896390500eb67720e1ceef16e160bb2a8d/bottle)。旧官方 Bottle 归档链接在验收时返回 404。该镜像 PNG 与先前公开 DS-MVTec 副本逐字节一致（900 × 900 RGB，523,230 字节）；未重新编码、裁剪或改像素，只换为中性文件名。原目录类别只用于溯源，不参与推理。
- 原图及随包的图像派生测量按 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 提供：署名、非商业使用，改编后再分发须使用相同许可。自著演示文字与从该文字编译的工作图并非 MVTec 或第三方厂商提供的规则。
