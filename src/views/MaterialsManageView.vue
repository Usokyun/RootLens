<script setup lang="ts">
import {
  IconBulb,
  IconInfoCircle,
  IconRefresh,
  IconRelation,
  IconStorage,
  IconUpload,
} from "@arco-design/web-vue/es/icon";
import { computed, onMounted, reactive, ref, watch } from "vue";

import type {
  KGDraftListRequest,
  KGDraftRecord,
  KGMaterialBuildSourcesResponse,
  KGMaterialChunkRecord,
  KGMaterialExtractionArtifactRecord,
  KGMaterialExtractionRunRecord,
  KGMaterialRecord,
  KGSourceDraftResponse,
  KGConstructionBuildDetail,
  KGConstructionBuildListResponse,
  KGConstructionBuildValidationResponse,
  KGConstructionReviewQueueEdge,
  KGConstructionReviewQueueResponse,
  KGStudioPayload,
} from "@/api/contracts";
import SectionCardTitle from "@/components/layout/SectionCardTitle.vue";
import ProvenanceInspectorDrawer from "@/components/provenance/ProvenanceInspectorDrawer.vue";
import { useAppPreferences } from "@/services/app-preferences";
import { extractFilesFromDataTransfer, markDragEventHandled } from "@/services/file-drop";
import { uploadKGMaterialFiles } from "@/services/material-upload";
import { getRootLensService } from "@/services/rootlens-service";
import {
  buildMaterialsBuildEdgeProvenance,
  buildMaterialsBuildProvenance,
  type ProvenanceInspectorState,
  type ProvenanceSourceMaterial,
} from "@/services/provenance-inspector";
import { downloadJsonFile } from "@/services/session-export";
import { formatClaimBoundaryCopy } from "@/services/ui-copy";
import { sourceSelectionReset, useWorkbenchState } from "@/services/workbench-state";

interface RootLensKGBuildExportV1 {
  schema_version: "rootlens-kg-build-export.v1";
  exported_at: string;
  source_mode: "mock" | "backend";
  build: KGConstructionBuildDetail["build"];
  summary: KGConstructionBuildDetail["summary"];
  manifest: KGConstructionBuildDetail["manifest"];
  claim_boundary: string;
}

const { preferences } = useAppPreferences();
const { state: workbenchState, updateState } = useWorkbenchState();

let sourceRevision = 0;
const loading = ref(false);
const errorMessage = ref("");
const actionMessage = ref("");
const activationLoading = ref(false);
const activationDataset = ref<"mvtec" | "wafer" | "tep">("mvtec");

const materials = ref<KGMaterialRecord[]>([]);
const builds = ref<KGConstructionBuildListResponse | null>(null);
const buildDetail = ref<KGConstructionBuildDetail | null>(null);
const buildSourcesPreview = ref<KGMaterialBuildSourcesResponse | null>(null);
const kgStudio = ref<KGStudioPayload | null>(null);
const draftHistory = ref<KGDraftRecord[]>([]);

const selectedMaterialId = ref<string | null>(null);
const selectedMaterialIds = ref<string[]>([]);
const selectedMaterialTab = ref<
  "detail" | "chunks" | "extractions" | "artifacts" | "drafts" | "preview"
>("detail");
const materialDetail = ref<KGMaterialRecord | null>(null);
const materialChunks = ref<KGMaterialChunkRecord[]>([]);
const materialExtractions = ref<KGMaterialExtractionRunRecord[]>([]);
const materialArtifacts = ref<KGMaterialExtractionArtifactRecord[]>([]);
const sourceDraftPreview = ref<KGSourceDraftResponse | null>(null);

const materialDetailLoading = ref(false);
const materialMutationLoading = ref(false);
const materialSourceDrawerVisible = ref(false);
const materialSourceTab = ref("upload");
const materialSourceTriggerRef = ref<{ $el: HTMLButtonElement } | null>(null);
const materialSourcePanelRef = ref<HTMLElement | null>(null);

const materialExtractLoading = ref(false);
const sourceDraftLoading = ref(false);

const buildDetailModalVisible = ref(false);
const buildDetailModalLoading = ref(false);
const buildDetailModalTab = ref<"manifest" | "qa" | "queue">("manifest");
const buildValidation = ref<KGConstructionBuildValidationResponse | null>(null);
const buildReviewQueue = ref<KGConstructionReviewQueueResponse | null>(null);
const buildDetailModalError = ref("");
const provenanceInspectorVisible = ref(false);
const provenanceInspectorState = ref<ProvenanceInspectorState | null>(null);
const buildReviewActionTargetKey = ref<string | null>(null);

const filters = reactive({
  search: "",
  dataset: "all",
  type: "all",
  status: "all",
  sortField: "updatedAt" as "updatedAt" | "title" | "type",
  sortOrder: "desc" as "asc" | "desc",
});

const uploadForm = reactive({
  files: [] as File[],
  title: "",
  scenario: "shared",
  sourceType: "text",
  notes: "",
  materialId: "",
});

const registerUrlForm = reactive({
  url: "",
  title: "",
  scenario: "shared",
  sourceType: "webpage",
  notes: "",
  materialId: "",
});

const sourceDraftForm = reactive({
  defaultScenario: "shared",
  confidence: 0.55,
});

const buildForm = reactive({
  output_name: "workspace-build",
  source_type: "structured_records" as "structured_records" | "manual_table",
  capability: "legacy",
});

const uploadInputRef = ref<HTMLInputElement | null>(null);
const uploadDragActive = ref(false);
const uploadDragDepth = ref(0);

const selectedBuildRunId = computed(
  () => workbenchState.value.selectedConstructionRunId,
);

const selectedMaterial = computed(() => {
  return (
    filteredMaterials.value.find((item) => item.material_id === selectedMaterialId.value) ??
    filteredMaterials.value[0] ??
    null
  );
});

const selectedMaterials = computed(() =>
  materials.value.filter((item) => selectedMaterialIds.value.includes(item.material_id)),
);

const materialClaimBoundaryCopy = computed(() =>
  formatClaimBoundaryCopy(
    materialDetail.value?.claim_boundary ??
      buildDetail.value?.build.claim_boundary ??
      kgStudio.value?.claim_boundary,
  ),
);

const canExportBuild = computed(() => !!buildDetail.value);

const materialsLibraryHelp =
  "backend mode 下优先展示真实素材库，再从 extract 推进到 build-sources。";

const selectedMaterialHelp = computed(() => [
  "聚合展示 detail / chunks / extractions / artifacts / draft history。",
  materialClaimBoundaryCopy.value,
]);

const uploadSourceHelp = [
  "优先走 material library，再进入 extract / build-sources。",
  "将远程来源先登记到 material library，再单独执行抽取。",
];

const buildResultsHelp =
  "保留现有 candidate KG build / QA / review queue 能力。";

const buildRecipeHelp = computed(() => [
  "先走 build-sources，再复用现有 construction build。",
  materialClaimBoundaryCopy.value,
]);

