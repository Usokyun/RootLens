import type { ApiClient } from '@/api/client'
import type { KGMaterialMutationResponse } from '@/api/contracts'

type MaterialUploader = ApiClient['uploadKGMaterial']
type MaterialUploadOptions = Omit<Parameters<MaterialUploader>[0], 'file'>

function materialTypeFromFilename(filename: string): string {
  const extension = filename.split('.').pop()?.toLowerCase()
  switch (extension) {
    case 'pdf': return 'pdf'
    case 'md':
    case 'markdown': return 'markdown'
    case 'txt': return 'text'
    case 'html':
    case 'htm': return 'webpage'
    case 'csv': return 'csv'
    case 'json': return 'json'
    case 'jsonl': return 'jsonl'
    default: return 'other'
  }
}

export async function uploadKGMaterialFiles(
  files: readonly File[],
  options: MaterialUploadOptions,
  upload: MaterialUploader,
): Promise<{
  uploaded: KGMaterialMutationResponse[]
  failed: { file: File; error: string }[]
}> {
  const uploaded: KGMaterialMutationResponse[] = []
  const failed: { file: File; error: string }[] = []
  const isBatch = files.length > 1

  for (const file of files) {
    try {
      uploaded.push(await upload({
        ...options,
        file,
        title: isBatch ? undefined : options.title,
        material_id: isBatch ? undefined : options.material_id,
        source_type: isBatch ? materialTypeFromFilename(file.name) : options.source_type,
      }))
    } catch (error) {
      failed.push({ file, error: error instanceof Error ? error.message : String(error) })
    }
  }

  return { uploaded, failed }
}
