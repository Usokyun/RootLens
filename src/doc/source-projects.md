# 源项目路径与资产索引

这份文档是给后续 LLM/Agent 使用的长期上下文入口，目标是避免每次都重新扫描两个上游项目。

> **当前边界说明（2026-05-17）**
>
> 当前 RootLens 前端以 `src/doc/backend-integration-current.md` 为真值：真实建图、Evidence 处理与 RCA 推理由后端仓库承接；RootLens 仅保留 backend-first 工作台、内置 Demo 与成品回放导入。
> `module-1/2/3` 等文档可继续作为历史背景资料阅读，但不再代表当前前端实现边界。

---

## 1. 主要路径

### 1.1 当前整合前端仓库（RootLens）

- 项目路径：`/Users/bytedance/my_project/RootLens`
- 用途：Vue 3 交互式可视分析原型、新前端壳、文档沉淀层

### 1.2 TEP_KG

- 项目路径：`/Users/bytedance/my_project/TEP_KG`
- 用途：工业流程时序根因推理、知识图谱构建、评估与交付

### 1.3 MVTec 容器目录

- 容器路径：`/Users/bytedance/my_project/MVTec`
- 说明：真正需要使用的项目根在其子目录 `KGTraceVis/`

### 1.4 MVTec / KGTraceVis 实际项目根

- 项目路径：`/Users/bytedance/my_project/MVTec/KGTraceVis`
- 用途：多源 evidence schema、pipeline、FastAPI 服务、React Web 原型、paper 资产

---

## 2. 推荐阅读顺序

如果后续 LLM 需要理解整体项目，请按这个顺序读取：

1. RootLens：`src/doc/backend-integration-current.md`
2. RootLens：`src/doc/source-projects.md`
3. `TEP_KG/docs/Root-KGD.md`
4. `TEP_KG/docs/kg-build-status.md`
5. `MVTec/KGTraceVis/README.md`
6. `MVTec/KGTraceVis/docs/project_design.md`
7. `MVTec/KGTraceVis/docs/evidence_schema.md`
8. 需要理解历史设计背景时，再读 RootLens：
   - `src/doc/module-1-graph-construction.md`
   - `src/doc/module-2-unified-evidence.md`
   - `src/doc/module-3-rca-engine.md`
   - `src/doc/frontend_handoff.md`
   - 其他 roadmap / acceptance 文档
9. 再进入对应 `src/` 和 `scripts/`

原则：

- 先看设计文档和 schema。
- 再看主代码目录。
- `outputs/`、`runs/`、`data/external/` 只做索引，不先当事实文档。

---

## 3. TEP_KG 资产说明

### 3.1 关键目录

| 路径 | 用途 |
| --- | --- |
| `/Users/bytedance/my_project/TEP_KG/src/tep_kg` | Root-KGD、RBC、传播、图构建、评估主代码 |
| `/Users/bytedance/my_project/TEP_KG/scripts` | KG/build/features/evaluation/delivery/RCA 等批处理入口 |
| `/Users/bytedance/my_project/TEP_KG/docs` | 论文学习笔记、构建状态、基线环境、数据结构等说明 |
| `/Users/bytedance/my_project/TEP_KG/ontology` | TEP ontology 与知识图谱 schema 资产 |
| `/Users/bytedance/my_project/TEP_KG/data/processed/rca` | 最终 RCA Graph 的节点与边，是 Root-KGD 和前端可视化应优先使用的图层 |
| `/Users/bytedance/my_project/TEP_KG/outputs` | RCA、边权训练、评估、delivery 等结果目录 |
| `/Users/bytedance/my_project/TEP_KG/data` | raw / processed / interim / datasets 分层 |

### 3.2 重点文件

| 路径 | 说明 |
| --- | --- |
| `/Users/bytedance/my_project/TEP_KG/docs/Root-KGD.md` | Root-KGD 方法总结，适合快速理解 TEP 根因推理主线 |
| `/Users/bytedance/my_project/TEP_KG/pyproject.toml` | 环境与依赖分层，说明 base/ml/dev 的职责 |
| `/Users/bytedance/my_project/TEP_KG/data/processed/rca/nodes.jsonl` | 最终 RCA Graph 节点 |
| `/Users/bytedance/my_project/TEP_KG/data/processed/rca/edges.jsonl` | 最终 RCA Graph 边 |
| `/Users/bytedance/my_project/TEP_KG/outputs/rca/graph_report.json` | RCA Graph 规模、关系分布、角色统计与图质量摘要 |
| `/Users/bytedance/my_project/TEP_KG/src/tep_kg/root_kgd.py` | 根因排序核心逻辑候选入口 |
| `/Users/bytedance/my_project/TEP_KG/src/tep_kg/rbc.py` | 变量贡献提取相关逻辑候选入口 |
| `/Users/bytedance/my_project/TEP_KG/src/tep_kg/graph_build.py` | 图谱构建相关逻辑候选入口 |

