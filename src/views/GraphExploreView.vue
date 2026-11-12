<script setup lang="ts">
import { Modal } from "@arco-design/web-vue";
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import type {
  PathGraphPath,
  ReviewLedgerRecord,
  ReviewTarget,
  RunCaseDetail,
  RunDetail,
  RunSummary,
} from "@/api/contracts";
import type { UnifiedGraphDataset } from "@/types/graph";
import ConstructionGraphPreview from "@/components/graphs/ConstructionGraphPreview.vue";
import KnowledgeForceGraph from "@/components/graphs/KnowledgeForceGraph.vue";
import GraphEditor from "@/components/knowledge/GraphEditor.vue";
import SourceTrail from "@/components/provenance/SourceTrail.vue";
import VisualEvidenceViewer from "@/components/evidence/VisualEvidenceViewer.vue";
import ObservationSignal from "@/components/evidence/ObservationSignal.vue";
import { useAppPreferences } from "@/services/app-preferences";
import { useWorkbenchState } from "@/services/workbench-state";
import {
  getRootLensService,
  canSubmitReviewTargetType,
} from "@/services/rootlens-service";
import {
  getLocalSessionEventName,
  getLocalSessionMeta,
  getStoredImportedGraphs,
  loadUnifiedGraphs,
} from "@/services/rootlens-data";
import {
  buildKGStudioDataset,
  candidateExplanationPaths,
  matchKnowledgeEdges,
  uniqueRootCauseCandidates,
} from "@/services/graph-workspace";
import { buildPathSubgraphDataset } from "@/services/graph-curation";
import { applyGraphPatch, type GraphPatch } from "@/services/graph-editor";
import {
  buildObservationBrowseItems,
  selectVisualEvidenceForObservation,
} from "@/services/evidence-observation";
import { resolveObservationForSelection } from "@/services/provenance-inspector";
import { buildWorkspaceProvenance } from "@/services/workspace-provenance";
import { formatScoringMethodLabel } from "@/services/ui-copy";
import {
  caseTitle,
  readable,
  runTitle,
  scoreText,
  shortDate,
} from "@/services/presentation";

const route = useRoute(),
  router = useRouter();
const { preferences } = useAppPreferences();
const { state: selection, updateState } = useWorkbenchState();
const buildId = computed(() =>
  typeof route.query.build_id === "string" ? route.query.build_id : null,
);
const runs = ref<RunSummary[]>([]),
  detail = ref<RunDetail | null>(null),
  baseGraph = ref<UnifiedGraphDataset | null>(null);
const loading = ref(false),
  error = ref(""),
  notice = ref("");
const panelTab = ref("source"),
  globalVisible = ref(false),
  technicalVisible = ref(false);
const mappingVisible = ref(false);
const graphSearch = ref(""),
  graphLabels = ref(true);
const selectedNodeId = ref<string | null>(null),
  selectedEdgeId = ref<string | null>(null);
const patch = ref<GraphPatch | null>(null);
const ledger = ref<ReviewLedgerRecord[]>([]),
  ledgerError = ref(""),
  reviewBusy = ref(false);
const form = reactive({
  action: "accept" as "accept" | "reject" | "needs_review",
  note: "",
});
const editorRef = ref<InstanceType<typeof GraphEditor> | null>(null);
const editorDirty = ref(false);
const editorEdgeId = computed(() => {
  const id = selectedEdgeId.value;
  if (baseGraph.value?.edges.some((e) => e.id === id)) return id;
  const edge = path.value?.edges.find((e) => e.edge_id === id);
  const matches = edge ? matchKnowledgeEdges(edge, baseGraph.value) : [];
  return matches.length === 1 ? matches[0]!.id : null;
});
function confirmDiscard(): Promise<boolean> {
  if (!editorDirty.value) return Promise.resolve(true);
  return new Promise((resolve) =>
    Modal.confirm({
      escToClose: false,
      title: "离开未保存的草稿？",
      content: "未保存的变更将被放弃；已保存版本不受影响。",
      okText: "放弃并离开",
      cancelText: "继续编辑",
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    }),
  );
}
function closeEditor() {
  void confirmDiscard().then((confirmed) => {
    if (!confirmed) return;
    if (editorDirty.value) editorRef.value?.discard();
    globalVisible.value = false;
  });
  return false;
}
let workspaceVersion = 0,
  runVersion = 0,
  ledgerVersion = 0,
  graphVersion = 0;
