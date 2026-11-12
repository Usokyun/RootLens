<script setup lang="ts">
import { IconUpload } from "@arco-design/web-vue/es/icon";
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { useRouter } from "vue-router";
import { getLocalSessionMeta } from "@/services/rootlens-data";
import { constructionGraphLocation } from "@/services/construction-graph";

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
import { readable, shortDate } from "@/services/presentation";
import SectionCardTitle from "@/components/layout/SectionCardTitle.vue";
import ProvenanceInspectorDrawer from "@/components/provenance/ProvenanceInspectorDrawer.vue";
import { useAppPreferences } from "@/services/app-preferences";
import {
  extractFilesFromDataTransfer,
  markDragEventHandled,
} from "@/services/file-drop";
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
import { useWorkbenchState } from "@/services/workbench-state";

interface RootLensKGBuildExportV1 {
  schema_version: "rootlens-kg-build-export.v1";
  exported_at: string;
  source_mode: "mock" | "backend";
  build: KGConstructionBuildDetail["build"];
  summary: KGConstructionBuildDetail["summary"];
  manifest: KGConstructionBuildDetail["manifest"];
  claim_boundary: string;
}

const router = useRouter();
const { preferences } = useAppPreferences();
const { state: workbenchState, updateState } = useWorkbenchState();

const loading = ref(false);
const buildLoading = ref(false);
const knowledgeTab = ref("library");
const materialFiltersVisible = ref(false);
const buildDrawerVisible = ref(false);
const errorMessage = ref("");
const actionMessage = ref("");

const materials = ref<KGMaterialRecord[]>([]);
const builds = ref<KGConstructionBuildListResponse | null>(null);
const buildDetail = ref<KGConstructionBuildDetail | null>(null);
const buildSourcesPreview = ref<KGMaterialBuildSourcesResponse | null>(null);
const canMutateMaterials = computed(
  () =>
    preferences.value.dataSourceMode === "backend" &&
    getLocalSessionMeta()?.source !== "import",
);
const reviewOffset = ref(0),
  reviewKey = ref<string | null>(null),
  buildReviewNote = ref("");
const selectedBuildEdge = computed(
  () =>
    buildReviewQueue.value?.edges.find(
      (e) => e.target_key === reviewKey.value,
    ) ??
    buildReviewQueue.value?.edges[0] ??
    null,
);
function entityLabel(id: string) {
  return readable(
    kgStudio.value?.graph_nodes.find((n) => n.node_id === id)?.label ?? id,
  );
}
function sourceLabel(id: string) {
  return kgStudio.value?.sources.find((s) => s.source_id === id)?.title ?? id;
}
function selectBuildEdge(key: string) {
  reviewKey.value = key;
  buildReviewNote.value = "";
}
async function reviewPage(page: number) {
  reviewOffset.value = (page - 1) * 12;
  if (buildDetail.value)
    await loadBuildDetailModalState(buildDetail.value.build.run_id);
}
const kgStudio = ref<KGStudioPayload | null>(null);
const draftHistory = ref<KGDraftRecord[]>([]);

const selectedMaterialId = ref<string | null>(null);
const selectedMaterialIds = ref<string[]>([]);
const selectedMaterialTab = ref<
  "detail" | "chunks" | "extractions" | "artifacts" | "drafts" | "preview"
>("chunks");
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
const buildDetailModalTab = ref<"manifest" | "qa" | "queue">("queue");
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
});

const uploadInputRef = ref<HTMLInputElement | null>(null);
const uploadDragActive = ref(false);
const uploadDragDepth = ref(0);

const selectedBuildRunId = computed(
  () => workbenchState.value.selectedConstructionRunId,
);

const selectedMaterial = computed(() => {
  return (
    filteredMaterials.value.find(
      (item) => item.material_id === selectedMaterialId.value,
    ) ??
    filteredMaterials.value[0] ??
    null
  );
});

const selectedMaterials = computed(() =>
  materials.value.filter((item) =>
    selectedMaterialIds.value.includes(item.material_id),
  ),
);

