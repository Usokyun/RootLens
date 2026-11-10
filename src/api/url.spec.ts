import { describe, expect, it } from 'vitest'
import { resolveApiBaseUrl } from '@/api/url'

describe('API origin selection', () => {
  it('uses the same-origin Vite proxy only for the configured local target', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:8000/', 'http://127.0.0.1:5174')).toBe('http://127.0.0.1:5174')
  })
  it('keeps another loopback port direct instead of contacting the wrong server', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:9000/', 'http://127.0.0.1:5174')).toBe('http://127.0.0.1:9000')
  })
  it('keeps an external backend direct and preserves non-browser use', () => {
    expect(resolveApiBaseUrl('https://backend.example/', 'https://app.example')).toBe('https://backend.example')
    expect(resolveApiBaseUrl('https://backend.example/', '')).toBe('https://backend.example')
  })
})
