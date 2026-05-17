import { describe, expect, it } from 'vitest'

import { resolveApiBaseUrl } from '@/api/client'

describe('resolveApiBaseUrl', () => {
  it('routes the default local backend through the same-origin proxy during local frontend development', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:8081', 'http://127.0.0.1:5174')).toBe(
      'http://127.0.0.1:5174',
    )
  })

  it('keeps custom loopback ports direct to avoid proxying the wrong backend', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:9000', 'http://127.0.0.1:5174')).toBe(
      'http://127.0.0.1:9000',
    )
  })

  it('keeps external API origins direct', () => {
    expect(resolveApiBaseUrl('https://example.com', 'http://127.0.0.1:5174')).toBe('https://example.com')
  })
})
