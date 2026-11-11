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
与实际LLM构图使用同一目录；`features[]` 给出 `feature_id/value_kind/unit/definition/requires_reference/allowed_values/semantic_role`。

- `allowed_values=null`：开放词汇或非类别特征，不表示空集合。`appearance.semantic_candidates` 始终开放。
- 有限值：`geometry.morphology=[linear,spot,scattered,dense]`，原始单ROI只产生前两种，外部聚合几何还可产生后两种；`geometry.location=[edge,surface]`，仅是图像网格位置；`classifier.pattern` 为独立模型的八类图案。
- 新构图的有限类别operand及绑定canonical目标不在目录中时，validation明确报告feature、unknown值与allowed值，走已有一次有界修复，不静默替换或截断。旧包未声明`allowed_values`仍可读，不回写冻结图。
- `semantic_role=diagnostic/presence_gate/context`区分具体诊断观测、通用存在门控与参考／背景。已知producer语义以共用目录为准，不能由LLM把generic字段改旗标绕过；旧图未声明时保持未指定，不回写冻结图。

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

### 候选独立诊断条件

这组操作只补一条候选局部条件，不是通用图编辑器：

- `GET /api/kg/working-graphs/{graph_id}/candidate-conditions` → `{conditions,features,subjects,zones}`。features为当前场景可产出且可比较的目录项，增加`allowed_operators`与`subject_kind=variable/focus`；subjects仅含图内已绑定的实际过程通道`{entity_id,label,external_id}`。
- `POST`同地址；请求示例如下。返回`{graph:WorkingGraphRecord,conditions:[...]}`，完成时已经保存，沿用既有图锁、自动备份、PG canonical包与Neo4j投影。
- `DELETE /api/kg/working-graphs/{graph_id}/candidate-conditions/{condition_id}`撤销本向导创建的独立束，返回同一外壳。conditions含`condition_id/predicate_id/pattern_id/expectation_rule_id/anomaly_gate_id/can_delete/delete_blocker`及原输入字段。

```json
{
  "candidate_id":"目标候选的实际ID", "label":"冷却水阀变化率条件",
  "feature_id":"statistics.slope_z", "op":"gte",
  "operand":{"kind":"number","number":0.01,"unit":"1/sample"},
  "subject_entity_id":"entity:tep_braatz.channel:xmv_10", "zone":null,
  "mode":"necessary", "description":"作者检验假设，非已验证工业规则",
  "source_assertion_ids":[]
}
```

`statistics.*`及`residual.contribution`必须选择已绑定通道；全局量／对象／ROI使用null；晶圆必须选择现有zone。未知变量、特征、单位、来源或范围明确报错，不自动制造实体或观测。可产出但图内尚未登记的特征加入目录定义，数据仍来自现有adapter。

新建诊断条件的GET仅列`diagnostic`特征，POST同样拒绝仅通用presence或主体背景的充分替代，具体错误为“不是候选区分条件”。这按目录语义分类，不按boolean类型一刀切；已有异常门仍可在原编辑器正常修改。

新增predicate与独立pattern只从目标hypothesis直接接expectation，不修改共享mechanism。pattern以ALL复用图中已有的显式`anomaly=true`门控，不复制gate增加票数；缺门控只拒绝新操作，不改变原推理入口。`mode`仅有`necessary`（不成立排除）、`expected`（不成立沿现有C计冲突）、`possible`（弱兼容、不计此期待的冲突）；不存在第四种“冲突模式”。

没有选择来源时明确保存人工`declared_demo_heuristic`，不伪造source/unit/locator。删除移除本束predicate、pattern、expectation和作者assertion，保留借用的gate、既有来源和可复用目录定义；出现额外引用就拒绝删除并说明共享依赖。下次任务使用新快照，历史run不变。

RootKGD不执行这些条件的阈值、AND/OR或mode惩罚。v2投影将同host／通道的逻辑期待集合化，并消除沿显式effect已被下游同通道期待覆盖的上游重复声明；重复同通道条件、等价pattern拆分不再制造额外信号或shortcut。新增原本未达的通道或显式effect关系仍可改变结构分数，不等于新条件结构一律无效。不同实际作用路径应通过明确mechanism/effect表达，不能靠多写逻辑pattern当成多条物理路径。

## 真实异步任务

