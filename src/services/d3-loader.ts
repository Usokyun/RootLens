/** Original force-graph renderer, loaded from the project lockfile rather than an external CDN. */
let renderer: Promise<typeof import('d3')> | null = null

export function loadD3() {
  renderer ??= import('d3')
  return renderer
}
