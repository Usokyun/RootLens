<script setup lang="ts">
import {
  IconLaunch,
  IconRefresh,
  IconUpload,
} from "@arco-design/web-vue/es/icon";
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { useRouter } from "vue-router";

import type {
  DashboardBootstrap,
  DashboardReasoningProfileOption,
  RunCaseDetail,
  RunDetail,
  RunSummary,
  UploadMode,
} from "@/api/contracts";
import VisualEvidenceViewer from "@/components/evidence/VisualEvidenceViewer.vue";
import ObservationSignal from "@/components/evidence/ObservationSignal.vue";
import {
  caseTitle,
  runTitle,
  readable,
  shortDate,
  scoreText,
} from "@/services/presentation";
import { useAppPreferences } from "@/services/app-preferences";
import { buildLocalImportResult } from "@/services/browser-runtime";
import {
  clearImportedSession,
  getImportedSessionSummary,
  getLocalSessionEventName,
  getLocalSessionMeta,
  saveImportedSession,
} from "@/services/rootlens-data";
import { getRootLensService } from "@/services/rootlens-service";
import { restoreSessionImportFile } from "@/services/session-export";
import {
  filterObservationBrowseItems,
  buildObservationBrowseItems,
  collectObservationModalities,
  collectObservationSources,
  findObservationBrowseItem,
  selectVisualEvidenceForObservation,
  type ObservationConfidenceBand,
  type ObservationModality,
} from "@/services/evidence-observation";
import {
  extractFirstFileFromDataTransfer,
  markDragEventHandled,
} from "@/services/file-drop";
import { formatReasonerAdapterLabel } from "@/services/ui-copy";
import { useWorkbenchState } from "@/services/workbench-state";

interface CaseEvidenceEntry {
  key: string;
  caseId: string;
  caseLabel: string;
  dataset: string;
  graphDatasetId: string;
  observationCount: number;
  facetSummary: string;
  evidenceSummary: string;
  hint: string;
  rawRefCount: number;
  topCandidate: string;
  reviewStatus: string;
  pathCount: number;
  searchableText: string;
  facetKeys: string[];
}

const router = useRouter();
const { preferences } = useAppPreferences();
const { state: workbenchState, updateState } = useWorkbenchState();
const isMockMode = computed(() => preferences.value.dataSourceMode === "mock");

const loading = ref(false);
// An older response must not publish a selection into this or another tab.
let runRequestVersion = 0;
let workspaceRequestVersion = 0;
const uploadLoading = ref(false);
const bootstrap = ref<DashboardBootstrap | null>(null);
const runs = ref<RunSummary[]>([]);
const runDetail = ref<RunDetail | null>(null);
const errorMessage = ref("");
const uploadMessage = ref("");
const uploadInputRef = ref<HTMLInputElement | null>(null);
const uploadDragActive = ref(false);
const uploadDragDepth = ref(0);

const replayModalVisible = ref(false);
const replayImportLoading = ref(false);
const replayRuntimeInputRef = ref<HTMLInputElement | null>(null);
const replayGraphsInputRef = ref<HTMLInputElement | null>(null);
const replayWorkspaceInputRef = ref<HTMLInputElement | null>(null);
const importedSessionMeta = ref(getLocalSessionMeta());
const importedSessionSummary = ref(getImportedSessionSummary());
const replayWarnings = ref<string[]>([]);

const replayImportForm = reactive({
  runtimeFile: null as File | null,
  graphsFile: null as File | null,
  workspaceFile: null as File | null,
});

const observationDetailModalVisible = ref(false);
const uploadDrawerVisible = ref(false);
const filtersVisible = ref(false);

const uploadForm = reactive({
  mode: "records" as UploadMode,
  dataset: "",
  topK: 5,
  file: null as File | null,
  objectName: "",
  defectType: "",
  modelPreset: "auto",
  reasoningProfileId: "",
});

const evidenceFilter = reactive({
  graph: workbenchState.value.evidenceFilterGraph ?? "all",
  modality: workbenchState.value.evidenceFilterModality ?? "all",
  source: workbenchState.value.evidenceFilterSource ?? "all",
  confidenceBand: workbenchState.value.evidenceFilterConfidenceBand,
  timeFrom: workbenchState.value.evidenceFilterTimeFrom ?? "",
  timeTo: workbenchState.value.evidenceFilterTimeTo ?? "",
  keyword: workbenchState.value.evidenceFilterKeyword ?? "",
});

const isReplaySessionActive = computed(
  () => importedSessionMeta.value?.source === "import",
);

const selectedObservationId = computed(
  () => workbenchState.value.selectedObservationId,
);
const normalizedObservationFilters = computed(() => ({
  graph: evidenceFilter.graph === "all" ? null : evidenceFilter.graph,
  modality:
    evidenceFilter.modality === "all"
      ? null
      : (evidenceFilter.modality as ObservationModality),
  source: evidenceFilter.source === "all" ? null : evidenceFilter.source,
  keyword: evidenceFilter.keyword.trim() || null,
  confidenceBand: evidenceFilter.confidenceBand as ObservationConfidenceBand,
  timeFrom: evidenceFilter.timeFrom || null,
  timeTo: evidenceFilter.timeTo || null,
}));

const selectedRunId = computed(() => workbenchState.value.selectedRunId);
const activeCaseId = computed(() => workbenchState.value.selectedCaseId);
const activeRun = computed(() => runDetail.value?.run ?? null);
const activeCase = computed(() => {
  if (!runDetail.value) {
    return null;
  }

  return (
    runDetail.value.cases.find((item) => item.case_id === activeCaseId.value) ??
    runDetail.value.cases[0] ??
    null
  );
});

const graphOptions = computed(() => {
  const options = new Set<string>();
  for (const caseItem of runDetail.value?.cases ?? []) {
    const graphId = getCaseGraphDatasetId(caseItem);
    if (graphId) {
      options.add(graphId);
    }
  }
  return [...options];
});

