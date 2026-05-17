# RootLens User Study Package

## 1. 目标

这套文档用于为 RootLens 设计一套 **可直接执行、可回写论文第 6.4 节、且符合当前前端真实边界** 的 user study / expert-feedback study。

本 study 的定位不是验证“系统已经证明了真实因果根因”，而是验证：

- RootLens 是否比孤立 detector 输出更利于跨源证据理解；
- 是否能让 analyst 更容易检查 evidence -> entity -> path -> candidate 的链路；
- provenance、consistency、correction 和 bounded feedback 是否真的帮助 review；
- `/materials` 的轻量策展能力是否适合 source-grounded KG review。

## 2. 当前边界

设计以 `src/doc/backend-integration-current.md` 为真值，并绑定当前前端三大页面：

- `/evidence`：上传 / 回放、case 与 observation 浏览、过滤、详情与跨页跳转
- `/graphs`：总图谱、path graph、候选根因、trace、provenance、review ledger
- `/materials`：material library、抽取、构图结果、QA、review queue、draft preview

需要明确告诉参与者：

- RootLens 当前输出的是 `candidate/plausible explanation only`
- 反馈是 **append-only bounded review state**
- 当前前端 **不会** 因用户反馈自动修改生产 KG

## 3. 建议使用方式

优先采用 **replay-first** 的受控执行方式：

- 正式 study：使用为论文准备的稳定 replay bundle
- pilot / dry run：可以直接使用仓库里已有案例

推荐把 study 分成两层：

- `Pilot`：先检查脚本、问卷、页面引导和案例是否顺手
- `Formal expert feedback`：用于论文第 6.4 节

## 4. 当前仓库可直接用于 Pilot 的案例

这些案例已经出现在当前仓库的 mock / generated 资产里，适合先跑小规模排练：

- `tep_0001`
- `wafer_0001`
- `mvtec_fixture_clean_scratch`
- `mvtec_noisy_0001`

它们适合验证前端工作流是否顺畅，但**不建议**直接当作论文正式 study 的唯一案例包。

## 5. 论文正式版建议案例包

为了和论文第 6 节更一致，正式 study 建议单独准备 3 到 4 组 replay pack：

- `TEP pack`
  一组成功 case + 一组 near-miss case，用于验证 ranked hypothesis 与 review workflow
- `WM811K pack`
  一组存在 consistency conflict 或 correction cue 的 case，用于验证 evidence-to-KG mismatch inspection
- `MVTec pack`
  一组 visual evidence 明确、candidate path 可解释的 case，用于验证 image-region / provenance / path review
- `Materials pack`
  一组带 review queue 的 candidate edge / build detail，用于验证 source-grounded KG curation

## 6. 文档结构

| 文件 | 用途 |
| --- | --- |
| `protocol.md` | study 设计总方案：研究问题、参与者、案例包、流程、任务和执行设置 |
| `questionnaires.md` | 招募筛选、前测、后测、总结问卷与访谈提纲 |
| `moderator-script.md` | 主持人口播脚本、任务提示、标准化追问与记录提醒 |
| `analysis-plan.md` | 如何整理定量/定性结果，并写回论文第 6.4 节 |
| `session-log-template.csv` | 记录任务完成、评分、引导次数和代表性引语的模板 |

## 7. 论文映射

| 论文主张 | 对应 study 关注点 | 对应页面 |
| --- | --- | --- |
| R1 Unified evidence | 不同模态是否能被放到同一 review 语境中比较 | `/evidence` |
| R2 Provenance / confidence / raw context | 参与者是否能说清某条线索来自哪里、有多可信 | `/evidence` `/graphs` |
| R3 Pluggable reasoning | 参与者是否把输出理解为“可审查候选”而不是事实 | `/graphs` |
| R4 Linked analysis | 是否能顺畅地从 observation 跳到 entity / path / candidate | `/evidence` `/graphs` |
| R5 Human-in-the-loop review / curation | bounded feedback 和 graph material curation 是否合适 | `/graphs` `/materials` |

## 8. 最低可用建议

如果时间有限，建议至少执行：

1. 2-4 名内部 pilot 参与者
2. 1 轮 baseline packet + 1 轮 RootLens interactive
3. 3 个核心任务：
   evidence triage、path inspection、provenance feedback
4. 1 份最终对比问卷
5. 1 段 10-15 分钟的半结构化访谈

如果正式论文阶段参与者数量不足，不建议把结果写成“严格 controlled user study”，而应写成 **expert feedback sessions** 或 **formative user study**。
