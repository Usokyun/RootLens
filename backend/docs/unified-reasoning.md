# 统一工业推理 v2：运行、构图与展示

2026-11-11。U0–U5 已实现：三个 adapter 进入同一类型契约、同一候选展开／条件执行／代价计算内核。不同场景变的是测量能力和知识，不是最终评分算法。

## 先运行真实测量 JSON，不需要数据库或模型调用

从仓库根目录进入 `backend/`，使用项目 uv 环境：

```bash
cd backend
uv run --no-sync python scripts/run_unified_reasoning.py \
  --knowledge data/kg/unified/bottle-working-graph.v2.json \
  --evidence data/examples/unified/mvtec-chipped.json \
  --evidence data/examples/unified/mvtec-normal.json \
  --evidence data/examples/unified/mvtec-insufficient.json \
  --output-dir runs/my-bottle-check
```

输出包含 canonical knowledge、实际图投影、逐问题 Evidence、结果和 manifest；输出目录必须是新的，避免覆盖历史结果。三份输入分别得到 4 个并列候选、无匹配、证据不足。它们来自实际公开图像的模型输出，不是设计样例。

TEP／Wafer 的可运行组合：

| 知识包 | Evidence JSON | 实际结果 |
| --- | --- | --- |
| `data/kg/unified/tep-working-graph.v2.json` | `data/examples/unified/tep-cooling-window.json` | 3 个候选，当前首位是错误的 reaction-kinetics 族 |
| `data/kg/unified/wafer-working-graph.v2.json` | `data/examples/unified/wafer-nearfull.json` | Near-full，score = −0.875 |

替换上述 CLI 的 `--knowledge` 和 `--evidence` 即可。CLI 同时接受独立 `knowledge-package.json` 和完整 v2 工作图包；旧的独立知识入口仍可用。

这些小型 JSON 随仓库提供。原始图片、数组、正常参考和权重不随 Git 提供，Frame 中保留原始资产 URI；**执行已冻结的标量比较不读取这些外部文件**。从原始数据重新计算时需要取回相应资产。样例清单与原始 run ID 在 `data/examples/unified/manifest.json`；它们用于理解输出，完整评价没有只选这几个样例。

## 从 backbone 到候选，实际执行了什么

```text
原始图片 / 数值窗口 / wafer cells
  → producer：定位、独立分类、几何或数值统计
  → 注册 adapter：EvidenceFrame（主体、feature、值、scope、procedure、reference）
  → grounding：明确 ID/别名/值映射，类型与参考检查，计算原子条件
  → knowledge：适用候选 → 可达机制 → 全部期待 → AND/OR/at_least 分支
  → 联合 scope 检查、完整支持／冲突／缺失、固定分母代价比较
  → 排名 + 联合证明 DAG + 使用的 observation 和原始图边
```

- **MVTec**：PatchCore 定位 → 连通 ROI 和检测网格／原图坐标 → 几何和可选 ROI VLM 候选。VLM 只接收有来源的外观词汇，不接收原因候选。每个 ROI 独立问题；开放候选集中没提到一个外观，不构成该外观的阴性。
- **TEP**：配套正常 scaler/PCA → 一基、闭区间窗口 → 全 52 通道 mean-z、population std-z、OLS slope、归一化平方残差贡献与序列引用。一个 Frame 有 53 主体、263 观测；当前图只引用其中 6 个原子条件，其余明确列为 unused。没有调用旧 Root-KGD 排名。
- **Wafer**：固定 0背景／1正常／2失效 → 有效 die 分母、中心／中圈／边缘密度、八连通簇和线性程度 → 独立 ResNet 图案观测。空区域为 missing；不读取原生图案标签形成预测。任务为 `pattern_family`，不是从图案直接宣布制造原因。

