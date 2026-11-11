# 在原工作台接通两个后端闭环（2026-11-11）

本轮在 `codex/restore-original-frontend@f5e93aa` 上渐进接回真实任务，不另建页面。原导航、三页布局、D3总图／局部网络与成品回放保留；已推送的 `codex/demo-two-loops@8cf4d0b` 是另一个历史界面版本，不覆盖。本轮未推送。

## 素材与构图：完成后打开确切的新工作图

1. 在 Backend 模式勾选原素材库中的资料；同一任务只允许所选场景和共享资料。既有文件／URL登记入口不变；单份“解析资料／重新解析”使用 `/api/tasks/material-parse`，成功后回读实际片段。
2. 原 Build Recipe 的“生成构图”提交 `/api/tasks/material-build`，绑定所选素材ID、场景能力和标题。已有解析可复用；无需先执行旧 `build-sources` 或装载另一份图。
3. 任务列表与阶段卡读取真实任务和事件：有总数时显示实际计数，LLM未知进度时只显示阶段；失败停在实际阶段。“按原输入重试”另建任务，不自动触发。旧构图记录及其详情仍可查看。
4. 完成卡自动选中该任务返回的 `result.graph_id`；“打开并编辑此图”携精确ID到 `/graphs?graph=...`。初始未启用，由图谱页保存完整包并启用后使用，不猜测另一张就绪图。

素材线原生Vitest 9项通过。独立Chrome真实只读消费了历史成功 `task_8217b6fb3f274fceb9d8519be95f2f38`（11阶段、精确工作图 `graph_7718009df1d94a288f99d1e428487679`）和历史失败 `task_2b5e770ad3114218bba64e58847b9cb5`（自动校验失败，未重试）。另一隔离context拦截所有写请求：受控构图返回解析计数、LLM不定、校验失败，明确点击后只发一次fixture重试并携fixture结果ID；两次POST均在浏览器测试中应答，没有进入后端。证据 `.playwright-mcp/material-loop/material-loop-check.json`、`01-actual-completed-task.png`、`02-fixture-llm-indeterminate.png`、`03-fixture-failure.png`。fixture完成结果不是实际新图。

## 构图请求额度由应用明确控制

一次任务默认最多两个文本请求（首次＋一次校验修复）；取消“允许一次自动修复”后只发首次。实际发现项目安装的OpenAI SDK 2.32.0默认允许两次传输重发，不能将其当作编译修复额度的一部分。仅source构图客户端设 `max_retries=0`；传输失败保留原任务阶段并停止，ROI／分析及其他客户端不变。

原生回归覆盖chat/responses构造与错误传播、传输失败不触发第二次编译请求；本机实际SDK用`httpx.MockTransport`收到503时，两种wire各只尝试一次HTTP，无外部请求。最终默认pytest **575 passed／4既有optional skipped**（3项隔离库opt-in、1项原TEP_KG缺失），修改文件Ruff及diff-check通过。日志 `/private/tmp/rootlens-restored-loop-pytest.log`，SDK证据 `/private/tmp/rootlens-source-sdk-attempts.json`。

确认96个持久任务无queued/running且两位前端owner无活跃写入后，只重载现有专用launchd API，PID `10919 → 85974`。`8012`健康，历史构图任务、Root运行及其Frame仍可读；不重新初始化或改写数据库，不为连通性发付费请求。

## 根因与图谱：完整包保存、启用、明确携图

图谱页继续使用原有D3节点—关系总图和局部网络。`/graphs?graph=...` 明确加载登记图；新图在原工作图包抽屉中编辑完整JSON并保存，然后“投入使用”。保存不从展示节点／边重建对象，保留新绑定、目录、角色、期待和来源；未保存编辑时不提交启用或携图。启用后“用这张图分析”以该图ID发出显式新建意图，不选最新图、不打开旧Run。

