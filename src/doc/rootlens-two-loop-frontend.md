# 双闭环前端：交互与实际走查

2026-11-11。前端工作台以真实后端任务为主线，三个一级页面重新组织为：

1. **素材管理 `/materials`**：知识资料导入、真实解析、定位原文、多选资料与 LLM 制作任务。
2. **知识图谱 `/graphs`**：语义关系图、对象/候选/机制/联合现象/观测条件、持久表单修改与明确投入使用。
3. **推理分析 `/evidence`**：原始样本或 Evidence 输入、已启用工作图与两种推理器、真实进度、保存结果与观测—路径联动。

默认只消费 API；取消旧 Demo/Backend 开关、前端推理及虚假回退。成套示例通过后端的公开资产目录载入**输入**，点击开始分析后才产生新任务。已保存分析明确作为历史结果打开。

## 启动与接口

当前验收前端：<http://127.0.0.1:5186>，API：<http://127.0.0.1:8012>。前端已接管原有 Vite，未按端口关闭其他进程。

```sh
VITE_API_BASE_URL=http://127.0.0.1:8012 \
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8012 \
npm run dev -- --host 127.0.0.1 --port 5186 --strictPort
```

任务、启用、保存分析和演示资料接口见 [双闭环后端契约](rootlens-two-loop-backend-contract.md)。前端的 `src/api/workbench.ts` 直接消费它；不临时拼装新的诊断结果。

## 可操作主路径

### A：资料到可用知识

- “导入知识资料”支持文件与 URL；“公开资料”入口只真实登记并解析资料，不偷偷导入图包。
- 资料可多选；原文按解析片段查看。制作弹窗明确场景、名称、来源、最多两次模型调用（含一次自动修复）；高级设置可关闭修复。
- 制作阶段和错误来自后端 Task。LLM 阶段只显示等待，不伪造百分比；失败保留记录，明确点击才能重试。
- 完成后“查看并修改图谱”。语义视图默认不显示 SourceAssertion/reified rule 技术节点。
- 表单可改名称/实体别名、条件特征/阈值/主体/区域、嵌套 AND/OR/至少N项组合、影响和预期关系、主体与词汇绑定。
- “保存修改并生效”后才能“投入使用”；启用后“使用此图分析”承接当前工作图。
- “导入已准备图谱”是明确跳过制作的独立入口，始终导入为新副本，初始未启用。

### B：样本到可追溯解释

- 明确区分“从原始样本开始”和“从 Evidence 开始”，并选择场景。
- TEP 原生 DAT/CSV 必须提供配套正常参考与一基闭区间窗口；MVTec 显式 ROI 外观模型选项；Wafer 保留原生 0/1/2 编码。
- 只允许选择当前场景已启用的 v2 图谱。统一约束推理支持三场景；RootKGD 在非 TEP 场景禁用。
- 结果先展示实际图像/区域、窗口/变量或网格与观测，再比较候选、支持/冲突/缺测和实际路径。分数不作为置信率，也不跨引擎合并。
- 路径是联合证明的一部分，条件、实际值、来源断言和技术引用分别呈现；完整 JSON/ID/DAG 后置。
- “下载本次 Evidence”是结果主操作。上传同一 Frame、选择同一图/推理器/保留候选数，可复算；历史分析仍保留原知识快照。

## 独立浏览器与当前走查证据

共享 Playwright MCP profile 报占用，未删除锁、未关闭现有浏览器。使用已安装的 Playwright 与 Chrome 启动全新 browser/context：

```js
import { chromium } from '/Users/hhm/.npm/_npx/9833c18b2d85bc59/node_modules/playwright/index.mjs'
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true,
})
const context = await browser.newContext({ viewport: { width: 1512, height: 982 } })
const page = await context.newPage()
```

