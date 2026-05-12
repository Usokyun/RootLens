<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'

import SessionBlockerCard from '@/components/workflow/SessionBlockerCard.vue'
import {
  buildAnalysisWorkspaceScope,
  clearDraftCase,
  clearFeedbackVerdict,
  getAnalysisWorkspaceEventName,
  getCaseFeedbackEntries,
  getFeedbackNote,
  getFeedbackVerdict,
  hasDraftCase,
  loadAnalysisWorkspace,
  overlayWorkspaceCases,
  saveDraftCase,
  setFeedbackNote,
  setFeedbackVerdict,
  type AnalystFeedbackTarget,
  type AnalystFeedbackVerdict,
  type AnalysisWorkspaceStorage,
} from '@/services/analysis-workspace'
import {
  buildFeedbackSummaryItems,
  type FeedbackSummaryItem,
} from '@/services/feedback-summary'
import {
  buildCaseFocus,
  buildCrossSignalFocus,
  buildObservationFocus,
  buildRoute1PathFocus,
  buildRoute2CandidateFocus,
  getAnalysisFocusEventName,
  loadAnalysisFocus,
  saveAnalysisFocus,
  type AnalysisFocusState,
} from '@/services/analysis-focus'
import {
  getImportedSessionSummary,
  getLocalSessionEventName,
  getLocalSessionMeta,
  loadRootLensRuntime,
  loadUnifiedGraphs,
} from '@/services/rootlens-data'
import {
  applyCorrectionWhatIf,
  applyObservationWhatIf,
  buildObservationPatchDiff,
  buildObservationPatchPreview,
  canApplyCorrectionCandidate,
  observationLabel,
  splitHintText,
  type ObservationWhatIfPatch,
} from '@/services/what-if'
import { buildWorkflowSnapshot } from '@/services/workflow'
import type { UnifiedGraphDataset } from '@/types/graph'
import type {
  CorrectionCandidate,
  CrossRouteSignal,
  EvidenceObservation,
  RankedPath,
  RootKGDCandidate,
  RootLensRuntimeCase,
} from '@/types/rootlens'

const cases = shallowRef<RootLensRuntimeCase[]>([])
const baseCases = shallowRef<RootLensRuntimeCase[]>([])
const activeCase = shallowRef<RootLensRuntimeCase | null>(null)
const graphDatasets = shallowRef<UnifiedGraphDataset[]>([])
const workspaceState = shallowRef<AnalysisWorkspaceStorage | null>(null)
const focusState = shallowRef<AnalysisFocusState | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const activeCaseId = ref('')
const sessionMeta = ref(getLocalSessionMeta())
const importSummary = ref(getImportedSessionSummary())
const whatIfObservationId = ref('')
const whatIfHintText = ref('')
const whatIfNotice = ref('')
const whatIfError = ref('')
const whatIfDraft = reactive<ObservationWhatIfPatch>({})
const feedbackNoteDrafts = reactive<Record<string, string>>({})
const router = useRouter()

const sessionLabel = computed(() =>
  sessionMeta.value?.source === 'import' ? '本地导入' : '内置示例',
)
const sessionSummary = computed(() => sessionMeta.value?.summary ?? '使用内置示例数据')
const analysisWorkspaceScope = computed(() => buildAnalysisWorkspaceScope(sessionMeta.value))
const workflow = computed(() => buildWorkflowSnapshot(sessionMeta.value, importSummary.value))
const canOpenGraphs = computed(() => workflow.value.hasGraphs)
const pageBlocker = computed(() => {
  if (workflow.value.hasCases) {
    return null
  }

  if (workflow.value.hasGraphs) {
    return {
      title: '当前会话只有图谱，无法执行 RCA',
      description:
        'RCA 工作台依赖 runtime case。你当前已经有统一图谱，但还没有由 evidence/case 文件生成可推理的 case，因此 route1 / route2 无法启动。',
      hints: [
        '回到系统入口后选择“追加 Evidence”，把 observation 组装成 runtime case。',
        '图谱工作台仍可用于检查节点、关系和图结构。',
      ],
      actions: [
        { key: 'import', label: '去追加 Evidence', type: 'primary' as const },
        { key: 'graphs', label: '查看图谱', type: 'outline' as const },
      ],
    }
  }

  return {
    title: '当前会话还没有 RCA 输入',
    description:
      'RCA 工作台需要完整的 runtime case。请先导入图谱并追加 evidence/case，或者直接恢复完整 bundle。',
    hints: [
      'runtime-only 可以让 Evidence / RCA 工作台可用，但 what-if 仍需要统一图谱支持。',
      '恢复完整 bundle 会同时带回 graphs、runtime、workspace 与共享焦点。',
    ],
    actions: [
      { key: 'import', label: '返回系统入口', type: 'primary' as const },
      { key: 'evidence', label: '查看 Evidence', type: 'outline' as const },
    ],
  }
})

function resolveActiveCase(
  currentCases: RootLensRuntimeCase[],
  caseId: string,
): RootLensRuntimeCase | null {
  return currentCases.find((item) => item.case_id === caseId) ?? currentCases[0] ?? null
}

const route1 = computed(() => activeCase.value?.analysis.route1 ?? null)
const route2 = computed(() => activeCase.value?.analysis.route2 ?? null)
const crossSignals = computed(() => activeCase.value?.analysis.cross_route_signals ?? [])
const isDraftCase = computed(() =>
  activeCase.value ? hasDraftCase(workspaceState.value, activeCase.value.case_id) : false,
)
const activeCaseFeedback = computed(() =>
  activeCase.value ? getCaseFeedbackEntries(workspaceState.value, activeCase.value.case_id) : [],
)
const acceptedFeedbackCount = computed(
  () => activeCaseFeedback.value.filter((item) => item.verdict === 'accepted').length,
)
const rejectedFeedbackCount = computed(
  () => activeCaseFeedback.value.filter((item) => item.verdict === 'rejected').length,
)
const notedFeedbackCount = computed(
  () => activeCaseFeedback.value.filter((item) => item.note?.trim()).length,
)
const feedbackSummaryItems = computed(() =>
  buildFeedbackSummaryItems(
    activeCaseFeedback.value,
    route1.value?.ranked_paths ?? [],
    route2.value?.ranked_candidates ?? [],
  ),
)
const focusedPathIds = computed(() => new Set(focusState.value?.selected_route1_path_ids ?? []))
const focusedCandidateIds = computed(() => new Set(focusState.value?.selected_route2_candidate_ids ?? []))
const highlightedObservationIds = computed(() => new Set(focusState.value?.highlighted_obs_ids ?? []))
const activeGraphDataset = computed<UnifiedGraphDataset | null>(() => {
  if (!activeCase.value) {
    return null
  }

  const preferredDatasetId =
    activeCase.value.analysis.graph_dataset_id ||
    activeCase.value.evidence.graph_dataset_id ||
    activeCase.value.graph_snapshot.dataset_id

  return (
    graphDatasets.value.find((dataset) => dataset.id === preferredDatasetId) ??
    graphDatasets.value[0] ??
    null
  )
})
const whatIfObservation = computed<EvidenceObservation | null>(() => {
  if (!activeCase.value) {
    return null
  }

  return (
    activeCase.value.evidence.observations.find((item) => item.obs_id === whatIfObservationId.value) ??
    activeCase.value.evidence.observations[0] ??
    null
  )
})
const whatIfObservationOptions = computed(() =>
  activeCase.value?.evidence.observations.map((observation) => ({
    label: observationLabel(observation),
    value: observation.obs_id,
  })) ?? [],
)
const whatIfDiffItems = computed(() => {
  if (!whatIfObservation.value) {
    return []
  }

  return buildObservationPatchDiff(whatIfObservation.value, {
    ...whatIfDraft,
    linked_entity_hints: splitHintText(whatIfHintText.value),
  })
})
const hasWhatIfChanges = computed(() => whatIfDiffItems.value.length > 0)

