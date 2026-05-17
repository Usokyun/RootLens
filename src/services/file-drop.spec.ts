import { describe, expect, it, vi } from 'vitest'

import { extractFirstFileFromDataTransfer, markDragEventHandled } from '@/services/file-drop'

describe('file drop helpers', () => {
  it('extracts the first dropped file from dataTransfer.items when available', () => {
    const file = new File(['hello'], 'runtime.json', { type: 'application/json' })

    expect(
      extractFirstFileFromDataTransfer({
        items: [
          {
            kind: 'file',
            getAsFile: () => file,
          },
        ],
        files: [],
      }),
    ).toBe(file)
  })

  it('falls back to dataTransfer.files.item when file items are unavailable', () => {
    const file = new File(['hello'], 'graphs.json', { type: 'application/json' })

    expect(
      extractFirstFileFromDataTransfer({
        items: [],
        files: {
          length: 1,
          item: (index: number) => (index === 0 ? file : null),
        },
      }),
    ).toBe(file)
  })

  it('supports non-iterable array-like file lists', () => {
    const file = new File(['hello'], 'evidence.jsonl', { type: 'application/jsonl' })

    expect(
      extractFirstFileFromDataTransfer({
        files: {
          0: file,
          length: 1,
        },
      }),
    ).toBe(file)
  })

  it('returns null when no dropped file can be resolved', () => {
    expect(
      extractFirstFileFromDataTransfer({
        items: [
          {
            kind: 'string',
            getAsFile: () => null,
          },
        ],
        files: {
          length: 0,
          item: () => null,
        },
      }),
    ).toBeNull()
  })

  it('marks drag events as handled and sets dropEffect when requested', () => {
    const preventDefault = vi.fn()
    const stopPropagation = vi.fn()
    const dataTransfer = { dropEffect: 'none' }

    markDragEventHandled(
      {
        preventDefault,
        stopPropagation,
        dataTransfer,
      },
      { dropEffect: 'copy' },
    )

    expect(preventDefault).toHaveBeenCalledTimes(1)
    expect(stopPropagation).toHaveBeenCalledTimes(1)
    expect(dataTransfer.dropEffect).toBe('copy')
  })
})
