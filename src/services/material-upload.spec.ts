import { describe, expect, it, vi } from 'vitest'

import type { ApiClient } from '@/api/client'
import type { KGMaterialMutationResponse } from '@/api/contracts'
import { uploadKGMaterialFiles } from '@/services/material-upload'

type UploadInput = Parameters<ApiClient['uploadKGMaterial']>[0]

function uploadedMaterial(input: UploadInput): KGMaterialMutationResponse {
  return {
    status: 'uploaded',
    material: {
      status: 'uploaded',
      material_id: input.material_id ?? input.file.name,
      title: input.title ?? input.file.name,
      scenario: input.scenario ?? 'shared',
      source_type: input.source_type ?? 'other',
      processing_status: 'uploaded',
    },
    note: '',
  }
}

describe('material batch upload', () => {
  it('uploads all 23 TEP files sequentially with shared scenario and separate identities', async () => {
    const names = [
      'paper.pdf',
      ...Array.from({ length: 5 }, (_, index) => `paper_${index}.md`),
      'README.txt',
      ...Array.from({ length: 5 }, (_, index) => `init_${index}.m`),
      'temexd_mod.c', 'teprob_mod.h',
      ...Array.from({ length: 5 }, (_, index) => `model_${index}.mdl`),
      ...Array.from({ length: 3 }, (_, index) => `initial_${index}.mat`),
      'temexd_mod.mexw64',
    ]
    const files = names.map((name) => new File(['contents'], name))
    let active = 0
    let maxActive = 0
    const upload = vi.fn(async (input: UploadInput) => {
      active += 1
      maxActive = Math.max(maxActive, active)
      await Promise.resolve()
      active -= 1
      return uploadedMaterial(input)
    })

    const result = await uploadKGMaterialFiles(files, {
      scenario: 'tep', notes: 'process sources', source_type: 'text',
      title: 'single title', material_id: 'single_id',
    }, upload)

    expect(result.uploaded).toHaveLength(23)
    expect(result.failed).toEqual([])
    expect(maxActive).toBe(1)
    expect(upload.mock.calls.map(([input]) => input.file)).toEqual(files)
    expect(upload.mock.calls.map(([input]) => input.source_type)).toEqual([
      'pdf', ...Array(5).fill('markdown'), 'text', ...Array(16).fill('other'),
    ])
    for (const [input] of upload.mock.calls) {
      expect(input).toMatchObject({ scenario: 'tep', notes: 'process sources' })
      expect(input.title).toBeUndefined()
      expect(input.material_id).toBeUndefined()
    }
  })

  it('preserves custom metadata for a single-file upload', async () => {
    const file = new File(['notes'], 'notes.txt')
    const upload = vi.fn(async (input: UploadInput) => uploadedMaterial(input))
    const options = {
      title: 'TEP manual', material_id: 'tep_manual', scenario: 'tep',
      source_type: 'text', notes: 'source', metadata: { version: 1 },
    }

    await uploadKGMaterialFiles([file], options, upload)

    expect(upload).toHaveBeenCalledExactlyOnceWith({ file, ...options })
  })

  it('identifies single-file formats when no custom type was chosen', async () => {
    const file = new File(['<p>source</p>'], 'manual.html')
    const upload = vi.fn(async (input: UploadInput) => uploadedMaterial(input))
    await uploadKGMaterialFiles([file], { scenario: 'shared' }, upload)
    expect(upload).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({
      file, scenario: 'shared', source_type: 'webpage',
    }))
  })

  it('continues after a failure and returns only failed files for retry', async () => {
    const files = ['one.md', 'two.pdf', 'three.m'].map((name) => new File(['source'], name))
    const upload = vi.fn(async (input: UploadInput) => {
      if (input.file === files[1]) throw new Error('upload failed')
      return uploadedMaterial(input)
    })

    const result = await uploadKGMaterialFiles(files, { scenario: 'tep' }, upload)

    expect(upload).toHaveBeenCalledTimes(3)
    expect(result.uploaded.map((item) => item.material.material_id)).toEqual(['one.md', 'three.m'])
    expect(result.failed).toEqual([{ file: files[1], error: 'upload failed' }])

    const retry = vi.fn(async (input: UploadInput) => uploadedMaterial(input))
    const retried = await uploadKGMaterialFiles(result.failed.map((item) => item.file), {}, retry)
    expect(retry).toHaveBeenCalledTimes(1)
    expect(retried.failed).toEqual([])
  })

  it('reports every failure without discarding pending files', async () => {
    const files = ['a.md', 'b.md'].map((name) => new File(['source'], name))
    const upload = vi.fn(async (): Promise<KGMaterialMutationResponse> => {
      throw 'offline'
    })

    const result = await uploadKGMaterialFiles(files, {}, upload)

    expect(result.uploaded).toEqual([])
    expect(result.failed).toEqual(files.map((file) => ({ file, error: 'offline' })))
  })

  it('does not send requests without selected files', async () => {
    const upload = vi.fn(async (input: UploadInput) => uploadedMaterial(input))

    expect(await uploadKGMaterialFiles([], {}, upload)).toEqual({ uploaded: [], failed: [] })
    expect(upload).not.toHaveBeenCalled()
  })

  it('detects mixed text formats case-insensitively', async () => {
    const files = ['a.PDF', 'b.MD', 'c.markdown', 'd.txt', 'e.html', 'f.htm', 'g.csv', 'h.json', 'i.jsonl', 'binary']
      .map((name) => new File(['source'], name))
    const upload = vi.fn(async (input: UploadInput) => uploadedMaterial(input))

    await uploadKGMaterialFiles(files, {}, upload)

    expect(upload.mock.calls.map(([input]) => input.source_type)).toEqual([
      'pdf', 'markdown', 'markdown', 'text', 'webpage', 'webpage', 'csv', 'json', 'jsonl', 'other',
    ])
  })
})