`EvidenceFrame` 使用闭合的 Pydantic 判别联合，禁止额外字段。非有限数字、布尔冒充数值、错单位、错参考、悬空引用和跨 scope 联合均不能悄悄执行。旧 Evidence 外壳继续兼容；只有注册的闭合 measurements 进入 v2，不让任意 metadata 自解释。

### 候选和分数

候选取自图的 `hypotheses`，按对象类别、`target_role` 和可测 footprint 召回；明确阴性也参与召回和排除。所有期待都检查，不只挑一条有利路径。

对同一问题固定候选原子并集 Q、有效真／假事实 O、满足事实 O⁺。每个依赖组等预算，重复来源不增加票数：

```text
U = 各组“未被完整联合证明解释的 O⁺ 比例”的均值
C = 各组“与候选 expected / necessary 期待冲突的 O 比例”的均值
A = 当前根假设的显式成本（默认 1；由图推出的机制不额外算假设）
J = U + 2 C + 0.25 A
score = -J；confidence = null
```

至少一个联合表现完整成立，且没有必要条件冲突／缺失，才进入支持排名。部分匹配、无支持和未评估项仍返回；同分不截断。每条图中展示路径都引用 `required_joint_fact_ids`：一条路径仅是联合证明的一部分。分数仅在同一问题内比较，不跨 ROI／窗口平均。

源码入口：`schema/unified_evidence.py`、`schema/unified_knowledge.py`、`core/unified_grounding.py`、`core/unified_reasoner.py`、`kg/unified_compiler.py`。当前 v0 是有界单根假设搜索，执行离散标量／集合比较和 scope join；interval／array 引用可归档，动态时间先后、多原因组合和数值距离损失尚未执行。

## LLM 制作的是可执行知识，不是最终答案

原始素材解析复用现有 TXT/Markdown、HTML、CSV/JSON 和文本 PDF parser。输入是定位片段 + producer 能力清单，不发送测试特征／答案：

1. LLM 生成小型 `KnowledgeBlueprint`：观测签名、诊断条件、竞争假设、机制、来源断言和缺失能力。
2. 确定性编译器生成规范 ID、绑定、强制异常门控、共享机制、期待边和完整公共 IR；相同原子复用。
3. 检查注册特征／算子、单位、scope、引用、来源、候选规模和有限证明。失败最多有界修复，不执行 LLM 生成的代码。
4. 自动生成可装载的 `working-graph.v2.json`，没有人工审核前提。数值阈值若不是资料值，明确记为 `declared_demo_heuristic`。

实际来源和制作：