打开历史分析时，“当前登记知识图谱”与“本次保存推理路径”各自读取自己的数据。局部路径、证明与观测引用保持保存结果的ID和方向；图像定位按实际ROI、过程定位按实际通道／窗口。已保存局部路径不可当成当前可编辑源边，不在浏览器重新构图或推理。

## 运行与证据：原运行页的新建分析入口

“新建分析”使用小型原Arco弹窗，不替换运行列表、Evidence详情或成品回放。选择原始输入或中间EvidenceFrame、场景、已启用工作图、兼容推理器；TEP原始文件同时提交正常参考与一基闭区间。手动图像默认不调用外部ROI模型。公开样例只填入输入，不自动运行；配套图只作隐式默认，手选／携带的明确图保留，切换须点击。

任务完成读取确切保存分析ID和Frame，不先以旧Run或Demo补结果。可以下载本次实际Evidence，用中间入口复算；旧Session导出不冒充新分析的导出。旧接口上传保持原合同。界面只读定位、候选、条件与数值，不重新生成观测或分数。

分析owner的隔离浏览器验证了真实目录、配套与明确选择、迟到目录不清上传、原始Wafer `.jsonl` 文件选择、受控失败只在显式动作时重试、真实保存分析读取与Frame下载逐字段一致。相关写请求均在fixture内拦截，未进入真实服务。证据 `.playwright-mcp/original-two-loop/analysis-dialog-check.json` 和 `analysis-file-chooser.json`。

## 源码检查

三线冻结候选原生Vitest **28文件／147项通过**，类型与生产构建通过；原全量Arco主chunk约771KB的大小警告保留。完整日志 `.playwright-mcp/original-two-loop/final-vitest.log`、`final-build.log`，tracked与新增文件的whitespace检查通过。后端除上述source预算修正外，推理、持久化和演示种子不变。

## 本机实际串联

可打开的结果及完整证据见[实际操作验收](../../backend/docs/original-ui-loop-acceptance.md)。该次真实执行与上面的受控失败分开：

- 原上传入口另登记一份272字节公开短摘，解析任务`task_6d507c9cd83247e5920da0e594d509f1`回读1个片段；短摘未参与构图，不调用模型。
- 唯一真实构图`task_d31016f07e86436aa98c20959b722be2`复用已登记Emhart PDF第13／20页的两片段，**1次文本LLM／8,543 tokens／0次修复**。新图`graph_fb6f04b8867c4cdb96ed92fc465bf28b`初始未启用；从完成卡进入原图谱，完整保存只改一条对象别名，启用后携同一图新建分析。
- 同图上传公开006原图，使用本地PatchCore、关闭外部ROI语义、统一条件溯因、`top_k=8`。实际细外观未观测，保存为**证据不足、0排名**。原Run `3d2bd6d2-af6e-4804-a4a8-8c37e99f9271` 下载Frame后普通上传，复算Run `f4e24f5e-47d6-48c0-bef3-10751bb467cf` 的完整`cases[].results`逐项精确一致，未重跑测量。原图可关联；遮罩／热图留在初次原图分析中。
- 单独的就绪适配图副本消费既有真实006外观Frame，有8个并列候选，`J=0.25`、排序分`-0.25`，35条去重源边精确对应局部D3网络。d04同一冻结窗口161–260验证两引擎及52条变量曲线；RootKGD使用全52贡献结构输入，结构分`0.5854474293642782`，不套统一代价或概率。没有将候选当成已证实原因。
- 没有新VLM、GPU任务、第二次文本制作或重跑Wafer推理矩阵。既有默认图与历史数据保留；新图和新结果是独立的验收记录。

最终[原工作台](http://127.0.0.1:5186/evidence) HTTP200，Vite PID84871；经代理及直连[API](http://127.0.0.1:8012/api/health)均返回ok，API PID85974。服务保持运行，未为交付再次重载；API仍由已有手动作业管理，不配置登录／开机自启。
