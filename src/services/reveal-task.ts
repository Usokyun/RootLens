import { nextTick } from 'vue'

/** Reveal a newly submitted/retried task once; polling never moves the viewport. */
export async function revealTask(taskId: string) {
  await nextTick()
  const element = Array.from(document.querySelectorAll<HTMLElement>('[data-task-id]')).find((node) => node.dataset.taskId === taskId)
  if (!element) return
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  element.scrollIntoView({ block: 'start', behavior: reducedMotion ? 'auto' : 'smooth' })
}