function refreshWorkspaceState() {
  workspaceState.value = loadAnalysisWorkspace(analysisWorkspaceScope.value)
}

function refreshFocusState() {
  focusState.value = loadAnalysisFocus(analysisWorkspaceScope.value)
}

function hydrateCases() {
  const currentCaseId = activeCaseId.value
  const focusedCaseId = focusState.value?.active_case_id

  cases.value = overlayWorkspaceCases(baseCases.value, workspaceState.value)
  activeCaseId.value = cases.value.some((item) => item.case_id === focusedCaseId)
    ? (focusedCaseId as string)
    : cases.value.some((item) => item.case_id === currentCaseId)
      ? currentCaseId
      : cases.value[0]?.case_id ?? ''
  activeCase.value = resolveActiveCase(cases.value, activeCaseId.value)
  syncFeedbackNoteDrafts()
}

function persistCaseFocus(caseItem: RootLensRuntimeCase | null) {
  if (!caseItem) {
    return
  }

  focusState.value = saveAnalysisFocus(
    analysisWorkspaceScope.value,
    buildCaseFocus(caseItem, 'reasoning'),
  )
}

function focusRoute1Path(path: RankedPath, targetView: 'graphs' | 'evidence' | null = null) {
  if (!activeCase.value) {
    return
  }

  if (targetView === 'graphs' && !canOpenGraphs.value) {
    return
  }

  focusState.value = saveAnalysisFocus(
    analysisWorkspaceScope.value,
    buildRoute1PathFocus(activeCase.value, path, 'reasoning'),
  )

  if (targetView) {
    void router.push({
      name: targetView,
    })
  }
}

function focusRoute2Candidate(
  candidate: RootKGDCandidate,
  targetView: 'graphs' | 'evidence' | null = null,
) {
  if (!activeCase.value) {
    return
  }

  if (targetView === 'graphs' && !canOpenGraphs.value) {
    return
  }

  focusState.value = saveAnalysisFocus(
    analysisWorkspaceScope.value,
    buildRoute2CandidateFocus(activeCase.value, candidate, 'reasoning'),
  )

  if (targetView) {
    void router.push({
      name: targetView,
    })
  }
}

function focusCrossSignal(signal: CrossRouteSignal, targetView: 'graphs' | 'evidence' = 'graphs') {
  if (!activeCase.value) {
    return
  }

  if (targetView === 'graphs' && !canOpenGraphs.value) {
    return
  }

  const supportingPaths =
    route1.value?.ranked_paths.filter((path) => signal.route1_path_ids.includes(path.path_id)) ?? []

  focusState.value = saveAnalysisFocus(
    analysisWorkspaceScope.value,
    buildCrossSignalFocus(activeCase.value, signal, supportingPaths, 'reasoning'),
  )

  void router.push({
    name: targetView,
  })
}

function openObservation(obsId: string) {
  if (!activeCase.value) {
    return
  }

  const observation =
    activeCase.value.evidence.observations.find((item) => item.obs_id === obsId) ?? null

  if (!observation) {
    return
  }

  focusState.value = saveAnalysisFocus(
    analysisWorkspaceScope.value,
    buildObservationFocus(activeCase.value, observation, 'reasoning'),
  )

  void router.push({
    name: 'evidence',
  })
}

async function loadRuntimeData() {
  loading.value = true
  errorMessage.value = ''
  whatIfError.value = ''
  whatIfNotice.value = ''

  try {
    const previousCaseId = activeCaseId.value
    const payload = await loadRootLensRuntime()
    let datasets: UnifiedGraphDataset[] = []

    try {
      const graphPayload = await loadUnifiedGraphs()
      datasets = graphPayload.datasets
    } catch {
      datasets = []
    }

    graphDatasets.value = datasets
    baseCases.value = payload.cases
    refreshWorkspaceState()
    refreshFocusState()
    activeCaseId.value = payload.cases.some((item) => item.case_id === focusState.value?.active_case_id)
      ? (focusState.value?.active_case_id as string)
      : payload.cases.some((item) => item.case_id === previousCaseId)
        ? previousCaseId
        : payload.cases[0]?.case_id ?? ''
    hydrateCases()
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'failed to load reasoning runtime bundle'
  } finally {
    loading.value = false
  }
}

function refreshSessionMeta() {
  sessionMeta.value = getLocalSessionMeta()
  importSummary.value = getImportedSessionSummary()
}

function handleSessionChange() {
  refreshSessionMeta()
  refreshFocusState()
  void loadRuntimeData()
}

function handleWorkspaceChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (
    customEvent.detail?.sessionScope &&
    customEvent.detail.sessionScope !== analysisWorkspaceScope.value
  ) {
    return
  }

  refreshWorkspaceState()
  hydrateCases()
}

function handleFocusChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (
    customEvent.detail?.sessionScope &&
    customEvent.detail.sessionScope !== analysisWorkspaceScope.value
  ) {
    return
  }

  refreshFocusState()
  hydrateCases()
}

function handleCaseChange(value: string | number | boolean) {
  activeCaseId.value = String(value)
  activeCase.value = resolveActiveCase(cases.value, activeCaseId.value)
  whatIfNotice.value = ''
  whatIfError.value = ''
  persistCaseFocus(activeCase.value)
}

function handleBlockerAction(actionKey: string) {
  if (actionKey === 'import') {
    void router.push({
      name: 'import',
    })
    return
  }

  if (actionKey === 'graphs') {
    void router.push({
      name: 'graphs',
    })
    return
  }

  if (actionKey === 'evidence') {
    void router.push({
      name: 'evidence',
    })
  }
}

function routeBadge(routeEnabled: boolean) {
  return routeEnabled ? 'green' : 'grayblue'
}