const observationItemsByCase = computed(
  () =>
    new Map(
      (runDetail.value?.cases ?? []).map((caseItem) => [
        caseItem.case_id,
        buildObservationBrowseItems(caseItem),
      ]),
    ),
);

const activeObservationItems = computed(() => {
  if (!activeCase.value) {
    return [];
  }

  return observationItemsByCase.value.get(activeCase.value.case_id) ?? [];
});

const filteredActiveObservationItems = computed(() =>
  filterObservationBrowseItems(
    activeObservationItems.value,
    normalizedObservationFilters.value,
  ),
);

const activeObservation = computed(
  () =>
    findObservationBrowseItem(
      activeObservationItems.value,
      selectedObservationId.value,
    ) ??
    activeObservationItems.value[0] ??
    null,
);

const observationModalityOptions = computed(() =>
  collectObservationModalities(caseEvidenceEntriesObservationItems.value),
);
const observationSourceOptions = computed(() =>
  collectObservationSources(caseEvidenceEntriesObservationItems.value),
);
const selectedObservationVisualEvidence = computed(() =>
  selectVisualEvidenceForObservation(
    activeObservation.value,
    activeCase.value?.visual_evidence ?? [],
  ),
);

const uploadAccept = computed(() => {
  const modeConfig = bootstrap.value?.upload_modes.find(
    (item) => item.mode === uploadForm.mode,
  );
  return modeConfig?.accepted_extensions.join(",") ?? "";
});

const uploadReasoningProfileOptions = computed<
  DashboardReasoningProfileOption[]
>(() => {
  const dataset = uploadForm.dataset.trim();
  if (!dataset) {
    return [];
  }

  return bootstrap.value?.reasoning_profile_options?.[dataset] ?? [];
});

const uploadReasoningHelp = computed(() => {
  if (!uploadForm.dataset) return "先选择数据集，才能指定推理配置。";
  if (!uploadReasoningProfileOptions.value.length)
    return "当前数据集使用后端默认推理配置。";
  return "留空时使用后端默认配置。";
});

const caseEvidenceEntriesObservationItems = computed(() =>
  (runDetail.value?.cases ?? []).flatMap((caseItem) =>
    buildObservationBrowseItems(caseItem),
  ),
);

const caseEvidenceEntries = computed<CaseEvidenceEntry[]>(() => {
  return (runDetail.value?.cases ?? []).map((caseItem) =>
    buildCaseEvidenceEntry(caseItem),
  );
});

const filteredCaseEvidenceEntries = computed(() => {
  return caseEvidenceEntries.value.filter((item) => {
    const observationItems =
      observationItemsByCase.value.get(item.caseId) ?? [];
    return (
      filterObservationBrowseItems(
        observationItems,
        normalizedObservationFilters.value,
      ).length > 0
    );
  });
});

const activeRootCauseList = computed(
  () => activeCase.value?.ranked_root_causes ?? [],
);

function toRecord(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function normalizeText(value: unknown, fallback = "--") {
  return typeof value === "string" && value.trim().length
    ? value.trim()
    : fallback;
}

function formatUploadModeLabel(mode: UploadMode | undefined | null) {
  switch (mode) {
    case "records":
      return "批量记录";
    case "evidence":
      return "单条证据";
    case "image":
      return "图像";
    default:
      return "--";
  }
}

function formatObservationModalityLabel(
  value: ObservationModality | null | undefined,
) {
  switch (value) {
    case "image":
      return "image";
    case "time_series":
      return "time_series";
    case "log":
      return "log";
    case "document":
      return "document";
    default:
      return "--";
  }
}

function getCaseGraphDatasetId(caseItem: RunCaseDetail) {
  const evidence = toRecord(caseItem.generated_evidence);
  return normalizeText(evidence?.graph_dataset_id, "default-graph");
}

function getCaseTopCandidate(caseItem: RunCaseDetail) {
  return caseItem.ranked_root_causes?.[0]?.candidate_name ?? "--";
}

function getCaseReviewStatus(caseItem: RunCaseDetail) {
  return caseItem.review_targets?.length ? "可审阅" : "无反馈目标";
}

function buildObservationTitle(
  observation: Record<string, unknown>,
  facet: string,
) {
  switch (facet) {
    case "variable":
      return `${normalizeText(observation.variable_name)} / ${normalizeText(observation.direction, "unknown")}`;
    case "image_defect":
      return `${normalizeText(observation.object)} / ${normalizeText(observation.anomaly_type)}`;
    case "log_event":
      return `${normalizeText(observation.event_code, normalizeText(observation.event_type))} / ${normalizeText(observation.equipment)}`;
    default:
      return normalizeText(observation.obs_id, "未命名 observation");
  }
}

function buildCaseEvidenceEntry(caseItem: RunCaseDetail): CaseEvidenceEntry {
  const evidence = toRecord(caseItem.generated_evidence);
  const observations = Array.isArray(evidence?.observations)
    ? evidence?.observations
    : [];
  const graphDatasetId = getCaseGraphDatasetId(caseItem);
  const caseLabel = caseItem.case_label ?? caseItem.case_id;
  const dataset = caseItem.dataset ?? "--";
  const facetCount = new Map<string, number>();
  const titles: string[] = [];
  const hints: string[] = [];
  let rawRefCount = 0;

  for (const item of observations) {
    const observation = toRecord(item);
    if (!observation) {
      continue;
    }

    const facet = normalizeText(observation.facet, "unknown");
    facetCount.set(facet, (facetCount.get(facet) ?? 0) + 1);
    titles.push(buildObservationTitle(observation, facet));

    const linkedHints = Array.isArray(observation.linked_entity_hints)
      ? observation.linked_entity_hints.map((hint) => String(hint))
      : [];
    if (linkedHints[0]) {
      hints.push(linkedHints[0]);
    }

    const rawRefs = Array.isArray(observation.raw_evidence_refs)
      ? observation.raw_evidence_refs
      : [];
    rawRefCount += rawRefs.length;
  }

  const facetKeys = [...facetCount.keys()];
  const facetSummary = facetKeys.length
    ? facetKeys
        .map(
          (facet) =>
            `${facet}${(facetCount.get(facet) ?? 0) > 1 ? `×${facetCount.get(facet)}` : ""}`,
        )
        .join(" / ")
    : "--";
  const evidenceSummary = titles.length
    ? `${titles[0]}${titles.length > 1 ? ` 等 ${titles.length} 条` : ""}`
    : "暂无 evidence";
  const hint = hints[0] ?? "--";

  return {
    key: caseItem.case_id,
    caseId: caseItem.case_id,
    caseLabel,
    dataset,
    graphDatasetId,
    observationCount: observations.length,
    facetSummary,
    evidenceSummary,
    hint,
    rawRefCount,
    topCandidate: getCaseTopCandidate(caseItem),
    reviewStatus: getCaseReviewStatus(caseItem),
    pathCount: caseItem.path_graph?.path_count ?? 0,
    searchableText: [
      caseLabel,
      dataset,
      graphDatasetId,
      facetSummary,
      evidenceSummary,
      hint,
      getCaseTopCandidate(caseItem),
    ]
      .join(" ")
      .toLowerCase(),
    facetKeys,
  };
}

function setUploadFile(file: File | null) {
  uploadForm.file = file;
}

function handleUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  setUploadFile(input?.files?.[0] ?? null);
}

