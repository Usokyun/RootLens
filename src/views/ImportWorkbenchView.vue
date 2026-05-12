<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import {
  buildAnalysisWorkspaceScope,
  getAnalysisWorkspaceEventName,
  loadAnalysisWorkspace,
  type AnalysisWorkspaceStorage,
} from '@/services/analysis-workspace'
import {
  getAnalysisFocusEventName,
  loadAnalysisFocus,
  type AnalysisFocusState,
} from '@/services/analysis-focus'
import { buildLocalImportResult, type LocalImportSummary } from '@/services/browser-runtime'
import {
  buildCurrentSessionExport,
  buildSessionExportBaseName,
  collectCurrentSessionArtifacts,
  downloadJsonFile,
  restoreSessionImportFile,
} from '@/services/session-export'
import {
  clearImportedSession,
  getImportedSessionSummary,
  getLocalSessionEventName,
  getLocalSessionMeta,
  saveImportedSession,
} from '@/services/rootlens-data'
import { buildWorkflowSnapshot, type WorkflowStageName } from '@/services/workflow'

type ImportPresetId = 'replay' | 'graphs' | 'evidence' | 'restore'
type ExportActionId = 'graphs' | 'runtime' | 'workspace' | 'bundle'
type NextActionKind = 'open-graphs' | 'open-evidence' | 'go-reasoning'

interface ImportPresetCard {
  id: ImportPresetId
  title: string
  buttonLabel: string
  description: string
  note: string
  supportTags: string[]
  disabled: boolean
  recommended: boolean
}

const router = useRouter()

const loading = ref(false)
const loadingPresetId = ref<ImportPresetId | null>(null)
const exportingId = ref<ExportActionId | null>(null)
const errorMessage = ref('')
const noticeMessage = ref('')
const warningMessages = ref<string[]>([])
const selectedFiles = shallowRef<File[]>([])
const importSummary = shallowRef<LocalImportSummary | null>(null)
const sessionMeta = ref(getLocalSessionMeta())
const lastImportLabel = ref('')
const workspaceState = shallowRef<AnalysisWorkspaceStorage | null>(null)
const focusState = shallowRef<AnalysisFocusState | null>(null)

const replayInput = ref<HTMLInputElement | null>(null)
const graphInput = ref<HTMLInputElement | null>(null)
const evidenceInput = ref<HTMLInputElement | null>(null)
const restoreInput = ref<HTMLInputElement | null>(null)

const detectedFiles = computed(() => importSummary.value?.detectedFiles ?? [])
const workflow = computed(() => buildWorkflowSnapshot(sessionMeta.value, importSummary.value))
const currentModeLabel = computed(() => workflow.value.modeLabel)
const datasetCountLabel = computed(() =>
  workflow.value.datasetCount === null ? 'demo' : String(workflow.value.datasetCount),
)
const caseCountLabel = computed(() =>
  workflow.value.caseCount === null ? 'demo' : String(workflow.value.caseCount),
)
const currentScope = computed(() => buildAnalysisWorkspaceScope(sessionMeta.value))
const workspaceCaseCount = computed(() => workspaceState.value?.cases.length ?? 0)
const workspaceFeedbackCount = computed(() =>
  workspaceState.value?.cases.reduce((sum, item) => sum + item.feedback_items.length, 0) ?? 0,
)
const hasFocusSnapshot = computed(
  () =>
    Boolean(
      focusState.value?.focus_kind ||
        focusState.value?.active_case_id ||
        focusState.value?.active_dataset_id ||
        focusState.value?.selected_observation_id ||
        focusState.value?.selected_route1_path_ids.length ||
        focusState.value?.selected_route2_candidate_ids.length ||
        focusState.value?.highlighted_node_ids.length ||
        focusState.value?.highlighted_edge_ids.length ||
        focusState.value?.highlighted_obs_ids.length,
    ),
)
const focusSummary = computed(() => {
  if (!hasFocusSnapshot.value || !focusState.value) {
    return 'empty'
  }

  return (
    focusState.value.focus_label ||
    focusState.value.active_case_id ||
    focusState.value.active_dataset_id ||
    'active'
  )
})
const sessionAssetRows = computed(() => [
  {
    label: '统一图谱',
    value: workflow.value.hasGraphs
      ? workflow.value.datasetCount === null
        ? 'demo graph'
        : `${workflow.value.datasetCount} dataset`
      : 'missing',
  },
  {
    label: 'Runtime Case',
    value: workflow.value.hasCases
      ? workflow.value.caseCount === null
        ? 'demo case'
        : `${workflow.value.caseCount} case`
      : 'missing',
  },
  {
    label: 'Workspace',
    value: workspaceCaseCount.value
      ? `${workspaceCaseCount.value} case / ${workspaceFeedbackCount.value} feedback`
      : 'empty',
  },
  {
    label: 'Shared Focus',
    value: hasFocusSnapshot.value ? focusSummary.value : 'empty',
  },
])
const recommendedPresetId = computed<ImportPresetId | null>(() => {
  if (workflow.value.hasCases) {
    return null
  }

  return workflow.value.hasGraphs ? 'evidence' : 'graphs'
})
const canExportGraphs = computed(() => workflow.value.hasGraphs)
const canExportRuntime = computed(() => workflow.value.hasCases)
const canExportWorkspace = computed(() => {
  return Boolean(
    workspaceState.value?.cases.length ||
      focusState.value?.focus_kind ||
      focusState.value?.highlighted_node_ids.length ||
      focusState.value?.highlighted_edge_ids.length ||
      focusState.value?.highlighted_obs_ids.length,
  )
})