本轮临时自动化入口：`/private/tmp/rootlens-frontend-inspect.mjs`（三页只读截图）、`/private/tmp/rootlens-frontend-flow.mjs`（实际图谱副本编辑/启用、Evidence运行/下载、打开历史TEP结果）。脚本各自建立隔离 browser/context，不清用户 storage。

2026-11-11 02:33 的真实 UI 走查：

- 导入本轮 LLM 图为验收副本 `graph_a6f465b4da3a4dabafd61ea6c708ebaa`，保存“前端实屏验收别名”，投入使用并跳转分析。
- 上传本轮实际玻璃样本生成的 Frame，任务 `task_b37d3aa08c7e4e59be20b1e3b5645e38` 完成；显示 7 个首位并列及另一个获支持但未在 top-k 列名次的候选。
- 实际点击观测、第二候选与路径，下载后端 Evidence；打开保存的真实 TEP RootKGD 运行 `6fc02e0e-9455-4412-b4c3-1f6d4605db17`。
- 页面和控制台未出现 JS 错误。实屏发现的 TEP 统计缺显、初始焦点、MVTec 新语义词显示已修正，继续做针对性走查。

截图位于 Git 忽略目录 `/Users/hhm/code/RootLens/.playwright-mcp/two-loop/`：

- `01-materials-first.png`、`02-graphs-first.png`、`03-analysis-first.png`：第一轮布局（随后已提高字号与对比度）。
- `04-graph-edited-enabled.png`：真实修改并启用。
- `05-bottle-evidence-result.png`、`06-bottle-linked-proof.png`：真实 Frame 新运行与联动。
- `07-tep-rootkgd.png`：打开真实全通道 RootKGD 结果（统计缺显修正前的反例记录）。

独立审核者另验一次 GUI 真实资料制作，不重复付费启动相同检查。后端/资产的科学有效性、模型负结果和来源限制由其各自记录约束，本页只记录 UI 实际行为。

## 最终交付与补充验收（02:54）

- `npm test`：**8 个文件 / 40 项通过**。覆盖当前任务 API、显式失败重试、轮询/断连、保存与启用分离、知识表达展示、分数/窗口语义、真实媒体键、正常门控与采样间隔、一次性任务聚焦。
- `npm run build`：类型检查与生产构建通过。只注册实际使用的 Arco 组件后，主入口约 50 KB，无旧的大 chunk 提示。
- `git diff --check`：前端、本轮项目测试规则和包配置通过。
- 旧复杂页面实现已替换；旧 Mock 后端、本地 runtime/推理装配、Session/Replay 兼容、反馈混合页、D3 CDN loader 及配套旧测试已移除。`public/generated` 既有快照资产保留，但当前代码不再读取。

### 实际修改影响与失败恢复

- UI 将验收副本异常条件 true→false 后，同一实际 Frame 的新任务 `task_84c4a01d490b407582c75eb5dece50be` 返回未形成完整支持；随后通过 UI 恢复 true，API 读回确认。已有运行仍保存原知识快照。
- 真实无效输入任务 `task_0cdaece80021485ab0894203490ed7eb` 失败；明确点击重试后创建 `task_3b4df2cc309743ee84f40bbf06fafcc8`，`retry_of` 指向原任务。没有自动重复模型调用。
- 服务不可用时，右上状态切为未连接，显示可重试错误。隔离浏览器中模拟连接失败后，实际恢复 API 与资料库读取，记录 `frontend-readonly-final.json`；此项是网络故障模拟，不冒充重启后端的证据。
- 新提交/显式重试只聚焦一次任务面板，轮询不抢滚动。无 LLM 重解析任务 `task_a0bbd8740c014c83a15386aa5e7f4fb4` 从正文下方提交后，任务面板滚入可视位置（y≈112）；记录 `frontend-progress-visibility.json`。

### 三场景实屏