- `GET /api/tasks?limit=50` → `{tasks:[Task]}`，最近任务优先。
- `GET /api/tasks/{task_id}?after_sequence=0` → `Task`，events 仅含 sequence 大于游标的事件。
- `POST /api/tasks/{task_id}/retry`：只对 failed/interrupted 创建**新 task**；保留原输入，不自动重试付费步骤。
- `POST /api/tasks/material-parse`，JSON `{"material_ids":["id"],"force":false}`。
- `POST /api/tasks/material-build`，JSON `{"material_ids":["id"],"dataset":"tep","title":"过程知识","capability_id":"process-window-v2","enable_when_ready":false,"max_repairs":1,"candidate_limit":null}`。每任务最多两次客户端模型请求（含一次自动修复），`max_repairs=0` 可关闭修复；首次校验错误与第二次调用均写入真实事件。source客户端关闭SDK自动传输重发；连接失败按原阶段终止，不进入知识修复，也不自动新建任务。视觉／过程建议紧凑≤16候选，默认硬上限32，`candidate_limit`可明确设1–64；wafer仍只允许声明的8个图案类。超建议只警示并完整保留，超硬限明确失败；不截断／自动合并。
- `POST /api/tasks/inference`，multipart：`file`、可选 `reference_file`、`graph_id`、`reasoner_id`、`input_mode`、`dataset`、`object_name`、`model_preset`、`semantic_mode`、`windows`、`title`、`top_k`。`windows` 为 JSON `[[1,100],[161,260]]`；一基闭区间。
- `POST /api/tasks/inference/demo`，JSON `{"sample_id":"...","graph_id":"...","reasoner_id":"unified_abduction","input_variant":"raw","top_k":5}`。`input_variant` 可选 `raw/evidence`，默认 raw。Evidence 模式只要求清单登记的 Frame；原图、网格、曲线等本地附件缺失时仍可推理，媒体状态如实返回。`supporting_assets` 的通用附件用 `frame_asset_id`；单帧附件用 `frame_case_id` 加 `case_asset_id`，避免多个窗口误共享一份数组。路径越界或把目录登记成文件仍拒绝；raw 模式仍要求原件及 TEP 正常参考。

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

这是两页唯一的任务提交合同。旧 `POST /api/runs/upload`、旧运行模型预设／下载、素材同步提取／构图、旧 `/api/kg/construction/*` 和旧草稿 HTTP 路由已退役。素材登记用 `/api/kg/materials/upload` 或 `/api/kg/materials/register-url`。已存旧 Run 的 GET、附件与回放仍供图谱历史使用；旧构图产物留在原路径，由离线工作流读取。

- `GET /api/kg/materials` 默认只列活动素材；`?archived=true` 只列已移出素材。记录的 `archived_at` 为 `null` 或移出时间。
- `POST /api/kg/materials/{material_id}/archive` 和 `/restore` 返回 `{status, material, note}`。移出和恢复不改原文件、提取结果或历史图谱来源；详情、片段和处理记录仍可按原 ID 读取。
- 排队或运行中的素材任务阻止移出（HTTP 409）；已移出素材要先恢复，才能新建或重试提取与构图任务。

升级既有库时，素材存储首次访问按需增加可空的 `archived_at` 列，已有记录保持活动。更新后端进程即可载入新路由；既有库不运行 `backend:init`。

Source Blueprint将presence/context条件提到ALL前置，原ANY或at_least仅作用于具体diagnostic atoms；ALL只等价重组。ANY/at_least收紧写入`authoring_normalizations`并在实际validation事件展示`semantic_change=true`；at_least计数不能满足剩余诊断项时明确失败，不猜替代count。纯门控签名与canonical JSON绕过均拒绝，每条支持proof必须包含具体诊断观测。`appearance.defect_present=true`不能单独证明Finish、部位或制造原因。

## 保存分析

- `GET /api/analyses` → `{runs:[AnalysisRunSummary]}`；不返回完整 cases 或知识快照。`outcome_counts` 按已保存 Frame 结果统计；明确的 `no_match`／`normal_reference_gate_is_false` 单独进入 `normal_gate_count`，不再计入 `no_match`。未保存结果时省略两项。
- `GET /api/analyses/{run_id}` → `AnalysisRun`；任务完成后用它载入。
- `GET /api/analyses/{run_id}/evidence`：下载本次实际生成的 `{frames:[...]}`，可按 `input_mode=evidence` 重新上传；不重跑 backbone/LLM。
- `GET /api/analyses/{run_id}/artifacts/{name}`：原图／mask／heatmap／输入等实际文件。
- `GET /api/demo-library` → `{samples:[{sample_id,title,dataset,input_mode,description,source,available,...}]}`，仅列受管的公开演示资产。
- 同时返回 `demos[]`（分组素材、图包、样本、配套数组、模型及来源）；每个资产有 `asset_id/download_url/available`。
- 每个group、嵌套sample及平铺sample都有`graph_ref`：`{graph_id,title,state,ready,enabled,available,note,asset_id,download_url,candidates}`。`state=ready/disabled/missing/ambiguous/unavailable`；只有`ready`且`available=true`可在无明确选图意图时自动使用。匹配读取注册图包与现存canonical知识，除graph身份外完整内容必须相同；原包身份只有内容仍相同时优先，否则只选唯一启用匹配，多份无法确定则ambiguous，不按latest／同场景猜。GET不导图、不启用或覆盖图；registry不可读明确unavailable，白名单资产下载仍独立可用。
- 推荐样例在前端只覆盖隐式默认选图；用户手选／route明确的图保留，并提示与配套图不同及切换动作。缺配套图时提示导入／启用或明确选图，不以最新启用的严格源图替代就绪演示图；源图对照仍可显式选择。
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
      "case_id":"...", "outcome":"supported", "scoring_method":"tep_rootkgd_propagation_v2",
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

