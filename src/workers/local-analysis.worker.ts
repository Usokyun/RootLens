import { buildLocalAnalysisResult } from '@/services/local-reasoning'
import type { UnifiedGraphDataset } from '@/types/graph'
import type { AnalysisResult, UnifiedEvidence } from '@/types/rootlens'

interface AnalysisWorkerRequest {
  id: number
  dataset: UnifiedGraphDataset
  evidence: UnifiedEvidence
}

interface AnalysisWorkerResponse {
  id: number
  result?: AnalysisResult
  error?: string
}

self.onmessage = (event: MessageEvent<AnalysisWorkerRequest>) => {
  const { id, dataset, evidence } = event.data

  try {
    const result = buildLocalAnalysisResult(dataset, evidence)
    const response: AnalysisWorkerResponse = {
      id,
      result,
    }
    self.postMessage(response)
  } catch (error) {
    const response: AnalysisWorkerResponse = {
      id,
      error: error instanceof Error ? error.message : 'RCA worker calculation failed',
    }
    self.postMessage(response)
  }
}

export {}
