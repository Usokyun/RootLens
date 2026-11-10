import { describe, expect, it } from 'vitest'
import type { DemoGraphReference, GraphSummary } from '@/api/workbench'
import { demoGraphReference, readyDemoGraph, demoGraphUnavailableNote } from './demo-graph-selection'
const ref:DemoGraphReference={graph_id:'paired',title:'配套图',state:'ready',ready:true,enabled:true,available:true,note:'',asset_id:'asset',download_url:'/asset',candidates:[]}
const graph=(id:string):GraphSummary=>({graph_id:id,title:id,dataset:'mvtec',enabled:true,status:'ready',node_count:1,edge_count:0,build_id:'b',knowledge:{schema_version:'rootlens-knowledge-package.v2'}})
describe('explicit sample-to-knowledge binding',()=>{
  it('requires the exact backend reference instead of latest/first enabled graph',()=>{expect(readyDemoGraph(ref,[graph('latest'),graph('paired')],'mvtec')?.graph_id).toBe('paired');expect(readyDemoGraph(ref,[graph('latest')],'mvtec')).toBeNull()})
  it('does not treat missing, ambiguous or disabled references as runnable pairings',()=>{for(const state of ['missing','ambiguous','disabled','unavailable']as const)expect(readyDemoGraph({...ref,state},[graph('paired')],'mvtec')).toBeNull();expect(readyDemoGraph(ref,[{...graph('paired'),enabled:false}],'mvtec')).toBeNull()})
  it('keeps an incompatible-scene graph out even if IDs match',()=>{expect(readyDemoGraph(ref,[graph('paired')],'tep')).toBeNull()})
  it('uses sample-specific provenance before its group and explains missing metadata',()=>{expect(demoGraphReference({graph_ref:ref},{graph_ref:{...ref,graph_id:'group'}})).toBe(ref);expect(demoGraphUnavailableNote(null)).toContain('尚未取得');expect(demoGraphUnavailableNote({...ref,state:'missing',note:'请导入配套知识包'})).toBe('请导入配套知识包')})
})
