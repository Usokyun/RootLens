import { describe, expect, it, vi } from 'vitest'

import { extractFilesFromDataTransfer, extractFirstFileFromDataTransfer, markDragEventHandled } from '@/services/file-drop'

describe('file drop helpers', () => {
  it('extracts all dropped files in order without duplicating items and files', () => {
    const files = [new File(['a'], 'paper.pdf'), new File(['b'], 'model.mdl')]

    expect(extractFilesFromDataTransfer({
      items: [
        { kind: 'string', getAsFile: () => null },
        { kind: 'file', getAsFile: () => null },
        ...files.map((file) => ({ kind: 'file', getAsFile: () => file })),
      ],
      files,
    })).toEqual(files)
  })

  it('extracts every file from a non-iterable FileList', () => {
    const files = [new File(['a'], 'a.m'), new File(['b'], 'b.mat')]

    expect(extractFilesFromDataTransfer({
      files: { length: files.length, item: (index) => files[index] ?? null },
    })).toEqual(files)
  })

  it('supports indexed multi-file lists and falls back from empty file items', () => {
    const files = [new File(['a'], 'a.c'), new File(['b'], 'b.h')]

    expect(extractFilesFromDataTransfer({
      items: { 0: { kind: 'file', getAsFile: () => null }, length: 1 },
      files: { 0: files[0], 1: files[1], length: 2 },
    })).toEqual(files)
  })

  it('returns no files for empty or missing transfers', () => {
    expect(extractFilesFromDataTransfer(null)).toEqual([])
    expect(extractFilesFromDataTransfer(undefined)).toEqual([])
    expect(extractFilesFromDataTransfer({ files: [] })).toEqual([])
  })

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