const nextAction = computed<{
  kind: NextActionKind
  route: WorkflowStageName
  label: string
  description: string
}>(() => {
  if (workflow.value.hasCases) {
    return {
      kind: 'go-reasoning',
      route: 'reasoning',
      label: '进入 RCA 分析',
      description: '当前会话已具备 case，可直接对比 route1 / route2 并执行 what-if。',
    }
  }

  if (workflow.value.hasGraphs) {
    return {
      kind: 'open-evidence',
      route: 'evidence',
      label: '追加 Evidence',
      description: '当前已经有统一图谱，下一步建议导入 evidence/case 文件生成或追加 runtime case。',
    }
  }

  return {
    kind: 'open-graphs',
    route: 'graphs',
    label: '导入图谱',
    description: '先导入 unified-graphs.json 或 nodes/edges 文件，启动浏览器端分析链路。',
  }
})

const importPresets = computed<ImportPresetCard[]>(() => [
  {
    id: 'replay',
    title: '1. 直接回放',
    buttonLabel: '导入完整会话',
    description:
      '`rootlens-runtime.json` + `unified-graphs.json` 一起导入，直接恢复完整图谱与 RCA 结果。',
    note:
      sessionMeta.value?.source === 'import'
        ? '适合用一组完整结果覆盖当前会话。'
        : '适合第一次进入系统时快速恢复完整链路。',
    supportTags: ['rootlens-runtime.json', 'unified-graphs.json'],
    disabled: false,
    recommended: recommendedPresetId.value === 'replay',
  },
  {
    id: 'graphs',
    title: '2. 本地构建图谱',
    buttonLabel: '导入图谱文件',
    description:
      'TEP 使用 `nodes.jsonl` + `edges.jsonl`，MVTec 使用 `nodes.csv` + `edges.csv` + 可选 reference 文件，浏览器本地生成统一图谱。',
    note: workflow.value.hasGraphs
      ? '导入后会替换当前图谱，并决定后续 Evidence 与 RCA 的分析基础。'
      : '这是主链路的第一步，完成后即可进入图谱检查或追加 Evidence。',
    supportTags: ['unified-graphs.json', 'nodes.jsonl', 'edges.jsonl', 'nodes.csv', 'edges.csv'],
    disabled: false,
    recommended: recommendedPresetId.value === 'graphs',
  },
  {
    id: 'evidence',
    title: '3. 追加 Evidence',
    buttonLabel: '导入 Evidence / case',
    description:
      '在已有图谱基础上导入 `evidence*.json` 或 `case*.json`，浏览器本地组装 runtime case；重复导入时会按 `case_id` 增量新增或覆盖已有 case。',
    note: workflow.value.hasGraphs
      ? '适合图谱已就绪后持续追加新的 case，直接驱动后续 RCA 分析。'
      : '当前会话没有可用图谱，先执行图谱导入后再追加 Evidence。',
    supportTags: ['evidence*.json', 'case*.json'],
    disabled: !workflow.value.hasGraphs,
    recommended: recommendedPresetId.value === 'evidence',
  },
  {
    id: 'restore',
    title: '4. 恢复导出结果',
    buttonLabel: '导入 Bundle / Workspace',
    description:
      '支持导入 `rootlens-session-export.v1` 或 `rootlens-analysis-workspace-export.v1`，恢复导出的完整会话或 analyst workspace。',
    note:
      'bundle 会恢复 graphs/runtime/workspace/focus；workspace export 会把草稿、反馈和共享焦点恢复到当前会话。',
    supportTags: ['rootlens-session-export.v1', 'rootlens-analysis-workspace-export.v1'],
    disabled: false,
    recommended: false,
  },
])

