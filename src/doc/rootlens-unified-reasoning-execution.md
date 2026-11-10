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
| U1 公共内核＋MVTec | 进行中：内核及服务合同完成，真实视觉验收待完成 | 公共图编译／有限证明、grounding、候选、完整期待、固定分母评分与证明 DAG 已运行；v2 工作图／API／现有结果兼容已接线，真实模型与屏幕验收随后执行 | U1a `2081464`；U1b 服务接线提交 |
| U2 LLM 构图与工作图 | 待开始 | 原始公开资料＋能力清单生成公共知识；有界修复；持久编辑、完整交换、图修改影响新推理 | 待完成 |
| U3 TEP 同核 | 待开始 | 正常参考、窗口、完整统计接入同一内核；不调用 TEP 特设排名；真实数据／反证检验 | 待完成 |
| U4 Wafer 同核 | 待开始 | 空间统计和区域定义接入冻结内核，验证输入编码、scope、正常及冲突 | 待完成 |
| U5 评价与交付 | 待开始 | 相同输入／知识的对照、消融、缺失／重复／删边／重命名检验；完整测试、实际界面、回放和复现说明 | 待完成 |

## 已知基线与验证路径

先前基线：后端 345 passed / 7 failed / 1 skipped，前端 19 文件 / 89 项及 build 通过；详见 [前期验收](/Users/hhm/code/RootLens/backend/docs/progressive-demo-2026-11-10.md)。它是历史证据，不当成本轮测试结果。

后端使用 `backend/` 的 uv 环境；新检查先使用离线 `uv run --no-sync`，需新增依赖时按锁文件更新。真实库验证只用明确指定的隔离测试库。运行及实验输出进入被忽略的 `backend/runs/unified_reasoning/`，小型公共种子与测试入库。

Bits 测试工具的 bootstrap 会向第三方发送本机身份元数据并尝试安装全局工具，不是实现本项目所需操作；不执行该上传／全局安装，使用项目既有 pytest／Vitest 完成测试。项目凭据只通过现有配置读取路径供模型客户端使用，不输出到日志或提交。

## 当前下一步

以原始公开资料和 adapter 能力清单制作实际 v2 知识包，完成真实 MVTec／正常例、持久库和界面验收，然后接入过程与空间观测。任何阶段的运行、实验及失败证据随实际产物追加，不以完成任务表替代真实验收。

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
