import { requestJson } from '@/api/client'
import type { KGMaterialListResponse, KGMaterialMutationResponse } from '@/api/contracts'

export function listArchivedMaterials(baseUrl: string) {
  return requestJson<KGMaterialListResponse>(baseUrl, '/api/kg/materials', undefined, new URLSearchParams({ archived: 'true' }))
}

export function changeMaterialArchive(baseUrl: string, materialId: string, action: 'archive' | 'restore') {
  return requestJson<KGMaterialMutationResponse>(baseUrl, `/api/kg/materials/${encodeURIComponent(materialId)}/${action}`, { method: 'POST' })
}
