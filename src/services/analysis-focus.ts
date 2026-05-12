import type {
  CrossRouteSignal,
  EvidenceObservation,
  RankedPath,
  RootKGDCandidate,
  RootLensRuntimeCase,
} from '@/types/rootlens'

const ANALYSIS_FOCUS_PREFIX = 'rootlens.analysis-focus'
const ANALYSIS_FOCUS_EVENT = 'rootlens:analysis-focus-change'
const ANALYSIS_FOCUS_SCHEMA = 'analysis-focus.v1'

export type AnalysisFocusKind =
  | 'case'
  | 'observation'
  | 'route1-path'
  | 'route2-candidate'
  | 'cross-signal'
  | null

export type AnalysisFocusSourceView = 'graphs' | 'evidence' | 'reasoning' | 'system' | null

export interface AnalysisFocusState {
  schema_version: string
  session_scope: string
  updated_at: string
  active_case_id: string | null
  active_dataset_id: string | null
  selected_observation_id: string | null
  selected_route1_path_ids: string[]
  selected_route2_candidate_ids: string[]
  highlighted_node_ids: string[]
  highlighted_edge_ids: string[]
  highlighted_obs_ids: string[]
  focus_kind: AnalysisFocusKind
  focus_label: string | null
  source_view: AnalysisFocusSourceView
}

type AnalysisFocusPatch = Partial<Omit<AnalysisFocusState, 'schema_version' | 'session_scope' | 'updated_at'>>

export interface AnalysisFocusSnapshot {
  active_case_id: string | null
  active_dataset_id: string | null
  selected_observation_id: string | null
  selected_route1_path_ids: string[]
  selected_route2_candidate_ids: string[]
  highlighted_node_ids: string[]
  highlighted_edge_ids: string[]
  highlighted_obs_ids: string[]
  focus_kind: AnalysisFocusKind
  focus_label: string | null
  source_view: AnalysisFocusSourceView
}

function readLocalStorage(key: string): unknown | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(key)
  if (!raw) {
    return null
  }

  return JSON.parse(raw)
}

function writeLocalStorage(key: string, value: unknown) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(key, JSON.stringify(value))
}

function removeLocalStorage(key: string) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(key)
}

function getStorageKey(sessionScope: string) {
  return `${ANALYSIS_FOCUS_PREFIX}:${sessionScope}`
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }

  return [...new Set(value.filter((item): item is string => typeof item === 'string' && item.length > 0))]
}

function buildEmptyFocus(sessionScope: string): AnalysisFocusState {
  return {
    schema_version: ANALYSIS_FOCUS_SCHEMA,
    session_scope: sessionScope,
    updated_at: new Date().toISOString(),
    active_case_id: null,
    active_dataset_id: null,
    selected_observation_id: null,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: [],
    highlighted_edge_ids: [],
    highlighted_obs_ids: [],
    focus_kind: null,
    focus_label: null,
    source_view: null,
  }
}

function parseFocusSnapshot(value: unknown): AnalysisFocusSnapshot | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }

  const candidate = value as Record<string, unknown>

  return {
    active_case_id: typeof candidate.active_case_id === 'string' ? candidate.active_case_id : null,
    active_dataset_id:
      typeof candidate.active_dataset_id === 'string' ? candidate.active_dataset_id : null,
    selected_observation_id:
      typeof candidate.selected_observation_id === 'string' ? candidate.selected_observation_id : null,
    selected_route1_path_ids: normalizeStringArray(candidate.selected_route1_path_ids),
    selected_route2_candidate_ids: normalizeStringArray(candidate.selected_route2_candidate_ids),
    highlighted_node_ids: normalizeStringArray(candidate.highlighted_node_ids),
    highlighted_edge_ids: normalizeStringArray(candidate.highlighted_edge_ids),
    highlighted_obs_ids: normalizeStringArray(candidate.highlighted_obs_ids),
    focus_kind:
      candidate.focus_kind === 'case' ||
      candidate.focus_kind === 'observation' ||
      candidate.focus_kind === 'route1-path' ||
      candidate.focus_kind === 'route2-candidate' ||
      candidate.focus_kind === 'cross-signal'
        ? candidate.focus_kind
        : null,
    focus_label: typeof candidate.focus_label === 'string' ? candidate.focus_label : null,
    source_view:
      candidate.source_view === 'graphs' ||
      candidate.source_view === 'evidence' ||
      candidate.source_view === 'reasoning' ||
      candidate.source_view === 'system'
        ? candidate.source_view
        : null,
  }
}

