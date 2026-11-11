import type { DirectiveBinding, ObjectDirective } from 'vue'

// Arco Select puts attributes on its wrapper, not its native keyboard target.
function applyControlLabel(element: HTMLElement, { value }: DirectiveBinding<string>) {
  const input = element.querySelector('input')
  if (!input) return

  input.id = `${element.id}-input`
  input.setAttribute('aria-label', value)
}

export const controlLabel: ObjectDirective<HTMLElement, string> = {
  mounted: applyControlLabel,
  updated: applyControlLabel,
}