function openUploadPicker() {
  uploadInputRef.value?.click();
}

function resetUploadDragState() {
  uploadDragDepth.value = 0;
  uploadDragActive.value = false;
}

function handleUploadDragEnter(event: DragEvent) {
  markDragEventHandled(event);
  uploadDragDepth.value += 1;
  uploadDragActive.value = true;
}

function handleUploadDragOver(event: DragEvent) {
  markDragEventHandled(event, { dropEffect: "copy" });
  uploadDragActive.value = true;
}

function handleUploadDragLeave(event: DragEvent) {
  markDragEventHandled(event);
  uploadDragDepth.value = Math.max(0, uploadDragDepth.value - 1);
  if (uploadDragDepth.value === 0) {
    uploadDragActive.value = false;
  }
}

function handleUploadDrop(event: DragEvent) {
  markDragEventHandled(event, { dropEffect: "copy" });
  setUploadFile(extractFirstFileFromDataTransfer(event.dataTransfer));
  resetUploadDragState();
}

function syncImportedSessionState() {
  importedSessionMeta.value = getLocalSessionMeta();
  importedSessionSummary.value = getImportedSessionSummary();
}

function handleLocalSessionChange() {
  syncImportedSessionState();
  void refreshWorkspace();
}

function resetReplayImportForm() {
  replayImportForm.runtimeFile = null;
  replayImportForm.graphsFile = null;
  replayImportForm.workspaceFile = null;
  replayWarnings.value = [];
}

function openReplayAssetsModal() {
  resetReplayImportForm();
  replayModalVisible.value = true;
}

function setReplayImportFile(
  kind: "runtimeFile" | "graphsFile" | "workspaceFile",
  file: File | null,
) {
  replayImportForm[kind] = file;
}

function handleReplayFileChange(
  kind: "runtimeFile" | "graphsFile" | "workspaceFile",
  event: Event,
) {
  const input = event.target as HTMLInputElement | null;
  setReplayImportFile(kind, input?.files?.[0] ?? null);
}

function openReplayFilePicker(
  kind: "runtimeFile" | "graphsFile" | "workspaceFile",
) {
  if (kind === "runtimeFile") {
    replayRuntimeInputRef.value?.click();
    return;
  }

  if (kind === "graphsFile") {
    replayGraphsInputRef.value?.click();
    return;
  }

  replayWorkspaceInputRef.value?.click();
}

async function readSessionImportSchema(file: File) {
  try {
    const payload = JSON.parse(await file.text()) as Record<string, unknown>;
    return typeof payload.schema_version === "string"
      ? payload.schema_version
      : null;
  } catch {
    throw new Error("附加恢复文件不是合法 JSON。");
  }
}

async function handleReplayImport() {
  const assetFiles = [
    replayImportForm.runtimeFile,
    replayImportForm.graphsFile,
  ].filter((file): file is File => Boolean(file));
  const workspaceFile = replayImportForm.workspaceFile;

  if (!assetFiles.length && !workspaceFile) {
    errorMessage.value = "请至少选择一份完整回放资产或工作区恢复文件。";
    return;
  }

  replayImportLoading.value = true;
  errorMessage.value = "";
  uploadMessage.value = "";

  try {
    const messages: string[] = [];
    const warnings: string[] = [];

    if (assetFiles.length) {
      const importResult = await buildLocalImportResult(assetFiles);
      saveImportedSession({
        graphs: importResult.graphs,
        runtime: importResult.runtime,
        summary: `导入完整回放资产：${importResult.summary.datasets.length} 个 dataset，${importResult.summary.cases.length} 个 case。`,
        importSummary: importResult.summary,
      });
      syncImportedSessionState();
      messages.push(
        `已导入完整回放资产：${importResult.summary.datasets.length} 个 dataset，${importResult.summary.cases.length} 个 case。`,
      );
      warnings.push(...importResult.summary.warnings);
    }

    if (workspaceFile) {
      const schemaVersion = await readSessionImportSchema(workspaceFile);
      if (assetFiles.length && schemaVersion === "rootlens-session-export.v1") {
        throw new Error(
          "完整 session bundle 请单独导入，不要与 runtime/graphs 原始资产混合。",
        );
      }

      const restoreResult = await restoreSessionImportFile(workspaceFile);
      syncImportedSessionState();
      messages.push(restoreResult.summary);
      warnings.push(...restoreResult.warnings);
    }

    replayWarnings.value = warnings;
    replayModalVisible.value = false;
    uploadMessage.value = [
      messages.join(" "),
      warnings.length ? `警告：${warnings.join("；")}` : "",
    ]
      .filter(Boolean)
      .join(" ");

    await refreshWorkspace();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    replayImportLoading.value = false;
  }
}

