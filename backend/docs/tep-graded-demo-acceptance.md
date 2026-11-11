# TEP 分级验收：反应器补偿与冷凝侧联合响应

2026-11-11，使用独立 RootLens 演示环境 `5188 → 8027`，完成一条新来源到工作图、两条真实原始输入到原生 Frame 复算。两条序列用同一图和独立 `d00` 正常数据，不用样本标签。发布物、固定数据版本与无密钥复算见 [TEP 演示包](../data/demo/graded_rca/tep/README.md)。

## 从来源制作到启用：模型生成与人工判断分开

1. 实际上传 [3,607 字节自著短材](../data/demo/graded_rca/tep/material.md)。提取 `task_c2843e650c624a90bcaaab65b5aad1d1` 返回 `su_9df3cbf8e23e6ddb`。以 `process-window-v2` 制作，`task_f681d68789dc472c8935d829a3aa88ad` 实际调用一次 `deepseek-flash`（8,252 tokens，0 修复）。三条签名都已由编译器绑定实际通道、窗口与异常门：暖出口、反应器温度近参考、冷凝侧调节／出口／分离器波动。
2. 从该任务打开[确切图](http://127.0.0.1:5188/graphs?graph=graph_c5d48f1204984c4fb213d47df95796ae)，修改 `XMV10` 显示名称与别名，完整包和 Neo4j 回读确认只是该实体行改变。初版图 **100 节点、70 条边**，默认不启用。
3. 上传并提取[人工曲线与 OR 依据](../data/demo/graded_rca/tep/expert-refinement.md)，提取 `task_45ec0b8bead2403c97a486aee105699b`、来源 `su_9a760cefadeb6fd4`；未再调用文本模型。在同一图的完整包编辑中，保留旧两反应器签名，但用**一条引用两者的 OR 期望**替换两条并列 `expected`，不在补偿成立时再扣未出现的暖出口。增加六个同窗同源槽、明确曲线和锚点，冷凝侧三项保留联合检查。保存 **104 节点、74 条边**，Neo4j 回读精确原边 ID，浏览器完整导出与后端包一致，再显式确认启用。

反应器外环 `CONTRL18` 读 XMEAS9 调内环给定，`CONTRL10` 才用 XMEAS21 更新 XMV10；冷凝侧 `CONTRL11` 读汽提塔底物流量 XMEAS17，不是同一结构。[反应器外环](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f#L1192-L1204)、[内环](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f#L905-L917)、[冷凝侧控制程序](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/temain_mod.f#L944-L958)。原过程还分开 XMV 命令与 VPOS 阀位状态，现有 Frame 没有真实阀位，不诊断阀卡滞。[阀动态方程](https://github.com/camaramm/tennessee-eastman-profBraatz/blob/0643318858ce7c87292bd59820b459e12a13d009/teprob.f#L791-L805)。

曲线在新原始运行前已保存启用。独立 `d00` 的五个正常 100 点窗中，XMV11／XMEAS22 最大绝对均值偏移 **0.1775／0.1505**，XMEAS11 最大波动 **1.1670**。这只为中性区定尺度；曲线端点是 `declared_demo_heuristic`，不是设备规格或统计置信限。d05 是此前已归档的对照，不是新盲测。每个唯一槽权重 1/6；XMEAS9 上下界共享一槽，异常门不计分。

## 原始、普通上传与同帧 RootKGD

两组原始样本使用中性上传名并验证留存字节与固定公开上游相同。独立 `d00` 的内容相同，但两个原始任务各自拟合并保存独立参考 ID。各窗 100 点、一基闭区间、间隔 180 秒，保留 52 条曲线、52 维残差贡献和 263 个类型化观测。每个原始 Run 下载本次 Frame 后普通上传，不再拟合或测量；同图、同解释器、同 Top K=8 的 **Frame、工作图快照、全部 `cases[].results` 和逐窗原始曲线逐字段相同**。包内 JSON 是真实浏览器下载和导出，不重写测量或媒体引用。

| 现场输入 | 原始 Run | 普通 Frame 重传 |
| --- | --- | --- |
| d04：1–100、161–260、261–360 | [序列 A 原始](http://127.0.0.1:5188/evidence/runs/5b722359-8a61-4daf-9ec4-d761421f89fb) | [三窗精确复算](http://127.0.0.1:5188/evidence/runs/b735f37e-27a6-4c95-a15f-21967e2a4ee0) |
| d05：161–260 | [序列 B 原始](http://127.0.0.1:5188/evidence/runs/2c95491d-dc32-4c6f-929a-669d74dc9bec) | [单窗精确复算](http://127.0.0.1:5188/evidence/runs/92379183-f7b9-49de-bd1c-f7383dea9557) |

d04 的 1–100 窗异常门为假，无候选路径；两个后窗，`XMV10=+7.172193/+7.059684`，`XMEAS9=−0.077194/+0.051463`，`XMEAS21=+0.085717/+0.279431`。暖出口没有支持，选中的是同一窗口的补偿分支；「反应器供冷侧入口冷却水偏暖」和「反应器过程侧放热负荷增加」均第 1，`P=S=1/3, C=0, V=1`。两个界同一测量，仍只有两个诊断槽支持。

d05 实测 `XMV11 mean_z=+1.403320`、`XMEAS22 mean_z=+1.804141`、`XMEAS11 std_z=7.044734`，贡献分别 **+0.100369、+0.144905、+0.166667**。两个冷凝候选共享证据，均第 1，`P=S=0.411940, C=0, V=1`。本窗实际 `XMV10=−0.335815`，在反应器另一评估下产生反证贡献 **−0.009535**；近参考的 XMEAS9 仍正，但只有一项诊断量获得净支持，所以反应器候选不进入「有支持」或「待核验」。

同一 d04 Frame 另用一次 [RootKGD 普通 Evidence](http://127.0.0.1:5188/evidence/runs/c3e61701-a503-451e-b29b-864f45a17bb1)。`rootkgd-host-channel.v2` 正常窗不排序，两个异常窗实际使用 52 维贡献；反应器两候选结构分各 **0.585447 / 0.575633** 并列首位。它不运行有符号阈值，不与分级分混排，也未区分该对原因。

## 同一 d05 Frame：变化来自新知识，不只来自公式

| 图与解释器 | 真实 Frame 的离线对照 |
| --- | --- |
| 旧图／统一条件溯因 | `no_match`，无推荐 |
| 旧图加阶段 A 曲线／分级解释溯因 | `insufficient_evidence`，无推荐 |
| 本轮图／统一条件溯因 | 冷凝两个解释并列 |
| 本轮图／分级解释溯因 | 同一对并列；量化各条件贡献和反应器反证 |

不比较不同拓扑和预算的 S。再对**离线副本**只改 XMEAS11：将波动从 7.044734 改为正常附近 1.0，冷凝两候选降为待核验，S 由 0.411940 变为 0.245273，V 仍是 1；把这一项标为缺测，S 相同但 V 变为 2/3。没有增加反证，也没有修改任何真实 Frame。新增波动量确实决定支持等级；这个对照不是过程干预或工艺诊断准确率。

## 回到实际曲线

d05 从分离器温度波动条件定位到本次保存的 `INPUT_OF` 原边，再到同一 XMEAS11 `statistics.std_z` 观测和样本 **161–260、100 点**的真实曲线。图谱实屏的 **12 条边**与保存源边集合完全一致；d05 共 8 条贡献／前置路径，d04 两个异常窗各 6 条。逐步比对 Neo4j 原边端点、关系和方向，路径标识为贡献，不当完整布尔证明。反应器未入榜的 XMV10 反证也能定位到同窗实测，不为它补一条不存在的图路径。

[公开验收摘要](../data/demo/graded_rca/tep/verification.json)记录完整任务／Run ID、保存真值、来源和路径。详细响应和实际实屏在 `backend/runs/tep_graded_full_chain/`（Git 忽略），重点 `09-d05-graded-three-cooling-cues.png`、`10-d05-graded-actual-source-edge.png`、`11-d05-source-to-actual-curve.png`、`12-d05-unranked-reactor-negative.png`、`13-d04-graded-cascade-compensation.png`。定向复验：

```bash
cd backend
uv run --offline --no-cache --no-sync pytest -q tests/test_public_tep_graded_demo.py
```
