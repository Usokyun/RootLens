interface DataTransferItemLike {
  kind?: string
  getAsFile?: () => File | null
}

interface FileListLike {
  readonly length?: number
  item?: (index: number) => File | null
  [index: number]: File | undefined
}

interface DataTransferLike {
  items?: Iterable<DataTransferItemLike> | ArrayLike<DataTransferItemLike> | null
  files?: FileListLike | File[] | null
}

interface DragEventLike {
  preventDefault: () => void
  stopPropagation?: () => void
  dataTransfer?: { dropEffect?: string | undefined } | null
}

function toItemArray(
  items: Iterable<DataTransferItemLike> | ArrayLike<DataTransferItemLike> | null | undefined,
): DataTransferItemLike[] {
  if (!items) {
    return []
  }

  if (Symbol.iterator in Object(items)) {
    return Array.from(items as Iterable<DataTransferItemLike>)
  }

  const list = items as ArrayLike<DataTransferItemLike>
  const result: DataTransferItemLike[] = []
  const length = typeof list.length === 'number' ? list.length : 0
  for (let index = 0; index < length; index += 1) {
    const item = list[index]
    if (item) {
      result.push(item)
    }
  }
  return result
}

export function extractFirstFileFromDataTransfer(
  dataTransfer: DataTransferLike | null | undefined,
): File | null {
  if (!dataTransfer) {
    return null
  }

  for (const item of toItemArray(dataTransfer.items)) {
    if (item.kind !== 'file' || typeof item.getAsFile !== 'function') {
      continue
    }

    const file = item.getAsFile()
    if (file) {
      return file
    }
  }

  const files = dataTransfer.files
  if (!files) {
    return null
  }

  if ('item' in files && typeof files.item === 'function') {
    const file = files.item(0)
    if (file) {
      return file
    }
  }

  const firstFile = files[0]
  return firstFile ?? null
}

export function markDragEventHandled(
  event: DragEventLike,
  options?: { dropEffect?: string },
) {
  event.preventDefault()
  event.stopPropagation?.()

  if (options?.dropEffect && event.dataTransfer) {
    event.dataTransfer.dropEffect = options.dropEffect
  }
}
