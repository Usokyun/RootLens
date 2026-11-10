# MVTec 首个闭环：使用与验收

2026-11-10，M1a / M1b / M1c 已落地。当前实跑范围是 **capsule、公开 STFPM OpenVINO 权重、TXT/Markdown 构图素材**。主体在 Python 后端，前端保留三页布局。

## 先看已有演示

本次本机验收使用独立数据库和开发端口，不替换日常数据库配置：

- 前端：`http://127.0.0.1:5186`；Backend 地址：`http://127.0.0.1:8012`。
- 原图正例 run：`9d56b045-9502-482d-8304-181bf98b327b`。
- 页面上传真实模型 records 的 run：`48f368f1-e248-4051-aae6-669cd2e3486a`。
- 后一个 run 使用页面装载的 `graph_5585e1b142d94d4789dd34da8ed5cc11`；原图 run 使用 `graph_6f61bff6ff604a71b175d1e50499a627`。

先在 Evidence 页打开后一个 run，选 `region_2` 的详情：可以同时看到原图、对应 ROI、mask、heatmap、两个坐标平面的 bbox、面积占比、几何量及视觉模型描述。再点“根因与图谱”→“链路”→“命中条件”，查看条件与实际路径。

这份 records 来自已执行的原图 detector / VLM，不包含用于推理的原生缺陷答案；重复上传 records 不追加模型调用。原始图片入口仍可重新执行模型。

截图与完整运行结果在 Git 忽略的 `backend/runs/mvtec_m1_public/`：`region-ui.png`、`trace-ui.png`、`demo_run.json`、`live_upload_0.json`～`live_upload_2.json`。

## 新的一次分析怎么做

1. **素材与构图**：上传 TXT/Markdown 素材并运行现有 LLM source compiler。编译器继续生成 source units、knowledge cards、实体和关系，新增 `domain_profiles.json.visual_runtime` 可执行画像。结构条件失败时最多自动重抽一次；不可用项记录在 `issues`。
2. 选择构图结果，点击 **装载为 MVTec 工作图**。无需人工审核；装载会检查可执行条件和实体/源边引用，写入隔离 Neo4j 命名空间，并在 PG 登记画像。写入失败不会显示 ready。
3. **运行与证据**：选择 `mvtec`，在现有“推理配置”中选这张工作图。
   - **批量记录**：上传 JSON/JSONL/CSV records。新策略需要逐区域数据、内联 mask 或明确几何；只有缺陷名称不构成几何证据。
   - **图像**：对象填 `capsule`，模型选 `stfpm`，缺陷标签留空。需要视觉语义时勾选 ROI 识别；它会发送公开图片的上下文缩略图与裁剪，最多分析 3 个区域。
4. 保存后的候选、路径、区域绑定、完整输入和 trace 均从 PG 重载。再次分析创建新 run，不覆盖旧 run 的输入快照。

旧入口省略工作图/profile 时，继续使用原默认策略；不会自动改用新算法。内置 `mvtec_feature_graph_v1` 针对 legacy 图动态编译条件；`working:<graph_id>` 使用指定工作图及其保存的画像。

API 对应关系：

| 请求 | 用途 |
| --- | --- |
| `POST /api/kg/construction/builds/{build_id}/activate`，JSON `{"title":"Capsule"}` | 创建一张工作图；不会覆盖旧图 |
| `GET /api/kg/working-graphs` | 列出 ready 工作图 |
| `GET /api/kg/studio?graph_id=...` | 读取选中工作图 |
| `POST /api/runs/upload`，Form `mode=image/records`, `dataset=mvtec`, `graph_id=...` | 指定工作图分析；也可传 `reasoning_profile_id=working:...` |
| 同上，`semantic_mode=vlm` | 显式开启图像语义；默认关闭，detector 明确判正常时不调用 |
| `POST /api/analyze`，JSON 增加 `graph_id` | 对已有统一 Evidence 执行选定工作图 |

`graph_id` 与显式不兼容策略一起提交会报错，不忽略图谱选择。

## Evidence 不再靠自由文本自解释

外层统一 Evidence 入口保持兼容；新策略只执行 `visual_region.v1` 的闭合字段和注册算子，不执行任意 metadata 或 LLM 生成的代码。

本次原图的实际观测节选：