const materialClaimBoundaryCopy = computed(() =>
  formatClaimBoundaryCopy(
    materialDetail.value?.claim_boundary ??
      buildDetail.value?.build.claim_boundary ??
      kgStudio.value?.claim_boundary,
  ),
);

const canExportBuild = computed(() => !!buildDetail.value);

const uploadSourceHelp = [
  "优先走 material library，再进入 extract / build-sources。",
  "将远程来源先登记到 material library，再单独执行抽取。",
];

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
      return (
        ((Number.isNaN(leftTime) ? 0 : leftTime) -
          (Number.isNaN(rightTime) ? 0 : rightTime)) *
        direction
      );
    }

    if (filters.sortField === "title") {
      return left.title.localeCompare(right.title) * direction;
    }

    return left.source_type.localeCompare(right.source_type) * direction;
  });
});

const provenanceSourceMaterials = computed<ProvenanceSourceMaterial[]>(() => [
  ...materials.value.map((item) => ({
    sourceId: item.source_id ?? item.material_id,
    title: item.title,
    path: item.url ?? item.path ?? item.uri ?? null,
    sourceType: item.source_type,
    note: item.notes ?? "",
  })),
  ...(kgStudio.value?.sources ?? []).map((item) => ({
    sourceId: item.source_id,
    title: item.title,
    path: item.path_or_url,
    sourceType: item.source_type,
    note: item.notes ?? "",
  })),
]);

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
    selectedMaterialIds.value = [
      ...new Set([...selectedMaterialIds.value, materialId]),
    ];
    return;
  }

  selectedMaterialIds.value = selectedMaterialIds.value.filter(
    (item) => item !== materialId,
  );
}

let materialVersion = 0,
  workspaceVersion = 0,
  buildVersion = 0,
  modalVersion = 0;
