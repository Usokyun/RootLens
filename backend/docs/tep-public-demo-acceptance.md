# TEP d04：真实三窗检验串级控制的替代观测

2026-11-11，在真实隔离栈完成「素材与构图 → 根因与图谱 → 运行与证据」。初版的暖出口规则确实未匹配；保存并复算该负例后，在同一图补入可追溯的串级补偿模式。最终原始入口和实际下载的 Frame 逐项一致，第二引擎保持独立的结构解释。[公开演示包](../data/demo/two_loop/tep/README.md)提供可执行图、原生 Evidence 和复演入口。

## 资料闭环：公开原文、一次构图、真实编辑启用

1. 上传[自著短材](../data/demo/two_loop/tep/material.md)，素材 `demo_tep_cooling_joint_public_source_20261111`，解析任务 `task_6d3d1f883c7c407e83914073ce081bc4` 提取 `su_bbdadde1501f4068`（第 1–15 行）。两条冷却回路的通道身份来自固定版本的 [TEP 过程程序](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/teprob.f)。
2. 只选这份材料，以 `process-window-v2` 制作。`task_5b1f4e1cccba4832b66a71534a84a73a` 实际经过解析 → LLM → 校验 → 编译 → 工作图就绪 → 完成。**1 次文本调用**（`deepseek-flash`，6,754 tokens），0 次修复，生成 **83 节点、42 条关系**，没有自动启用。
3. 打开该任务的[确切工作图](http://127.0.0.1:5186/graphs?graph=graph_59353d02949d453db100a0aedf52b827)。真实保存 `XMV10` 的名称「反应器冷却水调节量 · XMV10」和两个别名。完整包与 Neo4j 回读仅该实体行改变；源边 ID、绑定和条件未改。随后明确确认启用。

### 初版不匹配，保存失败所提供的证据

从同一图分析公开 [d04_te.dat](https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/0643318858ce7c87292bd59820b459e12a13d009/d04_te.dat) 的 161–260 窗口，使用独立 [d00.dat](https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/0643318858ce7c87292bd59820b459e12a13d009/d00.dat)。上传文件与固定上游字节一致；改用中性文件名，未把故障标签交给推理器。实测异常门为真，`XMV10` = +7.172193，但冷却水出口 `XMEAS21` 只为 +0.085717，未达到 +2。故得到 `no_match`、0 个入榜候选、0 条支持路径。

[初版原始 Run](http://127.0.0.1:5186/evidence/runs/2363ee79-aec3-49fe-9db7-3df4454a45c2) 下载的 Frame 经普通上传产生[初版复算 Run](http://127.0.0.1:5186/evidence/runs/939b2951-6799-467d-b2f0-dfcdfa0b6069)。Frame、完整图快照、结果和 52 条曲线完全一致；以下修订后两份历史记录的原值不变。

### 人工修订：补偿和暖出口是替代模式

固定原程序 [外环 CONTRL18](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f#L1192-L1204) 以反应器温度 `XMEAS(9)` 调整内环给定 `SETPT(10)`；[内环 CONTRL10](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f#L905-L917) 根据 `XMEAS(21)` 对该给定的误差调整 `XMV(10)`。因此控制努力上移可以和受控温度近参考同时出现。不要求出口也近参考，因为内环给定会变。

将[人工补充说明](../data/demo/two_loop/tep/expert-refinement.md)另行上传、提取（`task_f6e36ea80e0f4bdab937d5371c1cda8d`，`su_1681d52aa5544355` 第 1–14 行），**没有再次调用 LLM**。在图谱工作台高级完整包编辑中保存两条有符号 `XMEAS9` 边界（≥ −2 与 ≤ +2）和下列**一个**复合期望，各通道必须来自同一事件窗口、同一正常参考：

```text
异常门 ∧ (XMV10 mean_z ≥ +2)
      ∧ ((XMEAS21 mean_z ≥ +2) ∨ (−2 ≤ XMEAS9 mean_z ≤ +2))
```

保留旧暖出口现象及其原子，替换反应器共享机理的 `expected` 入口，不把暖出口失配再计为对成立补偿分支的独立反证。冷凝器原期望、候选假设、绑定和代价不变。完整包、Neo4j 回读与浏览器导出一致，仍是同一个已启用图，现有 **94 节点、69 条关系**。±2 是自著演示约定，不是设备限值或根因标签。第一异常窗帮助发现缺项，后一个窗检查同样条件是否再出现；两窗来自同一序列，不是独立样本评估。

## 分析闭环：原始适配一次，三窗 Frame 原样复算

普通上传原始序列和独立正常参考，输入三个一基闭窗口、180 秒采样、`unified_abduction`、Top K = 8。基础测量适配器从 500 × 52 正常参考拟合尺度与 18 个 PCA 分量；三个窗口共享参考，保存每窗 263 条观测、52 维残差贡献和 52 条各 100 点的原始曲线。正常残差能量的 0.99 分位门限为 26.668025。

| 保存分析 | 实际行为 |
| --- | --- |
| [最终原始 Run](http://127.0.0.1:5186/evidence/runs/755be821-e370-4d07-a4b9-890a26287a13) · `task_b01c30f3cc68425098f2fea498e2ea7c` | 运行实际过程适配、正常参考拟合和测量，不用文本或视觉模型。 |
| [最终 Evidence Run](http://127.0.0.1:5186/evidence/runs/f527c7b4-7e94-4c74-9ea1-e41d1a784405) · `task_7e7e57bb065c4ba08a235d21332d3296` | 从上述 Run 下载真实原生 Evidence 后普通上传，跳过测量 Backbone，继续使用同图和解释器。 |
| [RootKGD Run](http://127.0.0.1:5186/evidence/runs/6bd0b2b2-71dd-45b3-a8ec-12fa5d1cbccf) · `task_7aefdd4b2d144bff854e5a91eb2205bc` | 普通上传同一个下载文件，仅换解释器；同 Frame、同图快照、同窗口曲线。 |

最终原始与统一 Evidence Run 的**三条 Frame、图快照、完整 `cases[].results` 和逐窗全部 52 条曲线逐项相等**。随仓图是这次图谱工作台的完整导出，随仓 Evidence 是实际下载的原字节；两者不为发布改写观测或媒体引用。

| 样本窗口 | 残差能量／门 | XMV10 `mean_z` | XMEAS9 `mean_z` | XMEAS21 `mean_z` | 统一结果 |
| --- | --- | ---: | ---: | ---: | --- |
| 1–100 | 20.0552／假 | +0.0563 | −0.0289 | −0.0540 | `no_match`，无入榜／路径 |
| 161–260 | 60.9670／真 | +7.1722 | −0.0772 | +0.0857 | `ambiguous`，补偿分支为真 |
| 261–360 | 58.3166／真 | +7.0597 | +0.0515 | +0.2794 | `ambiguous`，补偿分支为真 |

两个异常窗各有 **2 个并列第 1、8 条支持路径**。候选是「反应器供冷侧入口冷却水偏暖」与「反应器过程侧放热负荷增加」，未解释 U = 0、冲突 C = 0、假设 A = 1、代价 J = 0.25，排序分 −0.25。原暖出口谓词仍为假；冷凝器两诊断量均不达 +2。三窗完整数值及实际条件真值见 [verification.json](../data/demo/two_loop/tep/verification.json)。没有测量足以分辨两个反应器假设。

### 从条件到同一观测；第二引擎单独解读

在 161–260 窗的保存详情，从 XMV10 条件点「在图中高亮」，命中已存源边 `signature:reactor_alternative_responses:definition::input::signature:reactor_cooling_load_shift:condition:0`；「定位同一观测」返回 `variable:xmv_10` 的实测值和同一 100 点曲线。两个异常窗统一引擎各有 56 个路径步、13 条不同源边；逐步核对了实际 Neo4j 源边 ID、方向／反向标记和连续性。依据关联到**路径**而非把一条边标作独立因果证明。

RootKGD 使用 `rootkgd-host-channel.v2` 投影和完整 52 维实测残差贡献，比较传播结构，**不执行**温度阈值或联合条件。正常门假时向量可用但不排序；两个异常窗的反应器两候选结构分各并列 **0.585447** 和 **0.575633**，冷凝器第二分别 **−0.002636**、**−0.001021**。每异常窗有 8 条结构路径、64 步、25 条不同实际源边，连续性同样核对。分数不是概率，也不因排名区分两个反应器原因。

## 两个单值反事实：另一条件没有被异常门补足

对 161–260 的离线 Frame 副本，固定其它观测、正常参考和图，每次只改一个类型化 `mean_z`：

| 唯一改动 | 哪条联合条件失配 | 完整支持结果 |
| --- | --- | --- |
| XMV10 从 +7.172193 改为 −7.172193 | 调节量不是正偏移，绝对值大仍不够 | `no_match`，0 入榜、0 支持路径 |
| XMEAS9 从 −0.077194 改为 +2.5 | 受控温度不再近参考，暖出口仍不达 +2 | `no_match`，0 入榜、0 支持路径 |

这是规则对实际输入的单值敏感性检查，不是另一次过程测量、物理干预或故障准确率评估。没有修改实际 Frame、保存的 Run 或默认历史图。复验：

```bash
cd backend
uv run --offline --no-sync pytest -q tests/test_public_tep_cascade_demo.py
```

实屏、实际任务事件与完整原始响应在 Git 忽略的 `backend/runs/tep_public_full_chain/`。依次查看 `03b-completed-source-task-events.png`、`05-edit-tep-channel-aliases.png`、`07-tep-raw-52-backbone-curves.png`、`09-human-cascade-full-package-edit.png`、`12-tep-joint-cascade-proof.png`、`13-tep-same-window-saved-path.png`、`14-tep-path-to-xmv10-and-window.png`、`finalFrame-backbone-skipped.png`。