```json
{
  "obs_id": "obs:mvtec_capsule_test_unknown_input_0:region_2",
  "value_type": "visual_region.v1",
  "value": {
    "region_id": "region_2",
    "source": "detector_mask",
    "coordinate_space": "detector_grid",
    "image_shape": [256, 256],
    "bbox_xyxy": [214, 150, 225, 161],
    "original_image_shape": [1000, 1000],
    "image_bbox_xyxy": [835.9375, 585.9375, 878.90625, 628.90625],
    "area_ratio": 0.0015411376953125,
    "aspect_ratio": 1.0,
    "eccentricity": 0.2871433094539342,
    "morphology": "spot",
    "semantic_candidates": ["PokeDefect"],
    "semantic_source": "vlm:deepseek-flash",
    "semantic_status": "predicted"
  }
}
```

节选省略了其他可选字段；完整值以保存的运行 JSON 为准。面积、形态和位置来自检测网格，位置 `edge` 不是经过物体分割验证的物理边缘。原图 bbox 仅在预处理的 resize / center-crop / identity 变换明确时还原；不按尺寸猜测对应关系。

画像中的条件例如：

```json
{
  "feature": "region.morphology",
  "op": "in",
  "value": ["spot"],
  "concept_id": "SpotMorphology",
  "source_edge_id": "PokeDefect|HAS_MORPHOLOGY|SpotMorphology|mvtec",
  "required": true,
  "group": "geometry"
}
```

- 支持的特征是对象、区域面积/长宽比/离心率/连通域数、形态/位置及语义候选；算子为 `eq/in/gte/lte/intersects`。条件列表为 AND，集合内为 OR；数值区间用上下界条件表达。
- 每个区域单独执行画像，保留 `matched / not_matched / missing`、实际值、预期值和来源。已识别的语义与缺陷不符会排除该画像；语义未请求可保留几何候选，明确 uncertain 则保留证据不足。
- 同一 mask 的多个几何量只计一个支持组，语义另计一组；不是独立概率相乘。候选跨区域取最高区域分，保留所有支持区域/路径；同分不强行解释成可区分。
- 正常、无匹配、证据不足分别处理；对象没有可执行画像时返回 `not_applicable` 及原因。重复区域 ID 拒绝输入，不覆盖绑定。新策略的空结果不会回退到 generic path，未检查的一致性不显示 1.0。

本次可展示路径：

```text
region_2：实测 spot + VLM 的 PokeDefect 候选
  → SpotMorphology
  → SUPPORTS_DEFECT（PokeDefect HAS_MORPHOLOGY SpotMorphology 的诊断反向视图）
  → PokeDefect
  → HAS_PLAUSIBLE_CAUSE
  → MechanicalContact
```

反向视图保存 `origin_edge_id` 与原始关系，不改写物理因果方向。作用域 Object 关系用于限制适用性，不作为主要诊断特征路径。KG 来源文字留在 source edges / `knowledge_evidence`，不冒充现场 observation。

## 配置与恢复

在 `backend/` 按锁文件安装：

```bash
uv sync --frozen --extra dev --extra llm --extra ml
# 已有 PG 库只加新表：先查看 SQL，确认连接后再 --apply
uv run --frozen --extra dev --extra llm --extra ml python scripts/migrate_working_graphs.py
uv run --frozen --extra dev --extra llm --extra ml python scripts/migrate_working_graphs.py --apply
```

本机若已安装 ML extras，后续 `uv run` 需继续带所需 extras，避免同步时移除正在使用的可选依赖。新空库仍走 README 的初始化流程；已有库不要运行 `backend:init`。迁移仅新增 `working_graphs`；完整输入/绑定快照使用已有 `analysis_runs.parameters`。新 run 的快照优先，未带快照的旧 run 保持原文件恢复方式，旧入口不增加迁移前提。

构图使用既有 `OPENAI_*` / `DEEPSEEK_*` 和 `SOURCE_KG_LLM_API`。ROI 可单独配置 `KGTRACEVIS_VISION_MODEL / BASE_URL / API_KEY / API`，未指定时复用已配置的模型服务；模型必须支持图片。凭据仅放被忽略的 `backend/.env.local`。

STFPM 沿用现有 `mvtec-stfpm` 下载入口，权重目录为 `runs/real_model_pipeline/assets/mvtec/checkpoints/openvino_model/`。XML、BIN 和 `meta_data_stfpm_capsule.json` 必须配套；后端现在使用导出的 Normalize、Resize 与原始阈值，不再误套默认预处理。