const activeCase = computed(
  () =>
    detail.value?.cases.find(
      (c) => c.case_id === selection.value.selectedCaseId,
    ) ??
    detail.value?.cases[0] ??
    null,
);
const candidates = computed(() =>
  uniqueRootCauseCandidates(activeCase.value?.ranked_root_causes ?? []),
);
const candidate = computed(
  () =>
    candidates.value.find(
      (c) =>
        c.candidate_id === selection.value.selectedCandidateId ||
        c.ranking_id === selection.value.selectedCandidateId,
    ) ??
    candidates.value[0] ??
    null,
);
const candidatePaths = computed(() =>
  candidateExplanationPaths(candidate.value, activeCase.value?.path_graph),
);
const path = computed<PathGraphPath | null>(
  () =>
    candidatePaths.value.find(
      (p) => p.path_id === selection.value.selectedPathId,
    ) ??
    candidatePaths.value[0] ??
    null,
);
const pathDataset = computed(() =>
  path.value
    ? buildPathSubgraphDataset({
        paths: [path.value],
        path_count: 1,
        node_count: path.value.nodes.length,
        edge_count: path.value.edges.length,
      })
    : null,
);
const graph = computed(() =>
  baseGraph.value && patch.value
    ? applyGraphPatch(baseGraph.value, patch.value)
    : baseGraph.value,
);
const sourceEdge = computed(() => {
  const edgeId = selectedEdgeId.value;
  if (!edgeId) return null;
  return (
    graph.value?.edges.find((e) => e.id === edgeId) ??
    pathDataset.value?.edges.find((e) => e.id === edgeId) ??
    null
  );
});
const sourceState = computed(() =>
  buildWorkspaceProvenance(
    activeCase.value,
    path.value,
    baseGraph.value,
    selectedEdgeId.value,
  ),
);
const observations = computed(() =>
  activeCase.value ? buildObservationBrowseItems(activeCase.value) : [],
);
const pathObservations = computed(() => {
  if (!activeCase.value || !path.value) return [];
  return path.value.supporting_evidence
    .filter((id): id is string => typeof id === "string")
    .map((id) => resolveObservationForSelection(activeCase.value!, id))
    .filter((item): item is NonNullable<typeof item> => item !== null);
});
const observation = computed(() => {
  const items = pathObservations.value.length
    ? pathObservations.value
    : observations.value;
  return (
    items.find((o) => o.id === selection.value.selectedObservationId) ??
    items[0] ??
    null
  );
});
const visuals = computed(() =>
  selectVisualEvidenceForObservation(
    observation.value,
    activeCase.value?.visual_evidence,
  ),
);
const reviewTarget = computed<ReviewTarget | null>(() => {
  const targets = activeCase.value?.review_targets ?? [];
  const type = selectedEdgeId.value
    ? "edge"
    : path.value
      ? "path"
      : "root_cause_candidate";
  const ids =
    type === "edge"
      ? [
          selectedEdgeId.value,
          ...(path.value?.edges ?? [])
            .filter((e) =>
              matchKnowledgeEdges(e, baseGraph.value).some(
                (k) => k.id === selectedEdgeId.value,
              ),
            )
            .map((e) => e.edge_id),
        ]
      : type === "path"
        ? [path.value?.path_id]
        : [candidate.value?.ranking_id, candidate.value?.candidate_id];
  return (
    targets.find(
      (t) =>
        t.target_type === type &&
        ids.includes(t.target_id) &&
        canSubmitReviewTargetType(t.target_type),
    ) ?? null
  );
});
const targetLabel = computed(() =>
  selectedEdgeId.value
    ? `关系 · ${readable(sourceEdge.value?.relation)}`
    : path.value
      ? `解释路径 · ${readable(candidate.value?.candidate_name)}`
      : `候选 · ${readable(candidate.value?.candidate_name)}`,
);
const nodeNames = computed(
  () =>
    new Map((graph.value?.nodes ?? []).map((n) => [n.id, readable(n.name)])),
);
const savedContext = computed(() =>
  [
    preferences.value.dataSourceMode,
    preferences.value.apiBaseUrl,
    detail.value?.run.run_id,
    activeCase.value?.case_id,
  ].join("|"),
);
function selectCandidate(id: string) {
  const c = candidates.value.find((c) => c.candidate_id === id);
  const next =
    c && activeCase.value?.path_graph
      ? candidateExplanationPaths(c, activeCase.value.path_graph)[0]
      : null;
  selectedNodeId.value = null;
  selectedEdgeId.value = null;
  form.note = "";
  notice.value = "";
  updateState({
    selectedCandidateId: id,
    selectedPathId: next?.path_id ?? null,
    selectedReviewTargetKey: null,
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  });
}
function selectEdge(id: string) {
  selectedEdgeId.value = id;
  selectedNodeId.value = null;
  panelTab.value = "source";
  form.note = "";
}
function selectNode(id: string) {
  selectedNodeId.value = id;
  selectedEdgeId.value = null;
}
async function graphSelect(
  payload: { type: "node" | "edge"; item: { id: string } } | null,
) {
  if (!(await editorRef.value?.confirmFormChange())) return;
  if (payload?.type === "node") selectNode(payload.item.id);
  else if (payload) selectEdge(payload.item.id);
}
function editGraph() {
  globalVisible.value = true;
}
function selectCase(id: string) {
  selectedNodeId.value = null;
  selectedEdgeId.value = null;
  form.note = "";
  notice.value = "";
  updateState({
    selectedCaseId: id,
    selectedObservationId: null,
    selectedCandidateId: null,
    selectedPathId: null,
    selectedReviewTargetKey: null,
  });
  syncRoute();
}
function syncRoute() {
  if (detail.value && activeCase.value)
    void router.replace({
      name: "graphs",
      query: {
        run_id: detail.value.run.run_id,
        case_id: activeCase.value.case_id,
      },
    });
}
async function loadRun(id: string) {
  const v = ++runVersion;
  const previous = { ...selection.value };
  const oldCase =
    typeof route.query.case_id === "string"
      ? route.query.case_id
      : previous.selectedCaseId;
  loading.value = true;
  error.value = "";
  detail.value = null;
  selectedEdgeId.value = null;
  selectedNodeId.value = null;
  baseGraph.value = null;
  patch.value = null;
  try {
    const result = await getRootLensService().getRun(id);
    if (v !== runVersion) return;
    const current =
      result.cases.find((c) => c.case_id === oldCase) ?? result.cases[0];
    const preserve =
      previous.selectedRunId === id &&
      previous.selectedCaseId === current?.case_id;
    detail.value = result;
    updateState({
      selectedRunId: id,
      selectedCaseId: current?.case_id ?? null,
      selectedCandidateId: preserve ? previous.selectedCandidateId : null,
      selectedPathId: preserve ? previous.selectedPathId : null,
      selectedReviewTargetKey: preserve
        ? previous.selectedReviewTargetKey
        : null,
    });
    syncRoute();
  } catch (e) {
    if (v === runVersion)
      error.value = e instanceof Error ? e.message : String(e);
  } finally {
    if (v === runVersion) loading.value = false;
  }
}
async function loadGraph(c: RunCaseDetail | null) {
  const v = ++graphVersion,
    workspace = workspaceVersion;
  baseGraph.value = null;
  patch.value = null;
  if (!c) return;
  try {
    let dataset: UnifiedGraphDataset | null;
    if (
      getLocalSessionMeta()?.source === "import" ||
      preferences.value.dataSourceMode === "mock"
    ) {
      const file =
        getLocalSessionMeta()?.source === "import"
          ? getStoredImportedGraphs()
          : await loadUnifiedGraphs();
      const datasetId = String(
        c.generated_evidence?.graph_dataset_id ?? c.graph_dataset_id ?? "",
      );
      const found =
        file?.datasets.find((d) => d.id === datasetId) ??
        file?.datasets.find((d) => d.id.startsWith(`${c.dataset}-`));
      if (found) {
        const scoped = found.nodes.some(
          (n) => typeof n.attributes.scenario === "string",
        );
        const nodes = scoped
          ? found.nodes.filter(
              (n) =>
                n.attributes.scenario === c.dataset ||
                n.attributes.scenario === "shared",
            )
          : found.nodes;
        const ids = new Set(nodes.map((n) => n.id));
        dataset = {
          ...found,
          id: scoped ? `${found.id}:${c.dataset}` : found.id,
          nodes,
          edges: found.edges.filter(
            (e) => ids.has(e.source) && ids.has(e.target),
          ),
          metadata: { ...found.metadata, scenario: c.dataset ?? "unknown" },
        };
      } else dataset = null;
    } else {
      dataset = buildKGStudioDataset(
        await getRootLensService().kgStudio(),
        c.dataset,
      );
    }
    if (v === graphVersion && workspace === workspaceVersion)
      baseGraph.value = dataset;
  } catch (e) {
    if (v === graphVersion && workspace === workspaceVersion)
      error.value = `知识图谱读取失败：${e instanceof Error ? e.message : String(e)}`;
  }
}
async function refresh() {
  const v = ++workspaceVersion;
  ++runVersion;
  loading.value = true;
  error.value = "";
  baseGraph.value = null;
  patch.value = null;
  detail.value = null;
  if (buildId.value) {
    loading.value = false;
    return;
  }
  try {
    const result = await getRootLensService().listRuns();
    if (v !== workspaceVersion) return;
    runs.value = result;
    const queryRun =
      typeof route.query.run_id === "string" ? route.query.run_id : null;
    const id =
      result.find(
        (r) => r.run_id === (queryRun ?? selection.value.selectedRunId),
      )?.run_id ?? result[0]?.run_id;
    if (id) await loadRun(id);
  } catch (e) {
    if (v === workspaceVersion)
      error.value = e instanceof Error ? e.message : String(e);
  } finally {
    if (v === workspaceVersion) loading.value = false;
  }
}
async function loadLedger() {
  const v = ++ledgerVersion;
  ledgerError.value = "";
  ledger.value = [];
  if (!activeCase.value || !detail.value) return;
  try {
    const result = await getRootLensService().listReviewLedger({
      run_id: detail.value.run.run_id,
      case_id: activeCase.value.case_id,
      limit: 100,
    });
    if (v === ledgerVersion) ledger.value = result.records;
  } catch (e) {
    if (v === ledgerVersion)
      ledgerError.value = e instanceof Error ? e.message : String(e);
  }
}
async function submitReview() {
  const target = reviewTarget.value;
  if (!target || !detail.value || !activeCase.value || reviewBusy.value) return;
  if (!form.note.trim()) {
    notice.value = "请记录审阅理由，便于之后追溯。";
    return;
  }
  const context = savedContext.value;
  reviewBusy.value = true;
  notice.value = "";
  try {
    await getRootLensService().submitReview({
      run_id: detail.value.run.run_id,
      case_id: activeCase.value.case_id,
      target_type: target.target_type,
      target_id: target.target_id,
      metadata: { target_key: target.target_key },
      action: form.action,
      note: form.note,
      reviewer: "analyst",
      source: "rootlens-graphs",
    });
    if (context !== savedContext.value) return;
    notice.value = "审阅已记录；未修改图谱或重新计算候选。";
    form.note = "";
    await loadLedger();
    panelTab.value = "history";
  } catch (e) {
    if (context === savedContext.value)
      notice.value = e instanceof Error ? e.message : String(e);
  } finally {
    reviewBusy.value = false;
  }
}
function backToEvidence() {
  void router.push({ name: "evidence" });
}
watch(
  () => [preferences.value.dataSourceMode, preferences.value.apiBaseUrl],
  refresh,
);
watch(
  () => activeCase.value,
  () => {
    void loadLedger();
    void loadGraph(activeCase.value);
  },
);
watch(() => route.query.build_id, refresh);
onBeforeRouteLeave(async () => {
  if (!(await confirmDiscard())) return false;
  ++workspaceVersion;
  ++runVersion;
  ++ledgerVersion;
  ++graphVersion;
  return true;
});
onMounted(() => {
  window.addEventListener(getLocalSessionEventName(), refresh);
  void refresh();
});
onBeforeUnmount(() => {
  ++workspaceVersion;
  ++runVersion;
  ++ledgerVersion;
  ++graphVersion;
  window.removeEventListener(getLocalSessionEventName(), refresh);
});
</script>