- 玻璃：先显示实际“裂纹或玻璃缺失”外观与拍摄部位未确认；原图、区域裁切、掩码、热力图按实际资产键切换。候选组保持并列，比较表折叠，默认能看到为何支持与尚缺条件。`13-glass-edge-firstscreen.png`、`14-glass-edge-roi.png`；本轮 Frame 新运行为 `21-final-glass-evidence.png`。
- TEP：完整 52 通道表直接读 Frame 统计，不在浏览器重新测量；点击变量更新完整窗口曲线，并与候选路径联动。`22-final-tep-rootkgd.png`。原生 Frame 正常窗口明确“未越过正常参考异常门/不启动候选排名”，保留 20.06 / 26.67 与每 180 秒采样；`20-native-frame-normal-window.png`、`frontend-normal-window.json`。
- Wafer：显示原始 0/1/2 网格与区域实际统计，选区域会联动显示范围；输出为图案类别。最终 near-full 为 `23-final-wafer-nearfull.png`；真实分歧仍保留在历史分析。原生上传接受 JSON 与 JSONL。
- 390 px 输入布局无横向溢出（clientWidth=scrollWidth=390）；`18-mobile-input.png`。全轮只读检查无 JS 错误。

### 独立审核的消费

独立审核者已通过 GUI 完成 PDF→真实制作 `task_6e68de18e2c74c30b51503b1c851ebe4`（首次校验失败→唯一一次修复成功）→`graph_3a24629ac3ce487097424b4983e05398`→修改候选名称/成本→保存/启用→分析承接。其 A 闭环截图在 `backend/runs/two_loop_demo/independent-review/`。

审核指出的进度不可见、正常门控误导、原生 Frame 采样间隔缺显、Wafer JSONL 选择器过滤均已修复。独立 B 闭环亦已完成，见 [最终独立验收](../../backend/docs/two-loop-acceptance.md)。Wafer 下载文件名已由后端修复，独立审核者已重新下载并通过原生 JSONL 入口普通上传。没有已知前端阻塞。

本机测试工具误执行的精确命令、输出与事件传输未知范围保存在 `.playwright-mcp/two-loop/tooling-incident.md`，不再执行安装/遥测。根 `AGENTS.md` 已按主 owner 授权加入窄的项目测试规则；事件事实由独立审核另存。

## Wafer 区域高亮与统计严格对齐（追加修复）

独立审核发现 SVG 高亮按“单元格数量的一半”取半径，比后端索引跨度多 0.5 个芯粒；中心/中圈/边缘实际高亮数量因此偏移。

- 当前显示使用后端 `measure_wafer_map` 同一公式：`rx=max((right-left)/2,1)`、`ry=max((bottom-top)/2,1)`。SVG 中心继续平移 0.5，对应实际芯粒中心坐标；边界保持中心 `r<=0.4`、中圈 `0.4<r<0.8`、边缘 `r>=0.8`。
- 新 `wafer-regions.ts` 只负责显示几何，不计算诊断或替换保存的测量。38×38 全有效合成网格回归固定为中心 172 / 中圈 516 / 边缘 756，并覆盖闭/开边界与最小半径。
- 只读打开现有真实 Run `33196a93-9a78-44e6-a4bd-b3b12023676f`，逐区点击后直接计数实际 SVG 高亮：中心 172 有效 / 156 失效，中圈 516 / 433，边缘 451 / 397。三个高亮失效率均与该 Run 保存的 Frame 精确一致；未重跑模型、任务或改图。
- 本轮 `npm test -- src/services/wafer-regions.spec.ts`：**3 项通过**；`npm run build` 通过。先前 40 项测试的有效证据保留。
- 实屏与计数：`.playwright-mcp/two-loop/24-wafer-center-aligned.png`、`wafer-zone-alignment-after.json`；独立脚本 `/private/tmp/rootlens-wafer-region-check.mjs`。

同时修正 `src/api/url.ts` 的 EOF 多余空行与 `src/api/workbench.ts` 的尾随空格。Git 由后端 owner 统一重暂存；前端未自行 stage/commit。
