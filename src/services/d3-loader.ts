/** Keep graph rendering available offline; no runtime CDN dependency. */
export async function loadD3(): Promise<any> {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    throw new Error('D3 renderer requires a browser environment.')
  }
  return import('d3')
}
