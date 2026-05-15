declare global {
  interface Window {
    d3?: any
    __rootlensD3Promise?: Promise<any>
  }
}

const D3_SCRIPT_SRC = 'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js'
const D3_SCRIPT_SELECTOR = 'script[data-rootlens-d3="true"]'

function resolveExistingD3() {
  if (typeof window === 'undefined') {
    return null
  }

  return window.d3 ?? null
}

export async function loadD3() {
  const existing = resolveExistingD3()
  if (existing) {
    return existing
  }

  if (typeof window === 'undefined' || typeof document === 'undefined') {
    throw new Error('D3 renderer requires a browser environment.')
  }

  if (window.__rootlensD3Promise) {
    return window.__rootlensD3Promise
  }

  window.__rootlensD3Promise = new Promise((resolve, reject) => {
    const settle = () => {
      if (window.d3) {
        resolve(window.d3)
        return
      }

      reject(new Error('D3 script loaded, but window.d3 is unavailable.'))
    }

    const fail = () => {
      window.__rootlensD3Promise = undefined
      reject(new Error('Failed to load D3 renderer script.'))
    }

    const existingScript = document.querySelector(D3_SCRIPT_SELECTOR) as HTMLScriptElement | null
    if (existingScript) {
      existingScript.addEventListener('load', settle, { once: true })
      existingScript.addEventListener('error', fail, { once: true })
      return
    }

    const script = document.createElement('script')
    script.src = D3_SCRIPT_SRC
    script.async = true
    script.defer = true
    script.dataset.rootlensD3 = 'true'
    script.crossOrigin = 'anonymous'
    script.addEventListener('load', settle, { once: true })
    script.addEventListener('error', fail, { once: true })
    document.head.appendChild(script)
  }).catch((error) => {
    window.__rootlensD3Promise = undefined
    throw error
  })

  return window.__rootlensD3Promise
}
