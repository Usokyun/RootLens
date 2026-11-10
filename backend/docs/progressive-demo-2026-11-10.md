# 三场景 Demo：使用与验收

2026-11-10，渐进计划 T01–T22 已完成。本轮保留三页布局，主体实现位于 Python 后端。人工审核、正式版本发布、置信校准、训练和完整 benchmark 不在本轮范围。

## 直接展示已有结果

本机开发前端 `http://127.0.0.1:5186`，Backend 地址 `http://127.0.0.1:8012`。使用独立的 `compose.test.yaml` 数据库，未替换日常数据库。

建议先展示 MVTec，再展示改图与 TEP。无需重新调用 LLM：

1. 在 Evidence 页点击“回放资产”，在 **workspace export / session bundle** 中单独选择 `runs/refactor_m2_m6/mvtec_final-session.json`，点击“导入并切换到回放”。
2. 选择区域详情，核对原图、ROI、mask、heatmap、几何值与模型语义；进入“根因与图谱”→“链路”，查看条件和源边。
3. 要一次切换三场景，导入 `runs/refactor_m2_m6/all-scenes-session.json`：包含 3 个图、3 个 run、22 个 case。也可单独导入 `wafer_final-session.json` / `tep_final-session.json`。
4. 编辑图谱时先退出回放，保持 Backend 模式。在 Graphs 页点击“管理工作图”。保存只影响新分析，不改写已有 run。

以上路径均相对 `backend/`，大文件被 Git 忽略。本机成果索引为 `runs/refactor_m2_m6/acceptance-index.json`。

| 场景 | 最终工作图 | 最终 run |
| --- | --- | --- |
| MVTec bottle | `graph_19019f83e6b143129b66e339ade88c16` | `9620cf7b-4a3a-4637-807c-933929e426e5` |
| Wafer | `graph_95c0118290d44df78c24d82600ca1319` | `6dfe3fca-4ada-4a9f-9ded-72953eeb7133` |
| TEP | `graph_3abdcde0f02d41fa9de0d9f641e8ec87` | `3808b971-686f-470f-b1f5-c20692927bb1` |

MVTec 最终 records 来自真实原图推理 run `8597ff37-e5ca-4214-bdd4-1c82cf79e4cc`，不是手填缺陷标签。其后的重分析只更换领域图的可执行投影，不追加模型调用。

## 素材现在实际解析，再交给 LLM

- TXT/Markdown：文本、字符和行定位；CSV：逐行内容与表头；JSON/JSONL：逐项内容及 JSONPath/行定位；HTML：实际正文文本。
- PDF：使用 **Docling Parse** 的文本层解析和页码。扫描件无文本时明确失败，尚不支持 OCR/Office。
- URL：实际 HTTP(S) 获取后按文件类型解析；保留原始 URI、获取/解析失败原因及重试记录。单份素材上限仍为 20 MB。
- 每次重解析写入独立 extraction 目录，保留历史产物；Chunks 显示实际内容和定位，不再只改一个 extracted 状态。
- 中间包为 `rootlens-source-units.v1`；compiler 直接复用片段 ID、定位与内容，不重复分块。旧的直接文本 compiler 调用仍可使用。
- 素材上传/解析、build 完成、工作图 ready 分别来自实际文件、构图产物和数据库登记。重新构图保留旧产物；页面遇到同名输出会生成新的输出目录。

实库验收：3 份 Markdown 各解析 1 段、各重解析一次，PG 中有对应的 2 次 extraction；公开 W3C PDF 取得 `Dummy PDF file` 和第 1 页定位。URL 的实际获取、404 后重试及 compiler 片段复用由本地 HTTP 测试源验收。

## 图谱包包含可执行知识，不只是图形

完整格式为 `rootlens-working-graph.v1`：`dataset`、nodes、edges、aliases、来源、反馈计数、RCA 元数据和 profiles 均往返保存。profiles 是闭合的视觉或 measured schema，不执行 LLM 生成的代码。

| API | 用途 |
| --- | --- |
| `POST /api/kg/construction/builds/{id}/activate` | 从构图装载新图；支持 `dataset=mvtec/wafer/tep` |
| `GET /api/kg/working-graphs/{id}/package` | 导出完整包 |
| `POST /api/kg/working-graphs/import` | 导入为新图，不覆盖原图 |
| `PUT /api/kg/working-graphs/{id}/package` | 显式保存当前图和画像，修改前保存备份 |
| `PATCH /api/kg/working-graphs/{id}` | upsert/delete 节点和边、别名、画像；删除依赖需显式处理 |
| `POST /api/runs/upload` + `graph_id` | 使用所选图的新快照分析 |
| `GET /api/runs/{id}/replay` | 导出该 run 当时的图、结果及图片 |

已有节点/边策展表单的“保存工作图”已接持久 API；结构化文本编辑可调整绑定和阈值。仅视觉画像支持“按关系重建”；Wafer/TEP 的数值阈值必须显式编辑或重新构图，不能无提示清空。

