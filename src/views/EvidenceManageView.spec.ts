import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { DashboardBootstrap, RunDetail } from '@/api/contracts'
import { updateAppPreferences } from '@/services/app-preferences'
import { getWorkbenchState, updateWorkbenchState } from '@/services/workbench-state'
import EvidenceManageView from './EvidenceManageView.vue'

const { service } = vi.hoisted(() => ({
  service: { bootstrap: vi.fn(), listRuns: vi.fn(), getRun: vi.fn() },
}))
vi.mock('@/services/rootlens-service', () => ({ getRootLensService: () => service }))

const bootstrap: DashboardBootstrap = {
  status: 'ok',
  api_version: 'test',
  claim_boundary: 'candidate only',
  supported_datasets: ['tep'],
  supported_feedback_targets: [],
  supported_feedback_actions: [],
  upload_modes: [{ mode: 'records', label: '批量记录', description: '', accepted_extensions: ['.json'], required_fields: [] }],
  reasoning_profile_options: {},
  mvtec_model_presets: { default_preset: 'auto', presets: [] },
  recent_runs: [],
}
function runDetail(runId: string): RunDetail {
  return {
    run: { run_id: runId, created_at: '2026-11-11T00:00:00Z', mode: 'records', source_filename: '', top_k: 5, run_dir: '', status: 'completed', dataset: 'tep', case_count: 0, evidence_count: 0, label: runId, model_preset: null, model_backend: null },
    workflow_steps: [], claim_boundary: 'candidate only', evidence: null, evidence_summary: null,
    evidence_with_analysis: null, analysis: null, summary: null, cases: [], linked_entities: [],
    correction_candidates: [], top_k_paths: [], ranked_root_causes: [],
    path_graph: { paths: [], path_count: 0, node_count: 0, edge_count: 0 },
    source_edge_provenance: [], review_targets: [], artifacts: {}, visual_evidence: [],
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

let app: App | null = null
let host: HTMLElement | null = null

async function settle() {
  for (let index = 0; index < 8; index += 1) {
    await nextTick()
    await Promise.resolve()
  }
}

async function mountView() {
  host = document.createElement('div')
  document.body.append(host)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { render: () => null } }],
  })
  await router.push('/')
  app = createApp(EvidenceManageView)
  app.use(router)
  app.directive('control-label', {})
  for (const name of ['a-button-group', 'a-empty', 'a-form', 'a-form-item', 'a-input', 'a-input-number', 'a-input-search', 'a-drawer', 'a-spin', 'a-space', 'a-tabs', 'a-tab-pane', 'a-divider', 'a-collapse', 'a-collapse-item', 'a-tag', 'a-tooltip']) {
    app.component(name, defineComponent({
      inheritAttrs: false,
      setup: (_, { slots }) => () => h('div', slots.default?.()),
    }))
  }
  app.component('a-select', defineComponent({
    props: ['modelValue'], emits:['update:modelValue','change'],
    setup: (props, { slots, attrs, emit }) => () => h('select', { ...attrs, value: props.modelValue, onChange: (event: Event) => { const value=(event.target as HTMLSelectElement).value; emit('update:modelValue',value);emit('change',value) } }, slots.default?.()),
  }))
  app.component('a-option',defineComponent({props:['value','label'],setup: props=>()=>h('option',{value:props.value},String(props.label??props.value))}))
  app.component('a-alert', defineComponent({
    props: ['title'],
    setup: (props) => () => h('div', String(props.title ?? '')),
  }))
  app.component('a-button', defineComponent({
    setup: (_, { slots, attrs }) => () => h('button', attrs, slots.default?.()),
  }))
  app.component('a-modal', defineComponent({
    props: ['visible'],
    setup: (props, { slots }) => () => props.visible ? h('div', slots.default?.()) : null,
  }))
  app.mount(host)
  await settle()
}

beforeEach(() => {
  vi.clearAllMocks()
  updateAppPreferences({ dataSourceMode: 'backend' })
  service.bootstrap.mockResolvedValue(bootstrap)
  service.listRuns.mockResolvedValue([])
})
afterEach(() => {
  app?.unmount()
  app = null
  host?.remove()
  host = null
})