async function handleSwitchToLiveUpload() {
  if (!isReplaySessionActive.value) {
    return;
  }

  clearImportedSession();
  syncImportedSessionState();
  replayWarnings.value = [];
  uploadMessage.value = "已退出回放会话，恢复当前实时/演示数据视图。";
  await refreshWorkspace();
}

function setSelectedObservation(observationId: string | null) {
  updateState({
    selectedObservationId: observationId,
  });
}

function openObservationDetail(observationId: string | null) {
  if (!observationId) {
    return;
  }

  setSelectedObservation(observationId);
  observationDetailModalVisible.value = true;
}

function setSelectedRun(runId: string) {
  updateState({
    selectedRunId: runId,
    selectedCaseId: null,
    selectedObservationId: null,
    selectedCandidateId: null,
    selectedPathId: null,
    selectedReviewTargetKey: null,
    selectedGraphNodeId: null,
    subgraphMode: "path",
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  });
}

function setSelectedCase(caseId: string | null) {
  updateState({
    selectedCaseId: caseId,
    selectedObservationId: null,
    selectedCandidateId: null,
    selectedPathId: null,
    selectedReviewTargetKey: null,
    selectedGraphNodeId: null,
    subgraphMode: "path",
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  });
}

async function loadRun(runId: string) {
  const requestVersion = ++runRequestVersion;
  loading.value = true;
  errorMessage.value = "";

  try {
    const detail = await getRootLensService().getRun(runId);
    if (requestVersion !== runRequestVersion) return;
    runDetail.value = detail;
    setSelectedRun(runId);
    const nextCaseId =
      detail.cases.find(
        (item) => item.case_id === workbenchState.value.selectedCaseId,
      )?.case_id ??
      detail.cases[0]?.case_id ??
      null;
    setSelectedCase(nextCaseId);
  } catch (error) {
    if (requestVersion === runRequestVersion) {
      errorMessage.value =
        error instanceof Error ? error.message : String(error);
    }
  } finally {
    if (requestVersion === runRequestVersion) loading.value = false;
  }
}

async function refreshWorkspace() {
  const requestVersion = ++workspaceRequestVersion;
  ++runRequestVersion;
  syncImportedSessionState();
  loading.value = true;
  errorMessage.value = "";

  try {
    const [bootstrapPayload, runSummaries] = await Promise.all([
      getRootLensService().bootstrap(),
      getRootLensService().listRuns(),
    ]);
    if (requestVersion !== workspaceRequestVersion) return;
    bootstrap.value = bootstrapPayload;
    runs.value = runSummaries;
    uploadForm.mode = bootstrapPayload.upload_modes[0]?.mode ?? "records";

    const nextRunId =
      runSummaries.find((item) => item.run_id === selectedRunId.value)
        ?.run_id ??
      runSummaries[0]?.run_id ??
      null;

    if (nextRunId) {
      await loadRun(nextRunId);
      return;
    }

    runDetail.value = null;
  } catch (error) {
    if (requestVersion === workspaceRequestVersion) {
      errorMessage.value =
        error instanceof Error ? error.message : String(error);
    }
  } finally {
    if (requestVersion === workspaceRequestVersion) loading.value = false;
  }
}

