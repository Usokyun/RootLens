# 统一推理重构执行记录

## 目标与授权

落实 [统一方法与可复算规格](/Users/hhm/code/RootLens/src/doc/rootlens-unified-reasoning-method-plan-2026-11-10.md) 的 U0–U5。用户已授权设置持续 goal、新建分支、纳入现有未提交内容、分阶段 commit，以及必要下载、模型执行和实验。只在新分支本地提交；没有另行发布／推送要求。

- 分支：`codex/unified-industrial-reasoning`。
- 基线提交：`5777705`，完整保存先前渐进重构、前端改动和统一方法设计样例。
- 公共内核不得按 dataset 选择评分公式；不同场景只变观测适配、注册能力和知识。
- 前端保持三页，旧 Evidence／策略保持原合同；不覆盖既有数据库，不终止用户正在使用的服务。

## 阶段与完成证据

| 阶段 | 状态 | 交付与验收 | 提交 |
| --- | --- | --- | --- |
| 现有成果基线 | 完成 | 106 个现有修改／新增文件纳入新分支；公开模板核对，未纳入真实配置、权重和运行数据 | `5777705` |
| U0 契约 | 完成 | Evidence v2、公共知识 IR、类型／单位／引用／区域／正常参考校验；三个设计样例可实际解析、往返及生成 JSON Schema；初始 37 项合同测试通过 | `09322ec` |
| U1 公共内核＋MVTec | 后端和真实模型闭环完成；实际页面验收随 U5 | 公开原图→PatchCore→ROI→公共内核→PG 运行快照，正例保留歧义、正常例无候选；视觉失败如实保留 | U1a `2081464`；U1b `950386a`；真实验收随 U2 |
| U2 LLM 构图与工作图 | 视觉能力目标完成；过程／空间能力随 U3、U4 | 原始厂家 PDF→LLM 领域蓝图→确定性编译→可加载知识；有界修复；持久编辑、完整交换、改图影响新推理；素材页仅加契约选择 | U2 提交 |
| U3 TEP 同核 | 待开始 | 正常参考、窗口、完整统计接入同一内核；不调用 TEP 特设排名；真实数据／反证检验 | 待完成 |
| U4 Wafer 同核 | 待开始 | 空间统计和区域定义接入冻结内核，验证输入编码、scope、正常及冲突 | 待完成 |
| U5 评价与交付 | 待开始 | 相同输入／知识的对照、消融、缺失／重复／删边／重命名检验；完整测试、实际界面、回放和复现说明 | 待完成 |

## 已知基线与验证路径

先前基线：后端 345 passed / 7 failed / 1 skipped，前端 19 文件 / 89 项及 build 通过；详见 [前期验收](/Users/hhm/code/RootLens/backend/docs/progressive-demo-2026-11-10.md)。它是历史证据，不当成本轮测试结果。

后端使用 `backend/` 的 uv 环境；新检查先使用离线 `uv run --no-sync`，需新增依赖时按锁文件更新。真实库验证只用明确指定的隔离测试库。运行及实验输出进入被忽略的 `backend/runs/unified_reasoning/`，小型公共种子与测试入库。

Bits 测试工具的 bootstrap 会向第三方发送本机身份元数据并尝试安装全局工具，不是实现本项目所需操作；不执行该上传／全局安装，使用项目既有 pytest／Vitest 完成测试。项目凭据只通过现有配置读取路径供模型客户端使用，不输出到日志或提交。

## 当前下一步

接入完整过程观测与公共知识，然后冻结内核接入空间观测；最后完成同输入对照、页面／回放和总验收。任何阶段的运行、实验及失败证据随实际产物追加，不以完成任务表替代真实验收。

## U1a：公共内核的实际证据

- 入口：`kgtracevis.core.unified_reasoner.UnifiedReasoner`；CLI 为 `/Users/hhm/code/RootLens/backend/scripts/run_unified_reasoning.py`。新模块未修改旧 pipeline 入口。
- 同一内核实际计算三份设计输入：MVTec 接触／磨损 J=0.25 并列、附着 J=1.916667 无支持；TEP 冷却 J=0.25、进料 J=1.916667；Wafer edge-ring J=0.25、nearfull J=1.916667。
- 实际运行输出：`/Users/hhm/code/RootLens/backend/runs/unified_reasoning/u1_core/manifest.json`，包含输入、知识、图视图与每个完整结果。仍是合成合同算例，不是 backbone／真实数据效果。
- 新合同＋内核测试 **63 passed**，新增／修改的统一推理文件 Ruff 通过。覆盖开放候选集、缺测与阴性、单位／正常参考错配、跨 ROI、重复／重排、完整反证、删边／改值／改别名、身份重命名、AND/OR/at_least、循环自支持、同分保留、搜索预算及 CLI 不覆盖旧输出。
- 当前一个 v2 Frame 表达一个聚焦问题；多个 ROI 由适配层生成多个 Frame，不将不同区域特征拼接。TEP 的一个 Frame 可联合多个主体变量，空间 Frame 可联合多个环带。

