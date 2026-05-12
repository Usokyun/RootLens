import { beforeEach } from 'vitest'

class LocalStorageMock implements Storage {
  private store = new Map<string, string>()

  get length() {
    return this.store.size
  }

  clear() {
    this.store.clear()
  }

  getItem(key: string) {
    return this.store.get(key) ?? null
  }

  key(index: number) {
    return [...this.store.keys()][index] ?? null
  }

  removeItem(key: string) {
    this.store.delete(key)
  }

  setItem(key: string, value: string) {
    this.store.set(key, String(value))
  }
}

beforeEach(() => {
  const localStorageMock = new LocalStorageMock()

  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: localStorageMock,
  })

  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: localStorageMock,
  })
})
