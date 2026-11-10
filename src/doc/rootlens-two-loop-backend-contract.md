# 双闭环 API 契约

2026-11-11。本轮 UI 消费下列接口；推理只使用明确选择且已启用的 v2 工作图。

## 图谱

保留 `GET /api/kg/working-graphs` → `{graphs:[{graph_id,title,dataset,status,enabled,knowledge,...}]}`。
`status=ready` 表示可执行包已校验并持久化；`enabled=true` 表示可供新分析选择。

- `GET /api/kg/working-graphs/{graph_id}/package`：完整 `rootlens-working-graph.v2` 包。
- `POST /api/kg/working-graphs/import`：导入新图，默认未启用。
- `PUT /api/kg/working-graphs/{graph_id}/package`：修改同一图，保存前自动备份；历史 run 不重算。
- `POST /api/kg/working-graphs/{graph_id}/enable`，JSON `{ "enabled": true }`：启用／停用。
- `GET /api/reasoners`：`{reasoners:[{reasoner_id,title,datasets,description}]}`；ID 固定 `unified_abduction`、`tep_rootkgd`。

### 制作能力与词汇绑定

`GET /api/authoring/capabilities` → `{capabilities:{mvtec:CapabilityManifest,tep:CapabilityManifest,wafer:CapabilityManifest}}`。
与实际LLM构图使用同一目录；`features[]` 给出 `feature_id/value_kind/unit/definition/requires_reference/allowed_values`。

- `allowed_values=null`：开放词汇或非类别特征，不表示空集合。`appearance.semantic_candidates` 始终开放。
- 有限值：`geometry.morphology=[linear,spot,scattered,dense]`，原始单ROI只产生前两种，外部聚合几何还可产生后两种；`geometry.location=[edge,surface]`，仅是图像网格位置；`classifier.pattern` 为独立模型的八类图案。
- 新构图的有限类别operand及绑定canonical目标不在目录中时，validation明确报告feature、unknown值与allowed值，走已有一次有界修复，不静默替换或截断。旧包未声明`allowed_values`仍可读，不回写冻结图。

人工绑定继续通过完整包 `knowledge.value_bindings` 新增／删除，再PUT保存。每项为：

```json
{
  "binding_id":"alias:legacy-scratch", "feature_id":"appearance.semantic_candidates",
  "external_value":"LegacyScratch", "canonical_value":"scratch",
  "procedure_model_id":null, "source_assertion_ids":["source:glossary"]
}
```

来源ID必须存在。映射只在同feature及指定模型（null表示全局）内生效，原观测及`actual_values`不改写，事实记录`applied_value_binding_ids`。保存／删除后下一次分析生效；历史运行与已编译快照不变。

LLM Blueprint也可提供`value_bindings[]`：`binding_key/relation=equivalent/feature_id/external_value/canonical_value/procedure_model_id/assertion`；assertion只允许`origin=source_explicit`，由编译器保留实际source ID、unit ID与locator。没有明确等价来源就留空，不把相似、上位词或缺失部位当等价，尤其不将`cracked_or_missing_glass`补成具体`broken_finish/chipped_finish`。代码校验来源身份与可执行类型，等价语义仍需作者据来源判断。

## 真实异步任务

- `GET /api/tasks?limit=50` → `{tasks:[Task]}`，最近任务优先。
- `GET /api/tasks/{task_id}?after_sequence=0` → `Task`，events 仅含 sequence 大于游标的事件。
- `POST /api/tasks/{task_id}/retry`：只对 failed/interrupted 创建**新 task**；保留原输入，不自动重试付费步骤。
- `POST /api/tasks/material-parse`，JSON `{"material_ids":["id"],"force":false}`。
- `POST /api/tasks/material-build`，JSON `{"material_ids":["id"],"dataset":"tep","title":"过程知识","capability_id":"process-window-v2","enable_when_ready":false,"max_repairs":1}`。默认最多两次模型调用（含一次自动修复），`max_repairs=0` 可关闭修复；首次校验错误与第二次调用均写入真实事件。第二次失败就停止，不自动新建任务。
- `POST /api/tasks/inference`，multipart：`file`、可选 `reference_file`、`graph_id`、`reasoner_id`、`input_mode`、`dataset`、`object_name`、`model_preset`、`semantic_mode`、`windows`、`title`、`top_k`。`windows` 为 JSON `[[1,100],[161,260]]`；一基闭区间。
- `POST /api/tasks/inference/demo`，JSON `{"sample_id":"...","graph_id":"...","reasoner_id":"unified_abduction","input_variant":"raw","top_k":5}`。`input_variant` 可选 `raw/evidence`，默认 raw。

`input_mode`：`evidence`=原生 EvidenceFrame JSON（单个／数组／`{frames:[...]}`）或旧结构化 Evidence；`records`=adapter records JSON/JSONL；`image`=MVTec 原图；`process`=52通道 dat/csv + 正常 `reference_file`；`wafer`=原生 0/1/2 网格 JSON（单个网格或带 `wafer_map` 的对象）。不允许用文件名／原生标签当推理答案。

```json
{
  "task_id":"task_...", "kind":"inference", "status":"running",
  "title":"过程分析", "created_at":"...", "updated_at":"...",
  "stage":"measurement", "stage_label":"测量与 Evidence",
  "progress":{"completed":1,"total":3,"unit":"窗口","indeterminate":false},
  "events":[{"sequence":3,"at":"...","stage":"measurement","label":"完成窗口 1–100","completed":1,"total":3,"unit":"窗口"}],
  "result":null, "error":null, "retry_of":null
}
```

