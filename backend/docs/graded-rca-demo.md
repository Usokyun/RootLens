# 三场景分级溯因演示：先看证据，再比较解释

三个场景共用 **分级解释溯因**（`graded_abduction`）。模型和 adapter 只产生可定位的测量；工作图声明哪些现象能解释、哪些观测支持或反驳它；后端选择合法的联合分支并分解分数。图谱是有向网络，保存详情里的分支是本次解释的投影。

## 快速复算：不用密钥、权重或旧数据库

按 [项目安装、数据库和启动](../../README.md#首次安装) 运行 RootLens。只给新空库初始化，不在现有库执行 `backend:init`。

1. 打开 **运行与证据 → 演示案例**，选 MVTec、TEP 或 WM811K。首次点 **安装并启用配套图**；这会创建或启用内容一致的工作图，不覆盖现有知识。已有可用配套图时直接开始分析。
2. 选 **中间 Evidence → 分级解释溯因**。后端对保存的真实观测重新推理。也可手动导入各场景 `working-graph.v2.json`、启用，然后上传同目录原生 `evidence.json`；需要与验收记录核对时，保留候选数设为 8。
3. 打开 **推理**，先看「有支持 / 待核验」，再点「定位实测」或「定位图谱源边」。仅有统计而未附本机图片、曲线或网格时会明确标注，数值和路径仍可复算。
4. **下载 Evidence** 返回本次原生 `{frames: […]}`。同图、同引擎、同候选数普通上传可复算；任务和 Run ID 会变。TEP 还可选 **RootKGD 图传播**看 52 通道贡献结构，RootKGD 分数不与 `S` 混算。

## 现场走两条完整链

**制作：** 在「素材与构图」添加演示素材，也可上传各场景 `material.md`。提取、查看片段后勾选并生成知识图谱；从任务进度或构图记录打开实际生成的图。LLM 初稿提供实体、关系、规则和绑定；后端为可用观测生成初始比较预算。在 **导入 / 导出 → 查看工作图包** 检查或调整 `observable_definitions[].grade` 与 `graded_policy`，保留当前图 ID 和来源引用。保存后重新打开，确认读回，再启用。要复演相同结果，请用已复核的演示图；新 LLM 构图的规则可能不同。

文本构图需要 `uv sync --frozen --extra dev --extra llm`；同时做原始视觉测量时也声明 `--extra ml --extra vision`。在被忽略的 `backend/.env.local` 配置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`（或同组 `DEEPSEEK_*`），并按服务选择 `SOURCE_KG_LLM_API`，见[模板](../.env.example)。

**原始推理：** [准备固定版本的公开输入与权重](#准备原始输入和权重)，再在同一案例选 **原始样本**。用刚制作的图时，从图页点「用这张图分析」，可明确选该图再上传。每个案例均无需 VLM：

| 场景 | 原始提交 | 在保存详情核对 |
| --- | --- | --- |
| [MVTec](../data/demo/graded_rca/mvtec/README.md) | [Bottle 006](../data/demo/graded_rca/mvtec/sample_006.png)，`bottle` / PatchCore / 关闭 ROI 外观语义 | 原图、热图和掩膜中的同一个 ROI，实测面积、长短比和离心率。两项工位假设的形态证据相同，保留并列。 |
| [TEP](../data/demo/graded_rca/tep/README.md) | d04 选择一基闭窗 `1–100`、`161–260`、`261–360`；d05 选 `161–260`；都用独立 d00，180 秒采样 | 正常窗门控、反应器／冷凝侧的竞争解释；点观测回到相应曲线。 |
| [WM811K](../data/demo/graded_rca/wafer/README.md) | 准备器从固定公开表裁取 248536、31707 两条原网格（无原生标签） | 分区密度、连通性、扇区与分类辅证；一个支持近全片，一个保留待核验。 |

在推理详情下载这次原始运行的 Evidence，再用同图和同一解释器普通上传。复跑不调用模型。对照样本和许可见各场景目录；不随仓库分发大权重、原始过程/晶圆数据表或第三方全文。

## 准备原始输入和权重

在 `backend/` 执行；按需要选择场景。准备器不写数据库、不改仓库里的图或 Frame。

```bash
# MVTec / WM811K 原始模型依赖；只跑 TEP 不需要这两个 extras
uv sync --frozen --extra dev --extra ml --extra vision
uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset mvtec --download
uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset tep --download
uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset wafer --download
```

权重和数据来源、目标文件、许可见各场景 README。原始视觉模型使用准备器输出的 `KGTRACEVIS_MVTEC_MODEL_MANIFEST` / `KGTRACEVIS_WM811K_CHECKPOINT` 设置，传给后端进程；修改后端环境后重启相应服务。只有准备了匹配资产才选择原始入口。

也可以用 CLI 在运行中的后端按清单安装／启用图并运行。输出目录用新目录；`--sample` 可重复，不指定时每场景选择推荐样本。

```bash
uv run --no-sync python scripts/prepare_two_loop_demo_api.py \
  --base-url http://127.0.0.1:8000 --variant evidence \
  --output-dir runs/graded-catalog-check
```

加 `--all --variant both` 可验收四个样本的两种输入。要只看 TEP 图传播，改用 `--sample tep-d04-graded --reasoner tep_rootkgd` 和新的输出目录。中途连接中断时，用原地址和目录加 `--resume`，读取已有任务而不重复提交。

## 分数怎么来的

`S = P − C`。支持 `P`、反证 `C` 都来自实际分支的唯一观测槽和共享固定权重。未测贡献为零，不缩小分母；`V` 是分支声明项中实际核验到的权重比例。`expected` 的实测不符才扣分，缺少 `possible` 的表现不构成反证。OR 只选完整规则允许的一支，不把两支观测拼成一个不存在的分支。没过异常门或硬性必要条件不进入推荐；关键量缺测可以留下「待核验」。同证据解释仍并列。候选的分数比较仅限同次分析，不是根因概率。

例如，[31707 的实际网格](http://127.0.0.1:5188/evidence/runs/35d5f058-4aa8-4f72-81be-c397c31a00db?tab=reasoning&case_id=wm811k_31707%2Fquery%2Fgrid)中，边缘扇区参与度 `0.9618` 对边缘环贡献 `+0.1818`，分类器标签只加 `+0.0909`；外圈失效率 `0.3033` 给 `−0.1067`、中心 `0.4853` 给 `−0.0984`。边缘环合计 `P=0.3557`、`C=0.2051`、`S=0.1507`，仍是待核验：边缘失效分布较广不等于边缘环。

[冻结对照的机器结果](../data/demo/graded_rca/stage-a-comparison.json) 使用旧三图和同一批 Frame，只补曲线、权重和判别锚点，三张图拓扑、旧统一结果与 TEP 旧 RootKGD 结果保持相同。Bottle 006 的离心率单值扫描 `0.899 → 0.900 → 0.901 → 0.940 → 0.980`，块状解释的 `S` 为 `0.6708 → 0.6667 → 0.6625 → 0.5000 → 0.3333`；缺测为 `S=0.6667、V=2/3`，有实测的边界值则 `V=1`。曲线宽度 ±25% 未破坏实测 006 的并列。上述扫描不是新图片测量；[MVTec 真实正反对照](mvtec-graded-demo-acceptance.md)单独记录。

## 新库里的唯一演示入口

在[独立验收前端 5189](http://127.0.0.1:5189/evidence)（API 8028）上，空工作图库直接显示三个场景。真实浏览器从 MVTec 卡首次安装图、提交默认 Evidence，进入[实际保存的结果](http://127.0.0.1:5189/evidence/runs/d84cd133-3849-46d0-873f-d684558b0724?tab=reasoning)，并由材料页登记同场景公开资料。旧运行、快照和 Dashboard API 不再供当前页面使用。

四个样本的原始／Evidence 两种入口共 **8 次完成**，覆盖同一组 7 个 Frame。两个入口的工作图和实际贡献源边一致；TEP 窗口曲线逐值相同，WM811K 的两帧分别定位到自己的网格。可查看 [d04 正常和异常窗口](http://127.0.0.1:5189/evidence/runs/3ec2ac11-16b8-4e27-be46-659ddf56b6aa)及 [31707 正反证](http://127.0.0.1:5189/evidence/runs/60312ed4-9b85-438d-88c1-9d6032d082e2?tab=reasoning&case_id=wm811k_31707%2Fquery%2Fgrid)。

另用公开 TEP 资料做了一次真实新构图：后端自动加了 6 个等权测量槽，没有猜测连续曲线；编辑、读回、启用后，同图提交 d04 原生 Frame 能完成分级推理。[新草图的结果](http://127.0.0.1:5189/evidence/runs/4f846bd2-78f0-4153-b7f9-6e652938a03f)正常窗门控、两个异常窗证据不足，仍保留贡献路径。稳定演示结果用上面复核过的配套图。

## 首次分级构图和原始测量验收

下面的运行保存在独立实例（[前端 5188](http://127.0.0.1:5188/evidence)，后端 `http://127.0.0.1:8027`）。每个场景的自著材料实际提取，并各调用文本模型一次生成待启用图；随后真实编辑、回读、导出并启用同一张图。每个原始运行下载原生 Evidence 后均用普通上传复跑，Frame、图快照、候选、分数、所选分支与实际源边逐字段一致。复跑不重测，整个验收未用 VLM。

可直接查看已启用的 [MVTec 工作图](http://127.0.0.1:5188/graphs?graph=graph_d1666b3b6f064b9190ee11b4eb18f692)、[TEP 工作图](http://127.0.0.1:5188/graphs?graph=graph_c5d48f1204984c4fb213d47df95796ae)和 [WM811K 工作图](http://127.0.0.1:5188/graphs?graph=graph_c1cea800587c43c3a2739ec8b812104b)。每张图的来源和具体人工修改见其公开包；本机任务和媒体不随 Git 分发。

| 场景 | 实际原始运行 → 同图 Evidence | 结果 |
| --- | --- | --- |
| MVTec | [006 原图](http://127.0.0.1:5188/evidence/runs/db943d30-e8f3-4613-aad7-7bccb49f8077?tab=reasoning) → [复算](http://127.0.0.1:5188/evidence/runs/aa13c65c-11a4-4e54-bdd7-d7d8905e38af?tab=reasoning) | 块状解释两项并列 `S=1`，点离心率定位实际源边和原 ROI。表面对照也呈块状，外轮廓和环带探针没达到事先定义的区分标准，未加入评分。 |
| TEP | [d04 三窗](http://127.0.0.1:5188/evidence/runs/5b722359-8a61-4daf-9ec4-d761421f89fb?tab=reasoning&case_id=process_window_161_260%2Fquery%2Fwindow) → [复算](http://127.0.0.1:5188/evidence/runs/b735f37e-27a6-4c95-a15f-21967e2a4ee0)；[d05](http://127.0.0.1:5188/evidence/runs/2c95491d-dc32-4c6f-929a-669d74dc9bec?tab=reasoning) → [复算](http://127.0.0.1:5188/evidence/runs/92379183-f7b9-49de-bd1c-f7383dea9557) | d04 正常窗无推荐；两个异常窗支持反应器补偿，两个原因各 `S=0.3333`。d05 旧图仍无推荐，新图同窗的两个均值和一个波动共同支持冷凝侧，两个原因各 `S=0.4119`。同一 d04 Frame 另有 [RootKGD 对照](http://127.0.0.1:5188/evidence/runs/c3e61701-a503-451e-b29b-864f45a17bb1?tab=reasoning&case_id=process_window_161_260%2Fquery%2Fwindow)。 |
| WM811K | [248536 与 31707 原网格](http://127.0.0.1:5188/evidence/runs/35d5f058-4aa8-4f72-81be-c397c31a00db?tab=reasoning) → [复算](http://127.0.0.1:5188/evidence/runs/65c616fb-6d49-4f48-80c7-cd157692e523?tab=reasoning) | 248536 近全片获支持 `S=0.8103`；31707 没有获支持图案，边缘环与边缘局部保留待核验。正／反贡献可定位到实际源边与原晶圆分区。 |