function hasMeaningfulFocus(focus: AnalysisFocusState): boolean {
  return Boolean(
    focus.active_case_id ||
      focus.active_dataset_id ||
      focus.selected_observation_id ||
      focus.selected_route1_path_ids.length ||
      focus.selected_route2_candidate_ids.length ||
      focus.highlighted_node_ids.length ||
      focus.highlighted_edge_ids.length ||
      focus.highlighted_obs_ids.length ||
      focus.focus_kind ||
      focus.focus_label,
  )
}

function persistFocus(focus: AnalysisFocusState) {
  if (hasMeaningfulFocus(focus)) {
    writeLocalStorage(getStorageKey(focus.session_scope), focus)
  } else {
    removeLocalStorage(getStorageKey(focus.session_scope))
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(ANALYSIS_FOCUS_EVENT, {
        detail: {
          sessionScope: focus.session_scope,
        },
      }),
    )
  }
}

function getCaseDatasetId(caseItem: RootLensRuntimeCase): string {
  return (
    caseItem.analysis.graph_dataset_id ||
    caseItem.evidence.graph_dataset_id ||
    caseItem.graph_snapshot.dataset_id
  )
}

function describeObservation(observation: EvidenceObservation): string {
  if (observation.facet === 'variable') {
    return observation.variable_name
  }

  if (observation.facet === 'image_defect') {
    return `${observation.object} / ${observation.anomaly_type}`
  }

  return observation.event_code
}

export function getAnalysisFocusEventName() {
  return ANALYSIS_FOCUS_EVENT
}

export function loadAnalysisFocus(sessionScope: string): AnalysisFocusState | null {
  const payload = readLocalStorage(getStorageKey(sessionScope))

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null
  }

  const candidate = payload as Record<string, unknown>

  if (
    candidate.schema_version !== ANALYSIS_FOCUS_SCHEMA ||
    candidate.session_scope !== sessionScope ||
    typeof candidate.updated_at !== 'string'
  ) {
    return null
  }

  const snapshot = parseFocusSnapshot(candidate)

  if (!snapshot) {
    return null
  }

  return {
    schema_version: ANALYSIS_FOCUS_SCHEMA,
    session_scope: sessionScope,
    updated_at: candidate.updated_at,
    ...snapshot,
  }
}

export function parseAnalysisFocusSnapshot(value: unknown): AnalysisFocusSnapshot | null {
  return parseFocusSnapshot(value)
}

export function saveAnalysisFocus(
  sessionScope: string,
  patch: AnalysisFocusPatch,
): AnalysisFocusState {
  const current = loadAnalysisFocus(sessionScope) ?? buildEmptyFocus(sessionScope)

  const nextFocus: AnalysisFocusState = {
    ...current,
    ...patch,
    selected_route1_path_ids:
      patch.selected_route1_path_ids === undefined
        ? current.selected_route1_path_ids
        : normalizeStringArray(patch.selected_route1_path_ids),
    selected_route2_candidate_ids:
      patch.selected_route2_candidate_ids === undefined
        ? current.selected_route2_candidate_ids
        : normalizeStringArray(patch.selected_route2_candidate_ids),
    highlighted_node_ids:
      patch.highlighted_node_ids === undefined
        ? current.highlighted_node_ids
        : normalizeStringArray(patch.highlighted_node_ids),
    highlighted_edge_ids:
      patch.highlighted_edge_ids === undefined
        ? current.highlighted_edge_ids
        : normalizeStringArray(patch.highlighted_edge_ids),
    highlighted_obs_ids:
      patch.highlighted_obs_ids === undefined
        ? current.highlighted_obs_ids
        : normalizeStringArray(patch.highlighted_obs_ids),
    updated_at: new Date().toISOString(),
  }

  persistFocus(nextFocus)

  return nextFocus
}

export function clearAnalysisFocus(sessionScope: string) {
  const nextFocus = buildEmptyFocus(sessionScope)
  persistFocus(nextFocus)
}

export function clearAnalysisHighlight(sessionScope: string) {
  return saveAnalysisFocus(sessionScope, {
    selected_observation_id: null,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: [],
    highlighted_edge_ids: [],
    highlighted_obs_ids: [],
    focus_kind: null,
    focus_label: null,
    source_view: null,
  })
}

