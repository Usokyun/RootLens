<script setup lang="ts">
import MeasuredEvidenceDetails from "@/components/evidence/MeasuredEvidenceDetails.vue"
import UnifiedReasoningDetails from '@/components/evidence/UnifiedReasoningDetails.vue'
import {
  IconBulb,
  IconCheckCircle,
  IconInfoCircle,
  IconRefresh,
  IconRelation,
  IconSave,
  IconSend,
  IconStorage,
} from "@arco-design/web-vue/es/icon";
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import type {
  KGStudioGraphNode,
  WorkingGraphPackage,
  WorkingGraphSummary,
  KGStudioPayload,
  PathGraphPath,
  ReviewLedgerRecord,
  RunDetail,
  RunSummary,
} from "@/api/contracts";
import KnowledgeForceGraph from "@/components/graphs/KnowledgeForceGraph.vue";
import RunPathGraph from "@/components/graphs/RunPathGraph.vue";
import SavedObservationLocation from "@/components/graphs/SavedObservationLocation.vue";
import SectionCardTitle from "@/components/layout/SectionCardTitle.vue";
import ProvenanceInspectorDrawer from "@/components/provenance/ProvenanceInspectorDrawer.vue";
import {
  type GraphCurationDecision,
  applyGraphCurationToDataset,
  areGraphCurationDraftsEqual,
  buildEmptyGraphCurationCaseDraft,
  buildNeighborhoodSubgraphDataset,
  buildPathSubgraphDataset,
  loadGraphCurationCaseDraft,
  replaceGraphEdgeDraft,
  replaceGraphNodeDraft,
  resetGraphCurationCaseDraft,
  saveGraphCurationCaseDraft,
  type MockGraphCurationCaseDraft,
  type MockGraphEdgeDraft,
  type MockGraphNodeDraft,
} from "@/services/graph-curation";
import { useAppPreferences } from "@/services/app-preferences";
import { newAnalysisRoute, savedAnalysisIntent, savedAnalysisRoute } from "@/services/analysis-entry";
import { graphArchiveRoute } from "@/services/working-graph-workspace";
import {
  buildCandidateSelectionPatch,
  buildLocalGraphSelectionPatch,
  buildTotalGraphSelectionPatch,
  findBestPathForCandidateInGraph,
  findReviewTargetInList,
  resolveSelectedRootCause,
  shouldAutoOpenCurationTabOnLocalGraphSelect,
} from "@/services/graph-explore-selection";
import {
  getLocalSessionMeta,
  loadUnifiedGraphs,
} from "@/services/rootlens-data";
import {
  canSubmitReviewTargetType,
  getRootLensService,
} from "@/services/rootlens-service";
import {
  buildObservationBrowseItems,
  findObservationBrowseItem,
} from "@/services/evidence-observation";
import {
  buildGraphReasoningInspection,
  type RecurrenceCaseHit,
  type TraceStep,
} from "@/services/graph-reasoning-inspection";
import {
  buildGraphCorrectionProvenance,
  buildGraphEdgeProvenance,
  buildGraphEntityLinkProvenance,
  buildGraphPathProvenance,
  resolveObservationForSelection,
  type ProvenanceInspectorState,
} from "@/services/provenance-inspector";
import {
  buildReviewLedgerDisplayItems,
  filterReviewLedgerRecords,
  formatReviewLedgerTargetType,
  isBoundedReviewTargetType,
  type ReviewLedgerDisplayItem,
  type ReviewLedgerTargetFilter,
} from "@/services/review-ledger";
import {
  formatClaimBoundaryCopy,
  formatScoringMethodLabel,
  resolveRunReasoningSummary,
} from "@/services/ui-copy";
import { buildSavedPathProvenance, savedPathForEdge, savedPathObservation, savedPathsForCandidate } from "@/services/saved-analysis-graph";
import { traceOutcome } from "@/services/unified-reasoning-display";
import {
  sourceSelectionReset,
  useWorkbenchState,
  type WorkbenchState,
} from "@/services/workbench-state";
import type {
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
} from "@/types/graph";

type GraphSelectPayload =
  | { type: "node"; item: UnifiedGraphNode }
  | { type: "edge"; item: UnifiedGraphEdge }
  | null;

type LocalGraphSelectPayload =
  | { type: "node"; id: string }
  | { type: "edge"; id: string }
  | null;

interface CurationSuggestion {
  id: string;
  kind: "node" | "edge";
  label: string;
  subtitle: string;
}

const route = useRoute();
const router = useRouter();
const props = defineProps<{ archiveOnly?: boolean }>();
const { preferences } = useAppPreferences();
const { state: workbenchState, updateState } = useWorkbenchState();

let workspaceRevision = 0;
let packageRevision = 0;
const loading = ref(false);
const runs = ref<RunSummary[]>([]);
const runDetail = ref<RunDetail | null>(null);
const kgStudio = ref<KGStudioPayload | null>(null);
const packageDrawerOpen = ref(false);
const packageText = ref("");
const packageBaseline = ref("");
const packageGraphId = ref<string | null>(null);
const packageBusy = ref(false);
const workingGraphs = ref<WorkingGraphSummary[]>([]);
const editableGraphId = computed(() => !props.archiveOnly && preferences.value.dataSourceMode === "backend"
  && getLocalSessionMeta()?.source !== "import" ? kgStudio.value?.graph_id : undefined);
const currentWorkingGraph = computed(() => workingGraphs.value.find(item => item.graph_id === editableGraphId.value));
const packageGraph = computed(() => workingGraphs.value.find(item => item.graph_id === packageGraphId.value));
const packageDirty = computed(() => packageText.value !== packageBaseline.value);
const currentGraphEnabled = computed(() => currentWorkingGraph.value?.status === "ready"
  && currentWorkingGraph.value.enabled === true && !!currentWorkingGraph.value.knowledge);

function rememberWorkingGraph(graph: WorkingGraphSummary) {
  workingGraphs.value = [...workingGraphs.value.filter(item => item.graph_id !== graph.graph_id), graph];
}

async function openGraphPackage() {
  packageDrawerOpen.value = true;
  const revision = ++packageRevision;
  try {
    const registry = await getRootLensService().listWorkingGraphs();
    if (revision !== packageRevision) return;
    workingGraphs.value = registry.graphs;
    if (editableGraphId.value && editableGraphId.value !== packageGraphId.value) await selectPackageGraph(editableGraphId.value);
  } catch (error) { if (revision === packageRevision) errorMessage.value = String(error); }
}
async function selectPackageGraph(id: string) {
  const revision = ++packageRevision;
  packageBusy.value = true;
  packageGraphId.value = null;
  packageText.value = "";
  packageBaseline.value = "";
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    const service = getRootLensService();
    const [body, studio] = await Promise.all([service.getWorkingGraphPackage(id), service.kgStudio(id)]);
    if (revision !== packageRevision) return;
    if (studio.graph_id !== id) throw new Error("后端没有返回所选工作图。");
    packageText.value = JSON.stringify(body, null, 2);
    packageBaseline.value = packageText.value;
    packageGraphId.value = id;
    kgStudio.value = studio;
    if (!runDetail.value && route.query.graph !== id) void router.replace({ name: "graphs", query: { graph: id } });
  } catch (error) { if (revision === packageRevision) errorMessage.value = String(error); }
  finally { if (revision === packageRevision) packageBusy.value = false; }
}
async function savePackage(importNew = false) {
  const id = packageGraphId.value;
  if (!importNew && !id) return;
  const revision = ++packageRevision;
  packageBusy.value = true;
  errorMessage.value = "";
  actionMessage.value = "";
  try {
    const body = JSON.parse(packageText.value) as WorkingGraphPackage;
    const service = getRootLensService();
    const result = importNew ? await service.importWorkingGraphPackage(body)
      : await service.saveWorkingGraphPackage(id!, body);
    if (revision !== packageRevision) return;
    rememberWorkingGraph(result);
    await selectPackageGraph(result.graph_id);
    if (packageGraphId.value === result.graph_id) {
      actionMessage.value = importNew ? "已导入为新图。确认内容后可投入使用。" : "工作图已保存；历史运行保持原结果。";
    }
  } catch (error) { if (revision === packageRevision) errorMessage.value = String(error); }
  finally { if (revision === packageRevision) packageBusy.value = false; }
}
async function enablePackageGraph() {
  const graph = packageGraph.value;
  if (!graph?.knowledge || graph.status !== "ready" || packageDirty.value || packageBusy.value) return;
  const revision = ++packageRevision;
  packageBusy.value = true;
  errorMessage.value = "";
  try {
    const enabled = await getRootLensService().enableWorkingGraph(graph.graph_id, true);
    if (revision !== packageRevision) return;
    rememberWorkingGraph(enabled);
    actionMessage.value = "工作图已投入使用，可携图新建分析。";
  } catch (error) { if (revision === packageRevision) errorMessage.value = String(error); }
  finally { if (revision === packageRevision) packageBusy.value = false; }
}
function useCurrentGraph() {
  if (!currentGraphEnabled.value || !editableGraphId.value
    || (packageGraphId.value === editableGraphId.value && packageDirty.value)) return;
  void router.push(newAnalysisRoute(editableGraphId.value));
}
function returnToEvidence() {
  const detail = runDetail.value;
  const backend = preferences.value.dataSourceMode === "backend" && getLocalSessionMeta()?.source !== "import";
  void router.push(backend && detail?.run.source_contract === "analysis-v2"
    ? savedAnalysisRoute("evidence", detail.run.run_id, activeCase.value?.case_id)
    : { name: "evidence" });
}
function downloadPackage() {
  const url = URL.createObjectURL(new Blob([packageText.value], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = "rootlens-working-graph.json"; a.click();
  URL.revokeObjectURL(url);
}
async function importPackageFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || packageBusy.value) return;
  const revision = packageRevision;
  const body = await file.text();
  if (revision !== packageRevision) return;
  packageText.value = body;
  await savePackage(true);
}
async function rebuildGraphProfiles() {
  if (!editableGraphId.value) return;
  try {
    await getRootLensService().mutateWorkingGraph(editableGraphId.value, { rebuild_profiles: true });
    await selectPackageGraph(editableGraphId.value);
    actionMessage.value = "已按当前关系重新编译画像。";
  } catch (error) { errorMessage.value = String(error); }
}

const bundledGraphDatasets = ref<UnifiedGraphDataset[]>([]);
const errorMessage = ref("");
const reviewMessage = ref("");
const totalGraphRenderMessage = ref("正在准备总图谱...");
const localGraphRenderMessage = ref("正在准备局部子图...");
const actionMessage = ref("");
const feedbackCardTab = ref<"rca" | "curation" | "trace" | "ledger">(props.archiveOnly ? "trace" : "rca");
const crossCaseCompareOpen = ref(false);
const selectedTraceStepId = ref<string | null>(null);
const provenanceInspectorVisible = ref(false);
const provenanceInspectorState = ref<ProvenanceInspectorState | null>(null);
const ledgerLoading = ref(false);
const ledgerErrorMessage = ref("");
const ledgerRecords = ref<ReviewLedgerRecord[]>([]);
const ledgerTargetTypeFilter = ref<ReviewLedgerTargetFilter>("all");
const pendingCaseSelectionPatch = ref<Partial<WorkbenchState> | null>(null);
const savedCaseDrafts = ref<Record<string, MockGraphCurationCaseDraft>>({});
const workingCaseDrafts = ref<Record<string, MockGraphCurationCaseDraft>>({});

const feedbackForm = reactive({
  reviewer: "rootlens-frontend",
  action: "accept" as "accept" | "reject",
  note: "",
  source: "rootlens-graphs",
});

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function normalizeText(value: unknown, fallback = "--") {
  return typeof value === "string" && value.trim().length
    ? value.trim()
    : fallback;
}

function normalizeNullableText(value: unknown) {
  return typeof value === "string" && value.trim().length ? value.trim() : null;
}

function parseAliasInput(value: string) {
  const aliases = value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length);

  return aliases.length ? [...new Set(aliases)] : null;
}

function formatAliasInput(value: string[] | null | undefined) {
  return value?.length ? value.join(", ") : "";
}

function formatScore(value: unknown) {
  return typeof value === "number" ? value.toFixed(3) : "--";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "--";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", { hour12: false });
}

function readStringAttribute(
  attributes: Record<string, unknown> | undefined,
  key: string,
) {
  if (!attributes) {
    return null;
  }

  const value = attributes[key];
  return typeof value === "string" && value.trim().length ? value.trim() : null;
}

function edgeDecisionFromReviewStatus(edge: UnifiedGraphEdge | null) {
  const reviewStatus = readStringAttribute(edge?.attributes, "review_status");
  if (reviewStatus === "reviewed") {
    return "accept" as const;
  }
  if (reviewStatus === "rejected") {
    return "reject" as const;
  }
  if (reviewStatus === "needs_completion") {
    return "needs_completion" as const;
  }
  return "revise" as const;
}

function resolveBundledDatasetId(dataset: string | null | undefined) {
  const normalized = typeof dataset === "string" ? dataset.toLowerCase() : "";
  if (normalized.includes("tep")) {
    return "tep-kg";
  }
  return "mvtec-project";
}

function resolveCaseGraphDatasetId(
  caseItem: RunDetail["cases"][number] | null | undefined,
) {
  const evidence = caseItem?.generated_evidence;
  if (!evidence || typeof evidence !== "object" || Array.isArray(evidence)) {
    return null;
  }

  const value = (evidence as Record<string, unknown>).graph_dataset_id;
  return typeof value === "string" && value.trim().length ? value.trim() : null;
}

function buildGraphRenderKey(dataset: UnifiedGraphDataset | null) {
  if (!dataset) {
    return null;
  }

  const nodeSignature = dataset.nodes
    .map((node) => {
      const attrs = node.attributes ?? {};
      return [
        node.id,
        node.name,
        node.category,
        node.kind,
        String(attrs.curation_status ?? ""),
        String(attrs.curation_updated_at ?? ""),
      ].join(":");
    })
    .join("|");

  const edgeSignature = dataset.edges
    .map((edge) => {
      const attrs = edge.attributes ?? {};
      return [
        edge.id,
        edge.source,
        edge.target,
        edge.relation,
        edge.label,
        String(edge.confidence ?? ""),
        String(attrs.review_status ?? ""),
        String(attrs.curation_decision ?? ""),
        String(attrs.curation_updated_at ?? ""),
      ].join(":");
    })
    .join("|");

  return [dataset.id, nodeSignature, edgeSignature].join("||");
}

function buildKGStudioDataset(
  payload: KGStudioPayload | null,
): UnifiedGraphDataset | null {
  if (!payload) {
    return null;
  }

  const nodeSeed = new Map<string, KGStudioGraphNode>();
  for (const node of payload.graph_nodes) {
    nodeSeed.set(node.node_id, node);
  }

  for (const edge of payload.graph_edges) {
    if (!nodeSeed.has(edge.head)) {
      nodeSeed.set(edge.head, {
        node_id: edge.head,
        label: edge.head,
        node_type: "Unknown",
        scenario: edge.scenario,
        description: edge.source,
      });
    }
    if (!nodeSeed.has(edge.tail)) {
      nodeSeed.set(edge.tail, {
        node_id: edge.tail,
        label: edge.tail,
        node_type: "Unknown",
        scenario: edge.scenario,
        description: edge.source,
      });
    }
  }

  const inDegree = new Map<string, number>();
  const outDegree = new Map<string, number>();

  for (const edge of payload.graph_edges) {
    outDegree.set(edge.head, (outDegree.get(edge.head) ?? 0) + 1);
    inDegree.set(edge.tail, (inDegree.get(edge.tail) ?? 0) + 1);
  }

  const nodes: UnifiedGraphNode[] = [...nodeSeed.values()].map((node) => ({
    id: node.node_id,
    name: node.label,
    category: node.scenario,
    kind: node.node_type,
    description: node.description,
    aliases: node.aliases ?? [],
    degree:
      (inDegree.get(node.node_id) ?? 0) + (outDegree.get(node.node_id) ?? 0),
    inDegree: inDegree.get(node.node_id) ?? 0,
    outDegree: outDegree.get(node.node_id) ?? 0,
    attributes: {
      scenario: node.scenario,
      node_type: node.node_type,
    },
    origin: {
      projectId: "kg-studio",
      projectLabel: "KG Studio",
      filePath: payload.nodes_path ?? "kg-studio",
      layer: "candidate-graph",
      rowNumber: 0,
    },
  }));

  const edges: UnifiedGraphEdge[] = payload.graph_edges.map((edge) => ({
    id: edge.edge_id,
    source: edge.head,
    target: edge.tail,
    relation: edge.relation,
    category: edge.scenario,
    label: edge.relation,
    confidence: edge.confidence,
    weight: edge.weight,
    directed: true,
    attributes: {
      source: edge.source,
      evidence: edge.evidence,
      review_status: edge.review_status,
      target_key: edge.edge_id,
    },
    origin: {
      projectId: "kg-studio",
      projectLabel: "KG Studio",
      filePath: payload.edges_path ?? "kg-studio",
      layer: "candidate-graph",
      rowNumber: 0,
    },
  }));

  return {
    id: payload.graph_id ?? payload.candidate_dir ?? "kg-studio",
    label: "总图谱",
    description: payload.note,
    graphKind: "candidate-graph",
    projectRoot: payload.candidate_dir ?? "kg-studio",
    sourceFiles: [],
    nodes,
    edges,
    metadata: {
      status: payload.status,
      claim_boundary: payload.claim_boundary,
    },
  };
}