describe('Evidence workspace refresh triggers', () => {
  it('does not reload the workspace for a workbench storage event from another tab', async () => {
    await mountView()
    updateWorkbenchState({ selectedCaseId: 'case-other-tab' })
    const event = new Event('storage')
    Object.defineProperties(event, {
      key: { value: 'rootlens.workbench-state' },
      storageArea: { value: window.localStorage },
    })
    window.dispatchEvent(event)
    await settle()
    expect(service.bootstrap).toHaveBeenCalledTimes(1)
    expect(service.listRuns).toHaveBeenCalledTimes(1)
  })

  it('does not refetch data when only presentation preferences change', async () => {
    await mountView()
    updateAppPreferences({ showDebugPanels: true, enablePageEntranceMotion: false })
    await settle()
    expect(service.bootstrap).toHaveBeenCalledTimes(1)
  })

  it('does not refetch data for an unchanged backend selection', async () => {
    await mountView()
    updateAppPreferences({ dataSourceMode: 'backend' })
    await settle()
    expect(service.bootstrap).toHaveBeenCalledTimes(1)
  })

  it('refreshes once when the backend address actually changes', async () => {
    await mountView()
    updateAppPreferences({ apiBaseUrl: 'http://127.0.0.1:9001' })
    await settle()
    expect(service.bootstrap).toHaveBeenCalledTimes(2)
    expect(service.listRuns).toHaveBeenCalledTimes(2)
  })

  it('refreshes once when the data source actually changes', async () => {
    await mountView()
    updateAppPreferences({ dataSourceMode: 'mock' })
    await settle()
    expect(service.bootstrap).toHaveBeenCalledTimes(2)
  })

  it('does not let an older run response overwrite a newer selection', async () => {
    const old = deferred<RunDetail>()
    service.listRuns.mockResolvedValue([runDetail('old-run').run, runDetail('new-run').run])
    service.getRun.mockImplementation((id: string) => id === 'old-run' ? old.promise : Promise.resolve(runDetail(id)))
    await mountView()
    const select=host!.querySelector<HTMLSelectElement>('select[aria-label="分析记录"]')!
    select.value='new-run'; select.dispatchEvent(new Event('change'))
    await settle()
    expect(getWorkbenchState().selectedRunId).toBe('new-run')
    old.resolve(runDetail('old-run'))
    await settle()
    expect(getWorkbenchState().selectedRunId).toBe('new-run')
    expect(service.getRun).toHaveBeenCalledTimes(2)
  })

  it('does not show a stale request failure after a newer run has loaded', async () => {
    const old = deferred<RunDetail>()
    service.listRuns.mockResolvedValue([runDetail('old-run').run, runDetail('new-run').run])
    service.getRun.mockImplementation((id: string) => id === 'old-run' ? old.promise : Promise.resolve(runDetail(id)))
    await mountView()
    const select=host!.querySelector<HTMLSelectElement>('select[aria-label="分析记录"]')!
    select.value='new-run'; select.dispatchEvent(new Event('change'))
    await settle()
    old.reject(new Error('stale failure'))
    await settle()
    expect(host!.textContent).not.toContain('stale failure')
    expect(getWorkbenchState().selectedRunId).toBe('new-run')
  })

  it('does not publish a selection after the page has unmounted', async () => {
    const old = deferred<RunDetail>()
    service.listRuns.mockResolvedValue([runDetail('old-run').run])
    service.getRun.mockReturnValue(old.promise)
    await mountView()
    app!.unmount()
    app = null
    old.resolve(runDetail('old-run'))
    await settle()
    expect(getWorkbenchState().selectedRunId).toBeNull()
  })

  it('ignores an old workspace response after the backend changes', async () => {
    const old = deferred<ReturnType<typeof runDetail>['run'][]>()
    service.listRuns.mockReturnValueOnce(old.promise).mockResolvedValue([])
    await mountView()
    updateAppPreferences({ apiBaseUrl: 'http://127.0.0.1:9001' })
    await settle()
    old.resolve([runDetail('old-backend-run').run])
    await settle()
    expect(service.getRun).not.toHaveBeenCalled()
  })

  it('still supports an explicit manual refresh', async () => {
    await mountView()
    const button = host!.querySelector<HTMLButtonElement>('button[aria-label="刷新证据"]')!
    button.click()
    await settle()
    expect(service.bootstrap).toHaveBeenCalledTimes(2)
    expect(service.listRuns).toHaveBeenCalledTimes(2)
  })
})