| 场景 | 原始资料 | 最终执行知识 |
| --- | --- | --- |
| bottle | [Emhart 2024 原始缺陷指南](https://www.emhartglass.com/sites/default/files/publications/2024-07/BEG_BR0060RevA-Defect_Guide-WEB.pdf)，PDF 13／20 页，2 片段／3008 字符 | 2 签名、5 假设、4 原子；没有来源支持的 break-size 阈值，几何保留但不虚构区分力 |
| TEP | [原始过程程序与控制示例](https://github.com/camaramm/tennessee-eastman-profBraatz)，3 片段／22709 字符 | 4 签名、5 假设、6 原子；使用真实通道 ID、正常参考与替代表现 |
| Wafer | [原始论文](https://ieeexplore.ieee.org/document/6932449/) 第 3–4 页可取正文与 [模型作者卡](https://huggingface.co/radai-agent/radai-wm811k-defect-detection)，3 片段／14348 字符 | 8 签名、8 图案假设、20 原子；阈值是声明的启发式，不是复现论文阈值 |

Wafer 原论文镜像本机 TLS 下载失败；保存的是 web PDF 提取的定位正文，不是本地完整图表解析。TEP 控制示例没有被证明与每条公开数据序列的生成控制配置完全相同。

构图 CLI（会调用已配置的文本模型）：

```bash
uv run --no-sync python scripts/build_unified_knowledge.py \
  --source path/to/source-units.json --capability visual-region-v2 \
  --scenario mvtec --title 'Source-grounded bottle knowledge' \
  --output-dir runs/my-source-build
```

能力 ID 另有 `process-window-v2`、`spatial-grid-v2`。也可传原始素材文件或重复 `--source`；传 `--blueprint path/to/authoring-blueprint.json` 可零模型调用重编译。默认视觉能力清单针对 bottle；新对象通过 `visual_capabilities(objects=...)` 声明，不能拿 bottle 模型冒用新对象。

本机原始片段在 `runs/unified_reasoning/public/{bottle,tep,wafer}-source-units.json`；最终 LLM 原文／蓝图／编译报告保留在 `u2_bottle_compact`／`u2_bottle_final`、`u3_tep_knowledge_alternatives`、`u4_wafer_single_target`。直接生成完整 IR、过细候选、错误 AND 和对称分类等失败也保留；U5 没再调图或调用模型来改善评价数字。

## 在现有三页使用 v2

1. **素材与构图**：勾选资料后点“生成知识图谱”，确认场景和名称。完成后“打开图谱”使用本次返回的图 ID。
2. **根因与图谱**：导入种子／新包、编辑完整 canonical `knowledge`、保存并投入使用。绑定、条件和规则一起保存，派生图不是第二份知识。历史 run 保留当时的图和结果。
3. **运行与证据**：“新建分析”选择已启用图和解释器，提交原始输入或原生 Frame。打开保存详情查看同一 Frame 的候选、实测值、联合条件或传播依据和源边；浏览器不重新判断。

离线研究仍可使用 v1 包和旧策略。下面是直接计算 v2 Frame、不保存 Run 的研究接口：

```bash
curl -sS -H 'Content-Type: application/json' \
  --data-binary @data/kg/unified/bottle-working-graph.v2.json \
  http://127.0.0.1:8012/api/kg/working-graphs/import
# 使用返回 graph_id；该入口计算结果，不新建持久 Run
curl -sS -H 'Content-Type: application/json' \
  --data-binary @data/examples/unified/mvtec-chipped.json \
  'http://127.0.0.1:8012/api/reasoning/<graph_id>/analyze?top_k=5'
```

持久分析使用 `POST /api/tasks/inference`（multipart，`input_mode=evidence` 可直接接收原生 Frame），由 `GET /api/analyses/{run_id}` 读取。已导入的图须先投入使用；完整包可经 `GET/PUT /api/kg/working-graphs/{graph_id}/package` 交换。旧 Run 上传端点已退役。

### 本机演示与恢复

当前演示前端 `http://127.0.0.1:5186`、API `http://127.0.0.1:8012` 使用独立 Compose 项目 `rootlens-mvtec-m1-test`：PG 55433、Neo4j bolt 57687；原本机库／来源备份保持。恢复命令和测试专用连接配置见 [M1 配置与恢复](mvtec-m1-demo.md#配置与恢复)，已有服务不要重复启动，不执行 `backend:init` 或删除卷。

完整回放：`runs/unified_reasoning/u5_replay/all-scenes-session.json`。包含 3 个原始 Run、3 张知识快照、22 个 case 与内嵌预览。运行页“导入回放”打开该成品，不请求后端重新测量或推理。D3 使用项目锁定依赖。

建议依次展示：bottle 的 4 条并列原因；TEP 的正常／异常窗口、完整 52 通道及错误首位对应的条件；Wafer 的实际网格、空间统计和分类一致／不一致。支持和失败都能从同一“推理依据”检查。

## 评价与已知限制

完整 [U5 评价与验收](unified-reasoning-u5.md) 和 [32 份结果摘要](unified-reasoning-u5-results.json) 随仓库保存。当前最明确的结论：统一执行管线和可追溯交换已经成立；来源知识的辨识力与感知失败仍决定实际效果。TEP 首位错误、视觉语义失败和 Wafer 未匹配项不能由“同一个内核”自动修复。
