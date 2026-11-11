/** Durable large replay payloads; localStorage keeps only small session metadata. */
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) { reject(new Error('当前浏览器不支持大型回放存储（IndexedDB）。')); return }
    const request = indexedDB.open('rootlens-replay-assets', 1)
    request.onupgradeneeded = () => { request.result.createObjectStore('runtime') }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}
export async function storeReplayRuntime(key: string, value: unknown): Promise<void> {
  const db = await database()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction('runtime', 'readwrite')
      tx.objectStore('runtime').put(value, key)
      tx.oncomplete = () => resolve()
      tx.onerror = tx.onabort = () => reject(tx.error ?? new Error('回放存储未完成。'))
    })
  } finally { db.close() }
}
export async function readReplayRuntime(key: string): Promise<unknown> {
  const db = await database()
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction('runtime', 'readonly').objectStore('runtime').get(key)
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
  } finally { db.close() }
}