export function restoreAnalysisFocus(
  sessionScope: string,
  value: unknown,
): AnalysisFocusState | null {
  const snapshot = parseFocusSnapshot(value)

  if (!snapshot) {
    const emptyFocus = buildEmptyFocus(sessionScope)
    persistFocus(emptyFocus)
    return null
  }

  const nextFocus: AnalysisFocusState = {
    schema_version: ANALYSIS_FOCUS_SCHEMA,
    session_scope: sessionScope,
    updated_at: new Date().toISOString(),
    ...snapshot,
  }

  persistFocus(nextFocus)

  return hasMeaningfulFocus(nextFocus) ? nextFocus : null
}

export function buildCaseFocus(
  caseItem: RootLensRuntimeCase,
  sourceView: AnalysisFocusSourceView,
): AnalysisFocusPatch {
  return {
    active_case_id: caseItem.case_id,
    active_dataset_id: getCaseDatasetId(caseItem),
    selected_observation_id: null,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: [],
    highlighted_edge_ids: [],
    highlighted_obs_ids: [],
    focus_kind: 'case',
    focus_label: caseItem.case_label,
    source_view: sourceView,
  }
}

export function buildObservationFocus(
  caseItem: RootLensRuntimeCase,
  observation: EvidenceObservation,
  sourceView: AnalysisFocusSourceView,
): AnalysisFocusPatch {
  return {
    active_case_id: caseItem.case_id,
    active_dataset_id: getCaseDatasetId(caseItem),
    selected_observation_id: observation.obs_id,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: observation.linked_entity_hints,
    highlighted_edge_ids: [],
    highlighted_obs_ids: [observation.obs_id],
    focus_kind: 'observation',
    focus_label: describeObservation(observation),
    source_view: sourceView,
  }
}

export function buildRoute1PathFocus(
  caseItem: RootLensRuntimeCase,
  path: RankedPath,
  sourceView: AnalysisFocusSourceView,
): AnalysisFocusPatch {
  return {
    active_case_id: caseItem.case_id,
    active_dataset_id: getCaseDatasetId(caseItem),
    selected_observation_id: null,
    selected_route1_path_ids: [path.path_id],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: path.nodes,
    highlighted_edge_ids: path.source_edges.map((edge) => edge.edge_id),
    highlighted_obs_ids: path.support_obs_ids,
    focus_kind: 'route1-path',
    focus_label: path.target_entity_name,
    source_view: sourceView,
  }
}

export function buildRoute2CandidateFocus(
  caseItem: RootLensRuntimeCase,
  candidate: RootKGDCandidate,
  sourceView: AnalysisFocusSourceView,
): AnalysisFocusPatch {
  return {
    active_case_id: caseItem.case_id,
    active_dataset_id: getCaseDatasetId(caseItem),
    selected_observation_id: null,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [candidate.candidate_id],
    highlighted_node_ids: [
      candidate.candidate_id,
      candidate.seed_variable_id,
      ...candidate.top_affected_variables.map((item) => item.entity_id),
    ],
    highlighted_edge_ids: [],
    highlighted_obs_ids: candidate.support_evidence_ids,
    focus_kind: 'route2-candidate',
    focus_label: candidate.candidate_name,
    source_view: sourceView,
  }
}

export function buildCrossSignalFocus(
  caseItem: RootLensRuntimeCase,
  signal: CrossRouteSignal,
  supportingPaths: RankedPath[],
  sourceView: AnalysisFocusSourceView,
): AnalysisFocusPatch {
  return {
    active_case_id: caseItem.case_id,
    active_dataset_id: getCaseDatasetId(caseItem),
    selected_observation_id: null,
    selected_route1_path_ids: signal.route1_path_ids,
    selected_route2_candidate_ids: [signal.candidate_id],
    highlighted_node_ids: [
      signal.candidate_id,
      ...supportingPaths.flatMap((path) => path.nodes),
    ],
    highlighted_edge_ids: supportingPaths.flatMap((path) =>
      path.source_edges.map((edge) => edge.edge_id),
    ),
    highlighted_obs_ids: signal.shared_obs_ids,
    focus_kind: 'cross-signal',
    focus_label: signal.candidate_name,
    source_view: sourceView,
  }
}
