import { computed, reactive, watch } from 'vue'
import { DEFAULT_BACKEND, workbenchApi, apiConnection, type GraphSummary, type Reasoner, type DemoLibrary, type WorkTask, type AnalysisSummary } from '@/api/workbench'

const SETTINGS_KEY = 'rootlens-workbench-v2'
interface Settings { baseUrl: string; graphId: string; analysisId: string }
function readSettings(): Settings {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? '{}')
    return { baseUrl: saved.baseUrl || DEFAULT_BACKEND, graphId: saved.graphId || '', analysisId: saved.analysisId || '' }
  } catch { return { baseUrl: DEFAULT_BACKEND, graphId: '', analysisId: '' } }
}
const saved = readSettings()
export const workspace = reactive({
  baseUrl: saved.baseUrl, graphId: saved.graphId, analysisId: saved.analysisId,
  graphs: [] as GraphSummary[], reasoners: [] as Reasoner[], demos: { demos: [], samples: [] } as DemoLibrary,
  tasks: [] as WorkTask[], analyses: [] as AnalysisSummary[], connected: false, loading: false, error: '',
  notice: '',
})
watch([() => apiConnection.available, () => apiConnection.error], ([available, error]) => {
  workspace.connected = available
  if (!available && error) workspace.error = error
  else if (available) workspace.error = ''
})
export const api = () => workbenchApi(workspace.baseUrl)
export const currentGraph = computed(() => workspace.graphs.find((g) => g.graph_id === workspace.graphId) ?? null)
export function persistSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({ baseUrl: workspace.baseUrl, graphId: workspace.graphId, analysisId: workspace.analysisId }))
}
export function selectGraph(id: string) { workspace.graphId = id; persistSettings() }
export function selectAnalysis(id: string) { workspace.analysisId = id; persistSettings() }
export function setBackend(url: string) { workspace.baseUrl = url.replace(/\/+$/, ''); persistSettings() }
export async function refreshGraphs() {
  workspace.graphs = (await api().graphs()).graphs
  if (workspace.graphId && !workspace.graphs.some((g) => g.graph_id === workspace.graphId)) selectGraph('')
}
export async function refreshAnalyses() { workspace.analyses = (await api().analyses()).runs }
export async function refreshTasks() { workspace.tasks = (await api().tasks()).tasks }
export function rememberTask(task: WorkTask) {
  workspace.tasks = [task, ...workspace.tasks.filter((t) => t.task_id !== task.task_id)].slice(0, 50)
}
let refreshing: Promise<void> | null = null
export function refreshWorkspace(): Promise<void> {
  if (refreshing) return refreshing
  refreshing = (async () => {
    workspace.loading = true; workspace.error = ''
    try {
      const [graphs, reasoners, demos, tasks, analyses] = await Promise.all([
        api().graphs(), api().reasoners(), api().demos(), api().tasks(), api().analyses(),
      ])
      workspace.graphs = graphs.graphs; workspace.reasoners = reasoners.reasoners
      workspace.demos = demos; workspace.tasks = tasks.tasks; workspace.analyses = analyses.runs
      workspace.connected = true
      if (workspace.graphId && !graphs.graphs.some((g) => g.graph_id === workspace.graphId)) selectGraph('')
    } catch (error) {
      workspace.connected = false; workspace.error = error instanceof Error ? error.message : String(error)
    } finally { workspace.loading = false; refreshing = null }
  })()
  return refreshing
}