### 3.3 适合复用到新系统的部分

- 最终 RCA Graph（作为图谱组装层 L3 的核心输入之一）
- 根因候选节点和传播路径
- TEP ontology / graph build 资产（12 种实体类型 + 20 种关系白名单，用于 L3 本体校验）
- Code 模态提取器中的解析逻辑：`parse_matlab`、`parse_c_like`、`parse_mdl`
- 评估指标和对比实验输出
- TEP 52 通道变量映射（`tep_variables.py`），用于统一 Evidence 中 `variable_name` 的图谱实体对齐

---

## 4. MVTec / KGTraceVis 资产说明

### 4.1 关键目录

| 路径 | 用途 |
| --- | --- |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/src/kgtracevis` | schema、adapters、core、service、viz、feedback 等核心代码 |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/web/src` | React 前端工作台原型 |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/docs` | 设计文档、实验协议、evidence schema、meeting notes |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/configs` | experiment、kg、neo4j、paths 等配置 |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/scripts` | build kg / run service / run experiment / generate evidence |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/paper` | 论文 TeX、sections、figures、tables |

### 4.2 重点文件

| 路径 | 说明 |
| --- | --- |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/README.md` | 项目定位、目录、运行方式和数据布局 |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/docs/project_design.md` | 核心库、scripts 和 app/client 的职责边界 |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/docs/evidence_schema.md` | 多源 evidence 的统一结构说明 |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/web/src/App.tsx` | 现有工作台顶层页面结构 |
| `/Users/bytedance/my_project/MVTec/KGTraceVis/src/kgtracevis/service` | 服务层入口与 API 相关实现目录 |

### 4.3 适合复用到新系统的部分

- evidence schema（作为统一 Evidence JSON 的设计基础）
- adapters / producers（作为 Image、Sequence 模态提取器的核心逻辑）
- path ranking / correction / feedback 相关流程（作为 RCA 引擎中路径排序的参考实现）
- service API 设计思路
- 现有工作台的信息结构与交互分区
- paper 资产组织方式

---

## 5. 融合映射建议

| 新系统目标层 | 优先复用来源 | 文档 |
|---|---|---|
| Source Registry | 两边的 `docs/` + RootLens `src/doc/` | `source-projects.md` |
| 图谱构建（L1-L4） | TEP_KG `parsing.py` + `ontology.py` + `graph_build.py`；MVTec adapters | `module-1-graph-construction.md` |
| 统一 Evidence | MVTec `evidence_schema.py` + adapters；TEP_KG `rbc.py` + `tep_variables.py` | `module-2-unified-evidence.md` |
| 路线 1：多模态线索组织 | MVTec `pipeline.py` / `entity_linker.py` / path ranking | `module-3-rca-engine.md` §3 |
| 路线 2：过程故障分析 | TEP_KG `root_kgd.py` / `rbc.py` / RFPA propagation | `module-3-rca-engine.md` §4 |
| RootLens 可视化工作台 | 当前仓库 `src/views/` + MVTec `web/src`（借结构，不借 React 实现） | `backend-integration-current.md` |
| Paper Runtime | MVTec `paper/` + TEP_KG `docs/` | `backend-integration-current.md` + 上游 docs |

---

## 6. 给未来 LLM 的操作规则

1. 不要把 `outputs/`、`runs/`、`data/external/` 直接当作项目事实源。
2. 先读 `docs/`、`README.md`、`project_design.md`、`backend-integration-current.md`。
3. 需要改接口时，先对齐 `schema`、`core`、`service`，不要直接从页面实现倒推。
4. MVTec 的外层路径不是实际项目根，真正工作路径是：
   `'/Users/bytedance/my_project/MVTec/KGTraceVis'`
5. RootLens 只是一层新的整合前端，不替代两个上游仓库的研究资产。