function formatScore(value: number) {
  return value.toFixed(2)
}

function pathSummary(path: RankedPath) {
  return path.node_names.join(' -> ')
}

function supportPathSummary(candidate: RootKGDCandidate) {
  return candidate.top_support_paths.map((item) => item.join(' -> '))
}

function formatCandidateValue(value: unknown) {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function feedbackKey(targetKind: AnalystFeedbackTarget, targetId: string) {
  return `${targetKind}:${targetId}`
}

function feedbackAnchorId(targetKind: AnalystFeedbackTarget, targetId: string) {
  return `feedback-target-${targetKind}-${targetId}`
}

function feedbackVerdict(
  targetKind: AnalystFeedbackTarget,
  targetId: string,
): AnalystFeedbackVerdict | null {
  if (!activeCase.value) {
    return null
  }

  return getFeedbackVerdict(
    workspaceState.value,
    activeCase.value.case_id,
    targetKind,
    targetId,
  )
}

function feedbackNote(
  targetKind: AnalystFeedbackTarget,
  targetId: string,
): string {
  if (!activeCase.value) {
    return ''
  }

  return getFeedbackNote(
    workspaceState.value,
    activeCase.value.case_id,
    targetKind,
    targetId,
  )
}

function feedbackLabel(verdict: AnalystFeedbackVerdict | null) {
  if (verdict === 'accepted') {
    return '已接受'
  }

  if (verdict === 'rejected') {
    return '已驳回'
  }

  return '未标注'
}

function feedbackColor(verdict: AnalystFeedbackVerdict | null) {
  if (verdict === 'accepted') {
    return 'green'
  }

  if (verdict === 'rejected') {
    return 'orangered'
  }

  return 'grayblue'
}

function formatUpdatedAt(value: string) {
  const parsed = new Date(value)

  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleString('zh-CN', {
    hour12: false,
  })
}

function scrollToFeedbackTarget(
  targetKind: AnalystFeedbackTarget,
  targetId: string,
) {
  if (typeof window === 'undefined') {
    return
  }

  window.requestAnimationFrame(() => {
    document
      .getElementById(feedbackAnchorId(targetKind, targetId))
      ?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
  })
}

function jumpToFeedbackTarget(item: FeedbackSummaryItem) {
  if (item.target_kind === 'route1-path') {
    const path = route1.value?.ranked_paths.find((value) => value.path_id === item.target_id)

    if (!path) {
      return
    }

    focusRoute1Path(path)
  } else {
    const candidate = route2.value?.ranked_candidates.find(
      (value) => value.candidate_id === item.target_id,
    )

    if (!candidate) {
      return
    }

    focusRoute2Candidate(candidate)
  }

  scrollToFeedbackTarget(item.target_kind, item.target_id)
}

function syncFeedbackNoteDrafts() {
  for (const key of Object.keys(feedbackNoteDrafts)) {
    delete feedbackNoteDrafts[key]
  }

  if (!activeCase.value) {
    return
  }

  for (const entry of activeCaseFeedback.value) {
    if (entry.note) {
      feedbackNoteDrafts[feedbackKey(entry.target_kind, entry.target_id)] = entry.note
    }
  }
}

function setFeedbackNoteDraft(
  targetKind: AnalystFeedbackTarget,
  targetId: string,
  value: string,
) {
  feedbackNoteDrafts[feedbackKey(targetKind, targetId)] = value
}

function commitFeedbackNote(
  targetKind: AnalystFeedbackTarget,
  targetId: string,
) {
  if (!activeCase.value) {
    return
  }

  const key = feedbackKey(targetKind, targetId)
  const draftValue = feedbackNoteDrafts[key] ?? ''
  const persistedValue = feedbackNote(targetKind, targetId)

  if (draftValue.trim() === persistedValue) {
    if (!draftValue.trim() && key in feedbackNoteDrafts) {
      delete feedbackNoteDrafts[key]
    }
    return
  }

  setFeedbackNote(
    analysisWorkspaceScope.value,
    activeCase.value.case_id,
    targetKind,
    targetId,
    draftValue,
  )

  refreshWorkspaceState()
  syncFeedbackNoteDrafts()
}

function setWhatIfDraft(next: ObservationWhatIfPatch) {
  for (const key of Object.keys(whatIfDraft)) {
    delete whatIfDraft[key as keyof ObservationWhatIfPatch]
  }

  Object.assign(whatIfDraft, next)
  whatIfHintText.value = next.linked_entity_hints?.join('\n') ?? ''
}

function syncWhatIfDraft() {
  const observation = whatIfObservation.value
  if (!observation) {
    setWhatIfDraft({})
    return
  }

  setWhatIfDraft(buildObservationPatchPreview(observation))
}

function applyManualWhatIf() {
  if (!activeCase.value || !whatIfObservation.value || !activeGraphDataset.value) {
    whatIfError.value = '当前会话缺少可重算的统一图谱，无法执行 what-if。'
    return
  }

  whatIfError.value = ''
  const updatedCase = applyObservationWhatIf(
    activeCase.value,
    activeGraphDataset.value,
    whatIfObservation.value.obs_id,
    {
      ...whatIfDraft,
      linked_entity_hints: splitHintText(whatIfHintText.value),
    },
  )
  saveDraftCase(analysisWorkspaceScope.value, updatedCase)
  refreshWorkspaceState()
  hydrateCases()
  whatIfNotice.value = `已基于 ${whatIfObservation.value.obs_id} 重新执行本地推理。`
}

function applyCorrection(candidate: CorrectionCandidate) {
  if (!activeCase.value || !activeGraphDataset.value) {
    whatIfError.value = '当前会话缺少可重算的统一图谱，无法应用修正候选。'
    return
  }

  try {
    const updatedCase = applyCorrectionWhatIf(activeCase.value, activeGraphDataset.value, candidate)
    saveDraftCase(analysisWorkspaceScope.value, updatedCase)
    refreshWorkspaceState()
    hydrateCases()
    whatIfObservationId.value = candidate.target_obs_id ?? whatIfObservationId.value
    whatIfNotice.value = `已应用修正候选 ${candidate.candidate_id} 并完成重算。`
    whatIfError.value = ''
  } catch (error) {
    whatIfError.value = error instanceof Error ? error.message : '修正候选应用失败'
  }
}

function resetActiveCase() {
  if (!activeCase.value) {
    return
  }

  const sourceCase =
    baseCases.value.find((caseItem) => caseItem.case_id === activeCase.value?.case_id) ?? null

  if (!sourceCase) {
    whatIfError.value = '未找到原始 case，无法恢复。'
    return
  }

  clearDraftCase(analysisWorkspaceScope.value, sourceCase.case_id)
  refreshWorkspaceState()
  hydrateCases()
  whatIfNotice.value = `已恢复 ${sourceCase.case_id} 的原始推理结果。`
  whatIfError.value = ''
}

function toggleFeedback(
  targetKind: AnalystFeedbackTarget,
  targetId: string,
  verdict: AnalystFeedbackVerdict,
) {
  if (!activeCase.value) {
    return
  }

  const currentVerdict = feedbackVerdict(targetKind, targetId)
  if (currentVerdict === verdict) {
    clearFeedbackVerdict(analysisWorkspaceScope.value, activeCase.value.case_id, targetKind, targetId)
  } else {
    setFeedbackVerdict(
      analysisWorkspaceScope.value,
      activeCase.value.case_id,
      targetKind,
      targetId,
      verdict,
    )
  }

  refreshWorkspaceState()
  syncFeedbackNoteDrafts()
}

watch(
  activeCase,
  (value) => {
    if (!value) {
      whatIfObservationId.value = ''
      setWhatIfDraft({})
      return
    }

    if (!value.evidence.observations.some((item) => item.obs_id === whatIfObservationId.value)) {
      whatIfObservationId.value = value.evidence.observations[0]?.obs_id ?? ''
    }

    syncFeedbackNoteDrafts()
  },
  {
    immediate: true,
  },
)

watch(whatIfObservation, () => {
  syncWhatIfDraft()
})

onMounted(() => {
  refreshSessionMeta()
  refreshFocusState()
  void loadRuntimeData()
  window.addEventListener(getLocalSessionEventName(), handleSessionChange)
  window.addEventListener(getAnalysisWorkspaceEventName(), handleWorkspaceChange)
  window.addEventListener(getAnalysisFocusEventName(), handleFocusChange)
})

onBeforeUnmount(() => {
  window.removeEventListener(getLocalSessionEventName(), handleSessionChange)
  window.removeEventListener(getAnalysisWorkspaceEventName(), handleWorkspaceChange)
  window.removeEventListener(getAnalysisFocusEventName(), handleFocusChange)
})
</script>

<template>
  <div class="page-stack reasoning-workbench">
    <section class="hero-panel">
      <div class="hero-panel__content">
        <div>
          <a-space wrap>
            <a-tag color="arcoblue">Route 1</a-tag>
            <a-tag color="orangered">Route 2</a-tag>
            <a-tag color="green">Cross Route Signals</a-tag>
          </a-space>
          <h2 class="hero-panel__title">RCA 分析</h2>
          <p class="hero-panel__body">
            这里开始消费 `AnalysisResult` contract。路线 1 保留 entity linking、consistency 和 path
            ranking；路线 2 保留 TEP 的 Root-KGD 输出结构，并由浏览器本地运行时生成候选排序、what-if 回放与人工反馈。
          </p>
        </div>

        <div class="hero-panel__brief">
          <div class="brief-item">
            <div class="brief-item__label">Case Count</div>
            <div class="brief-item__value">{{ cases.length }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">当前会话</div>
            <div class="brief-item__value">{{ sessionLabel }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">Route 1 Ready</div>
            <div class="brief-item__value">{{ route1 ? 'Yes' : 'No' }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">Route 2 Ready</div>
            <div class="brief-item__value">{{ route2 ? 'Yes' : 'No' }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">会话摘要</div>
            <div class="brief-item__value">{{ sessionSummary }}</div>
          </div>
        </div>
      </div>
    </section>

    <a-card v-if="loading" class="glass-card" :bordered="false">
      <a-spin dot tip="正在加载 reasoning runtime..." />
    </a-card>

    <SessionBlockerCard
      v-else-if="pageBlocker"
      badge="Reasoning Unavailable"
      :session-label="sessionLabel"
      :title="pageBlocker.title"
      :description="pageBlocker.description"
      :reason="errorMessage"
      :hints="pageBlocker.hints"
      :actions="pageBlocker.actions"
      @action="handleBlockerAction"
    />

    <a-alert
      v-else-if="errorMessage"
      type="error"
      show-icon
      :content="errorMessage"
    />

    <template v-else-if="activeCase">
      <a-card class="glass-card" :bordered="false">
        <div class="reasoning-toolbar">
          <div class="toolbar-block">
            <div class="toolbar-block__label">Case</div>
            <a-radio-group
              type="button"
              :model-value="activeCaseId"
              @change="handleCaseChange"
            >
              <a-radio
                v-for="caseItem in cases"
                :key="caseItem.case_id"
                :value="caseItem.case_id"
              >
                {{ caseItem.case_label }}
              </a-radio>
            </a-radio-group>
          </div>

          <div class="toolbar-block">
            <div class="toolbar-block__label">Runtime Notes</div>
            <div class="toolbar-note">
              {{ activeCase.summary }}
            </div>
          </div>
        </div>
      </a-card>

      <div class="reasoning-metrics">
        <div class="metric-card">
          <div class="metric-card__label">Graph Snapshot</div>
          <div class="metric-card__value">{{ activeCase.graph_snapshot.label }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-card__label">Dataset</div>
          <div class="metric-card__value">{{ activeCase.dataset }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-card__label">Route 1 Paths</div>
          <div class="metric-card__value">{{ route1?.ranked_paths.length ?? 0 }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-card__label">Route 2 Candidates</div>
          <div class="metric-card__value">{{ route2?.ranked_candidates.length ?? 0 }}</div>
        </div>
      </div>

      <a-card class="glass-card" :bordered="false">
        <template #title>Analyst Workspace</template>

        <div class="workspace-grid">
          <div class="candidate-metric">
            <span>Case Mode</span>
            <strong>{{ isDraftCase ? 'draft' : 'base' }}</strong>
          </div>
          <div class="candidate-metric">
            <span>Feedback Items</span>
            <strong>{{ activeCaseFeedback.length }}</strong>
          </div>
          <div class="candidate-metric">
            <span>Accepted</span>
            <strong>{{ acceptedFeedbackCount }}</strong>
          </div>
          <div class="candidate-metric">
            <span>Rejected</span>
            <strong>{{ rejectedFeedbackCount }}</strong>
          </div>
          <div class="candidate-metric">
            <span>Noted</span>
            <strong>{{ notedFeedbackCount }}</strong>
          </div>
        </div>

        <div v-if="focusState?.focus_kind" class="workspace-focus">
          <a-space wrap>
            <a-tag color="arcoblue">{{ focusState.focus_kind }}</a-tag>
            <a-tag color="green">{{ focusState.source_view ?? 'system' }}</a-tag>
            <a-tag color="grayblue">{{ focusState.focus_label ?? activeCase.case_label }}</a-tag>
          </a-space>
        </div>

        <p class="workspace-note">
          当前 case 的 what-if 草稿和人工反馈都保存在浏览器本地，会在刷新页面后自动恢复。
        </p>
      </a-card>

      <a-card
        v-if="feedbackSummaryItems.length"
        class="glass-card"
        :bordered="false"
      >
        <template #title>Feedback Summary</template>
        <template #extra>
          <a-space wrap>
            <a-tag color="green">accepted {{ acceptedFeedbackCount }}</a-tag>
            <a-tag color="orangered">rejected {{ rejectedFeedbackCount }}</a-tag>
            <a-tag color="gold">noted {{ notedFeedbackCount }}</a-tag>
          </a-space>
        </template>

        <div class="feedback-summary-list">
          <article
            v-for="item in feedbackSummaryItems"
            :key="item.feedback_id"
            class="feedback-summary-card"
          >
            <div class="feedback-summary-card__head">
              <div class="feedback-summary-card__content">
                <a-space wrap>
                  <a-tag color="arcoblue">{{ item.target_kind_label }}</a-tag>
                  <a-tag :color="feedbackColor(item.verdict)">
                    {{ feedbackLabel(item.verdict) }}
                  </a-tag>
                  <a-tag v-if="item.note" color="gold">已备注</a-tag>
                  <a-tag v-if="!item.target_available" color="grayblue">当前结果缺失</a-tag>
                </a-space>
                <strong>{{ item.title }}</strong>
                <p>{{ item.subtitle }}</p>
              </div>

              <a-button
                size="mini"
                :disabled="!item.target_available"
                @click="jumpToFeedbackTarget(item)"
              >
                {{ item.action_label }}
              </a-button>
            </div>

            <div class="feedback-summary-card__meta">
              最近更新 {{ formatUpdatedAt(item.updated_at) }}
            </div>

            <p v-if="item.note" class="feedback-summary-card__note">
              {{ item.note }}
            </p>
          </article>
        </div>
      </a-card>

      <a-card class="glass-card" :bordered="false">
        <template #title>What-if Replay</template>
        <template #extra>
          <a-space>
            <a-tag :color="isDraftCase ? 'orangered' : 'grayblue'">
              {{ isDraftCase ? 'draft' : 'base' }}
            </a-tag>
            <a-tag color="arcoblue">
              {{ activeGraphDataset ? activeGraphDataset.label : 'no graph dataset' }}
            </a-tag>
          </a-space>
        </template>

        <template v-if="activeGraphDataset">
          <div class="whatif-layout">
            <div class="toolbar-block">
              <div class="toolbar-block__label">Observation</div>
              <a-select
                v-model="whatIfObservationId"
                :options="whatIfObservationOptions"
                placeholder="选择一个 observation 进行 what-if 重算"
              />
            </div>

            <template v-if="whatIfObservation">
              <div class="whatif-grid">
                <a-input
                  v-if="whatIfObservation.facet === 'variable'"
                  v-model="whatIfDraft.variable_name"
                  placeholder="variable name"
                />
                <a-input-number
                  v-if="whatIfObservation.facet === 'variable'"
                  v-model="whatIfDraft.contribution"
                  :max="1"
                  :min="0"
                  :precision="3"
                  placeholder="contribution"
                />
                <a-select
                  v-if="whatIfObservation.facet === 'variable'"
                  v-model="whatIfDraft.direction"
                  :options="[
                    { label: 'increase', value: 'increase' },
                    { label: 'decrease', value: 'decrease' },
                    { label: 'unknown', value: 'unknown' },
                  ]"
                  placeholder="direction"
                />

                <a-input
                  v-if="whatIfObservation.facet === 'image_defect'"
                  v-model="whatIfDraft.object"
                  placeholder="object"
                />
                <a-input
                  v-if="whatIfObservation.facet === 'image_defect'"
                  v-model="whatIfDraft.anomaly_type"
                  placeholder="anomaly type"
                />
                <a-input
                  v-if="whatIfObservation.facet === 'image_defect'"
                  v-model="whatIfDraft.location"
                  placeholder="location"
                />
                <a-input-number
                  v-if="whatIfObservation.facet === 'image_defect'"
                  v-model="whatIfDraft.severity"
                  :max="1"
                  :min="0"
                  :precision="3"
                  placeholder="severity"
                />

                <a-input
                  v-if="whatIfObservation.facet === 'log_event'"
                  v-model="whatIfDraft.event_code"
                  placeholder="event code"
                />
                <a-input
                  v-if="whatIfObservation.facet === 'log_event'"
                  v-model="whatIfDraft.event_type"
                  placeholder="event type"
                />
                <a-input
                  v-if="whatIfObservation.facet === 'log_event'"
                  v-model="whatIfDraft.equipment"
                  placeholder="equipment"
                />

                <a-input-number
                  v-model="whatIfDraft.confidence"
                  :max="1"
                  :min="0"
                  :precision="3"
                  placeholder="confidence"
                />
              </div>

              <a-textarea
                v-model="whatIfHintText"
                :auto-size="{ minRows: 3, maxRows: 6 }"
                placeholder="linked entity hints，按换行 / 逗号 / 分号分隔"
              />

              <div class="subsection">
                <div class="subsection__label">What-if Diff</div>
                <div v-if="whatIfDiffItems.length" class="whatif-diff-list">
                  <div
                    v-for="item in whatIfDiffItems"
                    :key="item.key"
                    class="whatif-diff-item"
                  >
                    <div class="whatif-diff-item__label">{{ item.label }}</div>
                    <div class="whatif-diff-item__values">
                      <span>{{ item.before }}</span>
                      <strong>{{ item.after }}</strong>
                    </div>
                  </div>
                </div>
                <a-empty v-else description="当前 observation 还没有待应用的改动。" />
              </div>

              <div class="whatif-actions">
                <a-button
                  type="primary"
                  :disabled="!hasWhatIfChanges"
                  @click="applyManualWhatIf"
                >
                  应用变更并重算
                </a-button>
                <a-button :disabled="!isDraftCase" @click="resetActiveCase">
                  恢复原始 case
                </a-button>
              </div>
            </template>

            <a-alert
              v-if="whatIfNotice"
              type="info"
              show-icon
              :content="whatIfNotice"
            />
            <a-alert
              v-if="whatIfError"
              type="error"
              show-icon
              :content="whatIfError"
            />
          </div>
        </template>

        <a-empty v-else description="当前会话未包含统一图谱，无法执行本地 what-if 重算。" />
      </a-card>

      <div class="route-layout">
        <a-card class="glass-card" :bordered="false">
          <template #title>Route 1 / Clue Organization</template>
          <template #extra>
            <a-tag :color="routeBadge(Boolean(route1))">
              {{ route1 ? 'enabled' : 'disabled' }}
            </a-tag>
          </template>

          <template v-if="route1">
            <div class="route-metric-grid">
              <div class="route-metric">
                <span>Consistency</span>
                <strong>{{ formatScore(route1.consistency_score) }}</strong>
              </div>
              <div class="route-metric">
                <span>Linked Entities</span>
                <strong>{{ route1.linked_entities.length }}</strong>
              </div>
              <div class="route-metric">
                <span>Corrections</span>
                <strong>{{ route1.correction_candidates.length }}</strong>
              </div>
              <div class="route-metric">
                <span>Paths</span>
                <strong>{{ route1.ranked_paths.length }}</strong>
              </div>
            </div>

            <div class="section-block">
              <h3>Linked Entities</h3>
              <div class="table-shell">
                <table class="workbench-table">
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Mention</th>
                      <th>Selected</th>
                      <th>Match</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="entity in route1.linked_entities"
                      :key="entity.link_id"
                    >
                      <td>{{ entity.field }}</td>
                      <td>{{ entity.mention }}</td>
                      <td>
                        <div>{{ entity.selected_entity_name ?? 'unmatched' }}</div>
                        <code v-if="entity.selected_entity_id">{{ entity.selected_entity_id }}</code>
                      </td>
                      <td>{{ entity.match_type }}</td>
                      <td>{{ formatScore(entity.score) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="section-block">
              <h3>Correction Candidates</h3>
              <div v-if="route1.correction_candidates.length" class="correction-list">
                <div
                  v-for="candidate in route1.correction_candidates"
                  :key="candidate.candidate_id"
                  class="correction-card"
                >
                  <div class="correction-card__head">
                    <div>
                      <strong>{{ candidate.target_field }}</strong>
                      <p>{{ candidate.reason }}</p>
                    </div>
                    <a-tag color="arcoblue">
                      {{ formatScore(candidate.score) }}
                    </a-tag>
                  </div>

                  <div class="correction-card__body">
                    <div class="candidate-metric">
                      <span>Original</span>
                      <strong>{{ formatCandidateValue(candidate.original_value) }}</strong>
                    </div>
                    <div class="candidate-metric">
                      <span>Suggested</span>
                      <strong>{{ candidate.suggested_value }}</strong>
                    </div>
                    <div class="candidate-metric">
                      <span>Obs</span>
                      <strong>{{ candidate.target_obs_id ?? 'n/a' }}</strong>
                    </div>
                  </div>

                  <div class="whatif-actions">
                    <a-button
                      type="outline"
                      :disabled="!activeGraphDataset || !canApplyCorrectionCandidate(candidate)"
                      @click="applyCorrection(candidate)"
                    >
                      应用建议并重算
                    </a-button>
                  </div>
                </div>
              </div>

              <a-empty v-else description="当前 case 没有 route1 修正候选" />
            </div>

            <div class="section-block">
              <h3>Ranked Paths</h3>
              <div v-if="route1.ranked_paths.length" class="path-list">
                <div
                  v-for="pathItem in route1.ranked_paths"
                  :key="pathItem.path_id"
                  :id="feedbackAnchorId('route1-path', pathItem.path_id)"
                  class="path-card"
                  :class="{ 'path-card--active': focusedPathIds.has(pathItem.path_id) }"
                >
                  <div class="path-card__head">
                    <div>
                      <strong>{{ pathItem.target_entity_name }}</strong>
                      <p>{{ pathSummary(pathItem) }}</p>
                    </div>
                    <a-space wrap>
                      <a-tag color="arcoblue">score {{ formatScore(pathItem.score) }}</a-tag>
                      <a-tag color="green">
                        evidence {{ formatScore(pathItem.evidence_match) }}
                      </a-tag>
                    </a-space>
                  </div>

                  <div class="focus-actions">
                    <a-button
                      :disabled="!canOpenGraphs"
                      size="mini"
                      @click="focusRoute1Path(pathItem, 'graphs')"
                    >
                      在图中查看
                    </a-button>
                    <a-button
                      size="mini"
                      :disabled="!pathItem.support_obs_ids.length"
                      @click="focusRoute1Path(pathItem, 'evidence')"
                    >
                      查看证据
                    </a-button>
                  </div>

                  <div class="feedback-toolbar">
                    <a-tag :color="feedbackColor(feedbackVerdict('route1-path', pathItem.path_id))">
                      {{ feedbackLabel(feedbackVerdict('route1-path', pathItem.path_id)) }}
                    </a-tag>
                    <a-tag v-if="feedbackNote('route1-path', pathItem.path_id)" color="gold">
                      已备注
                    </a-tag>
                    <a-space wrap>
                      <a-button
                        size="mini"
                        status="success"
                        :type="
                          feedbackVerdict('route1-path', pathItem.path_id) === 'accepted'
                            ? 'primary'
                            : 'outline'
                        "
                        @click="toggleFeedback('route1-path', pathItem.path_id, 'accepted')"
                      >
                        接受
                      </a-button>
                      <a-button
                        size="mini"
                        status="danger"
                        :type="
                          feedbackVerdict('route1-path', pathItem.path_id) === 'rejected'
                            ? 'primary'
                            : 'outline'
                        "
                        @click="toggleFeedback('route1-path', pathItem.path_id, 'rejected')"
                      >
                        驳回
                      </a-button>
                    </a-space>
                  </div>

                  <a-textarea
                    :model-value="
                      feedbackNoteDrafts[feedbackKey('route1-path', pathItem.path_id)] ??
                      feedbackNote('route1-path', pathItem.path_id)
                    "
                    :auto-size="{ minRows: 2, maxRows: 4 }"
                    placeholder="记录该路径的人工判断、上下文或驳回理由；失焦后自动保存。"
                    @update:model-value="
                      (value) => setFeedbackNoteDraft('route1-path', pathItem.path_id, String(value ?? ''))
                    "
                    @blur="commitFeedbackNote('route1-path', pathItem.path_id)"
                  />

                  <div class="tag-wall">
                    <button
                      v-for="obsId in pathItem.support_obs_ids"
                      :key="obsId"
                      class="support-link"
                      :class="{ 'support-link--active': highlightedObservationIds.has(obsId) }"
                      type="button"
                      @click="openObservation(obsId)"
                    >
                      {{ obsId }}
                    </button>
                  </div>

                  <pre class="inline-code">{{ JSON.stringify(pathItem.source_edges, null, 2) }}</pre>
                </div>
              </div>

              <a-empty v-else description="当前 case 没有 route1 路径候选" />
            </div>
          </template>

          <a-empty v-else description="当前 case 未启用路线 1" />
        </a-card>

        <a-card class="glass-card" :bordered="false">
          <template #title>Route 2 / Process Fault Analysis</template>
          <template #extra>
            <a-tag :color="routeBadge(Boolean(route2))">
              {{ route2 ? 'enabled' : 'disabled' }}
            </a-tag>
          </template>

          <template v-if="route2">
            <div class="section-block">
              <h3>Fault Signature</h3>
              <div class="channel-list">
                <div
                  v-for="channel in route2.fault_signature.top_channels"
                  :key="channel.entity_id"
                  class="channel-card"
                >
                  <div class="channel-card__rank">#{{ channel.rank }}</div>
                  <div class="channel-card__body">
                    <strong>{{ channel.name }}</strong>
                    <code>{{ channel.entity_id }}</code>
                  </div>
                  <div class="channel-card__score">{{ formatScore(channel.contribution) }}</div>
                </div>
              </div>
            </div>

            <div class="section-block">
              <h3>Ranked Candidates</h3>
              <div v-if="route2.ranked_candidates.length" class="candidate-list">
                <div
                  v-for="candidate in route2.ranked_candidates"
                  :key="candidate.candidate_id"
                  :id="feedbackAnchorId('route2-candidate', candidate.candidate_id)"
                  class="candidate-card"
                  :class="{ 'candidate-card--active': focusedCandidateIds.has(candidate.candidate_id) }"
                >
                  <div class="candidate-card__head">
                    <div>
                      <strong>#{{ candidate.rank }} {{ candidate.candidate_name }}</strong>
                      <p>
                        {{ candidate.candidate_type }} / {{ candidate.candidate_role }}
                      </p>
                    </div>
                    <a-space wrap>
                      <a-tag color="arcoblue">
                        root {{ formatScore(candidate.root_score) }}
                      </a-tag>
                      <a-tag color="orangered">
                        rank {{ formatScore(candidate.ranking_score) }}
                      </a-tag>
                    </a-space>
                  </div>

                  <div class="focus-actions">
                    <a-button
                      :disabled="!canOpenGraphs"
                      size="mini"
                      @click="focusRoute2Candidate(candidate, 'graphs')"
                    >
                      高亮候选
                    </a-button>
                    <a-button
                      size="mini"
                      :disabled="!candidate.support_evidence_ids.length"
                      @click="focusRoute2Candidate(candidate, 'evidence')"
                    >
                      查看证据
                    </a-button>
                  </div>

                  <div class="feedback-toolbar">
                    <a-tag
                      :color="
                        feedbackColor(feedbackVerdict('route2-candidate', candidate.candidate_id))
                      "
                    >
                      {{ feedbackLabel(feedbackVerdict('route2-candidate', candidate.candidate_id)) }}
                    </a-tag>
                    <a-tag
                      v-if="feedbackNote('route2-candidate', candidate.candidate_id)"
                      color="gold"
                    >
                      已备注
                    </a-tag>
                    <a-space wrap>
                      <a-button
                        size="mini"
                        status="success"
                        :type="
                          feedbackVerdict('route2-candidate', candidate.candidate_id) === 'accepted'
                            ? 'primary'
                            : 'outline'
                        "
                        @click="toggleFeedback('route2-candidate', candidate.candidate_id, 'accepted')"
                      >
                        接受
                      </a-button>
                      <a-button
                        size="mini"
                        status="danger"
                        :type="
                          feedbackVerdict('route2-candidate', candidate.candidate_id) === 'rejected'
                            ? 'primary'
                            : 'outline'
                        "
                        @click="toggleFeedback('route2-candidate', candidate.candidate_id, 'rejected')"
                      >
                        驳回
                      </a-button>
                    </a-space>
                  </div>

                  <a-textarea
                    :model-value="
                      feedbackNoteDrafts[feedbackKey('route2-candidate', candidate.candidate_id)] ??
                      feedbackNote('route2-candidate', candidate.candidate_id)
                    "
                    :auto-size="{ minRows: 2, maxRows: 4 }"
                    placeholder="记录该候选的接受依据、排除原因或后续跟进建议；失焦后自动保存。"
                    @update:model-value="
                      (value) =>
                        setFeedbackNoteDraft(
                          'route2-candidate',
                          candidate.candidate_id,
                          String(value ?? ''),
                        )
                    "
                    @blur="commitFeedbackNote('route2-candidate', candidate.candidate_id)"
                  />

                  <div class="candidate-grid">
                    <div class="candidate-metric">
                      <span>Seed</span>
                      <strong>{{ candidate.seed_variable_id }}</strong>
                    </div>
                    <div class="candidate-metric">
                      <span>Coverage</span>
                      <strong>{{ formatScore(candidate.covered_contribution_mass) }}</strong>
                    </div>
                    <div class="candidate-metric">
                      <span>Entropy</span>
                      <strong>{{ formatScore(candidate.pattern_entropy) }}</strong>
                    </div>
                    <div class="candidate-metric">
                      <span>Adjustment</span>
                      <strong>{{ formatScore(candidate.ranking_adjustment) }}</strong>
                    </div>
                  </div>

                  <div class="subsection">
                    <div class="subsection__label">Top Affected Variables</div>
                    <div class="tag-wall">
                      <a-tag
                        v-for="variable in candidate.top_affected_variables"
                        :key="variable.entity_id"
                        color="grayblue"
                      >
                        {{ variable.name }} / {{ formatScore(variable.propagated_score) }}
                      </a-tag>
                    </div>
                  </div>

                  <div class="subsection">
                    <div class="subsection__label">Support Evidence</div>
                    <div class="tag-wall">
                      <button
                        v-for="obsId in candidate.support_evidence_ids"
                        :key="obsId"
                        class="support-link"
                        :class="{ 'support-link--active': highlightedObservationIds.has(obsId) }"
                        type="button"
                        @click="openObservation(obsId)"
                      >
                        {{ obsId }}
                      </button>
                    </div>
                  </div>

                  <div class="subsection">
                    <div class="subsection__label">Support Paths</div>
                    <div class="support-paths">
                      <div
                        v-for="pathLine in supportPathSummary(candidate)"
                        :key="pathLine"
                        class="support-paths__item"
                      >
                        {{ pathLine }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <a-empty v-else description="当前 case 没有 route2 根因候选" />
            </div>
          </template>

          <a-empty v-else description="当前 case 未启用路线 2" />
        </a-card>
      </div>

      <a-card
        v-if="crossSignals.length || activeCase.analysis.notes.length"
        class="glass-card"
        :bordered="false"
      >
        <template #title>Cross Route Signals & Notes</template>

        <div class="bottom-layout">
          <div v-if="crossSignals.length" class="section-block">
            <h3>Cross Route Signals</h3>
            <div class="signal-list">
              <div
                v-for="signal in crossSignals"
                :key="signal.candidate_id"
                class="signal-card"
                :class="{
                  'signal-card--active':
                    focusedCandidateIds.has(signal.candidate_id) ||
                    signal.route1_path_ids.some((pathId) => focusedPathIds.has(pathId)),
                }"
              >
                <strong>{{ signal.candidate_name }}</strong>
                <p>{{ signal.candidate_id }}</p>
                <div class="focus-actions">
                  <a-button
                    :disabled="!canOpenGraphs"
                    size="mini"
                    @click="focusCrossSignal(signal, 'graphs')"
                  >
                    联动图谱
                  </a-button>
                  <a-button size="mini" @click="focusCrossSignal(signal, 'evidence')">
                    联动证据
                  </a-button>
                </div>
                <div class="tag-wall">
                  <a-tag color="arcoblue">
                    route2 rank {{ signal.route2_rank ?? 'n/a' }}
                  </a-tag>
                  <a-tag
                    v-for="pathId in signal.route1_path_ids"
                    :key="pathId"
                    color="grayblue"
                  >
                    {{ pathId }}
                  </a-tag>
                </div>
              </div>
            </div>
          </div>

          <div class="section-block">
            <h3>Runtime Notes</h3>
            <div class="note-list">
              <div
                v-for="note in activeCase.analysis.notes"
                :key="note"
                class="note-item"
              >
                {{ note }}
              </div>
            </div>
          </div>
        </div>
      </a-card>
    </template>
  </div>
</template>

<style scoped>
.reasoning-workbench {
  gap: 18px;
}

.reasoning-toolbar {
  display: grid;
  gap: 18px;
}

.toolbar-block {
  display: grid;
  gap: 10px;
}

.toolbar-block__label {
  color: var(--kg-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.toolbar-note {
  padding: 14px 16px;
  border: 1px solid rgba(15, 139, 141, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.58);
  line-height: 1.7;
}

.reasoning-metrics {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  padding: 16px 18px;
  border: 1px solid var(--kg-line);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 10px 32px rgba(12, 31, 43, 0.06);
}

.metric-card__label {
  color: var(--kg-muted);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.metric-card__value {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 700;
}

.workspace-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.workspace-focus {
  margin-top: 14px;
}

.workspace-note {
  margin: 14px 0 0;
  color: var(--kg-muted);
  line-height: 1.7;
}

.feedback-summary-list {
  display: grid;
  gap: 12px;
}

.feedback-summary-card {
  padding: 16px 18px;
  border: 1px solid rgba(15, 139, 141, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.58);
}

.feedback-summary-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.feedback-summary-card__content {
  display: grid;
  gap: 10px;
}

.feedback-summary-card__content p {
  margin: 0;
  color: var(--kg-muted);
  line-height: 1.6;
}

.feedback-summary-card__meta {
  margin-top: 12px;
  color: var(--kg-muted);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.feedback-summary-card__note {
  margin: 12px 0 0;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(12, 31, 43, 0.04);
  line-height: 1.7;
}

.route-layout {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.whatif-layout {
  display: grid;
  gap: 14px;
}

.whatif-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.whatif-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.whatif-diff-list {
  display: grid;
  gap: 10px;
}

.whatif-diff-item {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(12, 31, 43, 0.04);
}

.whatif-diff-item__label {
  color: var(--kg-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.whatif-diff-item__values {
  display: grid;
  gap: 4px;
}

.whatif-diff-item__values span {
  color: var(--kg-muted);
  text-decoration: line-through;
}

.whatif-diff-item__values strong {
  font-size: 15px;
}

.route-metric-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.route-metric {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border: 1px solid rgba(18, 35, 47, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.54);
}

.route-metric span {
  color: var(--kg-muted);
  font-size: 12px;
}

.route-metric strong {
  font-size: 20px;
}

.section-block {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.section-block h3 {
  margin: 0;
  font-size: 18px;
}

.table-shell {
  overflow: auto;
}

.workbench-table {
  width: 100%;
  min-width: 640px;
  border-collapse: collapse;
}

.workbench-table th,
.workbench-table td {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(18, 35, 47, 0.08);
  text-align: left;
  vertical-align: top;
}

.workbench-table thead th {
  color: var(--kg-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.path-list,
.candidate-list,
.correction-list,
.signal-list,
.note-list,
.channel-list {
  display: grid;
  gap: 12px;
}

.path-card,
.candidate-card,
.correction-card,
.signal-card,
.note-item {
  padding: 14px 16px;
  border: 1px solid rgba(15, 139, 141, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.58);
}

.path-card--active,
.candidate-card--active,
.signal-card--active {
  border-color: rgba(15, 139, 141, 0.42);
  box-shadow: 0 16px 34px rgba(15, 139, 141, 0.12);
}

.path-card__head,
.candidate-card__head,
.correction-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.path-card__head p,
.candidate-card__head p,
.correction-card__head p,
.signal-card p {
  margin: 8px 0 0;
  color: var(--kg-muted);
  line-height: 1.6;
}

.correction-card__body {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 14px;
}

.feedback-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
}

.focus-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.tag-wall {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.support-link {
  padding: 7px 10px;
  border: 1px solid rgba(18, 35, 47, 0.12);
  border-radius: 999px;
  background: rgba(12, 31, 43, 0.04);
  color: var(--kg-text, #12232f);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.support-link:hover,
.support-link--active {
  transform: translateY(-1px);
  border-color: rgba(217, 119, 6, 0.42);
  box-shadow: 0 10px 20px rgba(217, 119, 6, 0.12);
}

.inline-code {
  overflow: auto;
  margin: 12px 0 0;
  padding: 14px;
  border-radius: 16px;
  background: rgba(12, 31, 43, 0.92);
  color: #eff8f8;
  font-size: 12px;
  line-height: 1.6;
}

.channel-card {
  display: grid;
  align-items: center;
  gap: 12px;
  grid-template-columns: 48px minmax(0, 1fr) 72px;
  padding: 14px 16px;
  border: 1px solid rgba(18, 35, 47, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.58);
}

.channel-card__rank {
  font-size: 22px;
  font-weight: 700;
}

.channel-card__body {
  display: grid;
  gap: 4px;
}

.channel-card__body code {
  color: var(--kg-muted);
}

.channel-card__score {
  text-align: right;
  font-size: 18px;
  font-weight: 700;
}

.candidate-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 14px;
}

.candidate-metric {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(12, 31, 43, 0.04);
}

.candidate-metric span,
.subsection__label {
  color: var(--kg-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.subsection {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.support-paths {
  display: grid;
  gap: 8px;
}

.support-paths__item {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(12, 31, 43, 0.04);
  font-family:
    'SFMono-Regular', 'SF Mono', 'Roboto Mono', 'Menlo', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.bottom-layout {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 1320px) {
  .route-layout,
  .bottom-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .reasoning-metrics,
  .workspace-grid,
  .route-metric-grid,
  .candidate-grid,
  .whatif-grid,
  .correction-card__body {
    grid-template-columns: 1fr 1fr;
  }

  .path-card__head,
  .candidate-card__head,
  .correction-card__head,
  .feedback-summary-card__head {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 720px) {
  .reasoning-metrics,
  .workspace-grid,
  .route-metric-grid,
  .candidate-grid,
  .whatif-grid,
  .correction-card__body {
    grid-template-columns: 1fr;
  }

  .channel-card {
    grid-template-columns: 1fr;
  }

  .channel-card__score {
    text-align: left;
  }
}
</style>
