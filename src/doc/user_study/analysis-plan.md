# RootLens User Study Analysis Plan

## 1. 目标

本文件定义如何把 session 记录、问卷和访谈整理成 **论文可写、但不过度外推** 的结果。

研究结论应聚焦：

- cross-source evidence sensemaking
- provenance-aware hypothesis inspection
- bounded feedback suitability
- lightweight KG curation usefulness

避免把主观反馈写成：

- causal correctness evidence
- detector performance evidence
- production deployment proof

## 2. Data Sources

每位参与者建议收集以下数据：

- 任务耗时
- 任务完成情况
- 主持人 rubric 评分
- 条件后量表
- 最终比较问卷
- think-aloud 录音转写
- 访谈纪要
- 屏幕录像中的关键操作片段

## 3. Primary Quantitative Measures

### 3.1 任务层指标

| 指标 | 说明 | 记录方式 |
| --- | --- | --- |
| Completion | 是否完成任务 | `0/1` |
| Time on task | 从读题到给出答案的时长 | 秒 |
| Assistance count | 主持人标准化提示次数 | `0/1/2+` |
| Confidence rating | 参与者对自身答案把握 | `1-7` |

### 3.2 Rubric 评分

建议由两名研究者独立评分，分歧再协商。

#### R-A: Evidence grounding score

- `0`：无法指出关键 observation，或只复述表面标签
- `1`：指出了 observation，但来源、置信度或 raw context 解释不完整
- `2`：能清楚指出 observation，并说明其来源、可靠性与下一步意义

#### R-B: Hypothesis inspection score

- `0`：只能说出候选名字，无法解释为什么被提出
- `1`：能部分描述 candidate 与 path，但缺少 evidence 或 graph 支撑
- `2`：能清晰描述 evidence -> entity -> path -> candidate 的链路

#### R-C: Claim-boundary calibration score

- `0`：把 candidate 当成已验证结论
- `1`：口头承认不确定性，但没有指出具体边界
- `2`：明确指出“候选 / plausible explanation only”，并说明仍需验证的部分

#### R-D: Review action score

- `0`：无法给出 accept / reject / hold decision
- `1`：给出 decision，但理由泛泛
- `2`：decision 与 provenance、mismatch 或 uncertainty 有清晰对应

#### R-E: Curation rationale score

仅用于 `/materials` 任务：

- `0`：只根据 edge 名字或直觉判断
- `1`：参考了部分 source 信息，但未形成完整理由
- `2`：明确基于 source-grounded material / preview / queue 信息做出判断

## 4. Questionnaire Analysis

### 4.1 推荐汇总方式

由于样本量通常不大，建议以描述性统计为主：

- 均值
- 中位数
- 四分位范围
- 参与者角色分组对比

### 4.2 可重点观察的题目

最终比较问卷中建议重点报告：

- 跨源证据比较是否更容易
- 是否更容易区分 evidence 与 candidate
- provenance 是否帮助 review
- claim boundary 是否清楚
- append-only feedback 是否合适

### 4.3 统计表达建议

如果 `n < 10`，优先写：

- `most participants reported`
- `participants generally found`
- `median ratings suggested`

不建议写：

- `significantly improved`
- `proved`

## 5. Qualitative Coding Scheme

建议围绕以下 5 个主题编码。

### Q1 Cross-source integration

正向信号：

- 参与者主动比较 image、time series、log 或 document cue
- 参与者认为 unified evidence 让 case context 更完整

负向信号：

- 参与者仍需要在多个外部材料间来回跳
- 不同模态被看成互不相关的碎片

### Q2 Provenance usefulness

正向信号：

- 参与者明确引用 source、snippet、artifact 或 edge provenance 做判断
- 参与者表示 provenance 帮助沟通或复核

负向信号：

- provenance 被认为是噪声或装饰信息
- 参与者虽然看到 provenance，但并不依赖它

### Q3 Boundary awareness

正向信号：

- 参与者自发使用“候选”“待验证”“plausible”之类措辞
- 参与者指出哪些部分仍需人工确认

负向信号：

- 参与者直接把 top candidate 当结论
- 参与者误以为 accept 会自动改写 KG

### Q4 Workflow continuity

正向信号：

- 参与者觉得 `/evidence` -> `/graphs` 的上下文保持自然
- 参与者觉得 selected case / observation 的保留减少了切换成本

负向信号：

- 参与者经常失去上下文
- 参与者不能理解某个高亮或候选从何而来

### Q5 Review-oriented curation

正向信号：

- 参与者接受 bounded review 与 append-only ledger
- 参与者能理解 `/materials` 是轻量策展台而不是 full editor

负向信号：

- 参与者强烈希望直接写回图谱
- 参与者认为 review target 语义不清

## 6. Recommended Figures and Tables

### 6.1 表格

建议至少输出 2 张表：

1. 参与者背景表
2. 任务与问卷结果汇总表

### 6.2 图

若需要图形化表达，可选：

- baseline vs RootLens 的关键 Likert 维度条形图
- 不同角色组的雷达图
- 任务 rubric 的箱线图或散点图

如果样本太小，也可以不用复杂图形，直接用表格和代表性引语。

## 7. Suggested Paper Write-up Template

下面给出适合写进论文第 6.4 节的模板句式。

### 7.1 Participants and Procedure

> We conducted `N` expert-feedback sessions with participants from `roles`.  
> Each session lasted approximately `X-Y` minutes and compared a baseline packet of isolated detector outputs with the RootLens workflow using replayed cases from `domains`.  
> Participants completed evidence-triage, hypothesis-inspection, and provenance-feedback tasks, and `K` participants additionally completed a lightweight KG curation task in the materials workspace.

### 7.2 Findings

> Across sessions, participants generally reported that RootLens made cross-source observations easier to organize into a case-centered review context.  
> They particularly valued `observation detail / provenance / trace / ledger`, which helped them explain why a candidate path was suggested rather than treating it as a verified causal conclusion.  
> Several participants also noted that the append-only review model matched their expectation for controlled RCA review, although `insert limitation here`.

### 7.3 Limitation Statement

> We do not interpret these sessions as evidence of causal correctness or production deployment readiness.  
> Instead, the feedback supports the claim that RootLens improves the inspectability, traceability, and reviewability of candidate RCA outputs.

## 8. Validity and Risk Notes

### 8.1 样本量小

如果人数少，应明确是 formative / expert feedback。

### 8.2 参与者偏内部

如果大多为内部研究成员，应在论文里写清楚，并避免过强普适性结论。

### 8.3 学习效应

由于推荐采用 baseline 在前，仍需在论文里说明：

- 通过轮换 domain 顺序来缓解
- task case 尽量用同类但不完全相同的案例

### 8.4 案例偏 replay

应说明 study 主要验证 analyst-facing workflow，而不是实时线上运行环境。