保存使用图级锁、Neo4j 单事务替换和 PG 状态更新；旧包在 `runs/working_graph_backups/`。PG 后续写失败时恢复原图和登记，恢复失败会明确报告备份路径。新 run 只读取一次图和画像；完整原始图快照随 run 存 PG。已有 run 不因编辑重算。

### 排除软件流程词，不按案例裁图

真实 LLM 从 3 份素材生成了 **69 节点/143 边**，视觉 2 份、Wafer 4 份、TEP 2 份画像。TEP 曾将条件绑定到候选本身，自动校验发现后用 1 次 LLM 反馈修复，未人工审核。

原始抽取中还混入了 `FileName`、`ForwardPropagation` 等软件流程词。原始 artifacts 保留用于追溯；工作图采用**可执行依赖投影**：保留所有画像引用、来源边端点，以及所有声明候选的物理传播路径，不使用任何 case 的值选择节点。最终 MVTec 8 节点/13 边，Wafer 13/27，TEP 7/35。

新 compiler 会自动输出 `runtime_views/{dataset}.working-graph.json`。素材页装载发送 `compact_runtime=true`；旧 API 默认装载行为保持。完整构图和完整工作图包是不同产物，导出不会混淆二者。

## MVTec：定位、几何、语义与路径对应

实际适配了 **capsule STFPM OpenVINO** 和 **bottle PatchCore Lightning**，不代表 15 类全部具备权重。

- STFPM 按导出 metadata 的 resize、normalize、图像/像素阈值执行。
- 新 PatchCore 路线使用 `torch.load(weights_only=True)` 和严格 state_dict，调用本地官方 Anomalib 模块；CPU、默认 256 resize/ImageNet normalization，使用 checkpoint 内的后处理阈值。没有开启远程代码信任，也不下载额外 ImageNet 权重。
- 新工作图图片入口按对象注册 checkpoint；没有对应权重就报错，不把 capsule 权重用于 bottle。旧入口保留原选择合同。
- 多区域、高分辨率坐标显式映射；最多 3 次 ROI 语义调用，其余区域标记预算未执行。可配置同对象正常参考，辅助分辨缺失/破裂结构。

对象注册文件默认 `runs/mvtec_models.json`，可用 `KGTRACEVIS_MVTEC_MODEL_MANIFEST` 指定；格式示例见 `configs/mvtec_models.example.json`。默认 PatchCore 下载地址已替换失效来源；本轮实际验收的第二对象权重是 bottle。

实际 bottle 正例：原图 900×900，detector 网格 256×256，bbox `[84,70,230,239]`，映射原图 `[295.31,246.09,808.59,840.23]`，面积比 **0.19093**。正常参考加入后，ROI 返回 `BrokenRimDefect`，路径为形态/位置/语义 → BrokenRimDefect → MechanicalImpact。后者是机制候选。

早期没有正常参考时，模型误将玻璃结构理解为封口材料，返回 uncertain；保留该 run。正常图分数约 0.344、无候选。M1 capsule 的 scratch 漏检及 crack/Poke 语义差异仍保留，见 [M1 验收](mvtec-m1-demo.md)。

新几何的 linear 要求细长 bbox 或较强的协方差细长度；不再把中等离心率的宽弧区域当作线状划痕。该形态仍只是描述，不能替代 ROI 语义。

## Wafer：分类与空间必须各有来源

闭合观测 `wafer-measurements.v1` 包含有效/失效 die、失效率、中心/中圈/边缘密度、连通簇、线性程度、分类输出及标注状态。

- 固定 0 背景 / 1 正常 / 2 失效；正常 0/1 图不会把所有正常 die 当故障。失效率分母为有效 die。
- 分类器按作者的 64×64 双线性 zoom、缩放和八类顺序执行；只接收网格和 case ID，不接收原生类别。
- 正常标注 None、无标注和模型未知保持区别。八分类器没有正常类，不能靠它单独判正常。
- 旧顶层 location/morphology 保留分类摘要合同，并标注 `wafer_pattern_summary`；新推理只执行独立的 measured 数值，不把此摘要当实测。
- `nearfull` 不再改写为“实测颗粒污染”。候选 `WidespreadYieldLoss` 只表示广泛 die 失效，机制仍未区分。

实跑公开表中每类 2 张、共 **18 张**原生网格，真实 ResNet 推理。2 张 nearfull 和 1 张 edge-ring 满足现有画像；其他 15 张无匹配。当前有 4 类画像，不把未覆盖或未过阈值的样例强配路径。这是功能走查，不是分类准确率评测。

公开 pickle 先经只允许固定 NumPy/Pandas 数据构造器的转换脚本导出 JSONL，再进入分类器。脚本拒绝其他全局符号，未使用不受限数据反序列化。

## TEP：完整窗口与当前图共同决定结果

新 `.dat` 路线对应 Braatz 原始 52 通道：XMEAS1–41、XMV1–11；窗口起止为 **1-based、包含两端**，180 秒/样本。旧训练 CSV 入口保留；新入口另建匹配的正常 scaler/PCA，不混用 legacy memory 模板。