function refreshSessionMeta() {
  sessionMeta.value = getLocalSessionMeta()
  importSummary.value = getImportedSessionSummary()
  refreshAnalysisState()
}

function refreshAnalysisState() {
  workspaceState.value = loadAnalysisWorkspace(currentScope.value)
  focusState.value = loadAnalysisFocus(currentScope.value)
}

function presetLabel(presetId: ImportPresetId) {
  switch (presetId) {
    case 'replay':
      return '完整回放'
    case 'graphs':
      return '图谱导入'
    case 'evidence':
      return 'Evidence 追加'
    case 'restore':
      return '导出恢复'
  }
}

function openImportPreset(presetId: ImportPresetId) {
  switch (presetId) {
    case 'replay':
      replayInput.value?.click()
      break
    case 'graphs':
      graphInput.value?.click()
      break
    case 'evidence':
      evidenceInput.value?.click()
      break
    case 'restore':
      restoreInput.value?.click()
      break
  }
}

async function runImport(presetId: ImportPresetId, files: File[]) {
  selectedFiles.value = files
  errorMessage.value = ''
  noticeMessage.value = ''
  warningMessages.value = []

  if (!files.length) {
    return
  }

  loading.value = true
  loadingPresetId.value = presetId

  try {
    const label = presetLabel(presetId)
    lastImportLabel.value = label

    if (presetId === 'restore') {
      if (files.length !== 1) {
        throw new Error('恢复导出结果时请只选择一个 bundle 或 workspace 文件。')
      }

      const result = await restoreSessionImportFile(files[0] as File)
      refreshSessionMeta()
      noticeMessage.value = result.summary
      warningMessages.value = result.warnings
      return
    }

    const result = await buildLocalImportResult(files)

    saveImportedSession({
      graphs: result.graphs,
      runtime: result.runtime,
      summary: `${label}：${result.summary.datasets.length} dataset(s), ${result.summary.cases.length} case(s)`,
      importSummary: result.summary,
    })

    importSummary.value = result.summary
    refreshSessionMeta()

    noticeMessage.value =
      `${label}完成：当前会话包含 ${result.summary.datasets.length} 个 dataset，` +
      `${result.summary.cases.length} 个 case。`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '本地导入失败'
  } finally {
    loading.value = false
    loadingPresetId.value = null
  }
}

async function handlePresetSelection(presetId: ImportPresetId, event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])

  try {
    await runImport(presetId, files)
  } finally {
    input.value = ''
  }
}

function useBundledDemo() {
  clearImportedSession()
  importSummary.value = null
  selectedFiles.value = []
  errorMessage.value = ''
  noticeMessage.value = '已切回内置示例数据。'
  warningMessages.value = []
  lastImportLabel.value = ''
  refreshSessionMeta()
}

function goToView(name: 'graphs' | 'evidence' | 'reasoning') {
  void router.push({
    name,
  })
}

function goToNextAction() {
  switch (nextAction.value.kind) {
    case 'open-graphs':
      openImportPreset('graphs')
      return
    case 'open-evidence':
      openImportPreset('evidence')
      return
    case 'go-reasoning':
      void router.push({
        name: nextAction.value.route,
      })
  }
}