本次独立库由以下命令恢复，保留其命名卷；**不要加 `down -v`**：

```bash
# RootLens 根目录
docker compose -p rootlens-mvtec-m1-test -f backend/compose.test.yaml up -d --wait
```

然后在本次演示进程中显式设置：PG `127.0.0.1:55433/rootlens_test`、Neo4j `bolt://127.0.0.1:57687`，凭据见仅限本机测试的 `compose.test.yaml`。后端使用 `ROOTLENS_API_PORT=8012 npm run dev:backend`；前端使用 `VITE_API_BASE_URL=http://127.0.0.1:8012 VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8012 npm run dev -- --host 127.0.0.1 --port 5186 --strictPort`。数据库变量必须传给后端进程，不覆盖用户原配置。

## 实际验收与尚未完成的部分

### 真实调用与输入结果

- 素材：`data/examples/materials/mvtec_capsule_diagnostic_notes.md`。其中制造机制明确是演示领域假设；素材库登记 ID 为 `mvtec_m1_capsule_notes_20261110`。
- LLM 构图：`sourcekg_5ce93ea85e5c`，31 个节点、62 条边、18 张卡；一次有界画像修复后有 3 份可执行画像。初始构图 4 次文本调用 / 32936 tokens，修复另 1 次 / 9654 tokens，分别保存在构图产物与 repair report。
- 最终原图正例的 ROI：2 次调用 / 2007 tokens。早期紧裁剪、上下文不足与一次格式错误的试运行被保留，未计入最终成功结果；本轮未训练或使用 GPU。

| 输入（原生类别仅供事后对照） | 实际结果 |
| --- | --- |
| `input_0.png`，原生 crack | detector 有两个区域；最终视觉模型排除背景细线，将胶囊下缘白色开口识别为 PokeDefect，图谱给出 MechanicalContact 候选。**没有识别成原生 crack 类别**。 |
| `input_1.png`，good | detector 判正常，0 区域，无候选，不调用 ROI 模型。 |
| `input_2.png`，scratch | 图像分数低于导出阈值，只有一个像素级区域；按图像判定返回无候选，属于本轮 detector 漏检，不调用 ROI 模型。 |

输入、许可与来源在 `runs/mvtec_m1_public/assets.json`；完整结果见 `live_acceptance.json`、`persistence_acceptance.json`。这三张图是闭环走查，不是类别准确率评测。

公开权重来源：[STFPM capsule 模型](https://huggingface.co/alexsu52/stfpm_mvtec_capsule)（模型卡 Apache-2.0）；图片来源：[capsule 数据镜像](https://huggingface.co/datasets/alexsu52/mvtec_capsule)，沿用 [MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) 的 CC-BY-NC-SA-4.0。只在被忽略的本机目录保留大文件，使用时遵守各自许可。

### 代码与页面检查

- 新区域/ROI/画像、source compiler、pipeline、registry、adapters、producers、PG 的定向检查通过；真实库测试覆盖同 ID 两张图、移除原因关系后候选变化、同 case 历史输入不串写、原 Evidence 文件不可用时从 PG 完整重载，以及失败装载不 ready。
- 前端：18 个文件 / 85 项测试通过；生产 build 通过，仍有既有大 chunk 警告。实际点击了装载工作图、选择工作图、上传 records、区域详情与链路条件；浏览器无 console error。
- 修改的 Python 文件 Ruff 通过。
- 最终完整后端：**329 passed / 7 failed / 1 skipped**，日志 `runs/mvtec-m1-full-final.log`。其中 6 项为本轮基线已有的缺失历史资产、固定 PatchCore 假设或 wafer user-study fixture；另 1 项是传入隔离 Neo4j 环境时，旧配置测试的 `env={}` 仍读系统环境。该测试单独清空 Neo4j 变量后通过。未将完整套件报告为全通过。

本轮测试库独立，旧运行库没有重建或导入；只有新空测试库初始化过种子。演示数据及开发服务不是开机自启配置。

### 后续增量已完成

本文件保留 M1 的首轮资产、数值与负结果。M2–M6 的素材解析、持久编辑/完整交换、bottle/PatchCore、WM811K、TEP 和完整回放已完成，见 [三场景使用与验收](progressive-demo-2026-11-10.md)。正式审核/发布和置信校准仍后置。