```bash
# 在 backend/，normal 和 sequence 换为实际文件
uv run --frozen --extra dev --extra llm --extra ml --extra parsers \
  python scripts/produce_tep_window_records.py \
  --normal runs/refactor_m2_m6/public/tep_d00.dat \
  --sequence runs/refactor_m2_m6/public/tep_d04_te.dat \
  --output-dir runs/my_tep_windows \
  --window 1:100 --window 161:260 --window 261:360 --fault-start-sample 161
```

生成的 `records.jsonl` 从原 Evidence 上传入口运行。正常参考 500 行、PCA 18 维；保留完整原始时序、全通道贡献、均值/标准差/斜率及参考参数文件。展示 top contributors 不截断计算输入。

实际窗口 161–260：残差能量 **60.967**，正常行能量 99% 分位 **26.668**；XMV10 平均偏移 **7.172 z**、RBC 贡献 **0.46090**。XMEAS9/21 的均值未过阈值，不能声称它们满足 mean-shift 条件；它们的残差分量确实进入数值评分，分别生成标记 `result=used` 的贡献路径。

画像条件触发候选，Root-KGD 传播算子在**当前工作图**上消费方向、权重、衰减和全通道向量。当前图的 ReactorCoolingDisturbance 得分 **0.35664**，汇聚 3 条路径；1–100 正常窗口无候选。诊断反向视图保留物理源边，不当作反向物理因果。

对同一真实窗口的图反事实检查：

| 变化 | 实际结果 |
| --- | --- |
| 原边权重 0.7 | 候选得分 0.35664 |
| 传播边权重改为 0.1 | 得分降为 0.05095 |
| 物理传播方向反转 | 无匹配 |
| 所有 mean-z 门槛改为 100 | 无匹配 |

阈值 2 z 和领域机制来自预先写下的公开演示知识假设，不按该窗口 fault ID 反推。新 reasoner 不消费 faultNumber/文件名标签。

## 回放保留原知识与完整结果

仍使用现有 `rootlens-session-export.v1` / `rootlens-runtime.v1`；增加可选 `backend_runs` 保存原 RunDetail，避免浏览器重新推导路径。旧回放仍可读取。图片使用内嵌预览；大 runtime 存 IndexedDB，小型会话继续兼容原 localStorage。资产写入成功后才发布会话指针，失败保留旧会话。

曾实际遇到图片回放超过 localStorage 配额，现已修复。MVTec 大回放重新导入、整页刷新、图和候选重载均通过；图页刷新后对 8012 **0 个请求**。TEP 趋势和回放路径也已实际看屏。没有浏览器 RCA/what-if 重算。

## 核验与已知失败

- 后端完整 pytest：**345 passed / 7 failed / 1 skipped**，与 M1 的 7 个失败 node IDs 相同，无新增失败。日志 `runs/m2-m6-full-pytest-final.log`。
- 7 项：旧配置测试受隔离 Neo4j 环境影响；缺少历史 real-output case、旧图片/mask/heatmap、crack/000.png；固定 PatchCore 默认假设；旧 wafer user-study 缺 fixture。未伪造这些资产来使测试变绿。
- 前端 **19 文件 / 89 项通过**，生产 build 通过；保留既有大 chunk 警告。日志 `runs/m6-frontend-tests-final.log`、`m6-ui-build-final.log`。
- 修改的 Python 文件 Ruff 通过，`runs/m6-ruff-final.log`。实库测试覆盖隔离、完整交换、编辑重分析、历史快照、保存失败恢复；parser 测试覆盖 URL/PDF 和失败重试。
- 页面实操：TEP 全通道趋势、工作图 JSON 保存、3 场景/22 case 合并 Session 导入、刷新、MVTec 图片和 TEP 趋势/路径。截图在 `runs/refactor_m2_m6/*ui.png`。

模型、数据、LLM 原始产物和数据库在 `runs/`，没有提交凭据、大权重或数据库；没有训练、GPU、人工审核流程或正式发布。

## 来源与恢复

- [bottle PatchCore checkpoint](https://huggingface.co/micguida1/mvtec-anomaly-checkpoints/tree/main/Patchcore/MVTecAD/bottle/latest/weights/lightning)；[公开 MVTec 图片镜像](https://huggingface.co/datasets/foersben/mvtec-ad)，遵守 MVTec AD 非商业数据许可。
- [RadAI WM811K 模型及预处理](https://huggingface.co/radai-agent/radai-wm811k-defect-detection)；[公开测试表](https://huggingface.co/datasets/lslattery/wafer-defect-detection)。模型卡声明不代替本轮评测。
- [Braatz TEP 原始参考数据](https://github.com/camaramm/tennessee-eastman-profBraatz)。
- [Docling Parse](https://github.com/docling-project/docling-parse)；[W3C 公开 PDF fixture](https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf)。

安装使用 `uv sync --frozen --extra dev --extra llm --extra ml --extra parsers`。本机独立库和端口恢复命令沿用 [M1 运行说明](mvtec-m1-demo.md#配置与恢复)。已有库只执行 working_graphs 增量迁移，不执行新空库初始化或删除卷。
