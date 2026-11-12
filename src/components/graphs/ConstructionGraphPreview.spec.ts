import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, ref, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { KGConstructionGraphPayload } from '@/api/contracts'
import ConstructionGraphPreview from './ConstructionGraphPreview.vue'

const { service, preferences } = vi.hoisted(() => ({
  service: { getKGConstructionGraph: vi.fn(), listKGConstructionBuilds: vi.fn() },
  preferences: { dataSourceMode: 'backend', apiBaseUrl: 'http://127.0.0.1:8000' },
}))
vi.mock('@/services/rootlens-service', () => ({ getRootLensService: () => service }))
vi.mock('@/services/app-preferences', () => ({ useAppPreferences: () => ({ preferences: { value: preferences } }) }))
vi.mock('@/services/rootlens-data', () => ({ getLocalSessionMeta: () => null }))
vi.mock('@/components/graphs/KnowledgeForceGraph.vue', async () => {
  const { h } = await import('vue')
  return { default: { props: ['dataset'], setup: (props: { dataset: { label: string; nodes: unknown[]; edges: unknown[] } }) =>
    () => h('div', { 'data-testid': 'snapshot-graph' }, `${props.dataset.label}: ${props.dataset.nodes.length} / ${props.dataset.edges.length}`),
  } }
})

function snapshot(buildId: string): KGConstructionGraphPayload {
  return {
    build_id: buildId, title: `${buildId} snapshot`, read_only: true, truncated: false,
    status: 'ok', claim_boundary: 'candidate only', candidate_dir: 'runs/build', nodes_path: 'nodes.csv', edges_path: 'edges.csv',
    source_registry_path: '', node_count: 1, edge_count: 0, scenario_counts: {}, review_status_counts: {}, source_counts: {}, confidence_summary: {}, validation_summary: null,
    sources: [], source_documents: [], review_targets: [], note: 'read-only', graph_edges: [],
    graph_nodes: [{ node_id: buildId, label: buildId, node_type: 'RootCause', scenario: 'mvtec', description: 'candidate' }],
  }
}
let app: App | null = null
let host: HTMLDivElement
async function settle() {
  for (let index = 0; index < 8; index += 1) await Promise.resolve()
  await nextTick()
}
async function mount(buildId = ref('mvtec')) {
  host = document.createElement('div')
  document.body.append(host)
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] })
  await router.push('/')
  app = createApp({ render: () => h(ConstructionGraphPreview, { buildId: buildId.value }) })
  app.use(router)
  for (const name of ['a-alert', 'a-tag', 'a-button', 'a-select', 'a-input', 'a-checkbox', 'a-empty']) {
    app.component(name, defineComponent({
      props: ['title', 'options'],
      setup: (props, { slots, attrs }) => () => h('div', attrs, [String(props.title ?? ''), slots.default?.()]),
    }))
  }
  app.mount(host)
  await settle()
}

beforeEach(() => {
  vi.clearAllMocks()
  preferences.dataSourceMode = 'backend'
  service.listKGConstructionBuilds.mockResolvedValue({ builds: [] })
  service.getKGConstructionGraph.mockImplementation(async (id: string) => snapshot(id))
})
afterEach(() => { app?.unmount(); app = null; host?.remove() })

describe('construction preview isolation', () => {
  it('displays the chosen snapshot with explicit no-RCA boundaries', async () => {
    await mount()
    expect(host.querySelector('[data-testid="snapshot-graph"]')?.textContent).toContain('mvtec snapshot: 1 / 0')
    expect(host.textContent).toContain('不触发分析')
    expect(service.getKGConstructionGraph).toHaveBeenCalledExactlyOnceWith('mvtec')
    expect(Object.keys(service)).toEqual(['getKGConstructionGraph', 'listKGConstructionBuilds'])
  })
  it('does not contact the backend or substitute a Demo graph in Demo mode', async () => {
    preferences.dataSourceMode = 'mock'
    await mount()
    expect(service.getKGConstructionGraph).not.toHaveBeenCalled()
    expect(host.textContent).toContain('构图快照需要 Backend 模式')
    expect(host.querySelector('[data-testid="snapshot-graph"]')).toBeNull()
  })
  it('reports an unavailable build instead of showing a different graph', async () => {
    service.getKGConstructionGraph.mockRejectedValue(new Error('snapshot unavailable'))
    await mount()
    expect(host.textContent).toContain('snapshot unavailable')
    expect(host.querySelector('[data-testid="snapshot-graph"]')).toBeNull()
  })
  it('keeps the graph usable when only the build selector list fails', async () => {
    service.listKGConstructionBuilds.mockRejectedValue(new Error('list unavailable'))
    await mount()
    expect(host.querySelector('[data-testid="snapshot-graph"]')?.textContent).toContain('mvtec snapshot')
  })
  it('ignores an older response after the selected build changes', async () => {
    let finishOld!: (value: KGConstructionGraphPayload) => void
    service.getKGConstructionGraph.mockImplementation((id: string) => id === 'old'
      ? new Promise<KGConstructionGraphPayload>(resolve => { finishOld = resolve })
      : Promise.resolve(snapshot(id)))
    const buildId = ref('old')
    await mount(buildId)
    buildId.value = 'new'
    await settle()
    expect(host.querySelector('[data-testid="snapshot-graph"]')?.textContent).toContain('new snapshot')
    finishOld(snapshot('old'))
    await settle()
    expect(host.querySelector('[data-testid="snapshot-graph"]')?.textContent).toContain('new snapshot')
    expect(host.textContent).not.toContain('old snapshot')
  })
})
