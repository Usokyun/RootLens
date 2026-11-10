import { afterEach, describe, expect, it, vi } from 'vitest'
import { revealTask } from '@/services/reveal-task'
afterEach(() => { document.body.innerHTML=''; vi.unstubAllGlobals() })
describe('new task visibility', () => {
  it('reveals exactly the newly submitted task and respects reduced motion', async () => {
    const element=document.createElement('section');element.dataset.taskId='new-task';document.body.append(element)
    element.scrollIntoView=vi.fn();vi.stubGlobal('matchMedia',vi.fn().mockReturnValue({matches:true}))
    await revealTask('new-task')
    expect(element.scrollIntoView).toHaveBeenCalledWith({block:'start',behavior:'auto'})
    await revealTask('another-task');expect(element.scrollIntoView).toHaveBeenCalledOnce()
  })
})