function ensureCaseDraftLoaded(caseId: string) {
  if (!savedCaseDrafts.value[caseId]) {
    const loaded = loadGraphCurationCaseDraft(caseId);
    savedCaseDrafts.value = {
      ...savedCaseDrafts.value,
      [caseId]: deepClone(loaded),
    };
    workingCaseDrafts.value = {
      ...workingCaseDrafts.value,
      [caseId]: deepClone(loaded),
    };
  }
}

const activeCase = computed(() => {
  if (!runDetail.value) {
    return null;
  }

  return (
    runDetail.value.cases.find(
      (item) => item.case_id === workbenchState.value.selectedCaseId,
    ) ??
    runDetail.value.cases[0] ??
    null
  );
});

const isSavedAnalysis = computed(() => runDetail.value?.run.source_contract === "analysis-v2");
const activePathGraph = computed(
  () => activeCase.value?.path_graph ?? (isSavedAnalysis.value ? null : runDetail.value?.path_graph) ?? null,
);

const activePath = computed(() => {
  const graph = activePathGraph.value;
  if (!graph) {
    return null;
  }

  return (
    graph.paths.find(
      (item) => item.path_id === workbenchState.value.selectedPathId,
    ) ??
    (isSavedAnalysis.value ? null : graph.paths[0]) ??
    null
  );
});

const activeCandidate = computed(() => {
  const list =
    activeCase.value?.ranked_root_causes ??
    (isSavedAnalysis.value ? [] : runDetail.value?.ranked_root_causes) ??
    [];
  return resolveSelectedRootCause(
    list,
    workbenchState.value.selectedCandidateId,
  );
});

const savedCandidatePaths = computed(() => isSavedAnalysis.value
  ? savedPathsForCandidate(activeCase.value, activeCandidate.value?.candidate_id) : []);
const savedOutcome = computed(() => {
  if (!isSavedAnalysis.value) return null;
  const result = activeCase.value?.reasoning_metadata?.query_results?.[0];
  return result?.reason === "normal_reference_gate_is_false" ? "正常参考门未触发，不排名"
    : result?.outcome ? traceOutcome(result.outcome) : null;
});

const activeVisualConditions = computed(() => {
  const matches = activeCandidate.value?.scoring_details?.profile_matches;
  if (!Array.isArray(matches)) return [];
  const rows = new Map<string, string>();
  for (const match of matches) {
    if (!Array.isArray(match?.conditions)) continue;
    for (const condition of match.conditions) {
      if (condition.result !== "matched" || condition.feature === "object") continue;
      const text = `${match.region_id ?? condition.channel ?? match.obs_id} · ${condition.feature}: ${JSON.stringify(condition.actual)} → ${condition.op} ${JSON.stringify(condition.value)}`;
      rows.set(text, text);
    }
  }
  return [...rows.values()];
});

const activeSavedCaseDraft = computed(() => {
  const caseId = activeCase.value?.case_id;
  return caseId ? (savedCaseDrafts.value[caseId] ?? null) : null;
});

const activeWorkingCaseDraft = computed(() => {
  const caseId = activeCase.value?.case_id;
  return caseId ? (workingCaseDrafts.value[caseId] ?? null) : null;
});

const baseTotalGraphDataset = computed<UnifiedGraphDataset | null>(() => {
  if (
    preferences.value.dataSourceMode === "backend" &&
    getLocalSessionMeta()?.source !== "import"
  ) {
    return buildKGStudioDataset(kgStudio.value);
  }

  const datasetId =
    resolveCaseGraphDatasetId(activeCase.value) ??
    resolveBundledDatasetId(
      activeCase.value?.dataset ?? runDetail.value?.run.dataset ?? null,
    );
  return (
    bundledGraphDatasets.value.find((dataset) => dataset.id === datasetId) ??
    bundledGraphDatasets.value[0] ??
    null
  );
});

const totalGraphDataset = computed<UnifiedGraphDataset | null>(() => {
  const dataset = baseTotalGraphDataset.value;
  if (!dataset) {
    return null;
  }

  return isSavedAnalysis.value ? dataset : applyGraphCurationToDataset(dataset, activeWorkingCaseDraft.value);
});

const pathSubgraphDataset = computed<UnifiedGraphDataset | null>(() => {
  if (!activePathGraph.value || (isSavedAnalysis.value && !activePathGraph.value.paths.length)) {
    return null;
  }

  const dataset = buildPathSubgraphDataset(activePathGraph.value);
  return props.archiveOnly || isSavedAnalysis.value ? dataset : applyGraphCurationToDataset(dataset, activeWorkingCaseDraft.value);
});

const neighborhoodGraphDataset = computed<UnifiedGraphDataset | null>(() => {
  if (!totalGraphDataset.value || !workbenchState.value.selectedGraphNodeId) {
    return null;
  }

  return buildNeighborhoodSubgraphDataset(
    totalGraphDataset.value,
    workbenchState.value.selectedGraphNodeId,
  );
});

const activeSubgraphMode = computed(() => {
  if (
    workbenchState.value.subgraphMode === "neighborhood" &&
    neighborhoodGraphDataset.value
  ) {
    return "neighborhood" as const;
  }
  return "path" as const;
});

const inspectingSavedPath = computed(() => isSavedAnalysis.value && activeSubgraphMode.value === "path");

const activeLocalGraphDataset = computed(() => {
  if (activeSubgraphMode.value === "neighborhood") {
    return neighborhoodGraphDataset.value;
  }
  return pathSubgraphDataset.value;
});

const localGraphRenderKey = computed(() =>
  buildGraphRenderKey(activeLocalGraphDataset.value),
);

const selectedGraphNode = computed(() => {
  if (!totalGraphDataset.value || !workbenchState.value.selectedGraphNodeId) {
    return null;
  }

  return (
    totalGraphDataset.value.nodes.find(
      (node) => node.id === workbenchState.value.selectedGraphNodeId,
    ) ?? null
  );
});

const activeCurationNode = computed(() => {
  if (
    !activeLocalGraphDataset.value ||
    !workbenchState.value.selectedSubgraphNodeId
  ) {
    return null;
  }

  return (
    activeLocalGraphDataset.value.nodes.find(
      (node) => node.id === workbenchState.value.selectedSubgraphNodeId,
    ) ?? null
  );
});

const activeCurationEdge = computed(() => {
  if (
    !activeLocalGraphDataset.value ||
    !workbenchState.value.selectedSubgraphEdgeId
  ) {
    return null;
  }

  return (
    activeLocalGraphDataset.value.edges.find(
      (edge) => edge.id === workbenchState.value.selectedSubgraphEdgeId,
    ) ?? null
  );
});

const selectedEdgeDraft = computed(() => {
  if (
    !activeWorkingCaseDraft.value ||
    !workbenchState.value.selectedSubgraphEdgeId
  ) {
    return null;
  }

  return (
    activeWorkingCaseDraft.value.edge_drafts.find(
      (draft) => draft.edge_id === workbenchState.value.selectedSubgraphEdgeId,
    ) ?? null
  );
});

const selectedNodeDraft = computed(() => {
  if (
    !activeWorkingCaseDraft.value ||
    !workbenchState.value.selectedSubgraphNodeId
  ) {
    return null;
  }

  return (
    activeWorkingCaseDraft.value.node_drafts.find(
      (draft) => draft.node_id === workbenchState.value.selectedSubgraphNodeId,
    ) ?? null
  );
});

const activeCurationSuggestions = computed<CurationSuggestion[]>(() => {
  const draft = activeWorkingCaseDraft.value;
  if (!draft) {
    return [];
  }

  const edgeSuggestions = draft.edge_drafts.map((item) => ({
    id: item.edge_id,
    kind: "edge" as const,
    label: item.relation ?? item.edge_id,
    subtitle: `${item.review_decision} · ${normalizeText(item.note, "点击进入边策展")}`,
  }));

  const nodeSuggestions = draft.node_drafts.map((item) => ({
    id: item.node_id,
    kind: "node" as const,
    label: item.display_name ?? item.node_id,
    subtitle: normalizeText(item.note, "点击进入节点策展"),
  }));

  return [...edgeSuggestions, ...nodeSuggestions];
});

const activeTraceEntityLink = computed(() => {
  if (!selectedTraceStepId.value?.startsWith("entity:")) {
    return null;
  }

  return (
    activeReasoningInspection.value.linkedEntities.find(
      (item) => `entity:${item.linkId}` === selectedTraceStepId.value,
    ) ?? null
  );
});

const activeSubmitTarget = computed(() => {
  const reviewTargets =
    activeCase.value?.review_targets ?? runDetail.value?.review_targets ?? [];
  const selectedTarget =
    reviewTargets.find(
      (item) =>
        item.target_key === workbenchState.value.selectedReviewTargetKey &&
        canSubmitReviewTargetType(item.target_type),
    ) ?? null;
  const candidateTarget =
    findReviewTargetInList(
      reviewTargets,
      "root_cause_candidate",
      activeCandidate.value?.ranking_id ?? activeCandidate.value?.candidate_id,
    ) ?? null;
  const edgeTarget =
    findReviewTargetInList(
      reviewTargets,
      "edge",
      activeCurationEdge.value?.id,
    ) ?? null;
  const entityLinkTarget =
    findReviewTargetInList(
      reviewTargets,
      "entity_link",
      activeTraceEntityLink.value?.linkId,
    ) ?? null;
  const pathTarget =
    findReviewTargetInList(reviewTargets, "path", activePath.value?.path_id) ??
    null;

  if (selectedTarget) {
    return selectedTarget;
  }

  if (candidateTarget && canSubmitReviewTargetType(candidateTarget.target_type)) {
    return candidateTarget;
  }

  if (edgeTarget && canSubmitReviewTargetType(edgeTarget.target_type)) {
    return edgeTarget;
  }

  if (
    entityLinkTarget &&
    canSubmitReviewTargetType(entityLinkTarget.target_type)
  ) {
    return entityLinkTarget;
  }

  if (pathTarget && canSubmitReviewTargetType(pathTarget.target_type)) {
    return pathTarget;
  }

  return (
    reviewTargets.find((item) => canSubmitReviewTargetType(item.target_type)) ??
    null
  );
});

const totalGraphFocusedNodeIds = computed(() => {
  const ids = new Set<string>();

  if (workbenchState.value.selectedGraphNodeId) {
    ids.add(workbenchState.value.selectedGraphNodeId);
  }
  if (workbenchState.value.selectedSubgraphNodeId) {
    ids.add(workbenchState.value.selectedSubgraphNodeId);
  }
  activeTraceStep.value?.focusNodeIds.forEach((id) => ids.add(id));
  selectedObservationFocus.value.nodeIds.forEach((id) => ids.add(id));

  return [...ids];
});

const totalGraphFocusedEdgeIds = computed(() => {
  const ids = new Set<string>();

  if (workbenchState.value.selectedSubgraphEdgeId) {
    ids.add(workbenchState.value.selectedSubgraphEdgeId);
  }
  activeTraceStep.value?.focusEdgeIds.forEach((id) => ids.add(id));
  selectedObservationFocus.value.edgeIds.forEach((id) => ids.add(id));

  return [...ids];
});

const localGraphFocusedNodeIds = computed(() => {
  const ids = new Set<string>();

  if (workbenchState.value.selectedGraphNodeId) {
    ids.add(workbenchState.value.selectedGraphNodeId);
  }
  if (workbenchState.value.selectedSubgraphNodeId) {
    ids.add(workbenchState.value.selectedSubgraphNodeId);
  }
  activeTraceStep.value?.focusNodeIds.forEach((id) => ids.add(id));
  selectedObservationFocus.value.nodeIds.forEach((id) => ids.add(id));
  if (inspectingSavedPath.value) activePath.value?.nodes.forEach(node => ids.add(node.node_id));

  return [...ids];
});

const localGraphFocusedEdgeIds = computed(() => {
  const ids = new Set<string>();

  if (workbenchState.value.selectedSubgraphEdgeId) {
    ids.add(workbenchState.value.selectedSubgraphEdgeId);
  }
  activeTraceStep.value?.focusEdgeIds.forEach((id) => ids.add(id));
  selectedObservationFocus.value.edgeIds.forEach((id) => ids.add(id));
  if (inspectingSavedPath.value) activePath.value?.edges.forEach(edge => ids.add(edge.edge_id));

  return [...ids];
});

const graphClaimBoundaryCopy = computed(() =>
  formatClaimBoundaryCopy(
    runDetail.value?.claim_boundary ?? kgStudio.value?.claim_boundary,
  ),
);

const activeReasoningSummary = computed(() =>
  resolveRunReasoningSummary(runDetail.value, activeCase.value),
);

const activeObservationContext = computed(() => {
  if (!activeCase.value) {
    return null;
  }

  return findObservationBrowseItem(
    buildObservationBrowseItems(activeCase.value),
    workbenchState.value.selectedObservationId,
  );
});

const savedPathOptions = computed(() => {
  if (!activeCase.value) return [];
  const observationLabels = new Map(buildObservationBrowseItems(activeCase.value).map(item => [item.id, item.title]));
  return savedCandidatePaths.value.map((path, index) => ({
    value: path.path_id,
    label: `路径 ${index + 1} · ${observationLabels.get(savedPathObservation(path) ?? "") ?? path.nodes[0]?.label ?? path.path_id}`,
  }));
});
const savedPathReason = computed(() => isSavedAnalysis.value
  ? normalizeNullableText(activeCase.value?.top_k_paths?.find(path => path.path_id === activePath.value?.path_id)?.reason) : null);

const activeReasoningInspection = computed(() =>
  buildGraphReasoningInspection({
    runDetail: runDetail.value,
    caseDetail: activeCase.value,
    selectedCandidateId: workbenchState.value.selectedCandidateId,
    selectedObservationId: workbenchState.value.selectedObservationId,
    selectedPathId: workbenchState.value.selectedPathId,
  }),
);

const activeTraceStep = computed(
  () =>
    activeReasoningInspection.value.traceSteps.find(
      (item) => item.stepId === selectedTraceStepId.value,
    ) ?? null,
);

const selectedObservationTraceSteps = computed(() => {
  const selectedObservationId = workbenchState.value.selectedObservationId;
  if (!selectedObservationId) {
    return [] as TraceStep[];
  }

  return activeReasoningInspection.value.traceSteps.filter(
    (item) =>
      item.kind === "observation" &&
      (item.observationId === selectedObservationId ||
        item.sharedObservationId === selectedObservationId),
  );
});

const selectedObservationFocus = computed(() => {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();

  for (const step of selectedObservationTraceSteps.value) {
    step.focusNodeIds.forEach((id) => nodeIds.add(id));
    step.focusEdgeIds.forEach((id) => edgeIds.add(id));
  }

  return {
    nodeIds: [...nodeIds],
    edgeIds: [...edgeIds],
  };
});

const filteredLedgerRecords = computed(() =>
  filterReviewLedgerRecords(ledgerRecords.value, ledgerTargetTypeFilter.value),
);

const ledgerDisplayItems = computed(() =>
  buildReviewLedgerDisplayItems(filteredLedgerRecords.value, activeCase.value),
);