async function loadBuildDetail(runId: string) {
  const v = ++buildVersion;
  try {
    const result = await getRootLensService().getKGConstructionBuild(runId);
    if (v !== buildVersion) return;
    buildDetail.value = result;
    updateState({ selectedConstructionRunId: runId });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
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
  const v = ++modalVersion;
  buildDetailModalLoading.value = true;
  buildDetailModalError.value = "";

  try {
    const [detailResult, validationResult, reviewQueueResult] =
      await Promise.allSettled([
        getRootLensService().getKGConstructionBuild(runId),
        getRootLensService().validateKGConstructionBuild(runId),
        getRootLensService().getKGConstructionReviewQueue(runId, {
          offset: reviewOffset.value,
          limit: 12,
        }),
      ]);

    if (v !== modalVersion) return;
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
    if (v !== modalVersion) return;
    buildDetailModalError.value =
      error instanceof Error ? error.message : String(error);
  } finally {
    if (v === modalVersion) buildDetailModalLoading.value = false;
  }
}

async function openBuildDetailModal(runId: string) {
  reviewOffset.value = 0;
  reviewKey.value = null;
  buildReviewNote.value = "";
  buildDetailModalVisible.value = true;
  buildDetailModalTab.value = "queue";
  await loadBuildDetailModalState(runId);
}

async function handleBuildReviewAction(
  targetKey: string,
  action: "accept" | "reject",
) {
  if (!buildDetail.value || buildReviewActionTargetKey.value) return;
  if (!buildReviewNote.value.trim()) {
    buildDetailModalError.value = "请填写审阅理由。";
    return;
  }
  const id = buildDetail.value.build.run_id,
    context = modalVersion;
  buildReviewActionTargetKey.value = targetKey;
  buildDetailModalError.value = "";
  try {
    await getRootLensService().reviewKGConstructionEdge(id, {
      action,
      target_key: targetKey,
      reviewer: "rootlens-frontend",
      note: buildReviewNote.value.trim(),
    });
    if (context !== modalVersion) return;
    actionMessage.value = `已记录${action === "accept" ? "接受" : "拒绝"}判断；未发布到运行图谱。`;
    buildReviewNote.value = "";
    await loadBuildDetailModalState(id);
  } catch (e) {
    if (context === modalVersion)
      buildDetailModalError.value = e instanceof Error ? e.message : String(e);
  } finally {
    buildReviewActionTargetKey.value = null;
  }
}

async function loadSelectedMaterialState(materialId: string) {
  const v = ++materialVersion;
  materialDetailLoading.value = true;
  sourceDraftPreview.value = null;

  try {
    const [detail, chunks, extractions, artifacts] = await Promise.all([
      getRootLensService().getKGMaterial(materialId),
      getRootLensService().getKGMaterialChunks(materialId),
      getRootLensService().getKGMaterialExtractions(materialId),
      getRootLensService().getKGMaterialArtifacts(materialId),
    ]);
    if (v !== materialVersion) return;
    materialDetail.value = detail.material;
    materialChunks.value = chunks.chunks;
    materialExtractions.value = extractions.runs;
    materialArtifacts.value = artifacts.artifacts;
  } catch (error) {
    if (v !== materialVersion) return;
    materialDetail.value = null;
    materialChunks.value = [];
    materialExtractions.value = [];
    materialArtifacts.value = [];
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    if (v === materialVersion) materialDetailLoading.value = false;
  }
}

async function refreshWorkspace() {
  const v = ++workspaceVersion;
  buildDetailModalVisible.value = false;
  buildDetail.value = null;
  buildReviewQueue.value = null;
  materialDetail.value = null;
  materialChunks.value = [];
  ++materialVersion;
  ++buildVersion;
  ++modalVersion;
  loading.value = true;
  errorMessage.value = "";

  try {
    const [
      materialsResponse,
      buildList,
      kgStudioPayload,
      draftHistoryResponse,
    ] = await Promise.allSettled([
      getRootLensService().listKGMaterials(),
      getRootLensService().listKGConstructionBuilds(),
      getRootLensService().kgStudio(),
      getRootLensService().listKGDrafts({ limit: 50 } as KGDraftListRequest),
    ]);

    if (v !== workspaceVersion) return;
    if (materialsResponse.status === "rejected") throw materialsResponse.reason;
    const materialList = materialsResponse.value;
    const buildResult =
      buildList.status === "fulfilled" ? buildList.value : null;
    materials.value = materialList.materials;
    builds.value = buildResult;
    kgStudio.value =
      kgStudioPayload.status === "fulfilled" ? kgStudioPayload.value : null;
    draftHistory.value =
      draftHistoryResponse.status === "fulfilled"
        ? draftHistoryResponse.value.records
        : [];
    const warnings = [
      buildList.status === "rejected" ? "构图记录暂不可用" : "",
      kgStudioPayload.status === "rejected" ? "图谱服务暂不可用" : "",
      draftHistoryResponse.status === "rejected" ? "草稿历史暂不可用" : "",
    ].filter(Boolean);
    if (warnings.length) errorMessage.value = warnings.join("；");

    selectedMaterialIds.value = selectedMaterialIds.value.filter((materialId) =>
      materialList.materials.some((item) => item.material_id === materialId),
    );

    const nextMaterialId =
      materialList.materials.find(
        (item) => item.material_id === selectedMaterialId.value,
      )?.material_id ??
      materialList.materials[0]?.material_id ??
      null;
    const sameMaterial = selectedMaterialId.value === nextMaterialId;
    selectedMaterialId.value = nextMaterialId;
    if (nextMaterialId && sameMaterial) {
      await loadSelectedMaterialState(nextMaterialId);
    } else if (!nextMaterialId) {
      materialDetail.value = null;
      materialChunks.value = [];
      materialExtractions.value = [];
      materialArtifacts.value = [];
    }

    if (v !== workspaceVersion) return;
    const nextBuildId =
      buildResult?.builds.find(
        (item) => item.run_id === selectedBuildRunId.value,
      )?.run_id ??
      buildResult?.builds[0]?.run_id ??
      null;

    if (nextBuildId) {
      await loadBuildDetail(nextBuildId);
    } else {
      buildDetail.value = null;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    if (v === workspaceVersion) loading.value = false;
  }
}

function handleMaterialSourceKeydown(event: KeyboardEvent) {
  if (event.key !== "Tab" || !materialSourceDrawerVisible.value) return;

  const drawer = materialSourcePanelRef.value?.closest(".arco-drawer");
  const controls = Array.from(
    drawer?.querySelectorAll<HTMLElement>(
      'button, input, textarea, select, a[href], [tabindex]:not([tabindex="-1"])',
    ) ?? [],
  ).filter(
    (control) =>
      control.tabIndex >= 0 &&
      !control.matches(":disabled") &&
      control.getClientRects().length > 0,
  );
  const first = controls[0];
  const last = controls[controls.length - 1];
  if (!first || !last) return;

  const active = document.activeElement;
  if (
    event.shiftKey &&
    (active === first || active === materialSourcePanelRef.value)
  ) {
    event.preventDefault();
    last.focus();
  } else if (
    !event.shiftKey &&
    (active === last || active === materialSourcePanelRef.value)
  ) {
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
      actionMessage.value =
        files.length === 1
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
      ]
        .filter(Boolean)
        .join("；");
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
    actionMessage.value = `已完成 extract：${response.material.material_id}`;
    await refreshWorkspace();
    selectedMaterialId.value = response.material.material_id;
    await loadSelectedMaterialState(response.material.material_id);
    selectedMaterialTab.value = "extractions";
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
    sourceDraftPreview.value = await getRootLensService().generateKGSourceDraft(
      {
        source_id:
          selectedMaterial.value.source_id ??
          selectedMaterial.value.material_id,
        source_text: materialChunks.value
          .slice(0, 5)
          .map((chunk) => chunk.text_content)
          .join("\n"),
        provider: "heuristic",
        default_scenario:
          sourceDraftForm.defaultScenario || selectedMaterial.value.scenario,
        confidence: sourceDraftForm.confidence,
      },
    );
    selectedMaterialTab.value = "preview";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    sourceDraftLoading.value = false;
  }
}

async function handleBuild() {
  if (buildLoading.value) return;
  if (!selectedMaterials.value.length) {
    actionMessage.value = "请先勾选至少一份已抽取素材。";
    return;
  }

  actionMessage.value = "";
  errorMessage.value = "";

  try {
    buildLoading.value = true;
    const buildSourcesResponse =
      await getRootLensService().buildKGMaterialSources({
        material_ids: selectedMaterials.value.map((item) => item.material_id),
        output_name: buildForm.output_name,
        overwrite: false,
        source_type: buildForm.source_type,
      });
    buildSourcesPreview.value = buildSourcesResponse;
    const response = await getRootLensService().buildKGConstruction(
      buildSourcesResponse.construction_request,
    );
    actionMessage.value = "图谱已生成，可核验来源与待审关系。";
    buildDrawerVisible.value = false;
    knowledgeTab.value = "builds";
    await refreshWorkspace();
    await loadBuildDetail(response.run_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error);
  } finally {
    buildLoading.value = false;
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
  actionMessage.value = "构图记录已导出。";
}

watch(
  [() => preferences.value.dataSourceMode, () => preferences.value.apiBaseUrl],
  () => {
    void refreshWorkspace();
  },
);

watch(selectedMaterialId, (materialId) => {
  if (!materialId) {
    ++materialVersion;
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
onBeforeUnmount(() => {
  ++materialVersion;
  ++workspaceVersion;
  ++buildVersion;
  ++modalVersion;
});
</script>

<template>
  <div class="demo-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">03 / KNOWLEDGE</span>
        <h2>让知识有据可查</h2>
      </div>
      <a-space
        ><a-button @click="router.push({ name: 'graphs' })"
          >返回关联分析</a-button
        ><a-button
          ref="materialSourceTriggerRef"
          :disabled="!canMutateMaterials"
          type="primary"
          @click="materialSourceDrawerVisible = true"
          >添加来源材料</a-button
        ></a-space
      >
    </header>
    <a-alert
      v-if="errorMessage"
      type="error"
      :title="errorMessage"
      class="page-alert"
    /><a-alert
      v-if="actionMessage"
      type="success"
      :title="actionMessage"
      class="page-alert"
      closable
    />
    <p v-if="!canMutateMaterials" class="subtle">
      已打包的来源说明与构图记录；上传、抽取和真实构图请切换 Backend。
    </p>
    <a-tabs v-model:active-key="knowledgeTab" class="knowledge-tabs">
      <a-tab-pane key="library" :title="`来源材料 · ${materials.length}`">
        <div class="materials-workspace">
          <section class="surface material-library">
            <div class="surface-heading">
              <a-input-search
                v-model="filters.search"
                aria-label="搜索来源材料"
                placeholder="查找文档或知识来源"
                allow-clear
              /><a-button @click="materialFiltersVisible = true">筛选</a-button>
            </div>
            <div
              v-for="material in filteredMaterials"
              :key="material.material_id"
              class="material-row"
              :class="{
                'is-active':
                  material.material_id === selectedMaterial?.material_id,
              }"
            >
              <a-checkbox
                :model-value="
                  selectedMaterialIds.includes(material.material_id)
                "
                :aria-label="`选择素材 ${material.title}`"
                @change="
                  toggleMaterialSelection(material.material_id, Boolean($event))
                "
              />
              <button
                class="material-row__select"
                @click="selectedMaterialId = material.material_id"
              >
                <strong>{{ material.title }}</strong
                ><span
                  >{{ readable(material.scenario) }} ·
                  {{ readable(material.source_type)
                  }}<template v-if="material.updated_at || material.created_at">
                    ·
                    {{
                      shortDate(material.updated_at ?? material.created_at)
                    }}</template
                  ></span
                >
              </button>
              <a-tag
                :color="
                  material.extraction_status === 'extracted' ? 'green' : 'gray'
                "
                >{{ formatMaterialStatus(material) }}</a-tag
              >
            </div>
            <a-empty
              v-if="!filteredMaterials.length"
              description="暂无匹配来源材料"
            />
            <div class="material-build-action">
              <span class="subtle">已选 {{ selectedMaterials.length }} 份</span
              ><a-button
                type="primary"
                :disabled="!selectedMaterials.length || !canMutateMaterials"
                @click="buildDrawerVisible = true"
                >用所选材料构图</a-button
              >
            </div>
          </section>
          <section class="surface material-reader">
            <template v-if="selectedMaterial">
              <div class="surface-heading">
                <h3>{{ selectedMaterial.title }}</h3>
                <a-button
                  :loading="materialExtractLoading"
                  :disabled="!canMutateMaterials"
                  @click="handleMaterialExtract"
                  >抽取知识</a-button
                >
              </div>
              <div class="material-origin">
                <span class="eyebrow">原始出处</span>
                <p class="break-anywhere">
                  {{ formatMaterialLocation(selectedMaterial) }}
                </p>
                <span v-if="selectedMaterial.notes" class="subtle">{{
                  selectedMaterial.notes
                }}</span>
              </div>
              <a-spin :loading="materialDetailLoading" class="block-spin">
                <a-tabs
                  v-model:active-key="selectedMaterialTab"
                  class="material-reader__tabs"
                >
                  <a-tab-pane key="chunks" title="原文片段"
                    ><div class="material-chunks">
                      <article
                        v-for="chunk in materialChunks"
                        :key="chunk.chunk_id"
                        class="source-excerpt"
                      >
                        <span class="eyebrow">{{
                          chunk.source_locator ||
                          `片段 ${chunk.chunk_index + 1}`
                        }}</span>
                        <p>{{ chunk.text_content }}</p>
                      </article>
                      <a-empty
                        v-if="!materialChunks.length"
                        description="尚未提供可定位原文；可执行抽取生成片段"
                      /></div
                  ></a-tab-pane>
                  <a-tab-pane key="extractions" title="抽取记录"
                    ><div class="material-chunks">
                      <div
                        v-for="item in materialExtractions"
                        :key="item.extraction_run_id"
                        class="review-entry"
                      >
                        <strong
                          >{{ readable(item.status) }} ·
                          {{ item.record_count ?? 0 }} 条记录</strong
                        >
                        <p class="subtle">
                          {{ shortDate(item.completed_at ?? item.started_at) }}
                          · {{ item.provider ?? "未记录提取器" }}
                        </p>
                        <p v-if="item.error_message">
                          {{ item.error_message }}
                        </p>
                      </div>
                      <a-empty
                        v-if="!materialExtractions.length"
                        description="暂无抽取记录"
                      /></div
                  ></a-tab-pane>
                  <a-tab-pane key="preview" title="关系草稿"
                    ><div class="material-chunks">
                      <a-button
                        :disabled="
                          !materialChunks.length || !canMutateMaterials
                        "
                        :loading="sourceDraftLoading"
                        @click="handleGenerateSourceDraftPreview"
                        >从原文生成候选预览</a-button
                      >
                      <div
                        v-for="(
                          item, index
                        ) in sourceDraftPreview?.candidate_edges ?? []"
                        :key="index"
                        class="source-excerpt"
                      >
                        <strong
                          >{{ item.head }} → {{ readable(item.relation) }} →
                          {{ item.tail }}</strong
                        >
                        <p>{{ item.evidence }}</p>
                        <span class="subtle">{{ item.source }}</span>
                      </div>
                      <p class="subtle">仅预览待审知识，不自动写入运行图谱。</p>
                    </div></a-tab-pane
                  >
                  <a-tab-pane key="detail" title="技术详情"
                    ><div class="material-chunks">
                      <a-collapse
                        ><a-collapse-item header="材料元数据" item-key="detail">
                          <pre class="raw-json">{{
                            formatJsonPreview(
                              materialDetail ?? selectedMaterial,
                            )
                          }}</pre></a-collapse-item
                        ><a-collapse-item
                          header="抽取产物"
                          item-key="artifacts"
                        >
                          <pre class="raw-json">{{
                            formatJsonPreview(materialArtifacts)
                          }}</pre>
                        </a-collapse-item></a-collapse
                      >
                    </div></a-tab-pane
                  >
                </a-tabs>
              </a-spin> </template
            ><a-empty v-else description="选择来源材料查看依据" />
          </section>
        </div>
      </a-tab-pane>
      <a-tab-pane
        key="builds"
        :title="`构图与审阅 · ${builds?.builds.length ?? 0}`"
      >
        <section class="surface build-library">
          <div class="surface-heading">
            <h3>已生成图谱</h3>
            <a-button :loading="loading" @click="refreshWorkspace"
              >刷新</a-button
            >
          </div>
          <div
            v-for="(build, index) in builds?.builds ?? []"
            :key="build.run_id"
            class="build-row"
          >
            <div>
              <strong>知识图谱 {{ String(index + 1).padStart(2, "0") }}</strong>
              <p class="subtle">
                {{ shortDate(build.created_at) }} ·
                {{ build.source_count }} 类来源 · {{ build.node_count }} 个节点
                / {{ build.edge_count }} 个关系
              </p>
            </div>
            <a-tag>{{ readable(build.status) }}</a-tag
            ><a-space
              ><a-button @click="openBuildDetailModal(build.run_id)"
                >来源与审阅</a-button
              ><a-button
                type="primary"
                :disabled="!canMutateMaterials"
                @click="router.push(constructionGraphLocation(build.run_id))"
                >查看图谱</a-button
              ></a-space
            >
          </div>
          <a-empty v-if="!builds?.builds.length" description="尚无构图记录" />
        </section>
      </a-tab-pane>
    </a-tabs>
    <a-drawer
      v-model:visible="materialFiltersVisible"
      title="筛选来源材料"
      :width="420"
      :footer="false"
      ><a-form
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
            :input-attrs="{
              id: 'material-filter-search-input',
              'aria-label': '搜索',
            }"
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
          <div
            id="material-filter-type"
            v-control-label="'类型'"
            class="workspace-control"
          >
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
      </a-form></a-drawer
    >
    <a-drawer
      v-model:visible="buildDrawerVisible"
      title="从来源材料构建图谱"
      :width="460"
      :footer="false"
    >
      <p class="subtle">
        {{ selectedMaterials.map((m) => m.title).join("、") }}
      </p>
      <a-form :model="buildForm" layout="vertical"
        ><a-form-item label="图谱名称"
          ><a-input
            v-model="buildForm.output_name"
            aria-label="图谱名称" /></a-form-item
        ><a-form-item label="来源格式"
          ><a-select v-model="buildForm.source_type" aria-label="来源格式"
            ><a-option value="structured_records">结构化抽取记录</a-option
            ><a-option value="manual_table">人工整理表格</a-option></a-select
          ></a-form-item
        ><a-button
          type="primary"
          :loading="buildLoading"
          long
          @click="handleBuild"
          >生成待审图谱</a-button
        ></a-form
      >
      <p class="subtle">生成图谱快照，不自动发布或替换当前运行图谱。</p>
      <a-collapse v-if="buildSourcesPreview"
        ><a-collapse-item header="构图请求详情" item-key="request">
          <pre class="raw-json">{{
            formatJsonPreview(buildSourcesPreview)
          }}</pre>
        </a-collapse-item></a-collapse
      >
    </a-drawer>
  </div>
  <a-modal
    v-model:visible="buildDetailModalVisible"
    title="构图来源与审阅"
    :footer="false"
    width="min(960px,94vw)"
  >
    <a-spin :loading="buildDetailModalLoading" class="block-spin"
      ><a-alert
        v-if="buildDetailModalError"
        type="warning"
        :title="buildDetailModalError"
      />
      <div class="evidence-facts">
        <div>
          <span>来源类别</span
          ><strong>{{ buildDetail?.build.source_count ?? 0 }} 类</strong>
        </div>
        <div>
          <span>图谱规模</span
          ><strong
            >{{ buildDetail?.build.node_count ?? 0 }} 节点 /
            {{ buildDetail?.build.edge_count ?? 0 }} 关系</strong
          >
        </div>
        <div>
          <span>状态</span
          ><strong>{{ readable(buildDetail?.build.status) }}</strong>
        </div>
      </div>
      <a-tabs v-model:active-key="buildDetailModalTab"
        ><a-tab-pane key="queue" title="待审关系">
          <div
            v-if="buildReviewQueue?.edges.length"
            class="build-review-workspace"
          >
            <div class="build-review-list">
              <button
                v-for="edge in buildReviewQueue.edges"
                :key="edge.target_key"
                class="build-review-item"
                :class="{
                  'is-active':
                    edge.target_key === selectedBuildEdge?.target_key,
                }"
                :aria-pressed="
                  edge.target_key === selectedBuildEdge?.target_key
                "
                @click="selectBuildEdge(edge.target_key)"
              >
                <strong>{{ entityLabel(edge.head) }}</strong
                ><span>{{ readable(edge.relation) }}</span
                ><strong>{{ entityLabel(edge.tail) }}</strong
                ><a-tag size="small">{{ readable(edge.review_status) }}</a-tag>
              </button>
            </div>
            <section v-if="selectedBuildEdge" class="build-review-detail">
              <h3>
                {{ entityLabel(selectedBuildEdge.head) }} →
                {{ entityLabel(selectedBuildEdge.tail) }}
              </h3>
              <a-space
                ><a-tag>{{ readable(selectedBuildEdge.relation) }}</a-tag
                ><span class="subtle"
                  >关系置信度
                  {{ selectedBuildEdge.confidence.toFixed(2) }}</span
                ></a-space
              >
              <h4>支持依据</h4>
              <blockquote class="source-document">
                {{ selectedBuildEdge.evidence || "未提供支持片段" }}
              </blockquote>
              <p class="subtle">{{ sourceLabel(selectedBuildEdge.source) }}</p>
              <a-button
                @click="openBuildReviewEdgeProvenance(selectedBuildEdge)"
                >核验来源</a-button
              >
              <a-divider /><a-form
                :model="{ note: buildReviewNote }"
                layout="vertical"
                ><a-form-item label="审阅理由" required
                  ><a-textarea
                    v-model="buildReviewNote"
                    v-control-label="'构图审阅理由'"
                    placeholder="依据是什么，为什么保留或拒绝？" /></a-form-item
                ><a-space
                  ><a-button
                    type="primary"
                    :loading="!!buildReviewActionTargetKey"
                    @click="
                      handleBuildReviewAction(
                        selectedBuildEdge.target_key,
                        'accept',
                      )
                    "
                    >接受</a-button
                  ><a-button
                    status="danger"
                    :loading="!!buildReviewActionTargetKey"
                    @click="
                      handleBuildReviewAction(
                        selectedBuildEdge.target_key,
                        'reject',
                      )
                    "
                    >拒绝</a-button
                  ></a-space
                ></a-form
              >
              <p class="subtle">记录对当前构图产物的判断，不发布到运行图谱。</p>
            </section>
          </div>
          <a-empty v-else description="当前构图暂无可审阅关系" />
          <a-pagination
            v-if="(buildReviewQueue?.total_count ?? 0) > 12"
            class="build-review-pagination"
            :total="buildReviewQueue?.total_count ?? 0"
            :page-size="12"
            :current="reviewOffset / 12 + 1"
            simple
            @change="reviewPage"
          /> </a-tab-pane
        ><a-tab-pane key="manifest" title="来源清单"
          ><div
            v-for="id in buildDetail?.build.source_ids ?? []"
            :key="id"
            class="source-excerpt"
          >
            <strong>{{
              materials.find((m) => m.source_id === id || m.material_id === id)
                ?.title ?? sourceLabel(id)
            }}</strong>
          </div>
          <a-button @click="openBuildProvenance">检查来源记录</a-button
          ><a-collapse
            ><a-collapse-item header="技术清单" item-key="manifest">
              <pre class="raw-json">{{
                formatJsonPreview(buildDetail?.manifest)
              }}</pre>
            </a-collapse-item></a-collapse
          ></a-tab-pane
        ><a-tab-pane key="qa" title="质检与导出"
          ><p class="subtle">质量检查仅针对构图产物，不代表候选根因已验证。</p>
          <a-button :disabled="!canExportBuild" @click="handleExportBuild"
            >导出构图记录</a-button
          ><a-collapse
            ><a-collapse-item header="质检详情" item-key="qa">
              <pre class="raw-json">{{
                formatJsonPreview(
                  buildValidation?.qa_report ?? buildDetail?.summary,
                )
              }}</pre>
            </a-collapse-item></a-collapse
          ></a-tab-pane
        ></a-tabs
      >
    </a-spin>
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
                <div
                  class="rl-file-dropzone__content rl-file-dropzone__content--fill"
                >
                  <div class="rl-file-dropzone__copy">
                    <strong>
                      {{
                        uploadForm.files.length > 1
                          ? `已选择 ${uploadForm.files.length} 个文件`
                          : (uploadForm.files[0]?.name ??
                            "拖动素材文件到这里，或点击选择文件")
                      }}
                    </strong>
                  </div>
                  <a-button
                    aria-label="选择素材文件"
                    size="small"
                    @click="openUploadPicker"
                  >
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
                  :disabled="
                    materialMutationLoading || uploadForm.files.length > 1
                  "
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
                  :disabled="
                    materialMutationLoading || uploadForm.files.length > 1
                  "
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
                  <a-select
                    aria-label="类型"
                    v-model="uploadForm.sourceType"
                    :disabled="
                      materialMutationLoading || uploadForm.files.length > 1
                    "
                  >
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
                :label-attrs="{
                  for: 'material-registerUrlForm-materialId-input',
                }"
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
                :label-attrs="{
                  for: 'material-registerUrlForm-scenario-input',
                }"
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
                :label-attrs="{
                  for: 'material-registerUrlForm-sourceType-input',
                }"
                class="workspace-form-item"
              >
                <div
                  id="material-registerUrlForm-sourceType"
                  v-control-label="'类型'"
                  class="workspace-control"
                >
                  <a-select
                    aria-label="类型"
                    v-model="registerUrlForm.sourceType"
                  >
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
              <a-button
                :loading="materialMutationLoading"
                @click="handleRegisterUrl"
              >
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