const filteredMaterials = computed(() => {
  const keyword = filters.search.trim().toLowerCase();
  const list = materials.value.filter((item) => {
    if (filters.dataset !== "all" && item.scenario !== filters.dataset) {
      return false;
    }
    if (filters.type !== "all" && item.source_type !== filters.type) {
      return false;
    }
    if (
      filters.status !== "all" &&
      item.processing_status !== filters.status &&
      item.extraction_status !== filters.status
    ) {
      return false;
    }
    if (!keyword) {
      return true;
    }

    return [
      item.title,
      item.material_id,
      item.source_type,
      item.notes,
      item.path,
      item.url,
      item.uri,
    ]
      .join(" ")
      .toLowerCase()
      .includes(keyword);
  });

  return list.sort((left, right) => {
    const direction = filters.sortOrder === "asc" ? 1 : -1;

    if (filters.sortField === "updatedAt") {
      const leftTime = Date.parse(left.updated_at ?? left.created_at ?? "");
      const rightTime = Date.parse(right.updated_at ?? right.created_at ?? "");
      return ((Number.isNaN(leftTime) ? 0 : leftTime) - (Number.isNaN(rightTime) ? 0 : rightTime)) * direction;
    }

    if (filters.sortField === "title") {
      return left.title.localeCompare(right.title) * direction;
    }

    return left.source_type.localeCompare(right.source_type) * direction;
  });
});

const provenanceSourceMaterials = computed<ProvenanceSourceMaterial[]>(() =>
  materials.value.map((item) => ({
    sourceId: item.source_id ?? item.material_id,
    title: item.title,
    path: item.url ?? item.path ?? item.uri ?? "--",
    sourceType: item.source_type,
    note: item.notes ?? "",
  })),
);

