import { afterEach, describe, expect, it, vi } from 'vitest'
import { candidateConditionsApi } from './candidate-conditions'
import { emptyCandidateCondition } from '@/services/candidate-conditions'
afterEach(()=>vi.unstubAllGlobals())
describe('candidate-specific condition API',()=>{
  it('uses only the narrow backend operator and preserves its typed request',async()=>{
    const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({})});vi.stubGlobal('fetch',fetch)
    const api=candidateConditionsApi('https://backend.example','graph/a'),input=emptyCandidateCondition('candidate:a')
    await api.catalog();await api.add(input);await api.remove('condition/a')
    expect(fetch.mock.calls.map(call=>call[0])).toEqual(['https://backend.example/api/kg/working-graphs/graph%2Fa/candidate-conditions','https://backend.example/api/kg/working-graphs/graph%2Fa/candidate-conditions','https://backend.example/api/kg/working-graphs/graph%2Fa/candidate-conditions/condition%2Fa'])
    expect(JSON.parse(fetch.mock.calls[1]![1].body)).toEqual(input);expect(fetch.mock.calls[2]![1].method).toBe('DELETE')
  })
})