当前`scoring_method=tep_rootkgd_propagation_v2`，`propagation.projection_version=rootkgd-host-channel.v2`。`propagation.projection`给出显式effect边数、规范host／通道集合边数、上游冗余链接数及每条链接的主来源／备选来源；保留真实effect方向和原传播／评分函数。主路径`source_edge_views`始终是实际源边组成的连续路径，`top_k_paths[].source_path_alternatives`单独保留等价或上游冗余声明的完整候选→通道源路径，不伪接到主路径。旧run保持原投影与分数；没有版本字段时仅显示“未记录”。

### 本次知识可分辨性与观测覆盖

新任务的每项`cases[].results[]`保存`authoring_diagnostics`（`schema_version=rootlens-candidate-discriminability.v1`），严格由该run的知识快照、Frame和实际推理结果生成，不改变候选或分数。历史run没有此字段时显示“未生成”，GET不会拿当前工作图补算。

- `grouping_status=available/unavailable/incomplete`与`issues[]`说明诊断是否完整；搜索预算不足不把有效推理任务变失败。
- unified的`grouping_basis=reachable_expectation_conditions`：`equivalence_groups[]`按可达`(pattern_id,mode)`签名分组；不同假设cost仍可同组，`cost_priors`单独显示先验，不能将分数差误认为数据区分。
- RootKGD只用该次实际完整通道向量和评分分解分组，`grouping_basis=actual_structural_projection`；缺输入为`structural_inputs_unavailable`，不拿逻辑条件组替代传播评分。
- `evidence_usage`保留总观测、已观测、条件grounding数与真实评分输入数，并列出`unreferenced_features`和`not_scored_features`。`condition_reference_status`与`score_input_status`区分完整、未知、正常门控未排名，未知不冒充0覆盖。
- `candidate_checks`列出本次已有expectation/predicate checks；RootKGD明确`condition_checks_used_for_score=false`，这些条件仅供作者检查，不影响传播分数。

## 存储与运行

任务和新分析使用指定 PG 的增量表，不重建既有表；输入／构图产物保留在 `backend/runs/two_loop_tasks`。工作图继续 PG canonical 包＋Neo4j 隔离投影。API 仍运行 8012，仅使用独立 PG 55433／Neo4j 57687，不操作普通库。

本轻量 worker 部署为一个 API 进程、两个线程任务 worker；不使用多进程 Uvicorn workers。新的任务服务第一次访问会把旧进程遗留的 queued/running 标为 interrupted，不自动重算。新知识制作的视觉默认硬预算为32候选／8签名／每签名32假设，过程为32／12／32，wafer为8／8／1；视觉／过程可显式调候选／每签名硬限到64。建议规模与结构硬限分开，报告保留二者。推理器原128候选、256分支、2048组合、1024状态搜索预算不改，耗尽仍明确search_incomplete。

本机8012演示服务改由手动加载的launchd会话作业 `com.rootlens.dev.two-loop-api` 管理，不依赖agent exec会话，不配置登录／开机自启。`backend/scripts/development_api.py` 提供 `start/status/stop/health --name two-loop-api`，启动8012时加 `--port 8012`；日志、PID记录与恢复命令见 [后端运行记录](../../backend/docs/two-loop-backend.md#0239-断连恢复进程归-launchd不归临时执行会话)。

本机隔离容器已存在但停止时，先确认 Docker 运行，从仓库根目录执行 `docker compose -p rootlens-mvtec-m1-test -f backend/compose.test.yaml start --wait postgres neo4j`，然后启动上述命名作业。该命令只启动既有容器，不建库或重建卷。服务起来后在 `backend/` 执行 `uv run --offline --no-sync python scripts/smoke_rootlens_dashboard.py` 检查两页实际读取。

复算除同一知识快照／reasoner外，还需保留 `run.input_snapshot.top_k` 等选项（本轮demo为8）；默认5会少返回部分候选和路径。RootKGD 的 `propagation.scoring_input_obs_ids` 列出所有52个实际评分输入，不将未展示路径的贡献误标为unused。
