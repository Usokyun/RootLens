# RootLens 双闭环演示：一张图贯通三个页面

用公开 MVTec AD `bottle` 原图 006，展示如何把**作者明确声明的条件**变成可运行的工作图，再把**实际模型观测**连到候选解释。默认不调用视觉语言模型。两个候选共享几何条件，不能把并列当成已确认的工艺根因。

先按 [README 的首次安装、数据库和启动](../../README.md#首次安装) 启动 Backend。在已有库上不要重跑 `backend:init`。以下数据路径相对 `backend/`。

## 快速复演：不用密钥、模型权重或历史库

四份文件位于 [MVTec 公开包](../data/demo/two_loop/mvtec/README.md)：`material.md`、`sample_006.png`、`working-graph.v2.json`、`evidence.json`。它们都随仓库提供。`/api/demo-library` 的 MVTec 组只登记 `bottle-rim-break`（界面名为「玻璃瓶局部异常 · 原图 006」）。

1. **根因与图谱** → **导入 / 导出 → 导入工作图包**，选择 `working-graph.v2.json`。导入创建本库的新图 ID，不覆盖已有图。**启用工作图 → 确认启用**。
2. 点 **用这张图分析**，选择 **中间 Evidence**，普通上传 `evidence.json`，选择 **统一条件溯因**，开始分析。这一步从实测观测重新推理，不执行 Backbone，也不读取预先写好的候选答案。
3. 或者在 **运行与证据 → 新建分析 → 公开演示样本** 选择原图 006 和 **中间 Evidence**。无显式选图时，服务只配内容一致、已启用的图；显式携图或手选会保留。样例入口能把受管原图与 Frame 关联；普通上传仍可完整复算，但不会拿 Frame 的原机器路径读取任意媒体。
4. 在保存详情查看 **Evidence → 推理 → 图谱**：核对两个几何条件、共享机理和来源边。**下载 Evidence** 导出本次保存的原生 `{frames:[…]}`，可继续普通上传复算。

同一快线路也可用真实 HTTP 客户端执行。默认开发 API 地址是 `127.0.0.1:8000`；使用其他实例时改 `--base-url`。输出目录需为新目录。

```bash
# 在 backend/
uv run --offline --no-sync python scripts/prepare_two_loop_demo.py --dataset mvtec
uv run --offline --no-sync python scripts/prepare_two_loop_demo_api.py \
  --base-url http://127.0.0.1:8000 \
  --sample bottle-rim-break --variant evidence \
  --output-dir runs/two_loop_demo/my-mvtec-evidence
```

客户端只为选中的场景查找或导入配套图。若已存在内容一致的启用图，直接复用；歧义或不可读则报出状态，不按最新图猜测。保存索引为输出目录的 `state.json`，完整任务和 Run 同目录保留。

## 走原图：先准备固定的 Bottle PatchCore

只有这一步需要视觉依赖和约 231 MB 的第三方权重。确认你有权使用该权重；来源库没有声明明确权重许可。准备器从[固定上游 revision](https://huggingface.co/micguida1/mvtec-anomaly-checkpoints/blob/17e6b9b9bbb42f2f0ccda588bd088724520b8348/Patchcore/MVTecAD/bottle/latest/weights/lightning/model.ckpt)获取并核对发布方的 LFS 完整性，不把权重入库或通过应用再分发。

```bash
# 在 backend/；已有这些 extras 不必重复同步
uv sync --frozen --extra dev --extra ml --extra vision
uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset mvtec --download
```

将下面变量加到后端进程环境，再按原项目命令启动后端。路径相对 `backend/`，准备器不会覆盖用户已有的模型登记或 `.env.local`。已有相同 Bottle PatchCore 登记的实例可直接使用，不必再下载。

```bash
# 从仓库根目录，数据库已健康、端口未占用
KGTRACEVIS_MVTEC_MODEL_MANIFEST=runs/two_loop_demo/mvtec-demo-models.json npm run dev:all
```

从启用图点 **用这张图分析**，选择 **原始样本**，公开样本选原图 006；也可上传 `sample_006.png`，对象 `bottle`、模型 PatchCore，保持 **提取 ROI 外观语义** 未勾选。不需要正常参考。实际运行产生定位热图、掩膜与几何；原图和检测网格的坐标体系由运行保存。短资料要求同一区域 `geometry.area_ratio ≥ 0.10`、`geometry.aspect_ratio ≤ 2`，不是在判断已知瓶口部位或真实制造故障。查看 **Backbone** 与 **Evidence**，然后点 **下载 Evidence**，在同图、同推理器、同保留候选数下普通上传复算。

命令行执行原图时将上一条客户端命令的 `--variant evidence` 改为 `--variant raw`，使用新的输出目录。若客户端断开，以相同地址和输出目录加 `--resume` 取回已提交任务；不重新提交。任务失败时查看保存的事件和原因。

## 从短 Markdown 开始制作：需要文本模型

1. **素材与构图 → 添加素材**，上传 `material.md`，场景选 MVTec。点 **提取内容**，检查原文片段。
2. 勾选这份素材，点 **生成知识图谱**。此操作真实调用你配置的 OpenAI-compatible 文本服务；服务端最多一次自动修复，正常上限为两个请求（生成＋修复），会产生提供商费用。文本服务不可用时使用上面的现成图快线，不把导入称为 LLM 制作。
3. 完成后点 **打开图谱**。在右侧检查实际来源、条件、并列候选；选中对象节点，**编辑节点**添加别名并保存。确认图中两个几何原子仍联合判断同一区域。然后启用这张图，点 **用这张图分析**；按上一节跑原图、下载并重传该次 Evidence。重新生成的图不一定与发布图相同，保留实际结果和明确的缺失，不换旧图补出候选。

首次需在 `backend/` 安装 `uv sync --frozen --extra dev --extra llm`；如同时走原图，请在同一次同步保留 `--extra ml --extra vision`。在忽略的 `backend/.env.local` 配置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`（或同组 `DEEPSEEK_*`）。接口类型 `SOURCE_KG_LLM_API=chat_completions` 或 `responses` 需与服务相符，见 [`backend/.env.example`](../.env.example)。不要将凭据放进 `VITE_` 变量。当前 MVTec 样例不需要视觉模型密钥。

## 已实跑的结果

- [三页实际操作验收](mvtec-public-demo-acceptance.md)：上传短资料并完成一次文本构图，编辑、启用同一图；实际原图和随后普通上传的 Frame 保存了完全一致的完整结果。两候选并列第一，总代价 `J = 0.25`，分数 `−0.25`（不是概率），有 6 条保存路径。
- 干净候选树只带随仓库发布的输入，使用新空 Compose 项目及单独后端，不读取现有 `.env.local` 或运行归档。先在无权重登记、无服务密钥时导入／启用配套图并执行 Evidence；再从上游固定版本下载权重，执行一次无 VLM 的 CPU 原图任务。两条路线都得到同一候选、代价和 6 条路径，实测同一区域面积占比 `0.2284393311`、长短边比 `1.1172839506`。Evidence 入口附受管原图；原图入口另生成掩膜和热图。本机核验记录为 `backend/runs/mvtec_public_fresh_clone/verification.json`，不依赖里面的 Run ID 启动。

## 其他场景与历史

- **TEP** 推荐 `tep-sequence-04`：独立正常参考、52 通道与真实窗口，统一条件溯因和 RootKGD 图传播分别解释条件证据和贡献结构。
- **晶圆**推荐 `wafer-nearfull`：原始 0/1/2 网格、独立分类与空间统计，近全片是图案类型，不是制造原因。
- 两者的清单和已保存数据未改。缺少可选本地资产时，按场景运行 `prepare_two_loop_demo.py --dataset tep` 或 `--dataset wafer`；需要从公开来源获取时才加 `--download`。Wafer 原始入口需要 `--extra ml --extra vision`；下载完整论文进行提取另需 `--extra parsers`。准备器不改登记图、不写回 Git 中的清单或 Frame，报告见 `runs/two_loop_demo/preparation-report.json`。
- 旧 PDF／ROI 示例、TEP 的原始与复算结果、晶圆分歧和严格 Finish 证据不足保留在[历史研究验收](two-loop-demo-history.md)，不进入当前 MVTec 列表。[演示资产索引](../../src/doc/rootlens-two-loop-demo-assets.md)说明分发和历史文件边界。

## 恢复现有本机演示服务

验收用的 5186／8012 与普通开发默认端口分开。已有进程直接复用。仅在这个本机隔离服务已停止时，复用既有 `rootlens-mvtec-m1-test` Compose 项目和手动 `two-loop-api` 命名作业；不要重新初始化或删除卷。

```bash
# 根目录；恢复本机指定隔离数据库，不创建第二个应用服务
docker compose -p rootlens-mvtec-m1-test -f backend/compose.test.yaml up -d --wait neo4j postgres
# backend/；仅检查/恢复这个已配置命名 API
uv run --offline --no-sync python scripts/development_api.py health --name two-loop-api
uv run --offline --no-sync python scripts/development_api.py start --name two-loop-api --port 8012
```

前端需要恢复时，在根目录以 `VITE_API_BASE_URL=http://127.0.0.1:8012 VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8012 npm run dev -- --host 127.0.0.1 --port 5186 --strictPort` 启动。已中断的任务保留输入和事件；明确重试，不自动重复付费。