async function runExport(
  actionId: ExportActionId,
  exporter: () => Promise<string>,
) {
  exportingId.value = actionId
  errorMessage.value = ''
  noticeMessage.value = ''
  warningMessages.value = []

  try {
    noticeMessage.value = await exporter()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '会话导出失败'
  } finally {
    exportingId.value = null
  }
}

function buildExportFileName(suffix: string) {
  return `${buildSessionExportBaseName(sessionMeta.value)}-${suffix}.json`
}

function exportGraphs() {
  void runExport('graphs', async () => {
    const artifacts = await collectCurrentSessionArtifacts()

    if (!artifacts.graphs) {
      throw new Error('当前会话没有可导出的统一图谱。')
    }

    downloadJsonFile(buildExportFileName('unified-graphs'), artifacts.graphs)
    return '已导出当前统一图谱。'
  })
}

function exportRuntime() {
  void runExport('runtime', async () => {
    const artifacts = await collectCurrentSessionArtifacts()

    if (!artifacts.runtime) {
      throw new Error('当前会话没有可导出的 runtime case。')
    }

    downloadJsonFile(buildExportFileName('rootlens-runtime'), artifacts.runtime)
    return '已导出当前 runtime bundle。'
  })
}

function exportWorkspace() {
  void runExport('workspace', async () => {
    const artifacts = await collectCurrentSessionArtifacts()

    if (!artifacts.analysisWorkspace && !artifacts.analysisFocus) {
      throw new Error('当前会话没有可导出的 analyst workspace 或 focus 状态。')
    }

    downloadJsonFile(buildExportFileName('analysis-workspace'), {
      schema_version: 'rootlens-analysis-workspace-export.v1',
      exported_at: new Date().toISOString(),
      session_meta: artifacts.sessionMeta,
      analysis_workspace: artifacts.analysisWorkspace,
      analysis_focus: artifacts.analysisFocus,
    })

    return '已导出当前 analyst workspace。'
  })
}

function exportBundle() {
  void runExport('bundle', async () => {
    const payload = await buildCurrentSessionExport()

    downloadJsonFile(buildExportFileName('session-bundle'), payload)
    return '已导出当前完整会话 bundle。'
  })
}

function handleSessionChange() {
  refreshSessionMeta()
}

function handleWorkspaceChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (
    customEvent.detail?.sessionScope &&
    customEvent.detail.sessionScope !== currentScope.value
  ) {
    return
  }

  refreshAnalysisState()
}

function handleFocusChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (
    customEvent.detail?.sessionScope &&
    customEvent.detail.sessionScope !== currentScope.value
  ) {
    return
  }

  refreshAnalysisState()
}