const ledgerBoundedTargetOptions = computed(() => [
  { value: "all", label: "全部 target" },
  { value: "path", label: formatReviewLedgerTargetType("path") },
  { value: "edge", label: formatReviewLedgerTargetType("edge") },
  { value: "entity_link", label: formatReviewLedgerTargetType("entity_link") },
  { value: "correction", label: formatReviewLedgerTargetType("correction") },
  { value: "root_cause_candidate", label: formatReviewLedgerTargetType("root_cause_candidate") },
]);

const ledgerIntroCopy =
  "本账本包含 path / edge / entity_link / correction / root_cause_candidate 的 append-only review 记录。";

const feedbackCardHintTooltip = computed(() => {
  if (feedbackCardTab.value === "rca") {
    return "candidate / path / edge / entity_link / correction 反馈都会进入正式 bounded ledger。";
  }

  if (feedbackCardTab.value === "curation") {
    return "当前 tab 只编辑本地 draft overlay，不直接改写原始图谱。";
  }

  if (feedbackCardTab.value === "ledger") {
    return ledgerIntroCopy;
  }

  return "当前 tab 主要用于 evidence → entity → path → candidate 的 linked inspection。";
});

const feedbackCardBadge = computed(() => {
  if (feedbackCardTab.value === "rca") {
    return activeSubmitTarget.value?.label ?? "暂无反馈目标";
  }

  if (feedbackCardTab.value === "curation") {
    return "本地 Draft Overlay";
  }

  if (feedbackCardTab.value === "ledger") {
    if (ledgerLoading.value) {
      return "正在加载 ledger";
    }

    return `${ledgerDisplayItems.value.length} 条 ledger 记录`;
  }

  return (
    activeReasoningInspection.value.candidate?.candidateName ??
    "切到候选后查看链路"
  );
});

const hasUnsavedCurationChanges = computed(() => {
  if (!activeCase.value) {
    return false;
  }

  return !areGraphCurationDraftsEqual(
    activeWorkingCaseDraft.value,
    activeSavedCaseDraft.value,
  );
});

const canRevertCurrentSelection = computed(() => {
  if (activeCurationEdge.value) {
    const savedDraft =
      activeSavedCaseDraft.value?.edge_drafts.find(
        (draft) => draft.edge_id === activeCurationEdge.value?.id,
      ) ?? null;
    return !areGraphCurationDraftsEqual(
      {
        case_id: activeCase.value?.case_id ?? "current",
        edge_drafts: selectedEdgeDraft.value ? [selectedEdgeDraft.value] : [],
        node_drafts: [],
      },
      {
        case_id: activeCase.value?.case_id ?? "current",
        edge_drafts: savedDraft ? [savedDraft] : [],
        node_drafts: [],
      },
    );
  }

  if (activeCurationNode.value) {
    const savedDraft =
      activeSavedCaseDraft.value?.node_drafts.find(
        (draft) => draft.node_id === activeCurationNode.value?.id,
      ) ?? null;
    return !areGraphCurationDraftsEqual(
      {
        case_id: activeCase.value?.case_id ?? "current",
        edge_drafts: [],
        node_drafts: selectedNodeDraft.value ? [selectedNodeDraft.value] : [],
      },
      {
        case_id: activeCase.value?.case_id ?? "current",
        edge_drafts: [],
        node_drafts: savedDraft ? [savedDraft] : [],
      },
    );
  }

  return false;
});

const localGraphDescription = computed(() => {
  if (activeSubgraphMode.value === "neighborhood") {
    return selectedGraphNode.value
      ? `当前展示 ${selectedGraphNode.value.name} 的一阶父子邻域；局部子图中的节点和边可单独选中，点击空白或再次点击当前项可取消局部选择。`
      : "当前展示总图节点的一阶邻域。";
  }

  return "默认展示当前 case 的 path_graph union 子图；点击总图节点可切换为邻域子图。";
});

const totalGraphHelp =
  "点击总图节点可切到对应的一阶邻域子图；右侧根因候选若能映射到图谱节点，也会复用同一套联动逻辑。";

const showsRegisteredGraph = computed(() =>
  preferences.value.dataSourceMode === "backend" && getLocalSessionMeta()?.source !== "import",
);
const totalGraphTitle = computed(() => showsRegisteredGraph.value ? "当前登记知识图谱" : "总图谱");
const localGraphTitle = computed(() => !showsRegisteredGraph.value ? "局部子图"
  : activeSubgraphMode.value === "neighborhood" ? "当前节点邻域" : "本次保存推理路径");

const localGraphHelp = computed(() => [localGraphDescription.value]);

const feedbackCardHelp = computed(() => [
  "在同一卡片中切换 RCA 反馈、图谱策展、推理链路与 Review Ledger。",
  graphClaimBoundaryCopy.value,
  feedbackCardHintTooltip.value,
]);

const graphRootCauseHelp =
  "顶部保留 Run / Case 切换；点击候选会联动总图与局部子图，再次点击同一项可取消选择。";

const edgeDecisionModel = computed<GraphCurationDecision>({
  get() {
    return (
      selectedEdgeDraft.value?.review_decision ??
      edgeDecisionFromReviewStatus(activeCurationEdge.value)
    );
  },
  set(value) {
    updateSelectedEdgeDraft({
      review_decision: value,
    });
  },
});

const edgeRelationModel = computed({
  get() {
    return (
      selectedEdgeDraft.value?.relation ??
      activeCurationEdge.value?.relation ??
      ""
    );
  },
  set(value: string) {
    updateSelectedEdgeDraft({
      relation: normalizeNullableText(value),
    });
  },
});

const edgeConfidenceModel = computed<number | undefined>({
  get() {
    const currentValue =
      selectedEdgeDraft.value?.confidence ??
      activeCurationEdge.value?.confidence ??
      null;
    return typeof currentValue === "number" ? currentValue : undefined;
  },
  set(value) {
    updateSelectedEdgeDraft({
      confidence: typeof value === "number" ? value : null,
    });
  },
});

const edgeNoteModel = computed({
  get() {
    return selectedEdgeDraft.value?.note ?? "";
  },
  set(value: string) {
    updateSelectedEdgeDraft({
      note: normalizeNullableText(value),
    });
  },
});

const nodeDisplayNameModel = computed({
  get() {
    return (
      selectedNodeDraft.value?.display_name ??
      activeCurationNode.value?.name ??
      ""
    );
  },
  set(value: string) {
    updateSelectedNodeDraft({
      display_name: normalizeNullableText(value),
    });
  },
});

const nodeAliasesModel = computed({
  get() {
    return formatAliasInput(
      selectedNodeDraft.value?.aliases ??
        activeCurationNode.value?.aliases ??
        null,
    );
  },
  set(value: string) {
    updateSelectedNodeDraft({
      aliases: parseAliasInput(value),
    });
  },
});

const nodeDescriptionModel = computed({
  get() {
    return (
      selectedNodeDraft.value?.description ??
      activeCurationNode.value?.description ??
      ""
    );
  },
  set(value: string) {
    updateSelectedNodeDraft({
      description: normalizeNullableText(value),
    });
  },
});

const nodeNoteModel = computed({
  get() {
    return selectedNodeDraft.value?.note ?? "";
  },
  set(value: string) {
    updateSelectedNodeDraft({
      note: normalizeNullableText(value),
    });
  },
});

function buildCaseSelection(detail: RunDetail, caseId: string | null) {
  const nextCase =
    detail.cases.find((item) => item.case_id === caseId) ??
    detail.cases[0] ??
    null;
  const saved = detail.run.source_contract === "analysis-v2";
  const keepFocus = workbenchState.value.selectedRunId === detail.run.run_id
    && workbenchState.value.selectedCaseId === nextCase?.case_id;
  const candidates = nextCase?.ranked_root_causes ?? (saved ? [] : detail.ranked_root_causes);
  const nextCandidate = (keepFocus ? candidates.find(item => item.ranking_id === workbenchState.value.selectedCandidateId) : null)
    ?? candidates[0] ?? null;
  const nextPathGraph = nextCase?.path_graph ?? (saved ? null : detail.path_graph);
  const previousObservationId = keepFocus ? workbenchState.value.selectedObservationId : null;
  const savedPaths = savedPathsForCandidate(nextCase, nextCandidate?.candidate_id);
  const nextPath = saved
    ? (keepFocus ? savedPaths.find(path => path.path_id === workbenchState.value.selectedPathId) : null)
      ?? savedPaths.find(path => path.supporting_evidence.includes(previousObservationId)) ?? savedPaths[0] ?? null
    : findBestPathForCandidateInGraph(nextCandidate, nextPathGraph) ?? nextPathGraph?.paths[0] ?? null;
  const reviewTargets = nextCase?.review_targets ?? detail.review_targets ?? [];
  const nextReviewTarget =
    findReviewTargetInList(
      reviewTargets,
      "root_cause_candidate",
      nextCandidate?.ranking_id ?? nextCandidate?.candidate_id,
    ) ?? findReviewTargetInList(reviewTargets, "path", nextPath?.path_id);

  return {
    selectedCaseId: nextCase?.case_id ?? null,
    selectedCandidateId: nextCandidate?.ranking_id ?? null,
    selectedPathId: nextPath?.path_id ?? null,
    ...(saved ? { selectedObservationId: nextCase && previousObservationId
      && findObservationBrowseItem(buildObservationBrowseItems(nextCase), previousObservationId)
      ? previousObservationId : savedPathObservation(nextPath) } : {}),
    selectedReviewTargetKey: nextReviewTarget?.target_key ?? null,
    selectedGraphNodeId: null,
    subgraphMode: "path" as const,
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  };
}

function findCandidateForPathInCase(
  caseItem: RunDetail["cases"][number],
  pathId: string | null,
) {
  if (!pathId) {
    return null;
  }

  const path =
    caseItem.path_graph?.paths.find((item) => item.path_id === pathId) ?? null;
  const candidates = caseItem.ranked_root_causes ?? [];

  if (isSavedAnalysis.value) return candidates.find(candidate => candidate.candidate_id === path?.target_entity_id) ?? null;

  return (
    candidates.find(
      (candidate) => candidate.ranking_id === `ranking:${pathId}`,
    ) ??
    candidates.find(
      (candidate) => candidate.candidate_id === path?.target_entity_id,
    ) ??
    candidates.find((candidate) =>
      path?.nodes.some(
        (node) =>
          node.node_id === candidate.candidate_id ||
          node.label === candidate.candidate_name ||
          node.label === candidate.candidate_label,
      ),
    ) ??
    null
  );
}

function isReasoningObservationActive(
  observationId: string,
  sharedObservationId: string,
) {
  return (
    selectedTraceStepId.value === `observation:${observationId}` ||
    (!selectedTraceStepId.value &&
      (workbenchState.value.selectedObservationId === observationId ||
        workbenchState.value.selectedObservationId === sharedObservationId))
  );
}

function selectReasoningTraceStep(step: TraceStep) {
  selectedTraceStepId.value = step.stepId;

  if (step.kind === "observation") {
    const observationId = step.sharedObservationId ?? step.observationId ?? null;
    if (isSavedAnalysis.value && observationId) {
      const path = activePath.value?.supporting_evidence.includes(observationId) ? activePath.value
        : savedCandidatePaths.value.find(item => item.supporting_evidence.includes(observationId));
      if (path) { focusSavedPath(path, observationId); return; }
    }
    updateState({
      selectedObservationId: observationId,
    });
    return;
  }

  if (step.kind === "entity") {
    if (
      !step.graphNodeId ||
      !(
        totalGraphDataset.value?.nodes.some(
          (node) => node.id === step.graphNodeId,
        ) ?? false
      )
    ) {
      return;
    }

    updateState({
      selectedGraphNodeId: step.graphNodeId,
      subgraphMode: "neighborhood",
      selectedSubgraphNodeId: step.graphNodeId,
      selectedSubgraphEdgeId: null,
    });
    return;
  }

  if (step.kind === "path") {
    if (isSavedAnalysis.value) { chooseSavedPath(step.pathId); return; }
    updateState({
      selectedPathId: step.pathId ?? workbenchState.value.selectedPathId,
      subgraphMode: "path",
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    });
    return;
  }

  if (step.kind === "candidate" && step.candidateId) {
    selectCandidate(step.candidateId);
  }
}

function activateReasoningStep(stepId: string) {
  const step = activeReasoningInspection.value.traceSteps.find(
    (item) => item.stepId === stepId,
  );
  if (!step) {
    return;
  }

  selectReasoningTraceStep(step);
}

function isReasoningStepActive(stepId: string) {
  return selectedTraceStepId.value === stepId;
}

function openGraphProvenance(state: ProvenanceInspectorState | null) {
  if (!state) {
    return;
  }

  provenanceInspectorState.value = state;
  provenanceInspectorVisible.value = true;
}

function openSelectedPathProvenance() {
  if (!activeCase.value) {
    return;
  }

  const pathId = activeReasoningInspection.value.selectedPath?.pathId ?? workbenchState.value.selectedPathId;
  if (isSavedAnalysis.value && pathId) {
    openGraphProvenance(buildSavedPathProvenance(activeCase.value, pathId, graphClaimBoundaryCopy.value, preferences.value.apiBaseUrl));
    return;
  }
  openGraphProvenance(
    buildGraphPathProvenance({
      caseDetail: activeCase.value,
      pathId,
      claimBoundary: graphClaimBoundaryCopy.value,
    }),
  );
}

function openEntityLinkProvenance(linkId: string) {
  if (!activeCase.value) {
    return;
  }

  openGraphProvenance(
    buildGraphEntityLinkProvenance({
      caseDetail: activeCase.value,
      linkId,
      claimBoundary: graphClaimBoundaryCopy.value,
    }),
  );
}

function openSelectedEdgeProvenance() {
  if (!activeCase.value || !activeCurationEdge.value) {
    return;
  }

  openGraphProvenance(
    buildGraphEdgeProvenance({
      caseDetail: activeCase.value,
      edge: activeCurationEdge.value,
      claimBoundary: graphClaimBoundaryCopy.value,
    }),
  );
}

function openLedgerRecordProvenance(item: ReviewLedgerDisplayItem) {
  if (!activeCase.value) {
    return;
  }

  if (item.target_type === "path") {
    openGraphProvenance(
      buildGraphPathProvenance({
        caseDetail: activeCase.value,
        pathId: item.target_id,
        claimBoundary: graphClaimBoundaryCopy.value,
      }),
    );
    return;
  }

  if (item.target_type === "entity_link") {
    openGraphProvenance(
      buildGraphEntityLinkProvenance({
        caseDetail: activeCase.value,
        linkId: item.target_id,
        claimBoundary: graphClaimBoundaryCopy.value,
      }),
    );
    return;
  }

  if (item.target_type === "correction") {
    openGraphProvenance(
      buildGraphCorrectionProvenance({
        caseDetail: activeCase.value,
        correctionId: item.target_id,
        claimBoundary: graphClaimBoundaryCopy.value,
      }),
    );
    return;
  }

  const sourceEdge =
    totalGraphDataset.value?.edges.find((edge) => edge.id === item.target_id) ??
    null;
  const fallbackEdge = sourceEdge
    ? sourceEdge
    : ({
        id: item.target_id,
        source: normalizeText(item.metadata?.source),
        target: normalizeText(item.metadata?.target),
        relation: normalizeText(item.metadata?.relation),
        confidence:
          typeof item.metadata?.confidence === "number"
            ? item.metadata.confidence
            : null,
        origin: undefined,
        attributes: {
          source: normalizeText(item.metadata?.source),
          evidence: normalizeText(item.metadata?.evidence),
        },
      } as const);

  openGraphProvenance(
    buildGraphEdgeProvenance({
      caseDetail: activeCase.value,
      edge: fallbackEdge,
      claimBoundary: graphClaimBoundaryCopy.value,
    }),
  );
}

function focusLedgerEdgeTarget(edgeId: string) {
  const edge =
    totalGraphDataset.value?.edges.find((item) => item.id === edgeId) ?? null;
  if (!edge) {
    return;
  }

  const centerNodeId =
    workbenchState.value.selectedGraphNodeId === edge.source ||
    workbenchState.value.selectedGraphNodeId === edge.target
      ? workbenchState.value.selectedGraphNodeId
      : edge.source;

  updateState({
    selectedGraphNodeId: centerNodeId,
    subgraphMode: "neighborhood",
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: edge.id,
  });
}