<template>
  <ConstructionGraphPreview v-if="buildId" :build-id="buildId" />
  <div v-else class="demo-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">02 / REASONING</span>
        <h2>沿着证据，检查解释</h2>
      </div>
      <a-space
        ><a-button @click="backToEvidence">返回证据</a-button
        ><a-button :disabled="!baseGraph" @click="globalVisible = true"
          >查看知识图谱</a-button
        ></a-space
      >
    </header>
    <a-alert v-if="error" type="error" :title="error" class="page-alert"
      ><template #action
        ><a-button @click="refresh">重试</a-button></template
      ></a-alert
    >
    <div class="context-toolbar">
      <div v-control-label="'分析记录'" class="labeled-control">
        <a-select
          :model-value="detail?.run.run_id"
          aria-label="分析记录"
          placeholder="分析记录"
          class="run-select"
          :loading="loading"
          @change="loadRun(String($event))"
          ><a-option
            v-for="r in runs"
            :key="r.run_id"
            :value="r.run_id"
            :label="runTitle(r)"
        /></a-select>
      </div>
      <div v-control-label="'当前案例'" class="labeled-control">
        <a-select
          :model-value="activeCase?.case_id"
          aria-label="当前案例"
          placeholder="当前案例"
          class="run-select"
          @change="selectCase(String($event))"
          ><a-option
            v-for="c in detail?.cases ?? []"
            :key="c.case_id"
            :value="c.case_id"
            :label="caseTitle(c)"
        /></a-select>
      </div>
      <a-tag color="gold">候选解释 · 非因果定论</a-tag>
    </div>
    <a-spin :loading="loading" class="block-spin">
      <div v-if="activeCase" class="reasoning-workspace">
        <aside class="surface candidates-panel">
          <div class="surface-heading">
            <h3>候选解释</h3>
            <a-tag>{{ candidates.length }}</a-tag>
          </div>
          <button
            v-for="c in candidates"
            :key="c.candidate_id"
            class="candidate-item"
            :class="{ 'is-active': c.candidate_id === candidate?.candidate_id }"
            :aria-pressed="c.candidate_id === candidate?.candidate_id"
            @click="selectCandidate(c.candidate_id)"
          >
            <span class="candidate-rank">{{
              String(c.rank).padStart(2, "0")
            }}</span>
            <div>
              <strong>{{ readable(c.candidate_name) }}</strong
              ><span>排序得分 {{ scoreText(c.score) }}</span>
            </div>
          </button>
          <a-empty v-if="!candidates.length" description="暂无候选解释" />
          <div class="candidate-method">
            <span class="subtle">{{
              formatScoringMethodLabel(candidate?.scoring_method)
            }}</span
            ><a-button type="text" @click="technicalVisible = true"
              >评分详情</a-button
            >
          </div>
        </aside>
        <main class="reasoning-main">
          <section class="surface explanation-panel">
            <div class="surface-heading">
              <h3>{{ readable(candidate?.candidate_name, "解释路径") }}</h3>
              <a-tag v-if="path">{{ path.edges.length }} 个关系</a-tag>
            </div>
            <div v-if="candidatePaths.length > 1" class="path-switch">
              <a-radio-group
                :model-value="path?.path_id"
                type="button"
                aria-label="解释路径"
                @change="updateState({ selectedPathId: String($event) })"
                ><a-radio
                  v-for="(p, i) in candidatePaths"
                  :key="p.path_id"
                  :value="p.path_id"
                  >路径 {{ i + 1 }}</a-radio
                ></a-radio-group
              >
            </div>
            <div v-if="path" class="explanation-path" aria-label="候选解释路径">
              <template
                v-for="(node, index) in path.nodes"
                :key="`${path.path_id}:${node.node_id}`"
              >
                <button
                  class="path-node"
                  :class="{
                    'is-active': selectedNodeId === node.node_id,
                    'is-target': index === path.nodes.length - 1,
                  }"
                  :aria-pressed="selectedNodeId === node.node_id"
                  @click="selectNode(node.node_id)"
                >
                  <span>{{
                    index === 0
                      ? "证据关联实体"
                      : index === path.nodes.length - 1
                        ? "候选原因"
                        : "中间知识"
                  }}</span
                  ><strong>{{ readable(node.label) }}</strong>
                </button>
                <button
                  v-if="path.edges[index]"
                  class="path-edge"
                  :class="{
                    'is-active': selectedEdgeId === path.edges[index]?.edge_id,
                  }"
                  :aria-label="`核验关系 ${readable(path.edges[index]?.relation)}`"
                  @click="selectEdge(path.edges[index]!.edge_id)"
                >
                  <span>{{ readable(path.edges[index]?.relation) }}</span
                  ><span class="path-arrow">⟶</span
                  ><small>{{ scoreText(path.edges[index]?.confidence) }}</small>
                </button>
              </template>
            </div>
            <a-empty
              v-else
              description="该候选未提供图谱解释路径；请检查评分详情与证据，不以其他候选路径替代。"
            />
            <div class="path-footer">
              <span class="subtle">{{
                selectedNodeId
                  ? `已选节点：${nodeNames.get(selectedNodeId) ?? readable(selectedNodeId)}`
                  : selectedEdgeId
                    ? "已选关系：右侧可核验依据与审阅"
                    : "点选关系核验来源；点选节点可进入知识编辑"
              }}</span
              ><a-button :disabled="!baseGraph" @click="editGraph"
                >编辑知识草稿</a-button
              >
            </div>
          </section>
          <section class="surface supporting-observation">
            <div class="surface-heading">
              <h3>
                {{ pathObservations.length ? "路径支持观察" : "案例观察" }}
              </h3>
              <a-button type="text" @click="mappingVisible = true"
                >实体映射与校正</a-button
              >
              <a-button type="text" @click="backToEvidence"
                >回到完整证据</a-button
              >
            </div>
            <p v-if="!pathObservations.length" class="subtle">
              当前解释未指定观察绑定，以下仅为案例上下文。
            </p>
            <VisualEvidenceViewer
              v-if="observation?.modality === 'image'"
              :items="visuals"
              :label="caseTitle(activeCase)"
            /><ObservationSignal
              v-else-if="observation"
              :observation="observation"
            /><a-empty v-else description="未提供关联观察" />
          </section>
        </main>
        <aside class="surface inspection-panel">
          <div class="surface-heading">
            <h3>{{ targetLabel }}</h3>
          </div>
          <a-tabs v-model:active-key="panelTab" :justify="true">
            <a-tab-pane key="source" title="来源核验"
              ><p
                v-if="preferences.dataSourceMode === 'backend'"
                class="subtle"
              >
                当前图谱的来源；旧分析未重算，可能与其历史版本不同。
              </p>
              <SourceTrail :state="sourceState" />
              <div class="inspector-action">
                <a-button
                  type="primary"
                  long
                  :disabled="!reviewTarget"
                  @click="panelTab = 'review'"
                  >审阅此对象</a-button
                >
              </div></a-tab-pane
            >
            <a-tab-pane key="review" title="人工审阅"
              ><div class="inspector-content">
                <p class="review-object">
                  当前对象<br /><strong>{{ targetLabel }}</strong>
                </p>
                <a-alert
                  v-if="!reviewTarget"
                  type="warning"
                  title="后端未提供此对象的可审阅目标"
                /><a-form :model="form" layout="vertical"
                  ><a-form-item label="判断"
                    ><a-radio-group
                      v-model="form.action"
                      direction="vertical"
                      aria-label="审阅判断"
                      ><a-radio value="accept">保留此解释 / 关系</a-radio
                      ><a-radio value="reject">不支持</a-radio
                      ><a-radio value="needs_review"
                        >需要进一步核验</a-radio
                      ></a-radio-group
                    ></a-form-item
                  ><a-form-item label="审阅理由" required
                    ><a-textarea
                      v-model="form.note"
                      v-control-label="'审阅理由'"
                      aria-label="审阅理由"
                      placeholder="依据是什么？还缺什么证据？"
                      :auto-size="{ minRows: 3, maxRows: 8 }" /></a-form-item
                  ><a-button
                    type="primary"
                    long
                    :disabled="!reviewTarget"
                    :loading="reviewBusy"
                    @click="submitReview"
                    >记录审阅</a-button
                  ></a-form
                >
                <p v-if="notice" role="status" class="review-notice">
                  {{ notice }}
                </p>
                <p class="subtle">记录判断，不自动改写图谱或候选排序。</p>
              </div></a-tab-pane
            >
            <a-tab-pane key="history" title="审阅记录"
              ><div class="inspector-content">
                <p v-if="notice" role="status" class="review-notice">
                  {{ notice }}
                </p>
                <a-alert v-if="ledgerError" type="error" :title="ledgerError" />
                <div
                  v-for="r in ledger"
                  :key="r.feedback_id"
                  class="review-entry"
                >
                  <div>
                    <a-tag
                      :color="
                        r.action === 'accept'
                          ? 'green'
                          : r.action === 'reject'
                            ? 'red'
                            : 'gold'
                      "
                      >{{
                        r.action === "accept"
                          ? "保留"
                          : r.action === "reject"
                            ? "不支持"
                            : "待核验"
                      }}</a-tag
                    ><span class="subtle">{{ shortDate(r.created_at) }}</span>
                  </div>
                  <strong>{{
                    r.target_type === "edge"
                      ? "知识关系"
                      : r.target_type === "path"
                        ? "解释路径"
                        : "候选对象"
                  }}</strong>
                  <p>{{ r.note || "未记录理由" }}</p>
                </div>
                <a-empty
                  v-if="!ledger.length && !ledgerError"
                  description="此案例尚无审阅记录"
                /></div
            ></a-tab-pane>
          </a-tabs>
        </aside>
      </div>
      <a-empty v-else-if="!loading" description="先选择一个有分析结果的案例" />
    </a-spin>
    <a-drawer
      v-model:visible="mappingVisible"
      title="证据如何关联到知识"
      :width="560"
      :footer="false"
    >
      <h3>实体映射</h3>
      <div
        v-for="(link, index) in activeCase?.linked_entities ?? []"
        :key="index"
        class="source-excerpt"
      >
        <strong
          >{{ readable(String(link.mention ?? link.field ?? "")) }} →
          {{
            readable(
              String(
                link.selected_entity_name ??
                  link.selected_entity_id ??
                  "未关联",
              ),
            )
          }}</strong
        >
        <p class="subtle">
          匹配得分
          {{ scoreText(typeof link.score === "number" ? link.score : null)
          }}<a-tag v-if="link.ambiguous" color="gold">存在歧义</a-tag>
        </p>
      </div>
      <a-empty
        v-if="!activeCase?.linked_entities?.length"
        description="未提供实体映射结果"
      />
      <a-divider />
      <h3>待核验校正</h3>
      <p class="subtle">后端返回的建议，不覆盖原始观察，也不自动成为事实。</p>
      <div
        v-for="(item, index) in activeCase?.correction_candidates ?? []"
        :key="index"
        class="source-excerpt"
      >
        <strong
          >{{ readable(String(item.original_value ?? "")) }} →
          {{
            readable(
              String(item.suggested_value ?? item.suggested_entity_id ?? ""),
            )
          }}</strong
        >
        <p>{{ item.reason }}</p>
        <a-tag color="gold">待核验</a-tag>
      </div>
      <a-empty
        v-if="!activeCase?.correction_candidates?.length"
        description="当前案例暂无校正建议"
      />
    </a-drawer>
    <a-modal
      v-model:visible="globalVisible"
      title="知识图谱与人工草稿"
      :footer="false"
      width="min(1500px, 96vw)"
      :mask-closable="false"
      :on-before-cancel="closeEditor"
    >
      <p
        v-if="
          baseGraph &&
          Number(baseGraph.metadata.full_edge_count) >
            Number(baseGraph.metadata.preview_edge_count)
        "
        class="subtle"
      >
        当前为有界图谱预览；未展示全部关系。现有关系来源不会用其他关系补齐。
      </p>
      <p v-if="selectedEdgeId && !editorEdgeId" class="subtle">
        该运行关系未能唯一对应当前图谱，请在图中选择具体关系再编辑。
      </p>
      <div class="graph-workshop">
        <section class="graph-workshop__canvas">
          <div class="context-toolbar">
            <a-input-search
              v-model="graphSearch"
              v-control-label="'查找图谱实体'"
              aria-label="查找图谱实体"
              placeholder="查找实体"
            /><a-checkbox v-model="graphLabels">显示名称</a-checkbox
            ><a-tag v-if="patch?.changes.length" color="purple"
              >{{ patch.changes.length }} 项草稿变更</a-tag
            >
          </div>
          <KnowledgeForceGraph
            v-if="graph"
            :dataset="graph"
            :show-labels="graphLabels"
            :search-term="graphSearch"
            :selected-node-id="selectedNodeId"
            :selected-edge-id="editorEdgeId"
            @select="graphSelect"
          />
          <p class="subtle">
            虚线 / 草稿为待核验知识；此处修改不改变既有 RCA 结果。
          </p>
        </section>
        <aside v-if="baseGraph" class="graph-workshop__editor">
          <GraphEditor
            ref="editorRef"
            :dataset="baseGraph"
            :selected-node-id="selectedNodeId"
            :selected-edge-id="editorEdgeId"
            @dirty="editorDirty = $event"
            @patch="patch = $event"
          />
        </aside>
      </div>
    </a-modal>
    <a-modal
      v-model:visible="technicalVisible"
      title="候选评分与技术详情"
      :footer="false"
      width="min(680px,94vw)"
      ><p>方法：{{ formatScoringMethodLabel(candidate?.scoring_method) }}</p>
      <p>排序得分 {{ scoreText(candidate?.score) }}；不是根因正确概率。</p>
      <pre class="raw-json">{{ JSON.stringify(candidate, null, 2) }}</pre>
    </a-modal>
  </div>
</template>