function formatDateTime(value: string | undefined | null) {
  if (!value) {
    return "--";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatJsonPreview(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function formatMaterialLocation(material: KGMaterialRecord | null | undefined) {
  if (!material) {
    return "--";
  }

  return material.url ?? material.path ?? material.uri ?? "--";
}

function formatMaterialStatus(material: KGMaterialRecord | null | undefined) {
  if (!material) {
    return "--";
  }

  if (material.extraction_status === "extracted") {
    return "已抽取";
  }

  if (material.extraction_status === "failed") {
    return "抽取失败";
  }

  return material.processing_status;
}

function setUploadFiles(files: File[]) {
  if (!materialMutationLoading.value) {
    uploadForm.files = files;
  }
}

function handleUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  setUploadFiles(Array.from(input?.files ?? []));
  if (input) input.value = "";
}

function openUploadPicker() {
  if (!materialMutationLoading.value) uploadInputRef.value?.click();
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
  setUploadFiles(extractFilesFromDataTransfer(event.dataTransfer));
  resetUploadDragState();
}

function toggleMaterialSelection(materialId: string, checked: boolean) {
  if (checked) {
    selectedMaterialIds.value = [...new Set([...selectedMaterialIds.value, materialId])];
    return;
  }

  selectedMaterialIds.value = selectedMaterialIds.value.filter((item) => item !== materialId);
}

async function loadBuildDetail(runId: string) {
  const revision = sourceRevision;
  try {
    const detail = await getRootLensService().getKGConstructionBuild(runId);
    if (revision !== sourceRevision) return;
    buildDetail.value = detail;
    updateState({ selectedConstructionRunId: runId });
  } catch (error) {
    if (revision === sourceRevision) errorMessage.value = error instanceof Error ? error.message : String(error);
  }
}

function openMaterialsProvenance(state: ProvenanceInspectorState | null) {
  if (!state) {
    return;
  }

  provenanceInspectorState.value = state;
  provenanceInspectorVisible.value = true;
}

function openBuildProvenance() {
  openMaterialsProvenance(
    buildMaterialsBuildProvenance({
      buildDetail: buildDetail.value,
      buildValidation: buildValidation.value,
      materials: provenanceSourceMaterials.value,
      claimBoundary: materialClaimBoundaryCopy.value,
    }),
  );
}

function openBuildReviewEdgeProvenance(edge: KGConstructionReviewQueueEdge) {
  openMaterialsProvenance(
    buildMaterialsBuildEdgeProvenance({
      buildDetail: buildDetail.value,
      edge,
      materials: provenanceSourceMaterials.value,
      claimBoundary: materialClaimBoundaryCopy.value,
    }),
  );
}

async function loadBuildDetailModalState(runId: string) {
  buildDetailModalLoading.value = true;
  buildDetailModalError.value = "";

  try {
    const [detailResult, validationResult, reviewQueueResult] =
      await Promise.allSettled([
        getRootLensService().getKGConstructionBuild(runId),
        getRootLensService().validateKGConstructionBuild(runId),
        getRootLensService().getKGConstructionReviewQueue(runId, { limit: 12 }),
      ]);

    if (detailResult.status !== "fulfilled") {
      throw detailResult.reason;
    }

    buildDetail.value = detailResult.value;
    updateState({ selectedConstructionRunId: runId });
    buildValidation.value =
      validationResult.status === "fulfilled" ? validationResult.value : null;
    buildReviewQueue.value =
      reviewQueueResult.status === "fulfilled" ? reviewQueueResult.value : null;

    const warnings = [
      validationResult.status === "rejected"
        ? "当前构图详情暂未返回 QA 报告。"
        : "",
      reviewQueueResult.status === "rejected"
        ? "当前构图详情暂未返回 review queue。"
        : "",
    ].filter(Boolean);

    buildDetailModalError.value = warnings.join(" ");
  } catch (error) {
    buildDetailModalError.value =
      error instanceof Error ? error.message : String(error);
  } finally {
    buildDetailModalLoading.value = false;
  }
}

async function openBuildDetailModal(runId: string) {
  buildDetailModalVisible.value = true;
  buildDetailModalTab.value = "manifest";
  await loadBuildDetailModalState(runId);
}

async function handleBuildReviewAction(
  targetKey: string,
  action: "accept" | "reject",
) {
  if (!buildDetail.value) {
    return;
  }

  buildReviewActionTargetKey.value = targetKey;
  buildDetailModalError.value = "";

  try {
    await getRootLensService().reviewKGConstructionEdge(
      buildDetail.value.build.run_id,
      {
        action,
        target_key: targetKey,
        reviewer: "rootlens-frontend",
      },
    );
    actionMessage.value = `已${action === "accept" ? "接受" : "拒绝"}构图边：${targetKey}`;
    await refreshWorkspace();
    await loadBuildDetailModalState(buildDetail.value.build.run_id);
    buildDetailModalTab.value = "queue";
  } catch (error) {
    buildDetailModalError.value =
      error instanceof Error ? error.message : String(error);
  } finally {
    buildReviewActionTargetKey.value = null;
  }
}

async function loadSelectedMaterialState(materialId: string) {
  const revision = sourceRevision;
  materialDetailLoading.value = true;
  sourceDraftPreview.value = null;

  try {
    const [detail, chunks, extractions, artifacts] = await Promise.all([
      getRootLensService().getKGMaterial(materialId),
      getRootLensService().getKGMaterialChunks(materialId),
      getRootLensService().getKGMaterialExtractions(materialId),
      getRootLensService().getKGMaterialArtifacts(materialId),
    ]);
    if (revision !== sourceRevision) return;
    materialDetail.value = detail.material;
    materialChunks.value = chunks.chunks;
    materialExtractions.value = extractions.runs;
    materialArtifacts.value = artifacts.artifacts;
  } catch (error) {
    if (revision !== sourceRevision) return;
    materialDetail.value = null;
    materialChunks.value = [];
    materialExtractions.value = [];
    materialArtifacts.value = [];
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    if (revision === sourceRevision) materialDetailLoading.value = false;
  }
}

async function handleActivateBuild() {
  if (!buildDetail.value || preferences.value.dataSourceMode !== "backend") return;
  activationLoading.value = true;
  errorMessage.value = "";
  try {
    const graph = await getRootLensService().activateWorkingGraph(
      buildDetail.value.build.run_id, `${activationDataset.value} · ${buildDetail.value.build.run_id}`, activationDataset.value,
      buildDetail.value.summary.target_contract === "unified-v2" ? "unified-v2" : "legacy",
    );
    actionMessage.value = `已装载 ${graph.title}。在 Evidence 页的推理配置中选择它。`;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    activationLoading.value = false;
  }
}

async function refreshWorkspace() {
  const revision = sourceRevision;
  loading.value = true;
  errorMessage.value = "";

  try {
    const [materialsResponse, buildList, kgStudioPayload, draftHistoryResponse] =
      await Promise.all([
        getRootLensService().listKGMaterials(),
        getRootLensService().listKGConstructionBuilds(),
        getRootLensService().kgStudio(),
        getRootLensService().listKGDrafts({ limit: 50 } as KGDraftListRequest),
      ]);

    if (revision !== sourceRevision) return;
    materials.value = materialsResponse.materials;
    builds.value = buildList;
    kgStudio.value = kgStudioPayload;
    draftHistory.value = draftHistoryResponse.records;

    selectedMaterialIds.value = selectedMaterialIds.value.filter((materialId) =>
      materialsResponse.materials.some((item) => item.material_id === materialId),
    );

    const nextMaterialId =
      materialsResponse.materials.find(
        (item) => item.material_id === selectedMaterialId.value,
      )?.material_id ?? materialsResponse.materials[0]?.material_id ?? null;
    selectedMaterialId.value = nextMaterialId;
    if (nextMaterialId) {
      await loadSelectedMaterialState(nextMaterialId);
    } else {
      materialDetail.value = null;
      materialChunks.value = [];
      materialExtractions.value = [];
      materialArtifacts.value = [];
    }

    if (revision !== sourceRevision) return;

    const nextBuildId =
      buildList.builds.find((item) => item.run_id === selectedBuildRunId.value)
        ?.run_id ??
      buildList.builds[0]?.run_id ??
      null;

    if (nextBuildId) {
      await loadBuildDetail(nextBuildId);
    } else {
      buildDetail.value = null;
    }
  } catch (error) {
    if (revision === sourceRevision) errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    if (revision === sourceRevision) loading.value = false;
  }
}

function handleMaterialSourceKeydown(event: KeyboardEvent) {
  if (event.key !== "Tab" || !materialSourceDrawerVisible.value) return;

  const drawer = materialSourcePanelRef.value?.closest(".arco-drawer");
  const controls = Array.from(
    drawer?.querySelectorAll<HTMLElement>(
      'button, input, textarea, select, a[href], [tabindex]:not([tabindex="-1"])',
    ) ?? [],
  ).filter((control) =>
    control.tabIndex >= 0 && !control.matches(":disabled") && control.getClientRects().length > 0,
  );
  const first = controls[0];
  const last = controls[controls.length - 1];
  if (!first || !last) return;

  const active = document.activeElement;
  if (event.shiftKey && (active === first || active === materialSourcePanelRef.value)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (active === last || active === materialSourcePanelRef.value)) {
    event.preventDefault();
    first.focus();
  }
}

async function handleMaterialUpload() {
  if (materialMutationLoading.value) return;
  if (!uploadForm.files.length) {
    actionMessage.value = "请选择待上传的素材文件。";
    return;
  }

  materialMutationLoading.value = true;
  actionMessage.value = "";
  errorMessage.value = "";

  try {
    const files = [...uploadForm.files];
    const { uploaded, failed } = await uploadKGMaterialFiles(
      files,
      {
        title: uploadForm.title || undefined,
        scenario: uploadForm.scenario || undefined,
        source_type: uploadForm.sourceType || undefined,
        notes: uploadForm.notes || undefined,
        material_id: uploadForm.materialId || undefined,
      },
      getRootLensService().uploadKGMaterial,
    );
    uploadForm.files = failed.map((item) => item.file);
    if (!failed.length) {
      uploadForm.title = "";
      uploadForm.notes = "";
      uploadForm.materialId = "";
    }
    const lastUploaded = uploaded[uploaded.length - 1];
    if (lastUploaded) {
      actionMessage.value = files.length === 1
        ? `素材已上传：${lastUploaded.material.material_id}`
        : `已上传 ${uploaded.length} 个素材。`;
      await refreshWorkspace();
      selectedMaterialId.value = lastUploaded.material.material_id;
      await loadSelectedMaterialState(lastUploaded.material.material_id);
    }
    if (failed.length) {
      errorMessage.value = [
        errorMessage.value,
        ...failed.map((item) => `${item.file.name}：${item.error}`),
      ].filter(Boolean).join("；");
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    materialMutationLoading.value = false;
  }
}

async function handleRegisterUrl() {
  if (!registerUrlForm.url.trim()) {
    actionMessage.value = "请输入待注册的 URL。";
    return;
  }

  materialMutationLoading.value = true;
  actionMessage.value = "";
  errorMessage.value = "";

  try {
    const response = await getRootLensService().registerKGMaterialUrl({
      url: registerUrlForm.url,
      title: registerUrlForm.title || undefined,
      scenario: registerUrlForm.scenario || undefined,
      source_type: registerUrlForm.sourceType || undefined,
      notes: registerUrlForm.notes || undefined,
      material_id: registerUrlForm.materialId || undefined,
    });
    actionMessage.value = `URL 已注册：${response.material.material_id}`;
    registerUrlForm.url = "";
    registerUrlForm.title = "";
    registerUrlForm.notes = "";
    registerUrlForm.materialId = "";
    await refreshWorkspace();
    selectedMaterialId.value = response.material.material_id;
    await loadSelectedMaterialState(response.material.material_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    materialMutationLoading.value = false;
  }
}

async function handleMaterialExtract() {
  if (!selectedMaterial.value) {
    actionMessage.value = "请先选择一份素材。";
    return;
  }

  materialExtractLoading.value = true;
  actionMessage.value = "";
  errorMessage.value = "";

  try {
    const response = await getRootLensService().extractKGMaterial(
      selectedMaterial.value.material_id,
      { overwrite: true },
    );
    actionMessage.value = `解析完成：${response.record_count} 个实际片段，可在 Chunks 查看内容与定位。`;
    await refreshWorkspace();
    selectedMaterialId.value = response.material.material_id;
    await loadSelectedMaterialState(response.material.material_id);
    selectedMaterialTab.value = "chunks";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    materialExtractLoading.value = false;
  }
}

async function handleGenerateSourceDraftPreview() {
  if (!selectedMaterial.value) {
    actionMessage.value = "请先选择一份素材。";
    return;
  }

  if (!materialChunks.value.length) {
    actionMessage.value = "请先对当前素材执行抽取，再生成预览。";
    return;
  }

  sourceDraftLoading.value = true;
  actionMessage.value = "";
  errorMessage.value = "";

  try {
    sourceDraftPreview.value = await getRootLensService().generateKGSourceDraft({
      source_id: selectedMaterial.value.source_id ?? selectedMaterial.value.material_id,
      source_text: materialChunks.value
        .slice(0, 5)
        .map((chunk) => chunk.text_content)
        .join("\n"),
      provider: "heuristic",
      default_scenario:
        sourceDraftForm.defaultScenario || selectedMaterial.value.scenario,
      confidence: sourceDraftForm.confidence,
    });
    selectedMaterialTab.value = "preview";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    sourceDraftLoading.value = false;
  }
}

async function handleBuild() {
  if (!selectedMaterials.value.length) {
    actionMessage.value = "请先勾选至少一份已抽取素材。";
    return;
  }

  actionMessage.value = "";
  errorMessage.value = "";

  try {
    const baseName = buildForm.output_name.trim();
    const outputName = (builds.value?.builds ?? []).some(build => build.output_dir.endsWith(`/${baseName}`))
      ? `${baseName}-${Date.now()}` : baseName;
    const buildSourcesResponse = await getRootLensService().buildKGMaterialSources({
      material_ids: selectedMaterials.value.map((item) => item.material_id),
      output_name: outputName,
      overwrite: false,
      source_type: buildForm.source_type,
      target_contract: buildForm.capability === "legacy" ? "legacy" : "unified-v2",
      ...(buildForm.capability !== "legacy" ? { capability_id: buildForm.capability } : {}),
    });
    buildSourcesPreview.value = buildSourcesResponse;
    const response = await getRootLensService().buildKGConstruction(
      buildSourcesResponse.construction_request,
    );
    actionMessage.value = `图谱已生成：${response.run_id}`;
    await refreshWorkspace();
    await loadBuildDetail(response.run_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  }
}

function handleExportBuild() {
  if (!buildDetail.value) {
    return;
  }

  const payload: RootLensKGBuildExportV1 = {
    schema_version: "rootlens-kg-build-export.v1",
    exported_at: new Date().toISOString(),
    source_mode: preferences.value.dataSourceMode,
    build: buildDetail.value.build,
    summary: buildDetail.value.summary,
    manifest: buildDetail.value.manifest,
    claim_boundary: buildDetail.value.build.claim_boundary,
  };

  downloadJsonFile(
    `rootlens-kg-build-${buildDetail.value.build.run_id}.json`,
    payload,
  );
  actionMessage.value = `已导出图谱 bundle：${buildDetail.value.build.run_id}`;
}

watch(
  () => [preferences.value.dataSourceMode, preferences.value.apiBaseUrl],
  () => {
    sourceRevision += 1;
    materials.value = []; builds.value = null; buildDetail.value = null; kgStudio.value = null; draftHistory.value = [];
    selectedMaterialId.value = null; selectedMaterialIds.value = []; materialDetail.value = null; sourceDraftPreview.value = null;
    materialChunks.value = []; materialExtractions.value = []; materialArtifacts.value = []; buildSourcesPreview.value = null;
    buildDetailModalVisible.value = false;
    updateState(sourceSelectionReset());
    void refreshWorkspace();
  },
);

watch(selectedMaterialId, (materialId) => {
  if (!materialId) {
    materialDetail.value = null;
    materialChunks.value = [];
    materialExtractions.value = [];
    materialArtifacts.value = [];
    sourceDraftPreview.value = null;
    return;
  }

  void loadSelectedMaterialState(materialId);
});

watch(selectedMaterial, (material) => {
  if (material?.scenario) {
    sourceDraftForm.defaultScenario = material.scenario;
  }
});

watch(filteredMaterials, (list) => {
  if (!list.length) {
    selectedMaterialId.value = null;
    return;
  }

  if (!list.some((item) => item.material_id === selectedMaterialId.value)) {
    selectedMaterialId.value = list[0].material_id;
  }
});

watch(buildDetailModalVisible, (visible) => {
  if (!visible) {
    provenanceInspectorVisible.value = false;
    provenanceInspectorState.value = null;
  }
});

onMounted(() => {
  void refreshWorkspace();
});
</script>

<template>
  <div
    class="rl-page rl-screen"
    :class="{ 'rl-page--motion': preferences.enablePageEntranceMotion }"
  >
    <a-alert v-if="errorMessage" class="rl-alert" type="error" :title="errorMessage" />
    <a-alert v-if="actionMessage" class="rl-alert" type="success" :title="actionMessage" />

    <section class="workspace-shell workspace-shell--materials">
      <div class="workspace-materials-layout">
        <section class="workspace-materials-top-grid">
          <article class="rl-section-card workspace-materials-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="素材库" :help="materialsLibraryHelp">
                    <icon-relation />
                  </SectionCardTitle>
                </h3>
              </div>
              <div class="rl-panel-actions">
                <a-tag color="green">{{ filteredMaterials.length }} 份</a-tag>
                <a-button
                  ref="materialSourceTriggerRef"
                  type="primary"
                  :aria-expanded="materialSourceDrawerVisible"
                  aria-controls="material-source-drawer"
                  @click="materialSourceDrawerVisible = true"
                >
                  <template #icon><icon-upload /></template>
                  上传 / 注册素材
                </a-button>
                <a-button :loading="loading" @click="refreshWorkspace">
                  <template #icon><icon-refresh /></template>
                  刷新视图
                </a-button>
              </div>
            </header>
            <div class="rl-section-card__body workspace-table-card workspace-table-card--fill">
              <a-form
                id="materials-form-1"
                :model="filters"
                layout="vertical"
                class="workspace-filter-row workspace-form"
              >
                <a-form-item
                  field="search"
                  label="搜索"
                  :label-attrs="{ for: 'material-filter-search-input' }"
                >
                  <a-input
                    :input-attrs="{ id: 'material-filter-search-input', 'aria-label': '搜索' }"
                    id="material-filter-search"
                    aria-label="搜索"
                    v-model="filters.search"
                    placeholder="搜索 material / 路径 / 说明"
                  />
                </a-form-item>
                <a-form-item
                  field="dataset"
                  label="场景"
                  :label-attrs="{ for: 'material-filter-dataset-input' }"
                >
                  <div
                    id="material-filter-dataset"
                    v-control-label="'场景'"
                    class="workspace-control"
                  >
                    <a-select aria-label="场景" v-model="filters.dataset">
                      <a-option value="all">全部场景</a-option>
                      <a-option value="shared">shared</a-option>
                      <a-option value="tep">tep</a-option>
                      <a-option value="mvtec">mvtec</a-option>
                      <a-option value="wafer">wafer</a-option>
                    </a-select>
                  </div>
                </a-form-item>
                <a-form-item
                  field="type"
                  label="类型"
                  :label-attrs="{ for: 'material-filter-type-input' }"
                >
                  <div id="material-filter-type" v-control-label="'类型'" class="workspace-control">
                    <a-select aria-label="类型" v-model="filters.type">
                      <a-option value="all">全部类型</a-option>
                      <a-option value="text">text</a-option>
                      <a-option value="markdown">markdown</a-option>
                      <a-option value="webpage">webpage</a-option>
                      <a-option value="pdf">pdf</a-option>
                      <a-option value="csv">csv</a-option>
                      <a-option value="json">json</a-option>
                      <a-option value="jsonl">jsonl</a-option>
                    </a-select>
                  </div>
                </a-form-item>
                <a-form-item
                  field="status"
                  label="状态"
                  :label-attrs="{ for: 'material-filter-status-input' }"
                >
                  <div
                    id="material-filter-status"
                    v-control-label="'状态'"
                    class="workspace-control"
                  >
                    <a-select aria-label="状态" v-model="filters.status">
                      <a-option value="all">全部状态</a-option>
                      <a-option value="registered">registered</a-option>
                      <a-option value="uploaded">uploaded</a-option>
                      <a-option value="extracted">extracted</a-option>
                    </a-select>
                  </div>
                </a-form-item>
                <a-form-item
                  field="sortField"
                  label="排序字段"
                  :label-attrs="{ for: 'material-filter-sortField-input' }"
                >
                  <div
                    id="material-filter-sortField"
                    v-control-label="'排序字段'"
                    class="workspace-control"
                  >
                    <a-select aria-label="排序字段" v-model="filters.sortField">
                      <a-option value="updatedAt">按更新时间</a-option>
                      <a-option value="title">按名称</a-option>
                      <a-option value="type">按类型</a-option>
                    </a-select>
                  </div>
                </a-form-item>
                <a-form-item
                  field="sortOrder"
                  label="排序方向"
                  :label-attrs="{ for: 'material-filter-sortOrder-input' }"
                >
                  <div
                    id="material-filter-sortOrder"
                    v-control-label="'排序方向'"
                    class="workspace-control"
                  >
                    <a-select aria-label="排序方向" v-model="filters.sortOrder">
                      <a-option value="desc">降序</a-option>
                      <a-option value="asc">升序</a-option>
                    </a-select>
                  </div>
                </a-form-item>
              </a-form>

              <div
                class="workspace-table-wrap workspace-table-wrap--materials workspace-table-wrap--fill"
              >
                <table class="workspace-table">
                  <thead>
                    <tr>
                      <th>选择</th>
                      <th>名称</th>
                      <th>类型</th>
                      <th>场景</th>
                      <th>source_id</th>
                      <th>状态</th>
                      <th>更新时间</th>
                    </tr>
                  </thead>
                  <tbody v-if="filteredMaterials.length">
                    <tr
                      v-for="material in filteredMaterials"
                      :key="material.material_id"
                      :class="{
                        'workspace-table__row--active':
                          material.material_id === selectedMaterial?.material_id,
                      }"
                      @click="selectedMaterialId = material.material_id"
                    >
                      <td>
                        <a-checkbox
                          :model-value="selectedMaterialIds.includes(material.material_id)"
                          :aria-label="'选择素材 ' + material.title"
                          @click.stop
                          @change="toggleMaterialSelection(material.material_id, Boolean($event))"
                        />
                      </td>
                      <td>
                        <strong>{{ material.title }}</strong>
                      </td>
                      <td>{{ material.source_type }}</td>
                      <td>{{ material.scenario }}</td>
                      <td>{{ material.source_id ?? '--' }}</td>
                      <td>{{ formatMaterialStatus(material) }}</td>
                      <td>{{ formatDateTime(material.updated_at ?? material.created_at) }}</td>
                    </tr>
                  </tbody>
                  <tbody v-else>
                    <tr class="workspace-table__row--empty">
                      <td colspan="7">
                        <div class="workspace-table__empty-state">
                          <a-empty>当前 backend material library 为空</a-empty>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </article>

          <div class="workspace-materials-top-side-stack">
            <article class="rl-section-card workspace-material-editor-card">
              <header class="rl-section-card__header">
                <div>
                  <h3 class="rl-section-card__title">
                    <SectionCardTitle title="当前选中素材" :help="selectedMaterialHelp">
                      <icon-storage />
                    </SectionCardTitle>
                  </h3>
                </div>
                <a-tag color="arcoblue">{{ selectedMaterial?.material_id ?? '未选择' }}</a-tag>
              </header>
              <a-form
                id="materials-form-2"
                :model="sourceDraftForm"
                layout="vertical"
                class="rl-section-card__body workspace-stack workspace-stack--tight workspace-form workspace-material-editor-form"
              >
                <div class="workspace-summary-list workspace-summary-list--two-col">
                  <div class="workspace-summary-list__item">
                    <span class="workspace-summary-label">
                      <icon-info-circle />
                      <span>类型</span>
                    </span>
                    <strong>{{ selectedMaterial?.source_type ?? '--' }}</strong>
                  </div>
                  <div class="workspace-summary-list__item">
                    <span class="workspace-summary-label">
                      <icon-bulb />
                      <span>场景</span>
                    </span>
                    <strong>{{ selectedMaterial?.scenario ?? '--' }}</strong>
                  </div>
                  <div class="workspace-summary-list__item">
                    <span class="workspace-summary-label">
                      <icon-storage />
                      <span>状态</span>
                    </span>
                    <strong>{{ formatMaterialStatus(selectedMaterial) }}</strong>
                  </div>
                  <div class="workspace-summary-list__item">
                    <span class="workspace-summary-label">
                      <icon-relation />
                      <span>Source ID</span>
                    </span>
                    <strong>{{ selectedMaterial?.source_id ?? '--' }}</strong>
                  </div>
                  <div class="workspace-summary-list__item">
                    <span class="workspace-summary-label">
                      <icon-upload />
                      <span>Chunks</span>
                    </span>
                    <strong>{{ materialChunks.length }}</strong>
                  </div>
                  <div class="workspace-summary-list__item">
                    <span class="workspace-summary-label">
                      <icon-info-circle />
                      <span>Extractions</span>
                    </span>
                    <strong>{{ materialExtractions.length }}</strong>
                  </div>
                </div>

                <div class="workspace-summary-list__item">
                  <span class="workspace-summary-label">
                    <icon-info-circle />
                    <span>Location</span>
                  </span>
                  <strong :title="formatMaterialLocation(selectedMaterial)">
                    {{ formatMaterialLocation(selectedMaterial) }}
                  </strong>
                </div>

                <div class="rl-form-actions rl-form-actions--dual">
                  <a-button
                    size="small"
                    :disabled="!selectedMaterial"
                    @click="
                      selectedMaterial?.material_id &&
                      loadSelectedMaterialState(selectedMaterial.material_id)
                    "
                  >
                    刷新详情
                  </a-button>
                  <a-button
                    type="primary"
                    size="small"
                    :disabled="!selectedMaterial"
                    :loading="materialExtractLoading"
                    @click="handleMaterialExtract"
                  >
                    执行抽取
                  </a-button>
                  <a-button
                    size="small"
                    :disabled="!selectedMaterial || !materialChunks.length"
                    :loading="sourceDraftLoading"
                    @click="handleGenerateSourceDraftPreview"
                  >
                    生成预览
                  </a-button>
                </div>

                <div class="workspace-form-row workspace-form-row--two">
                  <a-form-item
                    field="defaultScenario"
                    label="预览场景"
                    :label-attrs="{ for: 'material-sourceDraftForm-defaultScenario-input' }"
                    class="workspace-form-item"
                  >
                    <a-input
                      :input-attrs="{
                        id: 'material-sourceDraftForm-defaultScenario-input',
                        'aria-label': '预览场景',
                      }"
                      id="material-sourceDraftForm-defaultScenario"
                      aria-label="预览场景"
                      v-model="sourceDraftForm.defaultScenario"
                    />
                  </a-form-item>
                  <a-form-item
                    field="confidence"
                    label="预览置信度"
                    :label-attrs="{ for: 'material-sourceDraftForm-confidence-input' }"
                    class="workspace-form-item"
                  >
                    <a-input-number
                      :input-attrs="{
                        id: 'material-sourceDraftForm-confidence-input',
                        'aria-label': '预览置信度',
                      }"
                      id="material-sourceDraftForm-confidence"
                      aria-label="预览置信度"
                      v-model="sourceDraftForm.confidence"
                      :min="0"
                      :max="1"
                      :step="0.05"
                    />
                  </a-form-item>
                </div>

                <a-spin v-if="materialDetailLoading" />

                <a-tabs v-else v-model:active-key="selectedMaterialTab" lazy-load>
                  <a-tab-pane key="detail" title="Detail">
                    <pre class="rl-json-preview">{{
                      formatJsonPreview(materialDetail ?? selectedMaterial)
                    }}</pre>
                  </a-tab-pane>
                  <a-tab-pane key="chunks" title="Chunks">
                    <pre class="rl-json-preview">{{ formatJsonPreview(materialChunks) }}</pre>
                  </a-tab-pane>
                  <a-tab-pane key="extractions" title="Extractions">
                    <pre class="rl-json-preview">{{ formatJsonPreview(materialExtractions) }}</pre>
                  </a-tab-pane>
                  <a-tab-pane key="artifacts" title="Artifacts">
                    <pre class="rl-json-preview">{{ formatJsonPreview(materialArtifacts) }}</pre>
                  </a-tab-pane>
                  <a-tab-pane key="drafts" title="Draft History">
                    <pre class="rl-json-preview">{{ formatJsonPreview(draftHistory) }}</pre>
                  </a-tab-pane>
                  <a-tab-pane key="preview" title="Source Draft Preview">
                    <pre class="rl-json-preview">{{ formatJsonPreview(sourceDraftPreview) }}</pre>
                  </a-tab-pane>
                </a-tabs>
              </a-form>
            </article>
          </div>
        </section>

        <section class="workspace-materials-bottom-grid">
          <article class="rl-section-card workspace-builds-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="构图结果 / 已生成图谱" :help="buildResultsHelp">
                    <icon-relation />
                  </SectionCardTitle>
                </h3>
              </div>
              <a-tag color="gold">{{ builds?.builds.length ?? 0 }} 次</a-tag>
            </header>
            <div class="rl-section-card__body workspace-table-card workspace-table-card--fill">
              <div
                class="workspace-table-wrap workspace-table-wrap--builds workspace-table-wrap--fill"
              >
                <table class="workspace-table">
                  <thead>
                    <tr>
                      <th>图谱名</th>
                      <th>来源素材数</th>
                      <th>节点/边</th>
                      <th>状态</th>
                      <th>更新时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody v-if="builds?.builds.length ?? 0">
                    <tr
                      v-for="build in builds?.builds ?? []"
                      :key="build.run_id"
                      :class="{
                        'workspace-table__row--active': build.run_id === buildDetail?.build.run_id,
                      }"
                      @click="loadBuildDetail(build.run_id)"
                    >
                      <td>
                        <strong>{{ build.run_id }}</strong>
                      </td>
                      <td>{{ build.source_count }}</td>
                      <td>{{ build.node_count }} / {{ build.edge_count }}</td>
                      <td>{{ build.status }}</td>
                      <td>{{ formatDateTime(build.created_at) }}</td>
                      <td>
                        <a-button
                          size="mini"
                          type="text"
                          @click.stop="openBuildDetailModal(build.run_id)"
                        >
                          查看详情
                        </a-button>
                      </td>
                    </tr>
                  </tbody>
                  <tbody v-else>
                    <tr class="workspace-table__row--empty">
                      <td colspan="6">
                        <div class="workspace-table__empty-state">
                          <a-empty>暂无构图结果</a-empty>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </article>

          <article class="rl-section-card workspace-build-recipe-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="Build Recipe" :help="buildRecipeHelp">
                    <icon-bulb />
                  </SectionCardTitle>
                </h3>
              </div>
              <a-tag color="arcoblue">{{ selectedMaterials.length }} 份已选</a-tag>
            </header>
            <a-form
              id="materials-form-5"
              :model="buildForm"
              layout="vertical"
              class="rl-section-card__body workspace-stack workspace-form"
            >
              <div class="workspace-summary-list workspace-summary-list--two-col">
                <div class="workspace-summary-list__item">
                  <span class="workspace-summary-label">
                    <icon-upload />
                    <span>已选素材</span>
                  </span>
                  <strong>{{ selectedMaterials.length }}</strong>
                </div>
                <div class="workspace-summary-list__item">
                  <span class="workspace-summary-label">
                    <icon-storage />
                    <span>默认图谱</span>
                  </span>
                  <strong>{{ buildDetail?.build.run_id ?? '未选择' }}</strong>
                </div>
              </div>

              <div class="workspace-form-row workspace-form-row--two">
                <a-form-item
                  field="output_name"
                  label="输出图谱名"
                  :label-attrs="{ for: 'material-buildForm-output_name-input' }"
                  class="workspace-form-item"
                >
                  <a-input
                    :input-attrs="{
                      id: 'material-buildForm-output_name-input',
                      'aria-label': '输出图谱名',
                    }"
                    id="material-buildForm-output_name"
                    aria-label="输出图谱名"
                    v-model="buildForm.output_name"
                  />
                </a-form-item>
                <a-form-item
                  field="source_type"
                  label="来源类型"
                  :label-attrs="{ for: 'material-buildForm-source_type-input' }"
                  class="workspace-form-item"
                >
                  <div
                    id="material-buildForm-source_type"
                    v-control-label="'来源类型'"
                    class="workspace-control"
                  >
                    <a-select aria-label="来源类型" v-model="buildForm.source_type">
                      <a-option value="structured_records">structured_records</a-option>
                      <a-option value="manual_table">manual_table</a-option>
                    </a-select>
                  </div>
                </a-form-item>
              </div>

              <div class="rl-form-actions rl-form-actions--dual">
                <a-select v-model="buildForm.capability" aria-label="构图执行契约" style="width: 190px">
                  <a-option value="legacy">现有画像契约</a-option>
                  <a-option value="visual-region-v2">统一推理 · 图像 ROI</a-option>
                  <a-option value="process-window-v2">统一推理 · 过程窗口</a-option>
                  <a-option value="spatial-grid-v2">统一推理 · 空间网格</a-option>
                </a-select>
                <a-button type="primary" @click="handleBuild">生成构图</a-button>
                <a-button :disabled="!canExportBuild" @click="handleExportBuild">导出本地</a-button>
                <a-select v-model="activationDataset" style="width: 105px" aria-label="工作图场景"><a-option value="mvtec">MVTec</a-option><a-option value="wafer">Wafer</a-option><a-option value="tep">TEP</a-option></a-select>
                <a-button :disabled="!buildDetail || preferences.dataSourceMode !== 'backend'"
                  :loading="activationLoading" @click="handleActivateBuild">装载工作图</a-button>
                <a-button
                  :disabled="!buildDetail"
                  @click="
                    buildDetail?.build.run_id && openBuildDetailModal(buildDetail.build.run_id)
                  "
                >
                  构图详情
                </a-button>
              </div>

              <pre class="rl-json-preview">{{ formatJsonPreview(buildSourcesPreview) }}</pre>
            </a-form>
          </article>
        </section>
      </div>
    </section>
  </div>

  <a-modal
    v-model:visible="buildDetailModalVisible"
    title="构图详情"
    :footer="false"
    width="960px"
    class="workspace-build-detail-modal"
  >
    <div class="workspace-stack workspace-stack--tight">
      <div class="workspace-summary-list workspace-summary-list--two-col">
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">
            <icon-storage />
            <span>Build</span>
          </span>
          <strong>{{ buildDetail?.build.run_id ?? '--' }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">
            <icon-info-circle />
            <span>Status</span>
          </span>
          <strong>{{ buildDetail?.build.status ?? '--' }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">
            <icon-upload />
            <span>Sources</span>
          </span>
          <strong>{{ buildDetail?.build.source_count ?? 0 }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">
            <icon-relation />
            <span>Nodes / Edges</span>
          </span>
          <strong>
            {{ buildDetail?.build.node_count ?? 0 }} / {{ buildDetail?.build.edge_count ?? 0 }}
          </strong>
        </div>
      </div>

      <div class="workspace-claim-note workspace-claim-note--compact">
        <span class="workspace-summary-label">
          <icon-info-circle />
          <span>Claim boundary</span>
        </span>
        <strong>{{ materialClaimBoundaryCopy }}</strong>
      </div>

      <a-alert
        v-if="buildDetailModalError"
        type="warning"
        :show-icon="false"
        :title="buildDetailModalError"
      />

      <div v-if="buildDetailModalLoading" class="workspace-build-detail-modal__loading">
        <a-spin />
      </div>

      <a-tabs v-else v-model:active-key="buildDetailModalTab">
        <a-tab-pane key="manifest" title="Manifest">
          <div class="workspace-stack workspace-stack--tight">
            <div class="workspace-summary-list workspace-summary-list--two-col">
              <div class="workspace-summary-list__item">
                <span class="workspace-summary-label">
                  <icon-upload />
                  <span>Source IDs</span>
                </span>
                <strong>{{ buildDetail?.build.source_ids?.join(', ') || '--' }}</strong>
              </div>
              <div class="workspace-summary-list__item">
                <span class="workspace-summary-label">
                  <icon-relation />
                  <span>Manifest Path</span>
                </span>
                <strong>{{ buildDetail?.build.manifest_path ?? '--' }}</strong>
              </div>
            </div>
            <div class="workspace-feedback-pane__footer">
              <a-button size="small" @click="openBuildProvenance">
                Inspect Build Provenance
              </a-button>
            </div>
            <pre class="rl-json-preview">{{ formatJsonPreview(buildDetail?.manifest ?? {}) }}</pre>
          </div>
        </a-tab-pane>

        <a-tab-pane key="qa" title="QA / Summary">
          <div class="workspace-stack workspace-stack--tight">
            <pre class="rl-json-preview">{{ formatJsonPreview(buildDetail?.summary ?? {}) }}</pre>
            <pre class="rl-json-preview">{{
              formatJsonPreview(buildValidation?.qa_report ?? { note: '暂无 QA 详情（mock 占位）' })
            }}</pre>
          </div>
        </a-tab-pane>

        <a-tab-pane key="queue" title="Review Queue">
          <div
            v-if="buildReviewQueue?.edges.length"
            class="workspace-scroll-list workspace-scroll-list--fill workspace-build-review-queue"
          >
            <div
              class="workspace-build-review-edge"
              v-for="edge in buildReviewQueue.edges"
              :key="edge.target_key"
            >
              <div class="workspace-build-review-edge__head">
                <strong>{{ edge.head }} —{{ edge.relation }}→ {{ edge.tail }}</strong>
                <span>{{ edge.review_status }}</span>
              </div>
              <div class="workspace-build-review-edge__meta">
                <span>{{ edge.source }}</span>
                <span>confidence {{ edge.confidence.toFixed(2) }}</span>
              </div>
              <p>{{ edge.evidence || '当前边没有附带 evidence snippet。' }}</p>
              <div class="workspace-build-review-edge__actions">
                <a-button size="mini" type="text" @click="openBuildReviewEdgeProvenance(edge)">
                  Provenance
                </a-button>
                <a-button
                  size="mini"
                  type="primary"
                  :loading="buildReviewActionTargetKey === edge.target_key"
                  @click="handleBuildReviewAction(edge.target_key, 'accept')"
                >
                  接受
                </a-button>
                <a-button
                  size="mini"
                  status="danger"
                  :loading="buildReviewActionTargetKey === edge.target_key"
                  @click="handleBuildReviewAction(edge.target_key, 'reject')"
                >
                  拒绝
                </a-button>
              </div>
            </div>
          </div>
          <a-empty v-else>当前构图暂无待审阅边</a-empty>
        </a-tab-pane>
      </a-tabs>
    </div>
  </a-modal>

  <a-drawer
    v-model:visible="materialSourceDrawerVisible"
    width="min(520px, 100vw)"
    :body-style="{ padding: '12px' }"
    role="dialog"
    aria-modal="true"
    aria-label="上传 / 注册素材"
    :aria-hidden="!materialSourceDrawerVisible"
    @open="materialSourcePanelRef?.focus()"
    @close="materialSourceTriggerRef?.$el.focus()"
    @keydown="handleMaterialSourceKeydown"
  >
    <template #title>
      <SectionCardTitle title="上传 / 注册素材" :help="uploadSourceHelp">
        <icon-upload />
      </SectionCardTitle>
    </template>
    <div
      id="material-source-drawer"
      ref="materialSourcePanelRef"
      tabindex="-1"
      class="workspace-material-source-drawer workspace-stack"
    >
      <a-alert v-if="errorMessage" type="error" :title="errorMessage" />
      <a-alert v-if="actionMessage" type="success" :title="actionMessage" />
      <a-tabs v-model:active-key="materialSourceTab" lazy-load>
        <a-tab-pane key="upload" title="本地上传">
          <a-form
            id="materials-form-3"
            :model="uploadForm"
            :disabled="materialMutationLoading"
            layout="vertical"
            class="workspace-form"
          >
            <a-form-item
              label="本地文件"
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
                  multiple
                  :disabled="materialMutationLoading"
                  @change="handleUploadFileChange"
                />
                <div class="rl-file-dropzone__content rl-file-dropzone__content--fill">
                  <div class="rl-file-dropzone__copy">
                    <strong>
                      {{ uploadForm.files.length > 1 ? `已选择 ${uploadForm.files.length} 个文件` : uploadForm.files[0]?.name ?? '拖动素材文件到这里，或点击选择文件' }}
                    </strong>
                  </div>
                  <a-button aria-label="选择素材文件" size="small" @click="openUploadPicker">
                    选择文件
                  </a-button>
                </div>
              </div>
            </a-form-item>

            <div class="workspace-form-row workspace-form-row--two">
              <a-form-item
                field="title"
                label="标题"
                :label-attrs="{ for: 'material-uploadForm-title-input' }"
                class="workspace-form-item"
              >
                <a-input
                  :input-attrs="{
                    id: 'material-uploadForm-title-input',
                    'aria-label': '标题',
                  }"
                  id="material-uploadForm-title"
                  aria-label="标题"
                  v-model="uploadForm.title"
                  :disabled="materialMutationLoading || uploadForm.files.length > 1"
                />
              </a-form-item>
              <a-form-item
                field="materialId"
                label="素材 ID"
                :label-attrs="{ for: 'material-uploadForm-materialId-input' }"
                class="workspace-form-item"
              >
                <a-input
                  :input-attrs="{
                    id: 'material-uploadForm-materialId-input',
                    'aria-label': '素材 ID',
                  }"
                  id="material-uploadForm-materialId"
                  aria-label="素材 ID"
                  v-model="uploadForm.materialId"
                  :disabled="materialMutationLoading || uploadForm.files.length > 1"
                />
              </a-form-item>
            </div>
            <div class="workspace-form-row workspace-form-row--two">
              <a-form-item
                field="scenario"
                label="场景"
                :label-attrs="{ for: 'material-uploadForm-scenario-input' }"
                class="workspace-form-item"
              >
                <a-input
                  :input-attrs="{
                    id: 'material-uploadForm-scenario-input',
                    'aria-label': '场景',
                  }"
                  id="material-uploadForm-scenario"
                  aria-label="场景"
                  v-model="uploadForm.scenario"
                />
              </a-form-item>
              <a-form-item
                field="sourceType"
                label="类型"
                :label-attrs="{ for: 'material-uploadForm-sourceType-input' }"
                class="workspace-form-item"
              >
                <div
                  id="material-uploadForm-sourceType"
                  v-control-label="'类型'"
                  class="workspace-control"
                >
                  <a-select aria-label="类型" v-model="uploadForm.sourceType" :disabled="materialMutationLoading || uploadForm.files.length > 1">
                    <a-option value="text">text</a-option>
                    <a-option value="markdown">markdown</a-option>
                    <a-option value="webpage">webpage</a-option>
                    <a-option value="pdf">pdf</a-option>
                    <a-option value="csv">csv</a-option>
                    <a-option value="json">json</a-option>
                    <a-option value="jsonl">jsonl</a-option>
                    <a-option value="other">other</a-option>
                  </a-select>
                </div>
              </a-form-item>
            </div>
            <a-form-item
              field="notes"
              label="备注"
              :label-attrs="{ for: 'material-uploadForm-notes-input' }"
              class="workspace-form-item"
            >
              <a-textarea
                :textarea-attrs="{
                  id: 'material-uploadForm-notes-input',
                  'aria-label': '备注',
                }"
                id="material-uploadForm-notes"
                aria-label="备注"
                v-model="uploadForm.notes"
                :auto-size="{ minRows: 2, maxRows: 4 }"
              />
            </a-form-item>
            <div class="rl-form-actions">
              <a-button
                type="primary"
                :loading="materialMutationLoading"
                @click="handleMaterialUpload"
              >
                上传素材
              </a-button>
            </div>
          </a-form>
        </a-tab-pane>
        <a-tab-pane key="url" title="URL 注册">
          <a-form
            id="materials-form-4"
            :model="registerUrlForm"
            layout="vertical"
            class="workspace-form"
          >
            <a-form-item
              field="url"
              label="URL"
              :label-attrs="{ for: 'material-registerUrlForm-url-input' }"
              class="workspace-form-item"
            >
              <a-input
                :input-attrs="{
                  id: 'material-registerUrlForm-url-input',
                  'aria-label': 'URL',
                }"
                id="material-registerUrlForm-url"
                aria-label="URL"
                v-model="registerUrlForm.url"
                placeholder="https://example.com/doc"
              />
            </a-form-item>
            <div class="workspace-form-row workspace-form-row--two">
              <a-form-item
                field="title"
                label="标题"
                :label-attrs="{ for: 'material-registerUrlForm-title-input' }"
                class="workspace-form-item"
              >
                <a-input
                  :input-attrs="{
                    id: 'material-registerUrlForm-title-input',
                    'aria-label': '标题',
                  }"
                  id="material-registerUrlForm-title"
                  aria-label="标题"
                  v-model="registerUrlForm.title"
                />
              </a-form-item>
              <a-form-item
                field="materialId"
                label="素材 ID"
                :label-attrs="{ for: 'material-registerUrlForm-materialId-input' }"
                class="workspace-form-item"
              >
                <a-input
                  :input-attrs="{
                    id: 'material-registerUrlForm-materialId-input',
                    'aria-label': '素材 ID',
                  }"
                  id="material-registerUrlForm-materialId"
                  aria-label="素材 ID"
                  v-model="registerUrlForm.materialId"
                />
              </a-form-item>
            </div>
            <div class="workspace-form-row workspace-form-row--two">
              <a-form-item
                field="scenario"
                label="场景"
                :label-attrs="{ for: 'material-registerUrlForm-scenario-input' }"
                class="workspace-form-item"
              >
                <a-input
                  :input-attrs="{
                    id: 'material-registerUrlForm-scenario-input',
                    'aria-label': '场景',
                  }"
                  id="material-registerUrlForm-scenario"
                  aria-label="场景"
                  v-model="registerUrlForm.scenario"
                />
              </a-form-item>
              <a-form-item
                field="sourceType"
                label="类型"
                :label-attrs="{ for: 'material-registerUrlForm-sourceType-input' }"
                class="workspace-form-item"
              >
                <div
                  id="material-registerUrlForm-sourceType"
                  v-control-label="'类型'"
                  class="workspace-control"
                >
                  <a-select aria-label="类型" v-model="registerUrlForm.sourceType">
                    <a-option value="webpage">webpage</a-option>
                    <a-option value="pdf">pdf</a-option>
                    <a-option value="other">other</a-option>
                  </a-select>
                </div>
              </a-form-item>
            </div>
            <a-form-item
              field="notes"
              label="备注"
              :label-attrs="{ for: 'material-registerUrlForm-notes-input' }"
              class="workspace-form-item"
            >
              <a-textarea
                :textarea-attrs="{
                  id: 'material-registerUrlForm-notes-input',
                  'aria-label': '备注',
                }"
                id="material-registerUrlForm-notes"
                aria-label="备注"
                v-model="registerUrlForm.notes"
                :auto-size="{ minRows: 2, maxRows: 4 }"
              />
            </a-form-item>
            <div class="rl-form-actions">
              <a-button :loading="materialMutationLoading" @click="handleRegisterUrl">
                注册 URL 素材
              </a-button>
            </div>
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </div>
    <template #footer>
      <a-button @click="materialSourceDrawerVisible = false">收起</a-button>
    </template>
  </a-drawer>

  <ProvenanceInspectorDrawer
    v-model:visible="provenanceInspectorVisible"
    :state="provenanceInspectorState"
  />
</template>
