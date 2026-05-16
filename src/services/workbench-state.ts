import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

export interface WorkbenchState {
  selectedRunId: string | null
  selectedCaseId: string | null
  selectedPathId: string | null
  selectedCandidateId: string | null
  selectedReviewTargetKey: string | null
  selectedGraphNodeId: string | null
  subgraphMode: 'path' | 'neighborhood'
  selectedSubgraphNodeId: string | null
  selectedSubgraphEdgeId: string | null
  selectedConstructionRunId: string | null
}

interface WorkbenchStateApi {
  state: Ref<WorkbenchState>
  updateState: (patch: Partial<WorkbenchState>) => void
  resetState: () => void
}

const WORKBENCH_STATE_STORAGE_KEY = 'rootlens.workbench-state'
const WORKBENCH_STATE_UPDATED_EVENT = 'rootlens:workbench-state-updated'

const DEFAULT_WORKBENCH_STATE: WorkbenchState = {
  selectedRunId: null,
  selectedCaseId: null,
  selectedPathId: null,
  selectedCandidateId: null,
  selectedReviewTargetKey: null,
  selectedGraphNodeId: null,
  subgraphMode: 'path',
  selectedSubgraphNodeId: null,
  selectedSubgraphEdgeId: null,
  selectedConstructionRunId: null,
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function normalizeString(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }

  const normalized = value.trim()
  return normalized.length ? normalized : null
}

function normalizeWorkbenchState(candidate?: Partial<WorkbenchState> | null): WorkbenchState {
  return {
    selectedRunId: normalizeString(candidate?.selectedRunId),
    selectedCaseId: normalizeString(candidate?.selectedCaseId),
    selectedPathId: normalizeString(candidate?.selectedPathId),
    selectedCandidateId: normalizeString(candidate?.selectedCandidateId),
    selectedReviewTargetKey: normalizeString(candidate?.selectedReviewTargetKey),
    selectedGraphNodeId: normalizeString(candidate?.selectedGraphNodeId),
    subgraphMode: candidate?.subgraphMode === 'neighborhood' ? 'neighborhood' : 'path',
    selectedSubgraphNodeId: normalizeString(candidate?.selectedSubgraphNodeId),
    selectedSubgraphEdgeId: normalizeString(candidate?.selectedSubgraphEdgeId),
    selectedConstructionRunId: normalizeString(candidate?.selectedConstructionRunId),
  }
}

function readStoredWorkbenchState(): WorkbenchState {
  if (!canUseStorage()) {
    return { ...DEFAULT_WORKBENCH_STATE }
  }

  try {
    const rawValue = window.localStorage.getItem(WORKBENCH_STATE_STORAGE_KEY)
    if (!rawValue) {
      return { ...DEFAULT_WORKBENCH_STATE }
    }

    return normalizeWorkbenchState(JSON.parse(rawValue) as Partial<WorkbenchState>)
  } catch {
    return { ...DEFAULT_WORKBENCH_STATE }
  }
}

function writeStoredWorkbenchState(state: WorkbenchState) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(WORKBENCH_STATE_STORAGE_KEY, JSON.stringify(state))
  window.dispatchEvent(new CustomEvent(WORKBENCH_STATE_UPDATED_EVENT))
}

export function getWorkbenchStateEventName() {
  return WORKBENCH_STATE_UPDATED_EVENT
}

export function getWorkbenchState() {
  return readStoredWorkbenchState()
}

export function updateWorkbenchState(patch: Partial<WorkbenchState>) {
  const nextState = normalizeWorkbenchState({
    ...readStoredWorkbenchState(),
    ...patch,
  })
  writeStoredWorkbenchState(nextState)
  return nextState
}

export function resetWorkbenchState() {
  const nextState = { ...DEFAULT_WORKBENCH_STATE }
  writeStoredWorkbenchState(nextState)
  return nextState
}

export function useWorkbenchState(): WorkbenchStateApi {
  const state = ref<WorkbenchState>(readStoredWorkbenchState())

  const syncState = () => {
    state.value = readStoredWorkbenchState()
  }

  onMounted(() => {
    window.addEventListener('storage', syncState)
    window.addEventListener(WORKBENCH_STATE_UPDATED_EVENT, syncState as EventListener)
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.removeEventListener('storage', syncState)
    window.removeEventListener(WORKBENCH_STATE_UPDATED_EVENT, syncState as EventListener)
  })

  return {
    state,
    updateState(patch) {
      state.value = updateWorkbenchState(patch)
    },
    resetState() {
      state.value = resetWorkbenchState()
    },
  }
}