onMounted(() => {
  refreshSessionMeta()
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
  <div class="page-stack import-workbench">
    <input
      ref="replayInput"
      class="sr-only"
      accept=".json,application/json"
      type="file"
      multiple
      @change="(event) => handlePresetSelection('replay', event)"
    />
    <input
      ref="graphInput"
      class="sr-only"
      accept=".json,.jsonl,.csv,application/json,text/csv"
      type="file"
      multiple
      @change="(event) => handlePresetSelection('graphs', event)"
    />
    <input
      ref="evidenceInput"
      class="sr-only"
      accept=".json,application/json"
      type="file"
      multiple
      @change="(event) => handlePresetSelection('evidence', event)"
    />
    <input
      ref="restoreInput"
      class="sr-only"
      accept=".json,application/json"
      type="file"
      @change="(event) => handlePresetSelection('restore', event)"
    />

    <section class="hero-panel">
      <div class="hero-panel__content">
        <div>
          <a-space wrap>
            <a-tag color="arcoblue">Frontend Only</a-tag>
            <a-tag color="green">Graph Build</a-tag>
            <a-tag color="gold">Evidence Runtime</a-tag>
            <a-tag color="orangered">RCA Visualization</a-tag>
          </a-space>
          <h2 class="hero-panel__title">RootLens 可视化系统入口</h2>
          <p class="hero-panel__body">
            当前系统只保留主链路：导入数据、构建统一图谱、导入 Evidence、执行 RCA 分析。
            全部过程都在浏览器本地完成，不依赖后端。
          </p>
        </div>

        <div class="hero-panel__brief">
          <div class="brief-item">
            <div class="brief-item__label">当前数据源</div>
            <div class="brief-item__value">
              {{ sessionMeta?.source === 'import' ? '本地导入' : '内置示例' }}
            </div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">当前模式</div>
            <div class="brief-item__value">{{ currentModeLabel }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">Datasets / Cases</div>
            <div class="brief-item__value">{{ datasetCountLabel }} / {{ caseCountLabel }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">最近更新时间</div>
            <div class="brief-item__value">{{ sessionMeta?.updatedAt ?? '未导入' }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">最近摘要</div>
            <div class="brief-item__value">{{ sessionMeta?.summary ?? '未导入本地会话' }}</div>
          </div>
        </div>
      </div>
    </section>

    <a-card class="glass-card" :bordered="false">
      <div class="import-actions">
        <a-space wrap>
          <a-button
            type="primary"
            :loading="loading && loadingPresetId === 'graphs'"
            @click="openImportPreset('graphs')"
          >
            导入图谱
          </a-button>
          <a-button
            :disabled="!workflow.hasGraphs"
            :loading="loading && loadingPresetId === 'evidence'"
            @click="openImportPreset('evidence')"
          >
            追加 Evidence
          </a-button>
          <a-button
            type="outline"
            :loading="loading && loadingPresetId === 'replay'"
            @click="openImportPreset('replay')"
          >
            直接回放
          </a-button>
          <a-button @click="useBundledDemo">切回内置示例</a-button>
          <a-button type="outline" @click="goToView('graphs')">图谱可视化</a-button>
          <a-button type="outline" @click="goToView('evidence')">Evidence 审查</a-button>
          <a-button type="outline" @click="goToView('reasoning')">RCA 分析</a-button>
        </a-space>

        <div class="import-next">
          <div>
            <div class="import-next__label">建议下一步</div>
            <div class="import-next__title">{{ nextAction.label }}</div>
            <p class="import-next__body">{{ nextAction.description }}</p>
          </div>
          <a-button type="primary" @click="goToNextAction">
            {{ nextAction.label }}
          </a-button>
        </div>
      </div>
    </a-card>

    <div class="page-grid page-grid--2 import-mode-grid">
      <a-card class="glass-card" :bordered="false" title="阶段化导入">
        <div class="mode-list">
          <article
            v-for="preset in importPresets"
            :key="preset.id"
            class="mode-card"
            :class="{ 'mode-card--recommended': preset.recommended }"
          >
            <div class="mode-card__head">
              <div class="mode-card__title">{{ preset.title }}</div>
              <a-tag v-if="preset.recommended" color="green">推荐</a-tag>
            </div>

            <p class="mode-card__body">{{ preset.description }}</p>

            <div class="tag-wall">
              <a-tag
                v-for="tag in preset.supportTags"
                :key="`${preset.id}:${tag}`"
                color="grayblue"
              >
                {{ tag }}
              </a-tag>
            </div>

            <div class="mode-card__actions">
              <p class="mode-card__note">{{ preset.note }}</p>
              <a-button
                :disabled="preset.disabled"
                :loading="loading && loadingPresetId === preset.id"
                :type="preset.recommended ? 'primary' : 'outline'"
                @click="openImportPreset(preset.id)"
              >
                {{ preset.buttonLabel }}
              </a-button>
            </div>
          </article>
        </div>
      </a-card>

      <a-card class="glass-card" :bordered="false" title="当前链路状态">
        <div class="result-stack">
          <div class="result-row">
            <span>Session</span>
            <strong>{{ workflow.sessionLabel }}</strong>
          </div>
          <div class="result-row">
            <span>Mode</span>
            <strong>{{ currentModeLabel }}</strong>
          </div>
          <div class="result-row">
            <span>Datasets</span>
            <strong>{{ datasetCountLabel }}</strong>
          </div>
          <div class="result-row">
            <span>Cases</span>
            <strong>{{ caseCountLabel }}</strong>
          </div>
          <div class="result-row">
            <span>Warnings</span>
            <strong>{{ workflow.warningCount }}</strong>
          </div>
          <div class="result-row">
            <span>Recent Import</span>
            <strong>{{ lastImportLabel || 'none' }}</strong>
          </div>

          <div class="sub-block">
            <div class="sub-block__label">当前会话内容</div>
            <div class="result-stack">
              <div
                v-for="item in sessionAssetRows"
                :key="item.label"
                class="result-row"
              >
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </div>
        </div>
      </a-card>
    </div>

    <a-alert v-if="noticeMessage" type="success" show-icon :content="noticeMessage" />
    <a-alert
      v-for="warning in warningMessages"
      :key="warning"
      type="warning"
      show-icon
      :content="warning"
    />
    <a-alert v-if="errorMessage" type="error" show-icon :content="errorMessage" />

    <div class="page-grid page-grid--2">
      <a-card class="glass-card" :bordered="false" title="已选择文件">
        <template #extra>
          <span class="panel-extra">{{ lastImportLabel || '最近动作' }}</span>
        </template>

        <div v-if="selectedFiles.length" class="directory-list">
          <article
            v-for="file in selectedFiles"
            :key="`${file.name}:${file.size}`"
            class="directory-card"
          >
            <div class="directory-card__path">{{ file.webkitRelativePath || file.name }}</div>
            <p class="directory-card__purpose">
              {{ file.type || 'text/plain' }} · {{ file.size }} bytes
            </p>
          </article>
        </div>
        <a-empty v-else description="尚未选择本地文件" />
      </a-card>

      <a-card class="glass-card" :bordered="false" title="本次导入结果">
        <template v-if="importSummary">
          <div class="result-stack">
            <div class="result-row">
              <span>导入模式</span>
              <strong>{{ importSummary.sourceMode }}</strong>
            </div>
            <div class="result-row">
              <span>数据集数量</span>
              <strong>{{ importSummary.datasets.length }}</strong>
            </div>
            <div class="result-row">
              <span>案例数量</span>
              <strong>{{ importSummary.cases.length }}</strong>
            </div>

            <div class="sub-block">
              <div class="sub-block__label">Datasets</div>
              <div class="directory-list">
                <article
                  v-for="dataset in importSummary.datasets"
                  :key="dataset.id"
                  class="directory-card"
                >
                  <div class="directory-card__path">{{ dataset.label }}</div>
                  <p class="directory-card__purpose">
                    {{ dataset.id }} · {{ dataset.nodeCount }} nodes · {{ dataset.edgeCount }} edges
                  </p>
                </article>
              </div>
            </div>

            <div class="sub-block">
              <div class="sub-block__label">Cases</div>
              <div class="directory-list">
                <article
                  v-for="caseItem in importSummary.cases"
                  :key="caseItem.caseId"
                  class="directory-card"
                >
                  <div class="directory-card__path">{{ caseItem.caseLabel }}</div>
                  <p class="directory-card__purpose">{{ caseItem.caseId }} · {{ caseItem.dataset }}</p>
                </article>
              </div>
            </div>

            <a-alert
              v-for="warning in importSummary.warnings"
              :key="warning"
              type="warning"
              show-icon
              :content="warning"
            />
          </div>
        </template>

        <a-empty v-else description="尚未执行本地导入" />
      </a-card>
    </div>

    <a-card class="glass-card" :bordered="false" title="会话导出">
      <div class="export-grid">
        <article class="mode-card">
          <div class="mode-card__head">
            <div class="mode-card__title">导出统一图谱</div>
            <a-tag :color="canExportGraphs ? 'green' : 'grayblue'">
              {{ canExportGraphs ? 'ready' : 'unavailable' }}
            </a-tag>
          </div>
          <p class="mode-card__body">
            导出当前会话实际在用的 `unified-graphs.json`，可用于后续重放或共享图谱结构。
          </p>
          <div class="mode-card__actions">
            <p class="mode-card__note">适用于 graphs-only、graphs+evidence 与 demo 模式。</p>
            <a-button
              :disabled="!canExportGraphs"
              :loading="exportingId === 'graphs'"
              type="outline"
              @click="exportGraphs"
            >
              导出图谱
            </a-button>
          </div>
        </article>

        <article class="mode-card">
          <div class="mode-card__head">
            <div class="mode-card__title">导出 Runtime</div>
            <a-tag :color="canExportRuntime ? 'green' : 'grayblue'">
              {{ canExportRuntime ? 'ready' : 'unavailable' }}
            </a-tag>
          </div>
          <p class="mode-card__body">
            导出当前 case 集合和推理结果，生成 `rootlens-runtime.json` 用于完整回放。
          </p>
          <div class="mode-card__actions">
            <p class="mode-card__note">当 Evidence 已生成 runtime case 时可用。</p>
            <a-button
              :disabled="!canExportRuntime"
              :loading="exportingId === 'runtime'"
              type="outline"
              @click="exportRuntime"
            >
              导出 Runtime
            </a-button>
          </div>
        </article>

        <article class="mode-card">
          <div class="mode-card__head">
            <div class="mode-card__title">导出 Analyst Workspace</div>
            <a-tag :color="canExportWorkspace ? 'green' : 'grayblue'">
              {{ canExportWorkspace ? 'ready' : 'empty' }}
            </a-tag>
          </div>
          <p class="mode-card__body">
            导出当前会话的 draft case、人工反馈与共享分析焦点，便于保留分析过程。
          </p>
          <div class="mode-card__actions">
            <p class="mode-card__note">适用于 what-if、接受/驳回和跨页联动状态备份。</p>
            <a-button
              :disabled="!canExportWorkspace"
              :loading="exportingId === 'workspace'"
              type="outline"
              @click="exportWorkspace"
            >
              导出 Workspace
            </a-button>
          </div>
        </article>

        <article class="mode-card">
          <div class="mode-card__head">
            <div class="mode-card__title">导出完整会话 Bundle</div>
            <a-tag color="arcoblue">full</a-tag>
          </div>
          <p class="mode-card__body">
            一次导出 session meta、graphs、runtime、workspace 与 focus，便于迁移或归档。
          </p>
          <div class="mode-card__actions">
            <p class="mode-card__note">适用于演示归档、问题复现和离线交接。</p>
            <a-button
              :loading="exportingId === 'bundle'"
              type="primary"
              @click="exportBundle"
            >
              导出 Bundle
            </a-button>
          </div>
        </article>
      </div>
    </a-card>

    <a-card
      v-if="detectedFiles.length"
      class="glass-card"
      :bordered="false"
      title="检测到的文件路径"
    >
      <div class="tag-wall">
        <a-tag v-for="item in detectedFiles" :key="item" color="grayblue">{{ item }}</a-tag>
      </div>
    </a-card>
  </div>
</template>

<style scoped>
.sr-only {
  display: none;
}

.import-workbench {
  gap: 18px;
}

.import-actions {
  display: grid;
  gap: 18px;
}

.import-next {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 16px;
  border: 1px solid rgba(15, 139, 141, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.58);
}

.import-next__label,
.mode-card__title {
  color: var(--kg-accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.import-next__title {
  margin-top: 10px;
  font-size: 22px;
  font-weight: 700;
}

.import-next__body,
.mode-card__body,
.mode-card__note {
  margin: 8px 0 0;
  color: var(--kg-muted);
  line-height: 1.7;
}

.import-mode-grid {
  align-items: stretch;
}

.mode-list,
.export-grid {
  display: grid;
  gap: 12px;
}

.mode-card {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(15, 139, 141, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.58);
}

.mode-card--recommended {
  border-color: rgba(15, 139, 141, 0.34);
  box-shadow: 0 16px 32px rgba(15, 139, 141, 0.1);
}

.mode-card__head,
.mode-card__actions,
.result-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mode-card__actions {
  align-items: flex-end;
}

.mode-card__note {
  margin: 0;
}

.result-stack {
  display: grid;
  gap: 14px;
}

.result-row {
  padding: 12px 14px;
  border: 1px solid rgba(18, 35, 47, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.52);
}

.result-row span,
.sub-block__label,
.panel-extra {
  color: var(--kg-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.panel-extra {
  font-weight: 600;
}

.sub-block {
  display: grid;
  gap: 10px;
}

@media (max-width: 1080px) {
  .mode-card__actions {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 900px) {
  .import-next,
  .mode-card__head,
  .result-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