`status` 为 `queued/running/completed/failed/interrupted`。`failed` 保留 `error={stage,message,type}`；重启后未完成任务变 `interrupted`，不会永远转圈。LLM 阶段 `progress.indeterminate=true`，不伪造百分比。结果：parse 为 `{material_ids}`，build 为 `{graph_id,build_id}`，inference 为 `{run_id}`。

素材上传／URL 注册／列表／chunks 沿用 `/api/kg/materials` 系列；解析改走异步任务。构图任务自动完成解析（仅缺失时）、LLM、自动校验、确定性编译与隔离工作图装载；无需人工审核门。

## 保存分析

- `GET /api/analyses` → `{runs:[AnalysisRunSummary]}`。
- `GET /api/analyses/{run_id}` → `AnalysisRun`；任务完成后用它载入。
- `GET /api/analyses/{run_id}/evidence`：下载本次实际生成的 `{frames:[...]}`，可按 `input_mode=evidence` 重新上传；不重跑 backbone/LLM。
- `GET /api/analyses/{run_id}/artifacts/{name}`：原图／mask／heatmap／输入等实际文件。
- `GET /api/demo-library` → `{samples:[{sample_id,title,dataset,input_mode,description,source,available,...}]}`，仅列受管的公开演示资产。
- 同时返回 `demos[]`（分组素材、图包、样本、配套数组、模型及来源）；每个资产有 `asset_id/download_url/available`。
- `GET /api/demo-library/assets/{asset_id}`：白名单资产下载，`Content-Disposition` 明确保留真实安全文件名与后缀（例如 `.jsonl`），可原名重新上传。
- `POST /api/demo-library/{demo_id}/materials`：把原始资料实际登记到素材库，返回 `{materials:[...]}`；不偷偷导入预制图。重复点击复用同一素材，不覆盖原文件。

```json
{
  "run_id":"...", "title":"过程窗口", "created_at":"...", "status":"completed",
  "dataset":"tep", "input_mode":"process", "reasoner_id":"tep_rootkgd",
  "graph_id":"...", "graph_title":"过程知识", "case_count":2,
  "cases":[{
    "case_id":"...", "display_name":"样本 161–260", "evidence_frames":[{}],
    "results":[{
      "case_id":"...", "outcome":"supported", "scoring_method":"tep_rootkgd_propagation_v1",
      "ranked_root_causes":[], "grounded_facts":[], "candidate_evaluations":[],
      "proof_graph":{}, "unused_observation_ids":[]
    }],
    "generated_evidence":{}, "visual_evidence":[], "observation_locations":[]
  }],
  "working_graph_snapshot":{}, "artifacts":{}
}
```

unified 结果保留当前 `UnifiedReasoner.analyze` 的完整结果（U/C/A/J、支持／冲突／缺失、来源 ID、联合证明）。RootKGD 结果沿用相同外壳但 `scoring_details` 为余弦、贡献覆盖、传播熵等分解，绝不把该分数标成概率。每条路径提供显示名、实际 source assertion、obs IDs 与 scope/asset 定位。Frame 原始字段完整保存，页面以中文显示名默认呈现、稳定 ID 用于引用。

每个 case 另有 `media_status=available/not_attached` 与 `media_note`。普通 Frame 上传只含 URI 时不会任意读取本机路径或抓取 URL；未关联受管媒体则明确显示“只有统计与引用，原始媒体未附带”，数值推理仍执行。Demo 与本次原始分析登记的实际资产可关联：`visual_evidence[].url` 为图片／mask 预览，`process_trends=[{channel,samples}]` 为完整通道曲线，`wafer_map` 为原网格。`evidence_download_url` 指向本次 Frame 下载。

RootKGD `scoring_details` 固定给出 `cosine_similarity / covered_contribution_mass / uncovered_contribution_mass / propagation_entropy / active_channel_count / coverage_penalty / entropy_penalty / structural_score / observed_channel_vector[52] / propagated_channel_vector[52] / channel_order`，实际复用原 `ranking_score`：`cosine - 0.12*covered_mass - 0.03*entropy`。没有旧 memory 或按 fault family 的加分。`propagation.graph_channel_coverage` 明示图上不可达通道与其残差贡献质量。

## 存储与运行

任务和新分析使用指定 PG 的增量表，不重建既有表；输入／构图产物保留在 `backend/runs/two_loop_tasks`。工作图继续 PG canonical 包＋Neo4j 隔离投影。API 仍运行 8012，仅使用独立 PG 55433／Neo4j 57687，不操作普通库。

本轻量 worker 部署为一个 API 进程、两个线程任务 worker；不使用多进程 Uvicorn workers。新的任务服务第一次访问会把旧进程遗留的 queued/running 标为 interrupted，不自动重算。新知识制作的视觉预算为16候选／8签名／每签名16假设，过程为16／12／16，超过会明确列出 actual/allowed，不截断。

本机8012演示服务改由手动加载的launchd会话作业 `com.rootlens.dev.two-loop-api` 管理，不依赖agent exec会话，不配置登录／开机自启。`backend/scripts/development_api.py` 提供 `start/status/stop/health --name two-loop-api`，启动8012时加 `--port 8012`；日志、PID记录与恢复命令见 [后端运行记录](../../backend/docs/two-loop-backend.md#0239-断连恢复进程归-launchd不归临时执行会话)。

复算除同一知识快照／reasoner外，还需保留 `run.input_snapshot.top_k` 等选项（本轮demo为8）；默认5会少返回部分候选和路径。RootKGD 的 `propagation.scoring_input_obs_ids` 列出所有52个实际评分输入，不将未展示路径的贡献误标为unused。