## U1b：工作图与现有产品合同

- 新 `rootlens-working-graph.v2` 保存完整 canonical knowledge。复用既有 PG 工作图登记、图锁、Neo4j 单事务投影、保存前备份和失败恢复；v1 包及旧策略保留。加载时拒绝与 canonical knowledge 不一致的投影。
- 原生 v2 入口 `POST /api/reasoning/{graph_id}/analyze`；现有原图／records 入口选择 v2 工作图时使用相同公共内核。图像 adapter 按 ROI 分 query，保留检测、几何和语义来源，不执行原生标签／任意 metadata，也不由标签缺席制造 foreign-material 阴性。
- 现有结果桥接使用真实 Neo4j 边 ID，保留 v2 源边、联合证明与完整 frames/results。独立 ROI 不进行隐蔽的跨 scope 分数混合。回放由保存的 canonical snapshot 重建显示投影，不读取当前图。
- 前端保持三页与现有 JSON 抽屉，选择 v2 图显示公共策略。v2 规则通过完整 JSON 修改，派生边不允许单独改写。服务支持删除整条 effect/expectation，影响后续分析；别名、绑定和条件均可往返持久保存。
- 合同／内核／服务接线／旧工作图／原 run payload 检查 **73 passed / 2 skipped**（真实 DB opt-in 尚未执行）；前端 **19 文件 / 89 项通过**、生产 build 通过。真实图像、实际 DB 重启和屏幕验收仍待执行，不能据此称 U1 全部完成。

## U2：原始资料构图与真实 MVTec

- 原始资料为 [Bucher Emhart Glass 2024 缺陷指南](https://www.emhartglass.com/sites/default/files/publications/2024-07/BEG_BR0060RevA-Defect_Guide-WEB.pdf) PDF 第 13／20 页，经现有 Docling parser 实际取得 **2 个定位片段、3008 字符**。未给构图模型任何测试图、测试值或原生标签。
- 直接生成完整 IR 的两轮实验均暴露方向／类型／悬空引用问题。改用小型 `KnowledgeBlueprint`：LLM 提领域签名和候选，编译器生成 ID、作用域、强制门控、共享机制、来源与边。同条件复用同一原子，显示文本改写不制造新候选。每次最多一次修复，失败原文保留。
- 最终蓝图有 **2 个观测签名、5 类竞争原因、4 个原子条件**，未臆造 source 未给的 break-size 阈值。48 节点／67 边公共种子（含显式 legacy 值别名）位于 `backend/data/kg/unified/bottle-working-graph.v2.json`。来源断言、执行知识、别名、绑定、完整 JSON 导入导出均可编辑保存。
- 素材／compiler API 可显式选 `target_contract=unified-v2`、`capability_id=visual-region-v2`，装载时显式使用相同契约；默认 legacy 入口不增加新前提。CLI 支持原始素材或既有片段，也可零模型调用重编译已保存蓝图。
- 真正 PG／Neo4j 测试已执行：此前整合 **14 passed**，另新增 v2 独立连接重载／删规则／重新导入／旧快照测试 **1 passed**。沙箱内 URL 测试的 bind 限制已通过授权复核，**1 passed**，不是代码失败。
- 实际模型：相同公开 bottle PatchCore、正常参考和配置的 ROI VLM；冻结知识分析 4 张异常测试图＋1 张正常图。2 张额外固定编号图返回 **4 个 rank=1、score=-0.25 的并列候选、12 条实际规则路径**；1 张异常被 VLM 判正常，另 1 张语义 uncertain，均无强配候选；正常图无候选。这是功能／失败走查，不是准确率评测。
- 初始图的 ROI 词汇只有空泛描述，现改为仅从图的观测断言提供有来源的外观释义，不向 VLM 发送原因候选。对首张失败图仅重做一次语义仍 uncertain，失败保留；未覆盖或改写成正例。
- 本轮实际产物目录 `backend/runs/unified_reasoning/u1_mvtec_actual/`：正例 run `3e83390c-8360-4f1e-a73e-ccb521e96d21`、`6136854b-0913-4f87-8917-703717d7db6f`；正常 run `038a083f-af8a-4b44-a81e-05e7a9a9fde0`。API 重启后继续使用同一库，原 run 与图保留。页面／回放最终验收仍待 U5。
- 构图失败记录、17 候选的过细蓝图、最终原始蓝图及公开 PDF 均保留在 `backend/runs/unified_reasoning/u2_bottle_*` 和 `public/`。最终包从实际模型原文重编译，未手填工业因果图；另声明的 legacy 符号映射是工程兼容绑定，trace 保留实际旧值与使用的绑定 ID。