function handleLedgerRecordClick(item: ReviewLedgerDisplayItem) {
  if (!activeCase.value || !item.targetAvailable) {
    return;
  }

  selectedTraceStepId.value = null;

  if (item.target_type === "path") {
    updateState({
      selectedPathId: item.target_id,
      subgraphMode: "path",
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    });
    return;
  }

  if (item.target_type === "edge") {
    focusLedgerEdgeTarget(item.target_id);
    return;
  }

  if (item.target_type === "entity_link") {
    const link =
      activeCase.value.linked_entities?.find(
        (entry) =>
          typeof entry === "object" &&
          entry !== null &&
          !Array.isArray(entry) &&
          entry.link_id === item.target_id,
      ) ?? null;
    const nextObservation = resolveObservationForSelection(
      activeCase.value,
      typeof link === "object" && link
        ? ((link as Record<string, unknown>).obs_id as string | null)
        : null,
    );
    selectedTraceStepId.value = `entity:${item.target_id}`;
    updateState({
      selectedObservationId:
        nextObservation?.id ?? workbenchState.value.selectedObservationId,
      selectedGraphNodeId:
        typeof link === "object" &&
        link &&
        typeof (link as Record<string, unknown>).selected_entity_id === "string"
          ? ((link as Record<string, unknown>).selected_entity_id as string)
          : workbenchState.value.selectedGraphNodeId,
      subgraphMode:
        typeof link === "object" &&
        link &&
        typeof (link as Record<string, unknown>).selected_entity_id === "string"
          ? "neighborhood"
          : workbenchState.value.subgraphMode,
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    });
    return;
  }

  const correction =
    activeCase.value.correction_candidates?.find(
      (entry) =>
        typeof entry === "object" &&
        entry !== null &&
        !Array.isArray(entry) &&
        entry.candidate_id === item.target_id,
    ) ?? null;
  const nextObservation = resolveObservationForSelection(
    activeCase.value,
    typeof correction === "object" && correction
      ? ((correction as Record<string, unknown>).target_obs_id as string | null)
      : null,
  );
  if (nextObservation) {
    updateState({ selectedObservationId: nextObservation.id });
  }
}

function buildLedgerFriendlyError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  if (preferences.value.dataSourceMode === "backend") {
    return message.includes("404") || message.includes("405")
      ? "当前后端 review ledger 读取失败，请检查接口或当前 case 上下文。"
      : message;
  }

  return message;
}

async function loadReviewLedger() {
  if (!runDetail.value || !activeCase.value) {
    ledgerRecords.value = [];
    ledgerErrorMessage.value = "";
    return;
  }

  ledgerLoading.value = true;
  ledgerErrorMessage.value = "";

  try {
    const response = await getRootLensService().listReviewLedger({
      run_id: runDetail.value.run.run_id,
      case_id: activeCase.value.case_id,
      limit: 200,
    });
    ledgerRecords.value = response.records.filter((item) =>
      isBoundedReviewTargetType(item.target_type),
    );
  } catch (error) {
    ledgerRecords.value = [];
    ledgerErrorMessage.value = buildLedgerFriendlyError(error);
  } finally {
    ledgerLoading.value = false;
  }
}

function openCrossCaseCompare() {
  if (!activeReasoningInspection.value.candidate) {
    return;
  }

  crossCaseCompareOpen.value = true;
}

function jumpToRecurringCase(hit: RecurrenceCaseHit) {
  if (!runDetail.value) {
    return;
  }

  const nextCase = runDetail.value.cases.find(
    (item) => item.case_id === hit.caseId,
  );
  if (!nextCase) {
    return;
  }

  const baseSelection = buildCaseSelection(runDetail.value, hit.caseId);
  const matchedPathId = hit.matchedPathIds[0] ?? baseSelection.selectedPathId;
  const matchedCandidate = findCandidateForPathInCase(nextCase, matchedPathId);
  const reviewTargets =
    nextCase.review_targets ?? runDetail.value.review_targets ?? [];
  const nextReviewTarget =
    findReviewTargetInList(
      reviewTargets,
      "root_cause_candidate",
      matchedCandidate?.ranking_id ?? matchedCandidate?.candidate_id,
    ) ?? findReviewTargetInList(reviewTargets, "path", matchedPathId);
  const nextInspection = buildGraphReasoningInspection({
    runDetail: runDetail.value,
    caseDetail: nextCase,
    selectedCandidateId:
      matchedCandidate?.ranking_id ?? baseSelection.selectedCandidateId,
    selectedObservationId: hit.matchedObservationIds[0] ?? null,
    selectedPathId: matchedPathId,
  });
  const matchedObservation = hit.matchedObservationIds.length
    ? (nextInspection.supportingObservations.find(
        (item) =>
          hit.matchedObservationIds.includes(item.obsId) ||
          hit.matchedObservationIds.includes(item.sharedObservationId) ||
          (item.parentObservationId
            ? hit.matchedObservationIds.includes(item.parentObservationId)
            : false),
      ) ?? null)
    : null;

  pendingCaseSelectionPatch.value = {
    selectedCaseId: nextCase.case_id,
    selectedCandidateId:
      matchedCandidate?.ranking_id ?? baseSelection.selectedCandidateId,
    selectedPathId: matchedPathId ?? baseSelection.selectedPathId,
    selectedReviewTargetKey:
      nextReviewTarget?.target_key ?? baseSelection.selectedReviewTargetKey,
    selectedObservationId:
      matchedObservation?.sharedObservationId ??
      nextInspection.primaryObservation?.sharedObservationId ??
      null,
    selectedGraphNodeId: null,
    subgraphMode: "path",
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  };

  updateState({
    ...baseSelection,
    ...pendingCaseSelectionPatch.value,
  });
  feedbackCardTab.value = "trace";
  crossCaseCompareOpen.value = false;
  selectedTraceStepId.value = null;
  syncRouteQuery(runDetail.value.run.run_id, nextCase.case_id);
}

function syncRouteQuery(runId: string | null, caseId: string | null) {
  if (props.archiveOnly) {
    if (queryText(route.query.run_id) !== runId || queryText(route.query.case_id) !== caseId) {
      void router.replace(graphArchiveRoute(runId ?? undefined, caseId));
    }
    return;
  }
  const backend = preferences.value.dataSourceMode === "backend" && getLocalSessionMeta()?.source !== "import";
  const source = backend ? runDetail.value?.run.source_contract ?? null : null;
  const nextQuery = {
    ...route.query,
    run_id: runId ?? undefined,
    case_id: caseId ?? undefined,
    source: source ?? undefined,
  };

  const currentRunId =
    typeof route.query.run_id === "string" ? route.query.run_id : null;
  const currentCaseId =
    typeof route.query.case_id === "string" ? route.query.case_id : null;

  if (currentRunId === runId && currentCaseId === caseId && queryText(route.query.source) === source) {
    return;
  }

  void router.replace({
    query: nextQuery,
  });
}