async function handleUpload() {
  if (isMockMode.value) {
    uploadMessage.value =
      "内置 Demo 模式不开放上传，请切换到 backend 模式后再提交真实数据。";
    return;
  }

  if (!uploadForm.file) {
    uploadMessage.value = "请选择一个本地文件。";
    return;
  }

  uploadLoading.value = true;
  uploadMessage.value = "";
  errorMessage.value = "";

  try {
    const detail = await getRootLensService().uploadRun({
      file: uploadForm.file,
      mode: uploadForm.mode,
      dataset: uploadForm.dataset || undefined,
      object_name: uploadForm.objectName || undefined,
      defect_type: uploadForm.defectType || undefined,
      model_preset: uploadForm.modelPreset || undefined,
      reasoning_profile_id: uploadForm.reasoningProfileId || undefined,
      top_k: uploadForm.topK,
    });

    uploadMessage.value = `已生成运行：${detail.run.run_id}`;
    await refreshWorkspace();
    await loadRun(detail.run.run_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    uploadLoading.value = false;
  }
}

function openGraphExplore(caseId: string, observationId: string | null = null) {
  const runId = activeRun.value?.run_id ?? selectedRunId.value;
  if (!runId) {
    return;
  }

  updateState({
    selectedRunId: runId,
    selectedCaseId: caseId,
    selectedObservationId:
      observationId ??
      (caseId === activeCase.value?.case_id
        ? selectedObservationId.value
        : null),
    selectedGraphNodeId: null,
    subgraphMode: "path",
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  });

  void router.push({
    name: "graphs",
    query: {
      run_id: runId,
      case_id: caseId,
    },
  });
}

watch(
  [() => preferences.value.dataSourceMode, () => preferences.value.apiBaseUrl],
  () => {
    void refreshWorkspace();
  },
);

watch(
  () => workbenchState.value.selectedRunId,
  (runId) => {
    if (runId && runId !== runDetail.value?.run.run_id) {
      void loadRun(runId);
    }
  },
);

watch(
  () => [
    uploadForm.dataset,
    uploadReasoningProfileOptions.value
      .map((item) => item.profile_id)
      .join("|"),
  ],
  () => {
    if (!uploadForm.dataset) {
      uploadForm.reasoningProfileId = "";
      return;
    }

    if (!uploadForm.reasoningProfileId) {
      return;
    }

    if (
      !uploadReasoningProfileOptions.value.some(
        (item) => item.profile_id === uploadForm.reasoningProfileId,
      )
    ) {
      uploadForm.reasoningProfileId = "";
    }
  },
);

watch(
  () => [
    evidenceFilter.graph,
    evidenceFilter.modality,
    evidenceFilter.source,
    evidenceFilter.keyword,
    evidenceFilter.confidenceBand,
    evidenceFilter.timeFrom,
    evidenceFilter.timeTo,
  ],
  () => {
    updateState({
      evidenceFilterGraph: normalizedObservationFilters.value.graph,
      evidenceFilterModality: normalizedObservationFilters.value.modality,
      evidenceFilterSource: normalizedObservationFilters.value.source,
      evidenceFilterKeyword: normalizedObservationFilters.value.keyword,
      evidenceFilterConfidenceBand:
        normalizedObservationFilters.value.confidenceBand,
      evidenceFilterTimeFrom: normalizedObservationFilters.value.timeFrom,
      evidenceFilterTimeTo: normalizedObservationFilters.value.timeTo,
    });
  },
);

watch(activeObservationItems, (items) => {
  if (
    selectedObservationId.value &&
    !items.some((item) => item.id === selectedObservationId.value)
  ) {
    updateState({ selectedObservationId: null });
  }
});

onMounted(() => {
  syncImportedSessionState();
  window.addEventListener(
    getLocalSessionEventName(),
    handleLocalSessionChange as EventListener,
  );
  void refreshWorkspace();
});

onBeforeUnmount(() => {
  ++runRequestVersion;
  ++workspaceRequestVersion;
  window.removeEventListener(
    getLocalSessionEventName(),
    handleLocalSessionChange as EventListener,
  );
});
</script>

<template>
  <div class="demo-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">01 / EVIDENCE</span>
        <h2>从异常，看到证据</h2>
      </div>
      <a-space>
        <a-button @click="openReplayAssetsModal">导入回放</a-button>
        <a-button v-if="isReplaySessionActive" @click="handleSwitchToLiveUpload"
          >退出回放</a-button
        >
        <a-button
          v-else
          type="primary"
          :disabled="isMockMode"
          @click="uploadDrawerVisible = true"
          ><template #icon><icon-upload /></template>新建分析</a-button
        >
      </a-space>
    </header>
    <a-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      class="page-alert"
      ><template #action
        ><a-button size="small" @click="refreshWorkspace"
          >重试</a-button
        ></template
      ></a-alert
    >
    <a-alert
      v-if="uploadMessage"
      type="success"
      :title="uploadMessage"
      class="page-alert"
      closable
    />
    <div class="context-toolbar">
      <div v-control-label="'分析记录'" class="labeled-control">
        <a-select
          :model-value="selectedRunId ?? undefined"
          placeholder="选择分析记录"
          aria-label="分析记录"
          class="run-select"
          :loading="loading"
          @change="loadRun(String($event))"
        >
          <a-option
            v-for="run in runs"
            :key="run.run_id"
            :value="run.run_id"
            :label="runTitle(run)"
          />
        </a-select>
      </div>
      <span class="subtle"
        >{{ activeRun?.case_count ?? 0 }} 个案例 ·
        {{ shortDate(activeRun?.created_at) }}</span
      >
      <a-tag v-if="isReplaySessionActive" color="purple">成品回放</a-tag>
      <a-button type="text" aria-label="刷新证据" @click="refreshWorkspace"
        ><icon-refresh
      /></a-button>
    </div>
    <a-spin :loading="loading" class="block-spin">
      <div class="evidence-workspace">
        <aside class="surface case-sidebar">
          <div class="surface-heading">
            <h3>案例</h3>
            <a-tag>{{ filteredCaseEvidenceEntries.length }}</a-tag>
          </div>
          <a-input-search
            v-model="evidenceFilter.keyword"
            v-control-label="'搜索案例'"
            aria-label="搜索案例"
            placeholder="搜索异常或对象"
            allow-clear
          />
          <div class="case-list">
            <button
              v-for="entry in filteredCaseEvidenceEntries"
              :key="entry.caseId"
              class="case-item"
              :class="{ 'is-active': entry.caseId === activeCase?.case_id }"
              :aria-pressed="entry.caseId === activeCase?.case_id"
              @click="setSelectedCase(entry.caseId)"
            >
              <span class="case-item__dataset">{{
                readable(entry.dataset)
              }}</span>
              <strong>{{
                caseTitle(
                  runDetail?.cases.find(
                    (item) => item.case_id === entry.caseId,
                  ),
                )
              }}</strong>
              <span
                >{{ entry.observationCount }} 条观察 ·
                {{ entry.pathCount }} 条解释路径</span
              >
            </button>
            <a-empty
              v-if="!filteredCaseEvidenceEntries.length"
              description="没有匹配案例"
            />
          </div>
          <a-button long @click="filtersVisible = true">筛选证据</a-button>
        </aside>
        <main v-if="activeCase" class="evidence-main">
          <section class="surface observation-stage">
            <div class="surface-heading">
              <div>
                <span class="eyebrow">{{ readable(activeCase.dataset) }}</span>
                <h3>{{ caseTitle(activeCase) }}</h3>
              </div>
              <a-space
                ><a-tag v-if="activeObservation" color="arcoblue"
                  >观察置信度
                  {{ scoreText(activeObservation.confidence) }}</a-tag
                ><a-button
                  type="primary"
                  @click="
                    openGraphExplore(activeCase.case_id, activeObservation?.id)
                  "
                  >关联分析</a-button
                ></a-space
              >
            </div>
            <VisualEvidenceViewer
              v-if="activeObservation?.modality === 'image'"
              :items="selectedObservationVisualEvidence"
              :label="caseTitle(activeCase)"
            />
            <ObservationSignal
              v-else-if="activeObservation"
              :observation="activeObservation"
            />
            <a-empty v-else description="当前案例没有观察记录" />
            <div class="observation-strip">
              <button
                v-for="item in filteredActiveObservationItems"
                :key="item.id"
                class="observation-chip"
                :class="{ 'is-active': item.id === activeObservation?.id }"
                :aria-pressed="item.id === activeObservation?.id"
                @click="setSelectedObservation(item.id)"
              >
                <strong>{{ readable(item.title) }}</strong
                ><span
                  >{{ readable(item.modality) }} ·
                  {{ scoreText(item.confidence) }}</span
                >
              </button>
            </div>
          </section>
          <section class="surface evidence-summary">
            <div class="surface-heading">
              <h3>统一证据</h3>
              <a-button
                type="text"
                :disabled="!activeObservation"
                @click="openObservationDetail(activeObservation?.id ?? null)"
                >查看来源与字段</a-button
              >
            </div>
            <div class="evidence-facts">
              <div>
                <span>观察内容</span
                ><strong>{{ readable(activeObservation?.title) }}</strong>
              </div>
              <div>
                <span>来源模态</span
                ><strong>{{ readable(activeObservation?.modality) }}</strong>
              </div>
              <div>
                <span>关联线索</span
                ><strong>{{
                  activeObservation?.linkedEntityHints
                    .map((v) => readable(v))
                    .join("、") || "暂无"
                }}</strong>
              </div>
            </div>
            <div class="next-step">
              <div>
                <strong>接下来，检查这些证据如何支持候选解释</strong>
                <p class="subtle">
                  {{ activeRootCauseList.length }} 个候选 ·
                  {{ activeCase.path_graph?.path_count ?? 0 }} 条路径
                </p>
              </div>
              <a-button
                type="primary"
                @click="
                  openGraphExplore(activeCase.case_id, activeObservation?.id)
                "
                >查看关联分析 <icon-launch
              /></a-button>
            </div>
          </section>
        </main>
        <section v-else class="surface empty-workspace">
          <a-empty description="选择一个案例开始浏览" />
        </section>
      </div>
    </a-spin>
    <a-drawer
      v-model:visible="uploadDrawerVisible"
      title="新建分析"
      :width="520"
      :footer="false"
    >
      <a-form
        id="evidence-form-1"
        :model="uploadForm"
        layout="vertical"
        class="workspace-stack workspace-stack--fill workspace-upload-form-stack workspace-form"
      >
        <div class="workspace-form-row workspace-form-row--three">
          <a-form-item
            field="mode"
            label="模式"
            :label-attrs="{ for: 'evidence-uploadForm-mode-input' }"
            class="workspace-form-item"
          >
            <div
              id="evidence-uploadForm-mode"
              v-control-label="'模式'"
              class="workspace-control"
            >
              <div v-control-label="'模式'" class="labeled-control">
                <a-select aria-label="模式" v-model="uploadForm.mode">
                  <a-option
                    v-for="item in bootstrap?.upload_modes ?? []"
                    :key="item.mode"
                    :value="item.mode"
                  >
                    {{ formatUploadModeLabel(item.mode) }}
                  </a-option>
                </a-select>
              </div>
            </div>
          </a-form-item>
          <a-form-item
            field="dataset"
            label="数据集"
            :label-attrs="{ for: 'evidence-uploadForm-dataset-input' }"
            class="workspace-form-item"
          >
            <div
              id="evidence-uploadForm-dataset"
              v-control-label="'数据集'"
              class="workspace-control"
            >
              <div v-control-label="'数据集'" class="labeled-control">
                <a-select
                  aria-label="数据集"
                  v-model="uploadForm.dataset"
                  allow-clear
                >
                  <a-option value="">自动</a-option>
                  <a-option
                    v-for="dataset in bootstrap?.supported_datasets ?? []"
                    :key="dataset"
                    :value="dataset"
                  >
                    {{ dataset }}
                  </a-option>
                </a-select>
              </div>
            </div>
          </a-form-item>
          <a-form-item
            field="topK"
            label="候选数"
            :label-attrs="{ for: 'evidence-uploadForm-topK-input' }"
            class="workspace-form-item"
          >
            <a-input-number
              :input-attrs="{
                id: 'evidence-uploadForm-topK-input',
                'aria-label': '候选数',
              }"
              id="evidence-uploadForm-topK"
              v-control-label="'候选数'"
              aria-label="候选数"
              v-model="uploadForm.topK"
              :min="1"
              :max="20"
            />
          </a-form-item>
        </div>

        <a-form-item
          field="reasoningProfileId"
          label="推理配置"
          :label-attrs="{ for: 'evidence-uploadForm-reasoningProfileId-input' }"
          :tooltip="uploadReasoningHelp"
          class="workspace-form-item"
        >
          <div
            id="evidence-uploadForm-reasoningProfileId"
            v-control-label="'推理配置'"
            class="workspace-control"
          >
            <div v-control-label="'推理配置'" class="labeled-control">
              <a-select
                aria-label="推理配置"
                v-model="uploadForm.reasoningProfileId"
                :disabled="!uploadForm.dataset"
              >
                <a-option value="">自动（按数据集默认）</a-option>
                <a-option
                  v-for="option in uploadReasoningProfileOptions"
                  :key="option.profile_id"
                  :value="option.profile_id"
                >
                  {{ option.profile_id }} ·
                  {{ formatReasonerAdapterLabel(option.reasoner_adapter) }}
                </a-option>
              </a-select>
            </div>
          </div>
        </a-form-item>

        <div
          v-if="uploadForm.mode === 'image'"
          class="workspace-form-row workspace-form-row--three"
        >
          <a-form-item
            field="objectName"
            label="对象"
            :label-attrs="{ for: 'evidence-uploadForm-objectName-input' }"
            class="workspace-form-item"
          >
            <a-input
              :input-attrs="{
                id: 'evidence-uploadForm-objectName-input',
                'aria-label': '对象',
              }"
              id="evidence-uploadForm-objectName"
              v-control-label="'对象'"
              aria-label="对象"
              v-model="uploadForm.objectName"
              placeholder="例如 bottle"
            />
          </a-form-item>
          <a-form-item
            field="defectType"
            label="缺陷类型"
            :label-attrs="{ for: 'evidence-uploadForm-defectType-input' }"
            class="workspace-form-item"
          >
            <a-input
              :input-attrs="{
                id: 'evidence-uploadForm-defectType-input',
                'aria-label': '缺陷类型',
              }"
              id="evidence-uploadForm-defectType"
              v-control-label="'缺陷类型'"
              aria-label="缺陷类型"
              v-model="uploadForm.defectType"
              placeholder="例如 scratch"
            />
          </a-form-item>
          <a-form-item
            field="modelPreset"
            label="预设"
            :label-attrs="{ for: 'evidence-uploadForm-modelPreset-input' }"
            class="workspace-form-item"
          >
            <a-input
              :input-attrs="{
                id: 'evidence-uploadForm-modelPreset-input',
                'aria-label': '预设',
              }"
              id="evidence-uploadForm-modelPreset"
              v-control-label="'预设'"
              aria-label="预设"
              v-model="uploadForm.modelPreset"
              placeholder="auto"
            />
          </a-form-item>
        </div>

        <a-form-item
          label="文件"
          label-component="span"
          class="workspace-form-item workspace-dropzone-field"
        >
          <div
            class="rl-file-dropzone rl-file-dropzone--fill"
            :class="{ 'rl-file-dropzone--active': uploadDragActive }"
            @dragenter="handleUploadDragEnter"
            @dragover="handleUploadDragOver"
            @dragleave="handleUploadDragLeave"
            @drop="handleUploadDrop"
          >
            <input
              ref="uploadInputRef"
              class="rl-file-input-native"
              type="file"
              :accept="uploadAccept"
              @change="handleUploadFileChange"
            />
            <div
              class="rl-file-dropzone__content rl-file-dropzone__content--fill"
            >
              <div class="rl-file-dropzone__copy">
                <strong>
                  {{
                    uploadForm.file?.name ??
                    "拖动文件到这里，或点击按钮选择文件"
                  }}
                </strong>
                <span>{{
                  uploadAccept || "支持 JSON / JSONL / CSV / 图像输入"
                }}</span>
              </div>
              <a-button
                aria-label="选择运行文件"
                size="small"
                @click="openUploadPicker"
              >
                选择文件
              </a-button>
            </div>
          </div>
        </a-form-item>
      </a-form>
      <a-button
        type="primary"
        long
        :loading="uploadLoading"
        @click="handleUpload"
        >上传并分析</a-button
      >
    </a-drawer>
    <a-drawer
      v-model:visible="filtersVisible"
      title="筛选证据"
      :width="420"
      :footer="false"
    >
      <a-form
        id="evidence-form-2"
        :model="evidenceFilter"
        layout="horizontal"
        label-align="left"
        :label-col-props="{ flex: '64px' }"
        :wrapper-col-props="{ flex: '1' }"
        class="workspace-inline-filters workspace-inline-filters--two-col workspace-form workspace-form--compact-filters"
      >
        <a-form-item
          field="graph"
          label="图谱"
          :label-attrs="{ for: 'evidence-evidenceFilter-graph-input' }"
          class="workspace-form-item"
        >
          <div
            id="evidence-evidenceFilter-graph"
            v-control-label="'图谱'"
            class="workspace-control"
          >
            <div v-control-label="'图谱'" class="labeled-control">
              <a-select aria-label="图谱" v-model="evidenceFilter.graph">
                <a-option value="all">全部图谱</a-option>
                <a-option
                  v-for="graphId in graphOptions"
                  :key="graphId"
                  :value="graphId"
                >
                  {{ graphId }}
                </a-option>
              </a-select>
            </div>
          </div>
        </a-form-item>
        <a-form-item
          field="modality"
          label="模态"
          :label-attrs="{ for: 'evidence-evidenceFilter-modality-input' }"
          class="workspace-form-item"
        >
          <div
            id="evidence-evidenceFilter-modality"
            v-control-label="'模态'"
            class="workspace-control"
          >
            <div v-control-label="'模态'" class="labeled-control">
              <a-select aria-label="模态" v-model="evidenceFilter.modality">
                <a-option value="all">全部</a-option>
                <a-option
                  v-for="modality in observationModalityOptions"
                  :key="modality"
                  :value="modality"
                >
                  {{ formatObservationModalityLabel(modality) }}
                </a-option>
              </a-select>
            </div>
          </div>
        </a-form-item>
        <a-form-item
          field="source"
          label="来源"
          :label-attrs="{ for: 'evidence-evidenceFilter-source-input' }"
          class="workspace-form-item"
        >
          <div
            id="evidence-evidenceFilter-source"
            v-control-label="'来源'"
            class="workspace-control"
          >
            <div v-control-label="'来源'" class="labeled-control">
              <a-select aria-label="来源" v-model="evidenceFilter.source">
                <a-option value="all">全部来源</a-option>
                <a-option
                  v-for="source in observationSourceOptions"
                  :key="source"
                  :value="source"
                >
                  {{ source }}
                </a-option>
              </a-select>
            </div>
          </div>
        </a-form-item>
        <a-form-item
          field="confidenceBand"
          label="置信度"
          :label-attrs="{ for: 'evidence-evidenceFilter-confidenceBand-input' }"
          class="workspace-form-item"
        >
          <div
            id="evidence-evidenceFilter-confidenceBand"
            v-control-label="'置信度'"
            class="workspace-control"
          >
            <div v-control-label="'置信度'" class="labeled-control">
              <a-select
                aria-label="置信度"
                v-model="evidenceFilter.confidenceBand"
              >
                <a-option value="all">全部</a-option>
                <a-option value="high">高</a-option>
                <a-option value="medium">中</a-option>
                <a-option value="low">低</a-option>
              </a-select>
            </div>
          </div>
        </a-form-item>
        <a-form-item
          label="时间范围"
          :label-attrs="{ for: 'evidence-evidenceFilter-timeFrom-input' }"
          class="workspace-form-item workspace-inline-filters__wide"
        >
          <div class="workspace-form-row workspace-time-range">
            <a-input
              :input-attrs="{
                id: 'evidence-evidenceFilter-timeFrom-input',
                'aria-label': '开始时间',
              }"
              id="evidence-evidenceFilter-timeFrom"
              v-control-label="'开始时间'"
              aria-label="开始时间"
              v-model="evidenceFilter.timeFrom"
              type="datetime-local"
              placeholder="开始时间"
            />
            <a-input
              :input-attrs="{
                id: 'evidence-evidenceFilter-timeFrom-1-input',
                'aria-label': '结束时间',
              }"
              id="evidence-evidenceFilter-timeFrom-1"
              v-control-label="'结束时间'"
              aria-label="结束时间"
              v-model="evidenceFilter.timeTo"
              type="datetime-local"
              placeholder="结束时间"
            />
          </div>
        </a-form-item>
        <a-form-item
          field="keyword"
          label="关键字"
          :label-attrs="{ for: 'evidence-evidenceFilter-keyword-input' }"
          class="workspace-form-item workspace-inline-filters__wide"
        >
          <a-input
            :input-attrs="{
              id: 'evidence-evidenceFilter-keyword-input',
              'aria-label': '关键字',
            }"
            id="evidence-evidenceFilter-keyword"
            v-control-label="'关键字'"
            aria-label="关键字"
            v-model="evidenceFilter.keyword"
            placeholder="搜索 obs / source / hint / ref / variable / event"
          />
        </a-form-item>
      </a-form>
    </a-drawer>
    <a-modal
      v-model:visible="replayModalVisible"
      title="导入回放资产"
      :footer="false"
      :mask-closable="!replayImportLoading"
      :esc-to-close="!replayImportLoading"
      class="workspace-replay-modal"
    >
      <a-form
        id="evidence-form-3"
        :model="replayImportForm"
        layout="vertical"
        class="workspace-stack workspace-stack--tight workspace-form"
      >
        <a-form-item
          label="rootlens-runtime.json"
          tooltip="与 unified-graphs.json 一起导入。"
          label-component="span"
          class="workspace-replay-import-field"
        >
          <input
            ref="replayRuntimeInputRef"
            class="rl-file-input-native"
            type="file"
            accept=".json"
            @change="handleReplayFileChange('runtimeFile', $event)"
          />
          <a-button
            aria-label="选择 rootlens-runtime.json"
            size="small"
            @click="openReplayFilePicker('runtimeFile')"
          >
            {{ replayImportForm.runtimeFile?.name ?? "选择文件" }}
          </a-button>
        </a-form-item>

        <a-form-item
          label="unified-graphs.json"
          tooltip="与 rootlens-runtime.json 一起导入。"
          label-component="span"
          class="workspace-replay-import-field"
        >
          <input
            ref="replayGraphsInputRef"
            class="rl-file-input-native"
            type="file"
            accept=".json"
            @change="handleReplayFileChange('graphsFile', $event)"
          />
          <a-button
            aria-label="选择 unified-graphs.json"
            size="small"
            @click="openReplayFilePicker('graphsFile')"
          >
            {{ replayImportForm.graphsFile?.name ?? "选择文件" }}
          </a-button>
        </a-form-item>

        <a-form-item
          label="workspace export / session bundle"
          tooltip="可选工作区；完整 session bundle 请单独导入。"
          label-component="span"
          class="workspace-replay-import-field"
        >
          <input
            ref="replayWorkspaceInputRef"
            class="rl-file-input-native"
            type="file"
            accept=".json"
            @change="handleReplayFileChange('workspaceFile', $event)"
          />
          <a-button
            aria-label="选择 workspace export / session bundle"
            size="small"
            @click="openReplayFilePicker('workspaceFile')"
          >
            {{ replayImportForm.workspaceFile?.name ?? "选择文件" }}
          </a-button>
        </a-form-item>

        <a-alert
          type="info"
          :show-icon="false"
          title="资产导入仅支持完整回放（runtime + graphs）；若同时导入 workspace export，会先恢复回放资产，再叠加 workspace。完整 session bundle 请单独导入。"
        />

        <div class="rl-form-actions rl-form-actions--dual">
          <a-button
            type="primary"
            :loading="replayImportLoading"
            @click="handleReplayImport"
          >
            导入并切换到回放
          </a-button>
          <a-button
            :disabled="replayImportLoading"
            @click="replayModalVisible = false"
          >
            取消
          </a-button>
        </div>
      </a-form>
    </a-modal>
    <a-modal
      v-model:visible="observationDetailModalVisible"
      title="观察与原始出处"
      width="min(760px, 94vw)"
      :footer="false"
    >
      <template v-if="activeObservation">
        <div class="evidence-facts">
          <div>
            <span>观察</span
            ><strong>{{ readable(activeObservation.title) }}</strong>
          </div>
          <div>
            <span>置信度</span
            ><strong>{{ scoreText(activeObservation.confidence) }}</strong>
          </div>
          <div>
            <span>时间</span><strong>{{ activeObservation.timeLabel }}</strong>
          </div>
        </div>
        <h4>原始证据来源</h4>
        <div
          v-for="refItem in activeObservation.rawEvidenceRefs"
          :key="refItem.refId"
          class="source-excerpt"
        >
          <strong>{{ readable(refItem.label, "证据引用") }}</strong>
          <p class="break-anywhere">
            {{ refItem.filePath || "未记录文件位置"
            }}<span v-if="refItem.line"> · 第 {{ refItem.line }} 行</span>
          </p>
        </div>
        <a-empty
          v-if="!activeObservation.rawEvidenceRefs.length"
          description="此观察未记录原始来源定位"
        />
        <a-collapse
          ><a-collapse-item header="技术详情" item-key="technical"
            ><p class="break-anywhere">观察 ID：{{ activeObservation.id }}</p>
            <pre class="raw-json">{{
              JSON.stringify(activeObservation.rawObservation, null, 2)
            }}</pre>
          </a-collapse-item></a-collapse
        >
      </template>
    </a-modal>
  </div>
</template>
