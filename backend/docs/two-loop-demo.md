# RootLens 双闭环：三个公开样本、同一套操作

先按 [README 的首次安装、数据库和启动](../../README.md#首次安装) 启动 Backend。在已有库上不要重跑 `backend:init`。以下数据路径相对 `backend/`。

| 场景 | 公开包与样本 ID | 查看什么 |
| --- | --- | --- |
| MVTec | [Bottle 006](../data/demo/two_loop/mvtec/README.md) · `bottle-rim-break` | 一个 ROI 的面积 ≥ 0.10、长短边比 ≤ 2、离心率 ≤ 0.90 都成立；两个工艺假设仍并列。 |
| TEP | [冷却回路 d04](../data/demo/two_loop/tep/README.md) · `tep-sequence-04` | 52 通道、独立正常参考，窗口 1–100、161–260、261–360；看串级控制联合条件与 RootKGD 结构评分的区别。 |
| WM811K | [晶圆 248536](../data/demo/two_loop/wafer/README.md) · `wafer-nearfull` | 近全片分类还须有全片、中心和边缘密度及大连通分量；边缘环不由边缘高密度单独决定。 |

## 不用密钥或模型权重复算

1. 在 **根因与图谱 → 导入 / 导出 → 导入工作图包** 选相应公开包的 `working-graph.v2.json`。导入创建新图，不覆盖旧图。点 **启用工作图 → 确认启用**。
2. 从图页点 **用这张图分析**，选 **中间 Evidence**，普通上传同目录的 `evidence.json`，选 **统一条件溯因**。TEP 也可选 **RootKGD**。这是使用保存的真实观测重新推理，不运行测量或读取预存答案。
3. 或在 **运行与证据 → 新建分析 → 公开演示样本** 选择该场景及 **中间 Evidence**。只在隐式默认时自动配对内容一致、已启用的图；明确携图或手选保留。已准备的白名单附件才关联，不访问 Frame 里的任意文件路径。缺原图／曲线／网格时标明未关联，不影响已有标量条件和贡献复算。
4. 打开保存详情，在 **Evidence → 推理 → 图谱** 核对已用观测、真／假／未知条件和真实源边；**下载 Evidence** 返回本次保存的 `{frames:[…]}`。同图、同引擎、同保留候选数可普通上传复算。

以实际后端 API 执行同一路线；输出目录需为新目录。`--sample` 可重复；省略它时选择三个推荐样本。TEP 默认两种兼容解释器。

```bash
# 在 backend/，已 uv sync --frozen --extra dev
uv run --offline --no-sync python scripts/prepare_two_loop_demo.py
uv run --offline --no-sync python scripts/prepare_two_loop_demo_api.py \
  --base-url http://127.0.0.1:8000 --variant evidence \
  --output-dir runs/two_loop_demo/my-three-evidence
```

客户端只为选中的场景查找或导入配套图；歧义或不可读时报出状态，不按最新图猜测。`state.json` 指向完整任务和 Run。若轮询断开，使用同一地址和输出目录加 `--resume` 取回原任务，不重新提交。

## 原始入口：按场景准备固定输入

只有实际原始测量需要可选资产。安装项目锁定环境，MVTec／晶圆模型需要 `--extra ml --extra vision`，TEP 正常拟合与过程统计用基础依赖即可。准备器只写 `runs/two_loop_demo/` 下的缺失本地文件，不改清单、发布的 Frame、已有图或数据库。

```bash
# 在 backend/；只执行需要的场景
uv sync --frozen --extra dev --extra ml --extra vision  # MVTec／WM811K 原始模型
uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset mvtec --download
uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset tep --download
uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset wafer --download
```

- **MVTec**：原图已入库，约 231 MB 权重从 [Bottle PatchCore 固定版](https://huggingface.co/micguida1/mvtec-anomaly-checkpoints/blob/17e6b9b9bbb42f2f0ccda588bd088724520b8348/Patchcore/MVTecAD/bottle/latest/weights/lightning/model.ckpt)本机获取并核对完整性；上游未声明明确权重许可。后端变量 `KGTRACEVIS_MVTEC_MODEL_MANIFEST=runs/two_loop_demo/mvtec-demo-models.json`。原始输入用 `bottle`／PatchCore，关闭 ROI 视觉语义。不需要正常图。原图运行生成真实热图与掩膜，Evidence 快线关联随仓库的原图，不补造模型产物。
- **TEP**：从 [Braatz 固定版本](https://github.com/camaramm/tennessee-eastman-profBraatz/tree/0643318858ce7c87292bd59820b459e12a13d009)获取 `d04_te.dat` 与独立 `d00.dat`，准备器核对后存入 `runs/two_loop_demo/raw/tep/`。窗是一基闭区间，采样间隔 180 秒；两引擎都保留完整 52 通道。准备器可按 Frame 精确 ID 重建每个窗口的曲线附件，先核对保存观测，再绑定，不覆写原 Frame。
- **晶圆**：从 [WM811K 测试表固定版](https://huggingface.co/datasets/lslattery/wafer-defect-detection/tree/903fe28851d02a976db7a3a4bc12b6cfa2f5443c)校验后限读取数据构造器，裁取索引 248536；只生成身份与 `waferMap`，不传原生标签。网格原镜像未声明再分发许可，不随仓库。模型从 [RadAI ResNet34 固定版](https://huggingface.co/radai-agent/radai-wm811k-defect-detection/blob/61747cac7cba3eee3714fee86ab99f8250dd2e08/best_radai_resnet.pt)准备，MIT 模型许可不覆盖网格。后端变量 `KGTRACEVIS_WM811K_CHECKPOINT=runs/two_loop_demo/models/wm811k_resnet_61747ca.pt`；已有精确模型登记可复用。

若晶圆准备在连接 Hugging Face 时中断，可在 `backend/` 用 `curl` 取得同一固定文件。不要直接加载下载的文件；最后一条会在读取测试表前校验其大小和 LFS 摘要，模型权重也会校验。

```bash
mkdir -p runs/two_loop_demo/sources runs/two_loop_demo/models
fetch_missing() {
  [ -e "$2" ] || { curl -fL "$1" -o "$2.part" && mv -n "$2.part" "$2"; }
}
fetch_missing 'https://huggingface.co/datasets/lslattery/wafer-defect-detection/resolve/903fe28851d02a976db7a3a4bc12b6cfa2f5443c/test.pkl' \
  runs/two_loop_demo/sources/wm811k_test_903fe28.pkl &&
fetch_missing 'https://huggingface.co/radai-agent/radai-wm811k-defect-detection/resolve/61747cac7cba3eee3714fee86ab99f8250dd2e08/best_radai_resnet.pt' \
  runs/two_loop_demo/models/wm811k_resnet_61747ca.pt &&
uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset wafer --download
```

变量传给后端进程、相对 `backend/` 解析。不写入 `VITE_` 变量，不覆盖本机配置。已运行的服务不要再起第二个占用同一端口的进程。用对应工作图选择 **原始样本**，可选公开示例或手动上传。下载本次实际 Frame，再用同一图复算以核对两个入口。命令行改用 `--variant raw --sample <样本 ID>`。

## 走完整制作：仅这一步调用文本模型

1. **素材与构图 → 添加素材** 上传相应的 `material.md`，按场景提取并检查原文片段。
2. 勾选材料，点 **生成知识图谱**。该动作真实调用配置的 OpenAI-compatible 文本服务，最多一次自动修复，正常上限两个请求（生成＋修复）；可能产生费用。文本服务不可用时走上面的现成图快线。
3. 在任务里 **打开图谱**，检查条件、来源和单位。在右栏编辑对象名称或别名，再保存、启用。TEP 的人工补充单独标注来源和边界，不能把它说成初次模型生成。最后 **用这张图分析**，使用原始数据，下载该次实际 Evidence 并普通重传。新制作图与发行图可能不同；保留真实不足或冲突，不切旧图补结论。

需要 `uv sync --frozen --extra dev --extra llm`；如同时跑原始视觉模型，在同一次同步加 `--extra ml --extra vision`。在忽略的 `backend/.env.local` 配置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`（或同组 `DEEPSEEK_*`）；`SOURCE_KG_LLM_API` 按服务选 `chat_completions` 或 `responses`，见 [模板](../.env.example)。三个主演示均不需要 VLM。

## 阅读支持与待验证

联合条件完整成立才进入主榜和保存证明。统一引擎单列「待验证」，列出已有支持、反证和还需核验的条件；只有异常门成立并有具体支持才可能出现，不把它读作完整结论或给它编造正式证明路径。不同推理器分数含义不同；统一引擎用代价，RootKGD 比较真实图传播与完整残差贡献结构，均不是概率。

真实制作、编辑、原始／Frame 复算和负例分别见 [MVTec 验收](mvtec-public-demo-acceptance.md)、[TEP 公开包](../data/demo/two_loop/tep/README.md)、[WM811K 验收](wafer-public-demo-acceptance.md)。旧 PDF／ROI、不足对照和其它 TEP／晶圆研究保留在[历史研究验收](two-loop-demo-history.md)，不出现在最新默认样例中。

在新空 Compose 与仅基础／开发依赖的干净候选中，三图普通导入启用后，四次公开 Evidence 任务均成功（TEP 两引擎）；没有密钥、模型权重或旧运行归档。无过程附件时仍保存三窗结果；准备固定 d04／d00 后另核各窗 100×52 曲线与其窗口矩阵逐值一致。Wafer 固定公开文件及模型通过大小与发布摘要验证，裁出的 248536 JSONL 与实际原始运行输入逐字节相同。核验记录 `backend/runs/three_public_demos_fresh/verification.json` 不参与运行。

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