function queryText(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function updateWorkingCaseDraft(
  caseId: string,
  updater: (draft: MockGraphCurationCaseDraft) => MockGraphCurationCaseDraft,
) {
  ensureCaseDraftLoaded(caseId);
  const current =
    workingCaseDrafts.value[caseId] ?? buildEmptyGraphCurationCaseDraft(caseId);
  const nextDraft = updater(deepClone(current));
  workingCaseDrafts.value = {
    ...workingCaseDrafts.value,
    [caseId]: nextDraft,
  };
}

function updateSelectedEdgeDraft(patch: Partial<MockGraphEdgeDraft>) {
  const caseId = activeCase.value?.case_id;
  const edge = activeCurationEdge.value;
  if (!caseId || !edge) {
    return;
  }

  updateWorkingCaseDraft(caseId, (caseDraft) => {
    const previous = caseDraft.edge_drafts.find(
      (draft) => draft.edge_id === edge.id,
    );
    const nextDraft: MockGraphEdgeDraft = {
      edge_id: edge.id,
      target_key:
        patch.target_key ??
        previous?.target_key ??
        readStringAttribute(edge.attributes, "target_key") ??
        edge.id,
      review_decision:
        patch.review_decision ??
        previous?.review_decision ??
        edgeDecisionFromReviewStatus(edge),
      relation: patch.relation ?? previous?.relation ?? edge.relation,
      confidence: Object.prototype.hasOwnProperty.call(patch, "confidence")
        ? (patch.confidence ?? null)
        : (previous?.confidence ?? edge.confidence ?? null),
      note: Object.prototype.hasOwnProperty.call(patch, "note")
        ? (patch.note ?? null)
        : (previous?.note ?? null),
      updated_at: new Date().toISOString(),
    };

    return replaceGraphEdgeDraft(caseDraft, nextDraft);
  });
}

function updateSelectedNodeDraft(patch: Partial<MockGraphNodeDraft>) {
  const caseId = activeCase.value?.case_id;
  const node = activeCurationNode.value;
  if (!caseId || !node) {
    return;
  }

  updateWorkingCaseDraft(caseId, (caseDraft) => {
    const previous = caseDraft.node_drafts.find(
      (draft) => draft.node_id === node.id,
    );
    const nextDraft: MockGraphNodeDraft = {
      node_id: node.id,
      display_name: Object.prototype.hasOwnProperty.call(patch, "display_name")
        ? (patch.display_name ?? null)
        : (previous?.display_name ?? node.name),
      aliases: Object.prototype.hasOwnProperty.call(patch, "aliases")
        ? (patch.aliases ?? null)
        : (previous?.aliases ?? node.aliases ?? null),
      description: Object.prototype.hasOwnProperty.call(patch, "description")
        ? (patch.description ?? null)
        : (previous?.description ?? node.description ?? null),
      note: Object.prototype.hasOwnProperty.call(patch, "note")
        ? (patch.note ?? null)
        : (previous?.note ?? null),
      updated_at: new Date().toISOString(),
    };

    return replaceGraphNodeDraft(caseDraft, nextDraft);
  });
}

async function saveCurrentCaseDraft() {
  if (props.archiveOnly) return;
  if (inspectingSavedPath.value) return;
  const caseId = activeCase.value?.case_id;
  const currentDraft = activeWorkingCaseDraft.value;
  if (!caseId || !currentDraft) {
    return;
  }

  if (editableGraphId.value) {
    try {
      const service = getRootLensService();
      const body = await service.getWorkingGraphPackage(editableGraphId.value);
      if (body.schema_version === "rootlens-working-graph.v2") {
        await openGraphPackage();
        throw new Error("此图由可执行知识生成。请在已打开的完整 JSON 中修改概念、绑定与规则；投影边不能单独改写。");
      }
      const edgeId = (edge: typeof body.edges[number]) => [edge.head, edge.relation, edge.tail, edge.scenario].join("|");
      const upsert_nodes = currentDraft.node_drafts.flatMap((draft) => {
        const node = body.nodes.find((n) => n.id === draft.node_id);
        return node ? [{ ...node, name: draft.display_name ?? node.name,
          aliases: draft.aliases ?? node.aliases, description: draft.description ?? node.description }] : [];
      });
      const delete_edge_ids: string[] = [];
      const upsert_edges = currentDraft.edge_drafts.flatMap((draft) => {
        if (draft.edge_id.startsWith("view:")) {
          throw new Error("解释反向视图不能直接改写物理关系，请在总图中选择对应源边后编辑。");
        }
        const edge = body.edges.find((e) => edgeId(e) === draft.edge_id);
        if (!edge) throw new Error(`当前工作图不存在 ${draft.edge_id}；请刷新并选择源边。`);
        const next: typeof body.edges[number] = { ...edge, relation: draft.relation ?? edge.relation,
          confidence: draft.confidence ?? edge.confidence,
          review_status: draft.review_decision === "reject" ? "rejected" : edge.review_status };
        if (next.relation !== edge.relation) { delete_edge_ids.push(edgeId(edge)); next.external_edge_id = ""; }
        return [next];
      });
      await service.mutateWorkingGraph(editableGraphId.value, { upsert_nodes, upsert_edges, delete_edge_ids });
      kgStudio.value = await service.kgStudio(editableGraphId.value);
    } catch (error) { errorMessage.value = String(error); return; }
  }
  saveGraphCurationCaseDraft(currentDraft);
  const savedCopy = deepClone(currentDraft);
  savedCaseDrafts.value = {
    ...savedCaseDrafts.value,
    [caseId]: savedCopy,
  };
  workingCaseDrafts.value = {
    ...workingCaseDrafts.value,
    [caseId]: deepClone(savedCopy),
  };
  actionMessage.value = editableGraphId.value ? "工作图已保存，新分析生效；历史结果未重算。" : `已保存 ${caseId} 的本地策展草稿。`;
}

function revertCurrentSelectionDraft() {
  const caseId = activeCase.value?.case_id;
  if (!caseId) {
    return;
  }

  updateWorkingCaseDraft(caseId, (caseDraft) => {
    if (activeCurationEdge.value) {
      const savedDraft =
        activeSavedCaseDraft.value?.edge_drafts.find(
          (draft) => draft.edge_id === activeCurationEdge.value?.id,
        ) ?? null;
      return replaceGraphEdgeDraft(
        caseDraft,
        savedDraft ? deepClone(savedDraft) : null,
      );
    }

    if (activeCurationNode.value) {
      const savedDraft =
        activeSavedCaseDraft.value?.node_drafts.find(
          (draft) => draft.node_id === activeCurationNode.value?.id,
        ) ?? null;
      return replaceGraphNodeDraft(
        caseDraft,
        savedDraft ? deepClone(savedDraft) : null,
      );
    }

    return caseDraft;
  });

  actionMessage.value = "已撤销当前选中项的未保存修改。";
}

function resetCurrentCaseDraft() {
  const caseId = activeCase.value?.case_id;
  if (!caseId) {
    return;
  }

  resetGraphCurationCaseDraft(caseId);
  const reloaded = loadGraphCurationCaseDraft(caseId);
  savedCaseDrafts.value = {
    ...savedCaseDrafts.value,
    [caseId]: deepClone(reloaded),
  };
  workingCaseDrafts.value = {
    ...workingCaseDrafts.value,
    [caseId]: deepClone(reloaded),
  };
  actionMessage.value = `已重置 ${caseId} 的本地策展草稿。`;
}

function focusCurationSuggestion(item: CurationSuggestion) {
  if (!totalGraphDataset.value) {
    return;
  }

  if (item.kind === "node") {
    updateState({
      selectedGraphNodeId: item.id,
      subgraphMode: "neighborhood",
      selectedSubgraphNodeId: item.id,
      selectedSubgraphEdgeId: null,
    });
    feedbackCardTab.value = "curation";
    return;
  }

  const edge = totalGraphDataset.value.edges.find(
    (edgeItem) => edgeItem.id === item.id,
  );
  if (!edge) {
    return;
  }

  const centerNodeId =
    workbenchState.value.selectedGraphNodeId === edge.source ||
    workbenchState.value.selectedGraphNodeId === edge.target
      ? workbenchState.value.selectedGraphNodeId
      : edge.source;

  updateState({
    selectedGraphNodeId: centerNodeId,
    subgraphMode: "neighborhood",
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: edge.id,
  });
  feedbackCardTab.value = "curation";
}

function focusSavedPath(path: PathGraphPath, observationId?: string | null, edgeId?: string | null) {
  const candidate = activeCase.value?.ranked_root_causes?.find(item => item.candidate_id === path.target_entity_id);
  const sameGraph = !!kgStudio.value?.graph_id && kgStudio.value.graph_id === activeCase.value?.reasoning_metadata?.graph_id;
  updateState({
    selectedPathId: path.path_id,
    selectedCandidateId: candidate?.ranking_id ?? null,
    selectedObservationId: savedPathObservation(path, observationId),
    selectedGraphNodeId: sameGraph && totalGraphDataset.value?.nodes.some(node => node.id === candidate?.candidate_id)
      ? candidate?.candidate_id ?? null : null,
    selectedReviewTargetKey: null,
    subgraphMode: "path", selectedSubgraphNodeId: null, selectedSubgraphEdgeId: edgeId ?? null,
  });
}

function chooseSavedPath(value: unknown) {
  const path = savedCandidatePaths.value.find(item => item.path_id === value);
  if (!path) return;
  selectedTraceStepId.value = null;
  focusSavedPath(path, workbenchState.value.selectedObservationId);
}

function selectCandidate(candidateId: string) {
  if (isSavedAnalysis.value) {
    selectedTraceStepId.value = null;
    if (workbenchState.value.selectedCandidateId === candidateId) {
      updateState({ selectedCandidateId: null, selectedPathId: null, selectedObservationId: null,
        selectedGraphNodeId: null, selectedReviewTargetKey: null, subgraphMode: "path",
        selectedSubgraphNodeId: null, selectedSubgraphEdgeId: null });
      return;
    }
    const candidate = activeCase.value?.ranked_root_causes?.find(item => item.ranking_id === candidateId);
    if (!candidate) return;
    const paths = savedPathsForCandidate(activeCase.value, candidate.candidate_id);
    const path = paths.find(item => item.supporting_evidence.includes(workbenchState.value.selectedObservationId)) ?? paths[0];
    if (path) focusSavedPath(path, workbenchState.value.selectedObservationId);
    else updateState({ selectedCandidateId: candidateId, selectedPathId: null, selectedObservationId: null,
      selectedGraphNodeId: null, selectedReviewTargetKey: null, subgraphMode: "path",
      selectedSubgraphNodeId: null, selectedSubgraphEdgeId: null });
    feedbackCardTab.value = "trace";
    return;
  }
  updateState(
    buildCandidateSelectionPatch({
      state: workbenchState.value,
      candidateId,
      candidates:
        activeCase.value?.ranked_root_causes ??
        runDetail.value?.ranked_root_causes ??
        [],
      pathGraph: activePathGraph.value,
      reviewTargets:
        activeCase.value?.review_targets ??
        runDetail.value?.review_targets ??
        [],
      totalGraphDataset: totalGraphDataset.value,
    }),
  );
}

function handleTotalGraphSelect(payload: GraphSelectPayload) {
  if (payload?.type === "edge") {
    updateState({ selectedGraphNodeId: payload.item.source, subgraphMode: "neighborhood",
      selectedSubgraphNodeId: null, selectedSubgraphEdgeId: payload.item.id });
    feedbackCardTab.value = "curation";
    return;
  }
  if (isSavedAnalysis.value && payload?.type === "node") {
    const id = payload.item.id === workbenchState.value.selectedGraphNodeId ? null : payload.item.id;
    updateState({ selectedGraphNodeId: id, subgraphMode: id ? "neighborhood" : "path",
      selectedSubgraphNodeId: id, selectedSubgraphEdgeId: null });
    return;
  }

  updateState(
    buildTotalGraphSelectionPatch({
      state: workbenchState.value,
      payload: payload
        ? {
            type: "node",
            nodeId: payload.item.id,
          }
        : null,
      candidates:
        activeCase.value?.ranked_root_causes ??
        runDetail.value?.ranked_root_causes ??
        [],
      pathGraph: activePathGraph.value,
      reviewTargets:
        activeCase.value?.review_targets ??
        runDetail.value?.review_targets ??
        [],
      totalGraphDataset: totalGraphDataset.value,
    }),
  );
}

function handleLocalGraphSelect(payload: LocalGraphSelectPayload) {
  const patch = buildLocalGraphSelectionPatch(workbenchState.value, payload);
  if (inspectingSavedPath.value && payload?.type === "edge" && patch.selectedSubgraphEdgeId) {
    const path = savedPathForEdge(activeCase.value, payload.id, activeCandidate.value?.candidate_id, activePath.value?.path_id);
    if (path) {
      selectedTraceStepId.value = null;
      focusSavedPath(path, workbenchState.value.selectedObservationId, payload.id);
      feedbackCardTab.value = "trace";
      return;
    }
  }
  updateState(patch);

  if (
    !props.archiveOnly && shouldAutoOpenCurationTabOnLocalGraphSelect({
      hasActiveCandidate: Boolean(activeCandidate.value),
      payload,
    })
  ) {
    feedbackCardTab.value = "curation";
  }
}

function handleRunChange(value: unknown) {
  const runId = typeof value === "string" && value.trim().length ? value : null;
  if (!runId) {
    return;
  }

  pendingCaseSelectionPatch.value = null;
  selectedTraceStepId.value = null;
  crossCaseCompareOpen.value = false;
  if (props.archiveOnly) { void router.replace(graphArchiveRoute(runId)); return; }
  const summary = runs.value.find(item => item.run_id === runId);
  const backend = preferences.value.dataSourceMode === "backend" && getLocalSessionMeta()?.source !== "import";
  const source = backend ? summary?.source_contract : undefined;
  void router.replace(source === "analysis-v2" ? savedAnalysisRoute("graphs", runId)
    : { name: "graphs", query: { run_id: runId, source } });
}

function handleCaseChange(value: unknown) {
  if (!runDetail.value) {
    return;
  }

  const caseId =
    typeof value === "string" && value.trim().length ? value : null;
  const nextSelection = buildCaseSelection(runDetail.value, caseId);

  pendingCaseSelectionPatch.value = null;
  selectedTraceStepId.value = null;
  crossCaseCompareOpen.value = false;
  updateState(nextSelection);
  syncRouteQuery(runDetail.value.run.run_id, nextSelection.selectedCaseId);
}

async function refreshWorkspace() {
  const revision = ++workspaceRevision;
  loading.value = true;
  errorMessage.value = "";
  reviewMessage.value = "";
  runDetail.value = null;
  kgStudio.value = null;
  bundledGraphDatasets.value = [];
  selectedTraceStepId.value = null;
  provenanceInspectorVisible.value = false;
  provenanceInspectorState.value = null;
  pendingCaseSelectionPatch.value = null;
  totalGraphRenderMessage.value = "正在准备总图谱...";
  localGraphRenderMessage.value = "";

  try {
    const replayActive = getLocalSessionMeta()?.source === "import";
    const useLocalGraphs =
      replayActive || preferences.value.dataSourceMode !== "backend";
    const savedIntent = props.archiveOnly ? null : savedAnalysisIntent(route.query);
    const requestedGraph = props.archiveOnly ? null : queryText(route.query.graph);
    const requestedRun = savedIntent?.runId ?? queryText(route.query.run_id);
    const requestedFrame = savedIntent?.frameId ?? queryText(route.query.case_id);
    const runSource = savedIntent ? "analysis-v2" : props.archiveOnly || route.query.source === "legacy-run" ? "legacy-run" : null;
    if (useLocalGraphs && (props.archiveOnly || runSource || requestedGraph)) {
      runs.value = [];
      throw new Error("此链接指向后端保存结果或工作图，请切换 Backend 后查看。");
    }
    const service = getRootLensService();
    const graphTask = useLocalGraphs
      ? loadUnifiedGraphs()
      : requestedGraph ? service.kgStudio(requestedGraph) : Promise.resolve(null);
    const [runsResult, graphResult, registryResult, explicitRunResult] = await Promise.allSettled([
      props.archiveOnly ? service.listArchivedRuns() : service.listRuns(),
      graphTask,
      useLocalGraphs || props.archiveOnly ? Promise.resolve({ graphs: [] }) : service.listWorkingGraphs(),
      requestedRun && (runSource || useLocalGraphs) ? service.getRun(requestedRun, runSource ?? "legacy-run") : Promise.resolve(null),
    ] as const);

    if (revision !== workspaceRevision) return;
    runs.value = runsResult.status === "fulfilled" ? runsResult.value : [];
    workingGraphs.value = registryResult.status === "fulfilled" ? registryResult.value.graphs : [];
    if (runsResult.status === "rejected" && !requestedRun && !requestedGraph) throw runsResult.reason;

    if (graphResult.status === "fulfilled") {
      if (useLocalGraphs && graphResult.value) {
        bundledGraphDatasets.value = (
          graphResult.value as { datasets: UnifiedGraphDataset[] }
        ).datasets;
      } else if (requestedGraph) {
        if ((graphResult.value as KGStudioPayload | null)?.graph_id !== requestedGraph) throw new Error("后端没有返回所选工作图。");
        kgStudio.value = graphResult.value as KGStudioPayload;
      }
    } else {
      if (useLocalGraphs) {
        totalGraphRenderMessage.value = replayActive
          ? "当前回放会话未包含 unified-graphs.json。"
          : "论文演示图谱加载失败。";
      } else {
        totalGraphRenderMessage.value = graphResult.reason instanceof Error ? graphResult.reason.message : "所选登记图不可用。";
      }
    }

    // A material task opens its exact graph without adopting an older run.
    if (requestedGraph && !requestedRun) return;
    if (explicitRunResult.status === "rejected") throw explicitRunResult.reason;
    let detail = explicitRunResult.value;
    if (!detail) {
      if (runsResult.status === "rejected") throw runsResult.reason;
      const next = requestedRun
        ? runs.value.find(item => item.run_id === requestedRun)
        : runs.value.find(item => item.run_id === workbenchState.value.selectedRunId) ?? runs.value[0];
      if (requestedRun && !next) throw new Error("未在运行目录中找到所选记录。");
      if (next) {
        const source = useLocalGraphs ? "legacy-run" : next.source_contract;
        if (!source) throw new Error("运行目录未标记记录来源。");
        detail = await service.getRun(next.run_id, source);
      }
    }
    if (revision !== workspaceRevision) return;
    if (requestedFrame && !detail?.cases.some(item => item.case_id === requestedFrame)) {
      throw new Error("所选运行不包含此证据范围。");
    }
    if (detail) {
      runDetail.value = detail;
      if (!runs.value.some(item => item.run_id === detail.run.run_id)) runs.value = [detail.run, ...runs.value];
      const caseId = requestedFrame ?? (workbenchState.value.selectedRunId === detail.run.run_id ? workbenchState.value.selectedCaseId : null);
      const nextSelection = buildCaseSelection(detail, caseId);
      updateState({ selectedRunId: detail.run.run_id, selectedRunSource: useLocalGraphs ? null : detail.run.source_contract ?? null, ...nextSelection });
      syncRouteQuery(detail.run.run_id, nextSelection.selectedCaseId);
    }

    if (!useLocalGraphs && !requestedGraph && !props.archiveOnly) {
      const graphId = detail?.reasoning_metadata?.graph_id ?? detail?.cases[0]?.reasoning_metadata?.graph_id;
      if (detail?.run.source_contract === "analysis-v2" && !graphId) {
        totalGraphRenderMessage.value = "保存结果未记录登记图；本次路径仍可独立查看。";
        return;
      }
      try {
        const studio = await service.kgStudio(graphId ?? undefined);
        if (revision !== workspaceRevision) return;
        if (graphId && studio.graph_id !== graphId) throw new Error("后端没有返回所选登记图。");
        kgStudio.value = studio;
      } catch (error) {
        if (revision !== workspaceRevision) return;
        totalGraphRenderMessage.value = error instanceof Error ? error.message : String(error);
      }
    }
  } catch (error) {
    if (revision === workspaceRevision) errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    if (revision === workspaceRevision) loading.value = false;
  }
}

async function handleFeedbackSubmit() {
  if (props.archiveOnly) return;
  if (!activeCase.value || !activeSubmitTarget.value) {
    reviewMessage.value = "当前没有可提交的反馈目标。";
    return;
  }

  errorMessage.value = "";
  reviewMessage.value = "";

  try {
    const response = await getRootLensService().submitReview({
      run_id: runDetail.value?.run.run_id,
      case_id: activeCase.value.case_id,
      target_type: activeSubmitTarget.value.target_type,
      target_id: activeSubmitTarget.value.target_id,
      action: feedbackForm.action,
      note: feedbackForm.note,
      reviewer: feedbackForm.reviewer,
      source: feedbackForm.source,
    });

    reviewMessage.value = `反馈已记录：${String(response.record.feedback_id ?? response.status)}`;
    await loadReviewLedger();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  }
}

watch(
  [() => preferences.value.dataSourceMode, () => preferences.value.apiBaseUrl],
  () => {
    packageRevision += 1;
    packageBusy.value = false;
    packageDrawerOpen.value = false;
    packageGraphId.value = null;
    runDetail.value = null; runs.value = []; kgStudio.value = null; bundledGraphDatasets.value = [];
    updateState(sourceSelectionReset());
    void refreshWorkspace();
  },
);

watch(
  () => [queryText(route.query.run_id), queryText(route.query.case_id), queryText(route.query.source), queryText(route.query.graph)] as const,
  ([runId, caseId, source, graphId], [, , , previousGraphId]) => {
    if (route.name !== (props.archiveOnly ? "graph-archive" : "graphs")) return;
    if (!runId && graphId && kgStudio.value?.graph_id === graphId && !runDetail.value) return;
    if (runId && runId === runDetail.value?.run.run_id && graphId === previousGraphId
        && (source === "analysis-v2") === isSavedAnalysis.value) {
      if (!caseId || caseId === activeCase.value?.case_id) return;
      if (runDetail.value.cases.some(item => item.case_id === caseId)) { handleCaseChange(caseId); return; }
    }
    void refreshWorkspace();
  },
);

watch(
  () => feedbackCardTab.value,
  (tab) => {
    if (tab === "ledger") {
      void loadReviewLedger();
    }
  },
);

watch(
  () => activeCandidate.value?.ranking_id,
  (candidateId, previousCandidateId) => {
    if (candidateId === previousCandidateId) {
      return;
    }

    selectedTraceStepId.value = null;
    if (!candidateId) {
      crossCaseCompareOpen.value = false;
    }
  },
);

watch(
  [() => runDetail.value?.run.run_id, () => activeCase.value?.case_id],
  ([runId, caseId], [previousRunId, previousCaseId]) => {
    if (!runId || !caseId) {
      ledgerRecords.value = [];
      ledgerErrorMessage.value = "";
      return;
    }

    if (runId !== previousRunId || caseId !== previousCaseId) {
      ledgerRecords.value = [];
      ledgerErrorMessage.value = "";
      if (feedbackCardTab.value === "ledger") {
        void loadReviewLedger();
      }
    }
  },
);

watch(
  () => activeCase.value?.case_id,
  (caseId, previousCaseId) => {
    if (!caseId) {
      return;
    }

    if (!props.archiveOnly) ensureCaseDraftLoaded(caseId);
    actionMessage.value = "";

    if (caseId !== previousCaseId) {
      selectedTraceStepId.value = null;
      provenanceInspectorVisible.value = false;
      provenanceInspectorState.value = null;
      if (feedbackCardTab.value === "curation") {
        feedbackCardTab.value = "rca";
      }
    }

    if (!runDetail.value || caseId === previousCaseId) {
      return;
    }

    const pendingSelection =
      pendingCaseSelectionPatch.value?.selectedCaseId === caseId
        ? pendingCaseSelectionPatch.value
        : null;
    const nextSelection = {
      ...buildCaseSelection(runDetail.value, caseId),
      ...(pendingSelection ?? {}),
    };
    const nextSelectedObservationId =
      pendingSelection?.selectedObservationId ??
      workbenchState.value.selectedObservationId;

    if (
      nextSelection.selectedCandidateId !==
        workbenchState.value.selectedCandidateId ||
      nextSelection.selectedPathId !== workbenchState.value.selectedPathId ||
      nextSelection.selectedReviewTargetKey !==
        workbenchState.value.selectedReviewTargetKey ||
      nextSelection.selectedGraphNodeId !==
        workbenchState.value.selectedGraphNodeId ||
      nextSelection.subgraphMode !== workbenchState.value.subgraphMode ||
      nextSelectedObservationId !== workbenchState.value.selectedObservationId
    ) {
      updateState(nextSelection);
    }

    pendingCaseSelectionPatch.value = null;
    syncRouteQuery(runDetail.value.run.run_id, caseId);
  },
);

watch(
  [totalGraphDataset, () => workbenchState.value.selectedGraphNodeId],
  ([dataset, selectedGraphNodeId]) => {
    if (!selectedGraphNodeId) {
      return;
    }

    const hasNode =
      dataset?.nodes.some((node) => node.id === selectedGraphNodeId) ?? false;
    if (!hasNode) {
      updateState({
        selectedGraphNodeId: null,
        subgraphMode: "path",
        selectedSubgraphNodeId: null,
        selectedSubgraphEdgeId: null,
      });
    }
  },
);

watch(
  [
    activeLocalGraphDataset,
    () => workbenchState.value.selectedSubgraphNodeId,
    () => workbenchState.value.selectedSubgraphEdgeId,
  ],
  ([dataset, selectedNodeId, selectedEdgeId]) => {
    const patch: Record<string, string | null> = {};

    if (
      selectedNodeId &&
      !(dataset?.nodes.some((node) => node.id === selectedNodeId) ?? false)
    ) {
      patch.selectedSubgraphNodeId = null;
    }

    if (
      selectedEdgeId &&
      !(dataset?.edges.some((edge) => edge.id === selectedEdgeId) ?? false)
    ) {
      patch.selectedSubgraphEdgeId = null;
    }

    if (Object.keys(patch).length) {
      updateState(patch);
    }
  },
);

watch(
  [activeObservationContext, selectedObservationTraceSteps],
  ([value, traceSteps]) => {
    if (
      !value &&
      !traceSteps.length &&
      workbenchState.value.selectedObservationId
    ) {
      updateState({ selectedObservationId: null });
    }
  },
);

onMounted(() => {
  void refreshWorkspace();
});
onBeforeUnmount(() => { workspaceRevision += 1; packageRevision += 1; });
</script>

<template>
  <div
    class="rl-page rl-screen"
    :class="{ 'rl-page--motion': preferences.enablePageEntranceMotion }"
  >
    <a-alert v-if="errorMessage" class="rl-alert" type="error" :title="errorMessage" />

    <a-drawer v-if="!archiveOnly" v-model:visible="packageDrawerOpen" title="工作图与可执行画像" :width="760" :footer="false">
      <a-space direction="vertical" fill>
        <a-select placeholder="选择工作图" :model-value="packageGraphId ?? undefined" :disabled="packageBusy" @change="(id: string) => selectPackageGraph(id)">
          <a-option v-for="graph in workingGraphs" :key="graph.graph_id" :value="graph.graph_id">{{ graph.title }} · {{ graph.dataset }}</a-option>
        </a-select>
        <p>编辑节点、关系、别名与条件；v2 包请修改 knowledge 中的实体、绑定和规则。删除被引用对象前须同步修改相关规则；保存影响新分析，历史运行保持原结果。</p>
        <a-textarea v-model="packageText" :disabled="packageBusy" :auto-size="{ minRows: 18, maxRows: 28 }" aria-label="完整工作图包 JSON" />
        <a-space wrap>
          <a-button type="primary" :loading="packageBusy" :disabled="!packageGraphId || !packageDirty" @click="savePackage(false)">保存当前图</a-button>
          <a-button v-if="packageGraph?.knowledge && !packageGraph.enabled" :loading="packageBusy"
            :disabled="packageGraph.status !== 'ready' || packageDirty" @click="enablePackageGraph">投入使用</a-button>
          <a-button v-if="currentGraphEnabled && packageGraphId === editableGraphId" :disabled="packageDirty || packageBusy" @click="useCurrentGraph">用这张图分析</a-button>
          <a-button :disabled="!packageText" @click="downloadPackage">导出完整包</a-button>
          <a-button :loading="packageBusy" :disabled="!packageText" @click="savePackage(true)">导入为新图</a-button>
          <a-button v-if="workingGraphs.find(g => g.graph_id === editableGraphId)?.dataset === 'mvtec' && !workingGraphs.find(g => g.graph_id === editableGraphId)?.knowledge" :disabled="!editableGraphId" @click="rebuildGraphProfiles">按关系重建画像</a-button>
          <label>导入 JSON <input type="file" accept=".json" :disabled="packageBusy" @change="importPackageFile" /></label>
        </a-space>
        <a-tag v-if="packageGraph" :color="packageGraph.enabled ? 'green' : 'gray'">{{ packageGraph.enabled ? '已投入使用' : '未启用' }}</a-tag>
        <a-alert v-if="errorMessage" type="error">{{ errorMessage }}</a-alert>
        <a-alert v-if="actionMessage" type="success">{{ actionMessage }}</a-alert>
      </a-space>
    </a-drawer>
    <section class="workspace-shell">
      <div class="workspace-shell__main workspace-stack">
        <article v-if="!archiveOnly" class="rl-section-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">
                <SectionCardTitle :title="totalGraphTitle" :help="totalGraphHelp">
                  <icon-relation />
                </SectionCardTitle>
              </h3>
            </div>
            <div class="rl-panel-actions">
              <div class="rl-inline-tags">
                <a-tag color="green">{{ totalGraphDataset?.nodes.length ?? 0 }} 节点</a-tag>
                <a-tag color="gold">{{ totalGraphDataset?.edges.length ?? 0 }} 边</a-tag>
              </div>
              <a-button v-if="preferences.dataSourceMode === 'backend' && getLocalSessionMeta()?.source !== 'import'" @click="openGraphPackage">管理工作图</a-button>
              <a-button v-if="currentGraphEnabled" :disabled="loading || (packageGraphId === editableGraphId && packageDirty)" @click="useCurrentGraph">用这张图分析</a-button>
              <a-button :loading="loading" @click="refreshWorkspace">
                <template #icon><icon-refresh /></template>
                刷新视图
              </a-button>
              <a-button @click="returnToEvidence">返回运行与证据</a-button>
            </div>
          </header>
          <div class="rl-section-card__body workspace-graph-stage">
            <KnowledgeForceGraph
              v-if="totalGraphDataset"
              :dataset="totalGraphDataset"
              :show-labels="false"
              search-term=""
              :focused-node-ids="totalGraphFocusedNodeIds"
              :focused-edge-ids="totalGraphFocusedEdgeIds"
              :selected-node-id="workbenchState.selectedGraphNodeId"
              @select="handleTotalGraphSelect"
              @render-state="(payload) => (totalGraphRenderMessage = payload.message)"
            />
            <a-empty v-else>暂无总图谱数据</a-empty>
          </div>
          <div class="rl-section-card__footer">
            <span v-if="currentWorkingGraph" class="workspace-subtle" :title="currentWorkingGraph.graph_id">
              {{ currentWorkingGraph.title }} · {{ currentWorkingGraph.enabled ? '已启用' : '未启用' }}
            </span>
            <span class="workspace-subtle">{{ totalGraphRenderMessage }}</span>
          </div>
        </article>

        <section class="workspace-bottom-grid workspace-bottom-grid--graphs-main">
          <article class="rl-section-card workspace-graph-bottom-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle :title="archiveOnly ? '本次保存路径' : localGraphTitle" :help="localGraphHelp">
                    <icon-relation />
                  </SectionCardTitle>
                </h3>
              </div>
              <a-button v-if="isSavedAnalysis && activeSubgraphMode === 'neighborhood' && pathSubgraphDataset" type="text" size="small"
                @click="updateState({ subgraphMode: 'path', selectedSubgraphNodeId: null, selectedSubgraphEdgeId: null })">回到保存路径</a-button>
            </header>
            <div class="rl-section-card__body workspace-graph-stage workspace-graph-stage--local">
              <RunPathGraph
                v-if="activeLocalGraphDataset"
                :dataset="activeLocalGraphDataset"
                :render-key="localGraphRenderKey"
                :mode="activeSubgraphMode"
                :focused-node-ids="localGraphFocusedNodeIds"
                :focused-edge-ids="localGraphFocusedEdgeIds"
                :selected-node-id="workbenchState.selectedSubgraphNodeId"
                :selected-edge-id="workbenchState.selectedSubgraphEdgeId"
                @select="handleLocalGraphSelect"
                @render-state="(payload) => (localGraphRenderMessage = payload.message)"
              />
              <div v-else class="workspace-graph-stage__empty">
                <a-empty>{{ isSavedAnalysis ? '本窗口没有保存的推理路径' : '暂无局部子图' }}</a-empty>
              </div>
            </div>
            <div class="rl-section-card__footer">
              <span v-if="inspectingSavedPath" class="workspace-subtle" :title="activeCase?.reasoning_metadata?.graph_id ?? undefined">
                {{ runDetail?.summary?.graph_title ?? '分析时的知识快照' }} · 只读
              </span>
              <span class="workspace-subtle">{{ localGraphRenderMessage }}</span>
            </div>
          </article>

          <article class="rl-section-card workspace-feedback-card workspace-graph-bottom-card">
            <header class="rl-section-card__header workspace-feedback-card__header">
              <h3 class="rl-section-card__title">
                <SectionCardTitle :title="archiveOnly ? '档案解释' : '审阅与策展卡'" :help="feedbackCardHelp">
                  <icon-info-circle />
                </SectionCardTitle>
              </h3>
              <a-tooltip :content="feedbackCardBadge" position="left">
                <a-tag color="gold" class="workspace-feedback-card__badge">
                  {{ feedbackCardBadge }}
                </a-tag>
              </a-tooltip>
            </header>
            <div class="rl-section-card__body workspace-feedback-card__body">
              <a-tabs
                v-model:active-key="feedbackCardTab"
                lazy-load
                destroy-on-hide
                class="workspace-feedback-tabs"
                aria-label="审阅与策展"
              >
                <a-tab-pane key="rca" title="RCA">
                  <a-form
                    id="graph-form-1"
                    :model="feedbackForm"
                    layout="vertical"
                    class="workspace-feedback-compact workspace-feedback-compact--dense workspace-form"
                  >
                    <div
                      class="workspace-summary-list workspace-summary-list--two-col workspace-feedback-summary-list workspace-feedback-compact__summary"
                    >
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-bulb />
                          <span>当前候选</span>
                        </span>
                        <strong :title="activeCandidate?.candidate_name ?? '--'">
                          {{ activeCandidate?.candidate_name ?? '--' }}
                        </strong>
                      </div>
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-relation />
                          <span>当前路径</span>
                        </span>
                        <strong :title="activePath?.path_id ?? '--'">
                          {{ activePath?.path_id ?? '--' }}
                        </strong>
                      </div>
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-info-circle />
                          <span>反馈目标</span>
                        </span>
                        <strong
                          :title="
                            activeSubmitTarget?.label ?? activeSubmitTarget?.target_type ?? '--'
                          "
                        >
                          {{ activeSubmitTarget?.target_type ?? '--' }}
                        </strong>
                      </div>
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-storage />
                          <span>得分</span>
                        </span>
                        <strong>{{ formatScore(activeCandidate?.score) }}</strong>
                      </div>
                    </div>

                    <div v-if="!archiveOnly" class="workspace-feedback-compact__decision-bar">
                      <a-button
                        size="small"
                        :type="feedbackForm.action === 'accept' ? 'primary' : 'outline'"
                        class="workspace-feedback-compact__decision-button workspace-feedback-compact__decision-button--accept"
                        @click="feedbackForm.action = 'accept'"
                      >
                        接受
                      </a-button>
                      <a-button
                        size="small"
                        status="danger"
                        :type="feedbackForm.action === 'reject' ? 'primary' : 'outline'"
                        class="workspace-feedback-compact__decision-button workspace-feedback-compact__decision-button--reject"
                        @click="feedbackForm.action = 'reject'"
                      >
                        拒绝
                      </a-button>
                    </div>

                    <a-form-item
                      v-if="!archiveOnly"
                      field="note"
                      label="备注"
                      :label-attrs="{ for: 'graph-feedbackForm-note-input' }"
                      class="workspace-form-item workspace-feedback-compact__field workspace-feedback-compact__field--grow"
                    >
                      <a-textarea
                        :textarea-attrs="{
                          id: 'graph-feedbackForm-note-input',
                          'aria-label': '备注',
                        }"
                        id="graph-feedbackForm-note"
                        aria-label="备注"
                        v-model="feedbackForm.note"
                        class="workspace-feedback-compact__textarea"
                        placeholder="记录备注"
                      />
                    </a-form-item>

                    <div v-if="!archiveOnly" class="workspace-feedback-compact__footer">
                      <a-button type="primary" @click="handleFeedbackSubmit">
                        <template #icon>
                          <icon-send />
                        </template>
                        提交反馈
                      </a-button>
                    </div>

                    <a-alert
                      v-if="reviewMessage"
                      class="workspace-feedback-inline-alert"
                      :type="reviewMessage.startsWith('反馈已记录') ? 'success' : 'warning'"
                      :show-icon="false"
                      :title="reviewMessage"
                    />
                  </a-form>
                </a-tab-pane>
                <a-tab-pane v-if="!archiveOnly" key="curation" title="策展">
                  <section v-if="inspectingSavedPath" class="workspace-feedback-pane workspace-feedback-pane--curation">
                    <div class="workspace-claim-note workspace-claim-note--compact">
                      <strong>本次保存路径 · 只读</strong>
                      <span>编辑当前登记图不会改写这些边和节点。</span>
                    </div>
                    <p v-if="activeCurationNode" :title="activeCurationNode.id">节点 · {{ activeCurationNode.name }}</p>
                    <p v-if="activeCurationEdge" :title="activeCurationEdge.id">源边 · {{ activeCurationEdge.relation }}</p>
                    <a-button v-if="activePath" size="small" @click="openSelectedPathProvenance">查看保存来源</a-button>
                  </section>
                  <section v-else class="workspace-feedback-pane workspace-feedback-pane--curation">
                    <div class="workspace-feedback-pane__section">
                      <div class="workspace-feedback-pane__section-head">
                        <strong>
                          {{
                            activeCurationEdge
                              ? '边策展'
                              : activeCurationNode
                                ? '节点策展'
                                : '图谱策展'
                          }}
                        </strong>
                        <span>
                          {{ activeCurationEdge ? '边' : activeCurationNode ? '节点' : '待选' }}
                        </span>
                      </div>

                      <a-form
                        id="graph-form-2"
                        :model="selectedEdgeDraft ?? {}"
                        layout="vertical"
                        v-if="activeCurationEdge"
                        class="workspace-curation-panel workspace-form"
                      >
                        <div class="workspace-curation-meta">
                          <a-tooltip
                            :content="
                              normalizeText(
                                readStringAttribute(activeCurationEdge.attributes, 'evidence'),
                                '当前边没有附带 evidence snippet。',
                              )
                            "
                            position="top"
                          >
                            <div class="workspace-claim-note workspace-feedback-snippet-card">
                              <span class="workspace-summary-label">
                                <icon-info-circle />
                                <span>Evidence</span>
                              </span>
                              <strong class="workspace-feedback-snippet">
                                {{
                                  normalizeText(
                                    readStringAttribute(activeCurationEdge.attributes, 'evidence'),
                                    '当前边没有附带 evidence snippet。',
                                  )
                                }}
                              </strong>
                            </div>
                          </a-tooltip>
                          <a-button size="small" @click="openSelectedEdgeProvenance">
                            Inspect Provenance
                          </a-button>
                        </div>

                        <a-form-item
                          label="审阅决策"
                          :label-attrs="{ for: 'graph-edgeDecisionModel-input' }"
                          class="workspace-form-item"
                        >
                          <div
                            id="graph-edgeDecisionModel"
                            v-control-label="'审阅决策'"
                            class="workspace-control"
                          >
                            <a-select aria-label="审阅决策" v-model="edgeDecisionModel">
                              <a-option value="accept">accept</a-option>
                              <a-option value="reject">reject</a-option>
                              <a-option value="revise">revise</a-option>
                              <a-option value="needs_completion">needs_completion</a-option>
                            </a-select>
                          </div>
                        </a-form-item>

                        <div class="workspace-form-row workspace-form-row--two">
                          <a-form-item
                            label="关系"
                            :label-attrs="{ for: 'graph-edgeRelationModel-input' }"
                            class="workspace-form-item"
                          >
                            <a-input
                              :input-attrs="{
                                id: 'graph-edgeRelationModel-input',
                                'aria-label': '关系',
                              }"
                              id="graph-edgeRelationModel"
                              aria-label="关系"
                              v-model="edgeRelationModel"
                              placeholder="修改 relation 文本"
                            />
                          </a-form-item>
                          <a-form-item
                            label="置信度"
                            :label-attrs="{ for: 'graph-edgeConfidenceModel-input' }"
                            class="workspace-form-item"
                          >
                            <a-input-number
                              :input-attrs="{
                                id: 'graph-edgeConfidenceModel-input',
                                'aria-label': '置信度',
                              }"
                              id="graph-edgeConfidenceModel"
                              aria-label="置信度"
                              v-model="edgeConfidenceModel"
                              :min="0"
                              :max="1"
                              :step="0.01"
                              :precision="2"
                            />
                          </a-form-item>
                        </div>

                        <a-form-item
                          label="备注"
                          :label-attrs="{ for: 'graph-edgeNoteModel-input' }"
                          class="workspace-form-item workspace-curation-panel__field workspace-curation-panel__field--grow"
                        >
                          <a-textarea
                            :textarea-attrs="{
                              id: 'graph-edgeNoteModel-input',
                              'aria-label': '备注',
                            }"
                            id="graph-edgeNoteModel"
                            aria-label="备注"
                            v-model="edgeNoteModel"
                            class="workspace-curation-panel__textarea"
                            placeholder="记录为什么接受、拒绝或修订这条边。"
                          />
                        </a-form-item>
                      </a-form>

                      <a-form
                        id="graph-form-3"
                        :model="selectedNodeDraft ?? {}"
                        layout="vertical"
                        v-else-if="activeCurationNode"
                        class="workspace-curation-panel workspace-form"
                      >
                        <div
                          class="workspace-summary-list workspace-summary-list--two-col workspace-feedback-summary-list"
                        >
                          <div class="workspace-summary-list__item">
                            <span class="workspace-summary-label">
                              <icon-relation />
                              <span>节点 ID</span>
                            </span>
                            <strong>{{ activeCurationNode.id }}</strong>
                          </div>
                          <div class="workspace-summary-list__item">
                            <span class="workspace-summary-label">
                              <icon-info-circle />
                              <span>场景</span>
                            </span>
                            <strong>
                              {{
                                normalizeText(
                                  readStringAttribute(activeCurationNode.attributes, 'scenario'),
                                  activeCurationNode.category,
                                )
                              }}
                            </strong>
                          </div>
                          <div class="workspace-summary-list__item">
                            <span class="workspace-summary-label">
                              <icon-storage />
                              <span>Kind</span>
                            </span>
                            <strong>{{ normalizeText(activeCurationNode.kind) }}</strong>
                          </div>
                          <div class="workspace-summary-list__item">
                            <span class="workspace-summary-label">
                              <icon-bulb />
                              <span>说明</span>
                            </span>
                            <strong>{{ normalizeText(activeCurationNode.description) }}</strong>
                          </div>
                        </div>

                        <div class="workspace-form-row workspace-form-row--two">
                          <a-form-item
                            label="显示名称"
                            :label-attrs="{ for: 'graph-nodeDisplayNameModel-input' }"
                            class="workspace-form-item"
                          >
                            <a-input
                              :input-attrs="{
                                id: 'graph-nodeDisplayNameModel-input',
                                'aria-label': '显示名称',
                              }"
                              id="graph-nodeDisplayNameModel"
                              aria-label="显示名称"
                              v-model="nodeDisplayNameModel"
                              placeholder="节点展示名"
                            />
                          </a-form-item>
                          <a-form-item
                            label="别名"
                            :label-attrs="{ for: 'graph-nodeAliasesModel-input' }"
                            class="workspace-form-item"
                          >
                            <a-input
                              :input-attrs="{
                                id: 'graph-nodeAliasesModel-input',
                                'aria-label': '别名',
                              }"
                              id="graph-nodeAliasesModel"
                              aria-label="别名"
                              v-model="nodeAliasesModel"
                              placeholder="alias1, alias2"
                            />
                          </a-form-item>
                        </div>

                        <a-form-item
                          label="描述"
                          :label-attrs="{ for: 'graph-nodeDescriptionModel-input' }"
                          class="workspace-form-item workspace-curation-panel__field workspace-curation-panel__field--grow"
                        >
                          <a-textarea
                            :textarea-attrs="{
                              id: 'graph-nodeDescriptionModel-input',
                              'aria-label': '描述',
                            }"
                            id="graph-nodeDescriptionModel"
                            aria-label="描述"
                            v-model="nodeDescriptionModel"
                            class="workspace-curation-panel__textarea"
                            placeholder="补充节点说明或更保守的解释文案。"
                          />
                        </a-form-item>

                        <a-form-item
                          label="备注"
                          :label-attrs="{ for: 'graph-nodeNoteModel-input' }"
                          class="workspace-form-item"
                        >
                          <a-textarea
                            :textarea-attrs="{
                              id: 'graph-nodeNoteModel-input',
                              'aria-label': '备注',
                            }"
                            id="graph-nodeNoteModel"
                            aria-label="备注"
                            v-model="nodeNoteModel"
                            :auto-size="{ minRows: 3, maxRows: 5 }"
                            placeholder="策展备注（仅保存在本地草稿）"
                          />
                        </a-form-item>
                      </a-form>

                      <div v-else class="workspace-curation-empty">
                        <p>先在左侧局部子图中点击节点或边，再进入对应的本地策展表单。</p>
                        <div
                          v-if="activeCurationSuggestions.length"
                          class="workspace-curation-suggestions"
                        >
                          <button
                            v-for="item in activeCurationSuggestions"
                            :key="`${item.kind}:${item.id}`"
                            type="button"
                            class="workspace-curation-suggestion"
                            @click="focusCurationSuggestion(item)"
                          >
                            <strong>
                              {{ item.kind === 'edge' ? '边' : '节点' }} · {{ item.label }}
                            </strong>
                            <span>{{ item.subtitle }}</span>
                          </button>
                        </div>
                      </div>
                    </div>

                    <div class="workspace-curation-actions">
                      <a-button type="primary" @click="saveCurrentCaseDraft">
                        <template #icon>
                          <icon-save />
                        </template>
                        {{ editableGraphId ? "保存工作图" : "保存草稿" }}
                      </a-button>
                      <a-button
                        :disabled="!canRevertCurrentSelection"
                        @click="revertCurrentSelectionDraft"
                      >
                        撤销修改
                      </a-button>
                      <a-button status="warning" @click="resetCurrentCaseDraft">重置草稿</a-button>
                    </div>

                    <div
                      class="workspace-feedback-status"
                      :class="{
                        'workspace-feedback-status--success':
                          hasUnsavedCurationChanges === false && !!actionMessage,
                      }"
                    >
                      <div class="workspace-feedback-status__header">
                        <icon-check-circle v-if="actionMessage" />
                        <strong>
                          {{
                            actionMessage ||
                            (hasUnsavedCurationChanges
                              ? '当前有未保存的本地策展修改。'
                              : '当前 case 没有未保存改动。')
                          }}
                        </strong>
                      </div>
                      <div class="workspace-feedback-status__meta">
                        <span>未保存修改：{{ hasUnsavedCurationChanges ? '有' : '无' }}</span>
                        <span>节点草稿：{{ activeWorkingCaseDraft?.node_drafts.length ?? 0 }}</span>
                        <span>边草稿：{{ activeWorkingCaseDraft?.edge_drafts.length ?? 0 }}</span>
                      </div>
                    </div>
                  </section>
                </a-tab-pane>
                <a-tab-pane key="trace" title="链路">
                  <section class="workspace-feedback-pane workspace-feedback-pane--trace">
                    <div
                      class="workspace-feedback-pane__section workspace-feedback-pane__section--trace"
                    >
                      <div
                        class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
                      >
                        <strong>推理链路</strong>
                        <a-button
                          size="mini"
                          :disabled="!activeReasoningInspection.candidate"
                          @click="openCrossCaseCompare"
                        >
                          Compare
                        </a-button>
                      </div>

                      <SavedObservationLocation v-if="isSavedAnalysis && activeCase && activeObservationContext"
                        :case-detail="activeCase" :observation="activeObservationContext" :api-base="preferences.apiBaseUrl" />
                      <template v-if="activeReasoningInspection.candidate">
                        <div class="workspace-reasoning-trace">
                          <section class="workspace-reasoning-trace__section">
                            <div
                              class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
                            >
                              <strong>Candidate</strong>
                              <span
                                :title="activeReasoningInspection.candidate.selectedPathId ?? '--'"
                              >
                                {{ activeReasoningInspection.candidate.selectedPathId ?? '--' }}
                              </span>
                            </div>
                            <div
                              class="workspace-summary-list workspace-summary-list--two-col workspace-feedback-summary-list"
                            >
                              <div class="workspace-summary-list__item">
                                <span class="workspace-summary-label">Candidate</span>
                                <strong :title="activeReasoningInspection.candidate.candidateName">
                                  {{ activeReasoningInspection.candidate.candidateName }}
                                </strong>
                              </div>
                              <div class="workspace-summary-list__item">
                                <span class="workspace-summary-label">Rank / Score</span>
                                <strong>
                                  #{{ activeReasoningInspection.candidate.rank ?? '--' }}
                                  ·
                                  {{ formatScore(activeReasoningInspection.candidate.score) }}
                                </strong>
                              </div>
                              <div class="workspace-summary-list__item">
                                <span class="workspace-summary-label">Method / Role</span>
                                <strong
                                  :title="`${formatScoringMethodLabel(activeReasoningInspection.candidate.scoringMethod)} · ${normalizeText(activeReasoningInspection.candidate.role, 'candidate')}`"
                                >
                                  {{
                                    formatScoringMethodLabel(
                                      activeReasoningInspection.candidate.scoringMethod,
                                    )
                                  }}
                                  ·
                                  {{
                                    normalizeText(
                                      activeReasoningInspection.candidate.role,
                                      'candidate',
                                    )
                                  }}
                                </strong>
                              </div>
                              <div class="workspace-summary-list__item">
                                <span class="workspace-summary-label">Obs / Links</span>
                                <strong>
                                  {{
                                    activeReasoningInspection.candidate.supportingObservationCount
                                  }}
                                  /
                                  {{ activeReasoningInspection.candidate.linkedEntityCount }}
                                </strong>
                              </div>
                            </div>
                            <p
                              v-if="typeof activeCandidate?.scoring_details?.reason === 'string'"
                              class="workspace-visual-profile-reason"
                            >
                              {{ activeCandidate.scoring_details.reason }}
                            </p>
                            <details v-if="activeVisualConditions.length" class="workspace-visual-profile-details">
                              <summary>命中条件（{{ activeVisualConditions.length }}）</summary>
                              <ul>
                                <li v-for="condition in activeVisualConditions" :key="condition">
                                  {{ condition }}
                                </li>
                              </ul>
                            </details>
                            <a-select v-if="savedPathOptions.length" size="small" aria-label="保存路径"
                              :model-value="activePath?.path_id" placeholder="选择保存路径" @change="chooseSavedPath">
                              <a-option v-for="option in savedPathOptions" :key="option.value" :value="option.value">{{ option.label }}</a-option>
                            </a-select>
                            <p v-if="savedPathReason" class="workspace-visual-profile-reason">{{ savedPathReason }}</p>
                            <p v-if="inspectingSavedPath && activeCurationEdge" :title="activeCurationEdge.id" class="workspace-subtle">选中源边 · {{ activeCurationEdge.relation }}</p>
                          </section>

                          <MeasuredEvidenceDetails v-if="!isSavedAnalysis" :observation="activeObservationContext?.rawObservation" />
                          <section class="workspace-reasoning-trace__section">
                            <div
                              class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
                            >
                              <strong>Primary Observation</strong>
                              <span>
                                {{
                                  activeReasoningInspection.primaryObservation?.obsId ?? '未推导出'
                                }}
                              </span>
                            </div>
                            <button
                              v-if="activeReasoningInspection.primaryObservation"
                              type="button"
                              class="workspace-basic-list-item workspace-basic-list-item--reasoning"
                              :class="{
                                'workspace-basic-list-item--active': isReasoningObservationActive(
                                  activeReasoningInspection.primaryObservation.obsId,
                                  activeReasoningInspection.primaryObservation.sharedObservationId,
                                ),
                              }"
                              @click="
                                activateReasoningStep(
                                  `observation:${activeReasoningInspection.primaryObservation.obsId}`,
                                )
                              "
                            >
                              <div class="workspace-basic-list-item__primary">
                                {{ activeReasoningInspection.primaryObservation.title }}
                              </div>
                              <div
                                class="workspace-basic-list-item__meta workspace-basic-list-item__meta--reasoning"
                              >
                                <span>
                                  {{ activeReasoningInspection.primaryObservation.obsId }}
                                </span>
                                <span>
                                  {{ activeReasoningInspection.primaryObservation.modality }}
                                </span>
                                <span>
                                  confidence
                                  {{
                                    formatScore(
                                      activeReasoningInspection.primaryObservation.confidence,
                                    )
                                  }}
                                </span>
                                <span>
                                  {{
                                    activeReasoningInspection.primaryObservation.linkedEntityCount
                                  }}
                                  linked entity
                                </span>
                              </div>
                            </button>
                            <a-empty v-else description="当前候选暂无可解释 observation。" />
                          </section>

                          <section class="workspace-reasoning-trace__section">
                            <div
                              class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
                            >
                              <strong>Supporting Observations</strong>
                              <span>
                                {{ activeReasoningInspection.supportingObservations.length }} 项
                              </span>
                            </div>
                            <div
                              v-if="activeReasoningInspection.supportingObservations.length"
                              class="workspace-scroll-list workspace-scroll-list--reasoning"
                            >
                              <button
                                v-for="observation in activeReasoningInspection.supportingObservations.filter(
                                  (item) =>
                                    item.obsId !==
                                    activeReasoningInspection.primaryObservation?.obsId,
                                )"
                                :key="observation.obsId"
                                type="button"
                                class="workspace-basic-list-item workspace-basic-list-item--reasoning"
                                :class="{
                                  'workspace-basic-list-item--active': isReasoningObservationActive(
                                    observation.obsId,
                                    observation.sharedObservationId,
                                  ),
                                }"
                                @click="activateReasoningStep(`observation:${observation.obsId}`)"
                              >
                                <div class="workspace-basic-list-item__primary">
                                  {{ observation.title }}
                                </div>
                                <div
                                  class="workspace-basic-list-item__meta workspace-basic-list-item__meta--reasoning"
                                >
                                  <span>{{ observation.obsId }}</span>
                                  <span>{{ observation.modality }}</span>
                                  <span>confidence {{ formatScore(observation.confidence) }}</span>
                                  <span>{{ observation.linkedEntityCount }} linked entity</span>
                                </div>
                              </button>
                            </div>
                            <a-empty v-else description="当前候选没有 supporting observations。" />
                          </section>

                          <section class="workspace-reasoning-trace__section">
                            <div
                              class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
                            >
                              <strong>Linked entities</strong>
                              <span>{{ activeReasoningInspection.linkedEntities.length }} 项</span>
                            </div>
                            <div
                              v-if="activeReasoningInspection.linkedEntities.length"
                              class="workspace-scroll-list workspace-scroll-list--reasoning"
                            >
                              <div
                                v-for="entity in activeReasoningInspection.linkedEntities"
                                :key="`entity-card:${entity.linkId}`"
                                class="workspace-basic-list-item workspace-basic-list-item--reasoning"
                                :class="{
                                  'workspace-basic-list-item--active': isReasoningStepActive(
                                    `entity:${entity.linkId}`,
                                  ),
                                }"
                              >
                                <div class="workspace-basic-list-item__primary">
                                  {{ entity.entityName }}
                                </div>
                                <div
                                  class="workspace-basic-list-item__meta workspace-basic-list-item__meta--reasoning"
                                >
                                  <span>{{ entity.field }} · {{ entity.mention }}</span>
                                  <span>{{ entity.matchType ?? '--' }}</span>
                                  <span>confidence {{ formatScore(entity.score) }}</span>
                                </div>
                                <div
                                  class="workspace-basic-list-item__actions workspace-basic-list-item__actions--reasoning"
                                >
                                  <a-button
                                    size="mini"
                                    type="text"
                                    @click="activateReasoningStep(`entity:${entity.linkId}`)"
                                  >
                                    定位
                                  </a-button>
                                  <a-button
                                    size="mini"
                                    type="text"
                                    @click="openEntityLinkProvenance(entity.linkId)"
                                  >
                                    Provenance
                                  </a-button>
                                </div>
                              </div>
                            </div>
                            <a-empty v-else description="当前候选没有可展示的 linked entities。" />
                          </section>

                          <section class="workspace-reasoning-trace__section">
                            <div
                              class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
                            >
                              <strong>Entity / Path / Cause chain</strong>
                              <span>{{ activeReasoningInspection.traceSteps.length }} steps</span>
                            </div>
                            <div class="workspace-reasoning-chain">
                              <div class="workspace-reasoning-chain__group">
                                <span class="workspace-summary-label">Observations</span>
                                <div class="workspace-reasoning-chain__items">
                                  <button
                                    v-for="observation in activeReasoningInspection.supportingObservations"
                                    :key="`chain-observation:${observation.obsId}`"
                                    type="button"
                                    class="workspace-reasoning-chip"
                                    :class="{
                                      'workspace-reasoning-chip--active':
                                        isReasoningObservationActive(
                                          observation.obsId,
                                          observation.sharedObservationId,
                                        ),
                                    }"
                                    @click="
                                      activateReasoningStep(`observation:${observation.obsId}`)
                                    "
                                  >
                                    {{ observation.title }}
                                  </button>
                                </div>
                              </div>
                              <div class="workspace-reasoning-chain__arrow">→</div>
                              <div class="workspace-reasoning-chain__group">
                                <span class="workspace-summary-label">Linked entities</span>
                                <div class="workspace-reasoning-chain__items">
                                  <button
                                    v-for="entity in activeReasoningInspection.linkedEntities"
                                    :key="entity.linkId"
                                    type="button"
                                    class="workspace-reasoning-chip"
                                    :class="{
                                      'workspace-reasoning-chip--active': isReasoningStepActive(
                                        `entity:${entity.linkId}`,
                                      ),
                                    }"
                                    @click="activateReasoningStep(`entity:${entity.linkId}`)"
                                  >
                                    {{ entity.entityName }}
                                  </button>
                                </div>
                              </div>
                              <div class="workspace-reasoning-chain__arrow">→</div>
                              <div class="workspace-reasoning-chain__group">
                                <span class="workspace-summary-label">Path</span>
                                <div class="workspace-reasoning-chain__items">
                                  <div
                                    v-if="activeReasoningInspection.selectedPath"
                                    class="workspace-reasoning-chain__path-block"
                                  >
                                    <button
                                      type="button"
                                      class="workspace-reasoning-chip workspace-reasoning-chip--wide"
                                      :class="{
                                        'workspace-reasoning-chip--active': isReasoningStepActive(
                                          `path:${activeReasoningInspection.selectedPath.pathId}`,
                                        ),
                                      }"
                                      @click="
                                        activateReasoningStep(
                                          `path:${activeReasoningInspection.selectedPath.pathId}`,
                                        )
                                      "
                                    >
                                      {{ activeReasoningInspection.selectedPath.pathId }}
                                      ·
                                      {{
                                        activeReasoningInspection.selectedPath.relationSequence.join(
                                          ' → ',
                                        ) || activeReasoningInspection.selectedPath.targetEntityName
                                      }}
                                    </button>
                                    <a-button
                                      size="mini"
                                      type="text"
                                      class="workspace-reasoning-inline-action"
                                      @click="openSelectedPathProvenance"
                                    >
                                      Inspect Provenance
                                    </a-button>
                                  </div>
                                  <span v-else class="workspace-reasoning-trace__hint">
                                    当前候选没有显式 path。
                                  </span>
                                </div>
                              </div>
                              <div class="workspace-reasoning-chain__arrow">→</div>
                              <div class="workspace-reasoning-chain__group">
                                <span class="workspace-summary-label">Candidate cause</span>
                                <div class="workspace-reasoning-chain__items">
                                  <button
                                    type="button"
                                    class="workspace-reasoning-chip workspace-reasoning-chip--wide"
                                    :class="{
                                      'workspace-reasoning-chip--active': isReasoningStepActive(
                                        `candidate:${activeReasoningInspection.candidate.rankingId}`,
                                      ),
                                    }"
                                    @click="
                                      activateReasoningStep(
                                        `candidate:${activeReasoningInspection.candidate.rankingId}`,
                                      )
                                    "
                                  >
                                    #{{ activeReasoningInspection.candidate.rank ?? '--' }}
                                    {{ activeReasoningInspection.candidate.candidateName }}
                                  </button>
                                </div>
                              </div>
                            </div>
                          </section>
                        </div>
                      </template>
                      <a-empty
                        v-else
                        description="先从右侧根因列表中选中一个候选，再查看 evidence → entity → path → candidate 的联动链路。"
                      />
                    </div>
                  </section>
                </a-tab-pane>
                <a-tab-pane key="ledger" title="记录">
                  <section class="workspace-feedback-pane workspace-feedback-pane--ledger">
                    <div
                      class="workspace-feedback-pane__section workspace-feedback-pane__section--ledger"
                    >
                      <div
                        class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
                      >
                        <strong>Review Ledger</strong>
                        <span :title="activeCase?.case_label ?? activeCase?.case_id ?? '--'">
                          {{ activeCase?.case_label ?? activeCase?.case_id ?? '--' }}
                        </span>
                      </div>

                      <a-form
                        id="graph-form-4"
                        :model="{ target: ledgerTargetTypeFilter }"
                        layout="vertical"
                        class="workspace-feedback-toolbar workspace-feedback-toolbar--ledger workspace-form"
                      >
                        <div class="workspace-feedback-toolbar__group">
                          <a-tooltip :content="ledgerIntroCopy" position="top">
                            <span class="workspace-feedback-toolbar__pill">bounded only</span>
                          </a-tooltip>
                        </div>
                        <a-form-item
                          label="目标"
                          :label-attrs="{ for: 'graph-ledgerTargetTypeFilter-input' }"
                          class="workspace-form-item workspace-feedback-toolbar__field"
                        >
                          <div
                            id="graph-ledgerTargetTypeFilter"
                            v-control-label="'目标'"
                            class="workspace-control"
                          >
                            <a-select
                              aria-label="目标"
                              v-model="ledgerTargetTypeFilter"
                              size="small"
                            >
                              <a-option
                                v-for="option in ledgerBoundedTargetOptions"
                                :key="option.value"
                                :value="option.value"
                              >
                                {{ option.label }}
                              </a-option>
                            </a-select>
                          </div>
                        </a-form-item>
                      </a-form>

                      <a-alert
                        v-if="ledgerErrorMessage"
                        type="warning"
                        :show-icon="false"
                        :title="ledgerErrorMessage"
                      />

                      <div v-if="ledgerLoading" class="workspace-build-detail-modal__loading">
                        <a-spin />
                      </div>
                      <div
                        v-else-if="ledgerDisplayItems.length"
                        class="workspace-scroll-list workspace-scroll-list--ledger"
                      >
                        <div
                          v-for="item in ledgerDisplayItems"
                          :key="item.feedback_id"
                          class="workspace-basic-list-item workspace-basic-list-item--ledger"
                          @click="handleLedgerRecordClick(item)"
                        >
                          <div class="workspace-basic-list-item__primary" :title="item.title">
                            {{ item.title }}
                          </div>
                          <div
                            class="workspace-basic-list-item__meta workspace-basic-list-item__meta--reasoning"
                          >
                            <span>{{ item.targetTypeLabel }} · {{ item.target_id }}</span>
                            <span>{{ item.actionLabel }} · {{ item.reviewer ?? 'anonymous' }}</span>
                            <span>{{ formatDateTime(item.created_at) }}</span>
                          </div>
                          <p class="workspace-ledger-record__subtitle" :title="item.subtitle">
                            {{ item.subtitle }}
                          </p>
                          <p
                            v-if="item.note"
                            class="workspace-ledger-record__note"
                            :title="item.note"
                          >
                            {{ item.note }}
                          </p>
                          <div
                            class="workspace-basic-list-item__actions workspace-basic-list-item__actions--reasoning"
                          >
                            <a-button
                              size="mini"
                              type="text"
                              :disabled="!item.targetAvailable"
                              @click.stop="handleLedgerRecordClick(item)"
                            >
                              定位
                            </a-button>
                            <a-button
                              size="mini"
                              type="text"
                              :disabled="!item.targetAvailable"
                              @click.stop="openLedgerRecordProvenance(item)"
                            >
                              Inspect Provenance
                            </a-button>
                          </div>
                        </div>
                      </div>
                      <a-empty
                        v-else
                        description="当前 run / case 暂无 bounded review ledger 记录。"
                      />
                    </div>
                  </section>
                </a-tab-pane>
              </a-tabs>
            </div>
          </article>
        </section>
      </div>

      <aside class="workspace-shell__aside workspace-shell__aside--graphs">
        <article class="rl-section-card workspace-root-cause-aside-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">
                <SectionCardTitle title="根因列表" :help="graphRootCauseHelp">
                  <icon-bulb />
                </SectionCardTitle>
              </h3>
            </div>
            <a-tag color="green">{{ activeCase?.ranked_root_causes?.length ?? 0 }}</a-tag>
          </header>
          <div class="rl-section-card__body workspace-root-cause-aside-card__body">
            <a-form
              id="graph-form-5"
              :model="workbenchState"
              layout="vertical"
              class="workspace-root-cause-aside-card__context workspace-stack workspace-stack--tight workspace-form"
            >
              <a-form-item
                label="运行"
                :label-attrs="{ for: 'graph-run-input' }"
                class="workspace-form-item"
              >
                <div id="graph-run" v-control-label="'运行'" class="workspace-control">
                  <a-select
                    aria-label="运行"
                    :model-value="runDetail?.run.run_id"
                    @change="handleRunChange"
                  >
                    <a-option v-for="run in runs" :key="run.run_id" :value="run.run_id">
                      {{ run.label }}
                    </a-option>
                  </a-select>
                </div>
              </a-form-item>
              <a-form-item
                label="案例"
                :label-attrs="{ for: 'graph-case-input' }"
                class="workspace-form-item"
              >
                <div id="graph-case" v-control-label="'案例'" class="workspace-control">
                  <a-select
                    aria-label="案例"
                    :model-value="activeCase?.case_id"
                    @change="handleCaseChange"
                  >
                    <a-option
                      v-for="caseItem in runDetail?.cases ?? []"
                      :key="caseItem.case_id"
                      :value="caseItem.case_id"
                    >
                      {{ caseItem.case_label ?? caseItem.case_id }}
                    </a-option>
                  </a-select>
                </div>
              </a-form-item>

              <a-alert
                v-if="activeReasoningSummary.fallbackApplied"
                type="info"
                :show-icon="false"
                :title="
                  activeReasoningSummary.fallbackReason
                    ? `当前结果已回退到通用路径推理：${activeReasoningSummary.fallbackReason}`
                    : '当前结果已回退到通用路径推理'
                "
              />
              <a-tag v-if="savedOutcome" color="arcoblue">{{ savedOutcome }}</a-tag>
            </a-form>

            <section class="workspace-root-cause-aside-card__list">
              <div class="workspace-root-cause-aside-card__section-header">
                <strong>候选根因</strong>
                <UnifiedReasoningDetails :metadata="activeCase?.reasoning_metadata" :candidate-id="activeCandidate?.candidate_id" :query-id="activeCandidate?.scoring_details?.query_id" />
                <span>{{ activeCandidate ? '已选中 1 项' : '当前未选中' }}</span>
              </div>
              <div class="workspace-scroll-list workspace-scroll-list--fill">
                <button
                  v-for="candidate in activeCase?.ranked_root_causes ?? []"
                  :key="candidate.ranking_id"
                  type="button"
                  class="workspace-list-item"
                  :class="{
                    'workspace-list-item--active':
                      candidate.ranking_id === activeCandidate?.ranking_id,
                  }"
                  @click="selectCandidate(candidate.ranking_id)"
                >
                  <div class="workspace-list-item__head">
                    <strong>#{{ candidate.rank }} {{ candidate.candidate_name }}</strong>
                    <span :title="String(candidate.score ?? '')">{{ formatScore(candidate.score) }}</span>
                  </div>
                  <div class="workspace-list-item__meta">
                    <span>{{ formatScoringMethodLabel(candidate.scoring_method) }}</span>
                    <span>{{ normalizeText(candidate.candidate_role, 'candidate') }}</span>
                  </div>
                </button>
                <a-empty v-if="!activeCase?.ranked_root_causes?.length">暂无候选根因</a-empty>
              </div>
            </section>
          </div>
        </article>
      </aside>

      <ProvenanceInspectorDrawer
        v-model:visible="provenanceInspectorVisible"
        :state="provenanceInspectorState"
      />

      <a-drawer
        v-model:visible="crossCaseCompareOpen"
        width="420px"
        title="Cross-case Compare"
        :footer="false"
      >
        <div class="workspace-recurrence-drawer">
          <div class="workspace-claim-note workspace-claim-note--compact">
            <span class="workspace-summary-label">
              <icon-info-circle />
              <span>Compare scope</span>
            </span>
            <strong>
              {{
                activeReasoningInspection.crossCaseRecurrence?.currentCaseLabel ??
                activeCase?.case_label ??
                activeCase?.case_id ??
                '--'
              }}
              · same run only
            </strong>
          </div>

          <section class="workspace-feedback-pane__section">
            <div
              class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
            >
              <strong>Recurring entities</strong>
              <span>
                {{ activeReasoningInspection.crossCaseRecurrence?.recurringEntities.length ?? 0 }}
                项
              </span>
            </div>
            <div
              v-if="activeReasoningInspection.crossCaseRecurrence?.recurringEntities.length"
              class="workspace-recurrence-list"
            >
              <article
                v-for="entity in activeReasoningInspection.crossCaseRecurrence?.recurringEntities ??
                []"
                :key="entity.entityId"
                class="workspace-recurrence-card"
              >
                <div class="workspace-recurrence-card__head">
                  <strong>{{ entity.entityName }}</strong>
                  <span>{{ entity.occurrenceCount }} case(s)</span>
                </div>
                <div class="workspace-recurrence-card__meta">
                  <span>{{ entity.entityId }}</span>
                  <span>
                    当前 observation: {{ entity.currentObservationIds.join(', ') || '--' }}
                  </span>
                </div>
                <div class="workspace-recurrence-card__hits">
                  <button
                    v-for="hit in entity.caseHits"
                    :key="`${entity.entityId}:${hit.caseId}`"
                    type="button"
                    class="workspace-basic-list-item workspace-basic-list-item--recurrence"
                    @click="jumpToRecurringCase(hit)"
                  >
                    <div class="workspace-basic-list-item__primary">
                      {{ hit.caseLabel }}
                    </div>
                    <div
                      class="workspace-basic-list-item__meta workspace-basic-list-item__meta--reasoning"
                    >
                      <span>{{ hit.caseId }}</span>
                      <span>{{ hit.matchedPathIds.join(', ') || 'entity recurrence' }}</span>
                    </div>
                  </button>
                </div>
              </article>
            </div>
            <a-empty
              v-else
              description="当前候选的实体在同 run 其他 case 中没有显式 recurrence。"
            />
          </section>

          <section class="workspace-feedback-pane__section">
            <div
              class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
            >
              <strong>Recurring paths</strong>
              <span>
                {{ activeReasoningInspection.crossCaseRecurrence?.recurringPaths.length ?? 0 }} 项
              </span>
            </div>
            <div
              v-if="activeReasoningInspection.crossCaseRecurrence?.recurringPaths.length"
              class="workspace-recurrence-list"
            >
              <article
                v-for="pathSummary in activeReasoningInspection.crossCaseRecurrence
                  ?.recurringPaths ?? []"
                :key="pathSummary.signature"
                class="workspace-recurrence-card"
              >
                <div class="workspace-recurrence-card__head">
                  <strong>{{ pathSummary.targetEntityName }}</strong>
                  <span>{{ pathSummary.occurrenceCount }} case(s)</span>
                </div>
                <div class="workspace-recurrence-card__meta">
                  <span>{{ pathSummary.signature }}</span>
                  <span>{{ pathSummary.relationSequence.join(' → ') || '--' }}</span>
                </div>
                <div class="workspace-recurrence-card__hits">
                  <button
                    v-for="hit in pathSummary.caseHits"
                    :key="`${pathSummary.signature}:${hit.caseId}`"
                    type="button"
                    class="workspace-basic-list-item workspace-basic-list-item--recurrence"
                    @click="jumpToRecurringCase(hit)"
                  >
                    <div class="workspace-basic-list-item__primary">
                      {{ hit.caseLabel }}
                    </div>
                    <div
                      class="workspace-basic-list-item__meta workspace-basic-list-item__meta--reasoning"
                    >
                      <span>{{ hit.caseId }}</span>
                      <span>{{ hit.matchedPathIds.join(', ') || 'path recurrence' }}</span>
                    </div>
                  </button>
                </div>
              </article>
            </div>
            <a-empty v-else description="当前候选路径在同 run 其他 case 中没有显式 recurrence。" />
          </section>
        </div>
      </a-drawer>
    </section>
  </div>
</template>
