import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import type { AnalysisRun, Dataset, DemoGroup, DemoGraphReference } from '@/api/workbench'
const calls = vi.hoisted(() => ({ analysis:vi.fn(), graph:vi.fn(), task:vi.fn(), retryTask:vi.fn(), authoringCapabilities:vi.fn(), refreshGraphs:vi.fn(), refreshAnalyses:vi.fn(), refreshWorkspace:vi.fn() }))
vi.mock('@/services/workspace', async () => {
  const {reactive,computed}=await import('vue')
  const workspace=reactive({baseUrl:'http://127.0.0.1:8012',graphId:'',graphSelection:'explicit' as 'explicit'|'implicit',analysisId:'',graphs:[] as import('@/api/workbench').GraphSummary[],reasoners:[] as import('@/api/workbench').Reasoner[],demos:{demos:[],samples:[]},tasks:[],analyses:[],connected:true,loading:false,error:'',notice:''})
  return {workspace,currentGraph:computed(()=>workspace.graphs.find(g=>g.graph_id===workspace.graphId)??null),api:()=>calls,
    selectGraph:(id:string,origin:'explicit'|'implicit'='explicit')=>{workspace.graphId=id;workspace.graphSelection=id?origin:'implicit'},selectAnalysis:(id:string)=>{workspace.analysisId=id},
    refreshWorkspace:calls.refreshWorkspace,refreshGraphs:calls.refreshGraphs,refreshAnalyses:calls.refreshAnalyses,refreshTasks:async()=>{},rememberTask:()=>{},setBackend:()=>{}}
})
import AppShell from '@/App.vue'
import GraphView from '@/views/GraphExploreView.vue'
import EvidenceView from '@/views/EvidenceManageView.vue'
import { workspace, selectGraph } from '@/services/workspace'

const oldRun: AnalysisRun = {run_id:'old-wafer',title:'旧晶圆分析',created_at:'2026-11-11',status:'completed',dataset:'wafer',input_mode:'wafer',reasoner_id:'unified_abduction',graph_id:'wafer-graph',graph_title:'晶圆知识',case_count:1,cases:[{case_id:'wafer-case',display_name:'晶圆样本',evidence_frames:[{case_id:'wafer-query',source_dataset:'wafer',subjects:[],scopes:[],observations:[],task:{}}],results:[{case_id:'wafer-query',outcome:'no_match'}],generated_evidence:{},visual_evidence:[],observation_locations:[]}],working_graph_snapshot:{knowledge:{}},artifacts:{}}
function graph(id:string,dataset:Dataset,title:string) {return {graph_id:id,title,dataset,enabled:true,status:'ready',node_count:1,edge_count:0,build_id:'test',knowledge:{schema_version:'rootlens-knowledge-package.v2',entities:[{entity_id:'object',label:title,kind:'Object',aliases:[]}],hypotheses:[{hypothesis_id:'candidate',label:'候选',target_role:'mechanism',assumption_cost:1,applies_to_class_id:'object'}],mechanisms:[],pattern_definitions:[],observable_definitions:[],source_assertions:[]}}}
const OverlayStub=defineComponent({props:['visible'],setup(props,{slots}){return()=>props.visible?h('div',slots.default?.()):null}})
const SlotStub=defineComponent({setup(_,{slots}){return()=>h('div',slots.default?.())}})
let app:App|null=null,router:Router,root:HTMLElement
async function mount(path='/evidence') {
  router=createRouter({history:createMemoryHistory(),routes:[{path:'/evidence',name:'evidence',component:EvidenceView,meta:{label:'推理分析'}},{path:'/graphs',name:'graphs',component:GraphView,meta:{label:'知识图谱'}},{path:'/materials',name:'materials',component:SlotStub,meta:{label:'素材管理'}}]})
  await router.push(path);await router.isReady()
  root=document.createElement('div');document.body.append(root)
  app=createApp(AppShell).use(router).component('AConfigProvider',SlotStub).component('AModal',OverlayStub).component('ADrawer',OverlayStub);app.mount(root)
  await nextTick()
}
async function restored() {await vi.waitFor(()=>expect(root.querySelector('.run-results')?.textContent).toContain('旧晶圆分析'))}
async function freshGlass() {
  await vi.waitFor(()=>{expect(root.querySelector('.analysis-setup')).not.toBeNull();expect(root.querySelector('.run-results')).toBeNull();expect((root.querySelector('[aria-label="工作图谱"]') as HTMLSelectElement).value).toBe('glass-graph');expect(workspace.analysisId).toBe('')})
  expect((root.querySelector('[aria-label="工作图谱"]') as HTMLSelectElement).value).toBe('glass-graph')
  expect(workspace.graphId).toBe('glass-graph');expect(workspace.analysisId).toBe('')
}
beforeEach(()=>{
  vi.clearAllMocks();vi.stubGlobal('scrollTo',vi.fn())
  Object.assign(workspace,{graphId:'wafer-graph',graphSelection:'explicit',analysisId:'old-wafer',graphs:[graph('wafer-graph','wafer','晶圆知识'),graph('glass-graph','mvtec','玻璃知识')],reasoners:[{reasoner_id:'unified_abduction',title:'统一约束推理',datasets:['mvtec','wafer','tep'],description:''},{reasoner_id:'tep_rootkgd',title:'RootKGD',datasets:['tep'],description:''}],tasks:[],analyses:[oldRun],demos:{demos:[],samples:[]},connected:true,error:''})
  calls.authoringCapabilities.mockResolvedValue({capabilities:{}});calls.refreshGraphs.mockResolvedValue(undefined);calls.refreshAnalyses.mockResolvedValue(undefined);calls.refreshWorkspace.mockResolvedValue(undefined)
  calls.analysis.mockResolvedValue(oldRun)
  calls.graph.mockImplementation(async(id:string)=>{const selected=workspace.graphs.find(g=>g.graph_id===id)!;return {schema_version:'rootlens-working-graph.v2',graph_id:id,title:selected.title,dataset:selected.dataset,build_id:'test',knowledge:selected.knowledge}})
})
afterEach(()=>{app?.unmount();app=null;document.body.innerHTML='';vi.unstubAllGlobals()})

describe('graph-to-analysis context across routes',()=>{
  it('restores a saved analysis on ordinary history navigation',async()=>{await mount();await restored();expect(calls.analysis).toHaveBeenCalledWith('old-wafer')})
  it('prioritizes a fresh graph intent on initial mount without fetching the old analysis',async()=>{await mount('/evidence?intent=new-analysis&graph=glass-graph');await freshGlass();expect(calls.analysis).not.toHaveBeenCalled()})
  it('keeps setup non-interactive until delayed metadata and the one-time entry intent are settled',async()=>{
    let resolve!:()=>void;calls.refreshGraphs.mockImplementation(()=>new Promise<void>(r=>{resolve=r}))
    await mount('/evidence?intent=new-analysis&graph=glass-graph')
    expect(root.querySelector('.analysis-setup')).toBeNull();expect(root.querySelector('.analysis-initializing')?.textContent).toContain('正在准备')
    expect(calls.analysis).not.toHaveBeenCalled();resolve();await freshGlass()
    Array.from(root.querySelectorAll<HTMLButtonElement>('.input-kind-options button')).find(button=>button.textContent?.includes('Evidence'))!.click();await nextTick()
    const upload=root.querySelector<HTMLInputElement>('.inference-drop input')!;Object.defineProperty(upload,'files',{value:[new File(['{}'],'kept-frame.json',{type:'application/json'})]});upload.dispatchEvent(new Event('change',{bubbles:true}));await nextTick();await nextTick()
    expect(root.querySelector('.input-kind-options button.active')?.textContent).toContain('Evidence');expect(root.querySelector('.inference-drop')?.textContent).toContain('kept-frame.json');expect((root.querySelector('[aria-label="工作图谱"]')as HTMLSelectElement).value).toBe('glass-graph')
  })
  it('consumes a same-route graph intent arriving during initialization without restoring old history',async()=>{
    let resolve!:()=>void;calls.refreshGraphs.mockImplementation(()=>new Promise<void>(r=>{resolve=r}))
    await mount();expect(root.querySelector('.analysis-setup')).toBeNull();selectGraph('glass-graph');await nextTick();(root.querySelector('.rail-bottom a')as HTMLAnchorElement).click();await vi.waitFor(()=>expect(router.currentRoute.value.query.intent).toBe('new-analysis'));resolve();await freshGlass();expect(calls.analysis).not.toHaveBeenCalled()
  })
  it('uses the graph-page action after a different historical run was opened',async()=>{
    await mount();await restored();await router.push('/graphs')
    await vi.waitFor(()=>expect(root.querySelector('[aria-label="选择知识图谱"]')).not.toBeNull())
    const select=root.querySelector('[aria-label="选择知识图谱"]') as HTMLSelectElement;select.value='glass-graph';select.dispatchEvent(new Event('change',{bubbles:true}))
    await vi.waitFor(()=>expect(workspace.graphId).toBe('glass-graph'))
    await vi.waitFor(()=>expect(root.querySelector('.knowledge-inspector')).not.toBeNull())
    const button=Array.from(root.querySelectorAll<HTMLButtonElement>('.graph-toolbar button')).find(b=>b.textContent?.includes('使用此图分析'))!;button.click()
    await freshGlass();expect(calls.analysis).toHaveBeenCalledTimes(1)
  })
  it('handles the sidebar action while already on the analysis route',async()=>{
    await mount();await restored();selectGraph('glass-graph');await nextTick();(root.querySelector('.rail-bottom a') as HTMLAnchorElement).click()
    await freshGlass();expect(calls.analysis).toHaveBeenCalledTimes(1)
  })
  it('opens the requested candidate from a saved diagnostic without losing it to a section watcher',async()=>{
    calls.graph.mockImplementation(async(id:string)=>{const selected=workspace.graphs.find(g=>g.graph_id===id)!;return {schema_version:'rootlens-working-graph.v2',graph_id:id,title:selected.title,dataset:selected.dataset,build_id:'test',knowledge:{...selected.knowledge,hypotheses:[{hypothesis_id:'first',label:'首个候选',assumption_cost:1},{hypothesis_id:'second',label:'指定候选',assumption_cost:1}]}}})
    await mount('/graphs?graph=glass-graph&candidate=second')
    await vi.waitFor(()=>expect((root.querySelector('.knowledge-editor input') as HTMLInputElement)?.value).toBe('指定候选'))
  })
  it('does not let New Analysis overwrite the current graph with the historical graph',async()=>{
    await mount();await restored();selectGraph('glass-graph');await nextTick()
    Array.from(root.querySelectorAll<HTMLButtonElement>('.page-heading__actions button')).find(b=>b.textContent?.includes('新建分析'))!.click()
    await freshGlass();expect(calls.analysis).toHaveBeenCalledTimes(1)
  })
  it('ignores a late historical response after an explicit fresh-analysis action',async()=>{
    let resolve!:(value:AnalysisRun)=>void;calls.analysis.mockImplementation(()=>new Promise<AnalysisRun>(r=>{resolve=r}))
    await mount();await vi.waitFor(()=>expect(calls.analysis).toHaveBeenCalledTimes(1));selectGraph('glass-graph');await nextTick();(root.querySelector('.rail-bottom a') as HTMLAnchorElement).click();await freshGlass()
    resolve(oldRun);await nextTick();await nextTick();expect(root.querySelector('.run-results')).toBeNull();expect(workspace.analysisId).toBe('')
  })
})


function demo(dataset:Dataset,reference?:Partial<DemoGraphReference>):DemoGroup {
  const graph_ref:DemoGraphReference={graph_id:`${dataset}-paired`,title:'样例配套图',state:'ready',ready:true,enabled:true,available:true,note:'',asset_id:'paired-asset',download_url:'/api/demo-library/assets/paired',candidates:[],...reference}
  return {id:dataset,dataset,title:`${dataset}样例`,purpose:'真实输入',capability_id:'cap',materials:[],working_graph:{},graph_ref,samples:[{id:`sample-${dataset}`,title:'推荐样例输入',dataset,recommended:true,raw_input:{available:true},evidence:{available:true}}]}
}
async function loadRecommended(dataset:Dataset) {
  const label={mvtec:'视觉缺陷',tep:'过程监测',wafer:'晶圆图案'}[dataset]
  Array.from(root.querySelectorAll<HTMLButtonElement>('.demo-choice')).find(button=>button.textContent?.includes(label))!.click();await nextTick()
  Array.from(root.querySelectorAll<HTMLButtonElement>('.sample-entry-button')).find(button=>button.textContent?.includes('Evidence'))!.click();await nextTick();await nextTick()
}
function selectedGraphId(){return(root.querySelector('[aria-label="工作图谱"]')as HTMLSelectElement).value}
function chooseWorkingGraph(id:string){const select=root.querySelector('[aria-label="工作图谱"]')as HTMLSelectElement;select.value=id;select.dispatchEvent(new Event('change',{bubbles:true}))}
function configureDemoWorkspace(reference?:Partial<DemoGraphReference>){
  Object.assign(workspace,{graphId:'',graphSelection:'implicit',analysisId:'',graphs:[graph('strict-source','mvtec','严格原资料图'),graph('mvtec-paired','mvtec','玻璃配套图'),graph('tep-paired','tep','过程配套图'),graph('wafer-paired','wafer','晶圆配套图')],demos:{demos:[demo('mvtec',reference),demo('tep'),demo('wafer')],samples:[]}})
}
describe('recommended sample graph selection provenance',()=>{
  it('replaces only an implicit default with the exact paired graph in all three scenes',async()=>{
    configureDemoWorkspace();await mount();await vi.waitFor(()=>expect(root.querySelector('.analysis-setup')).not.toBeNull());expect(selectedGraphId()).toBe('strict-source');expect(workspace.graphSelection).toBe('implicit')
    for(const scene of ['mvtec','tep','wafer']as const){await loadRecommended(scene);expect(selectedGraphId()).toBe(`${scene}-paired`);expect(workspace.graphSelection).toBe('implicit');expect(root.querySelector('.demo-graph-context')?.textContent).toContain('已选择样例配套图')}
  })
  it('preserves a user dropdown choice and switches only on the explicit paired-graph action without clearing the input',async()=>{
    configureDemoWorkspace();await mount();await vi.waitFor(()=>expect(root.querySelector('.analysis-setup')).not.toBeNull());chooseWorkingGraph('strict-source');await nextTick();await loadRecommended('mvtec')
    expect(selectedGraphId()).toBe('strict-source');expect(root.querySelector('.demo-graph-context')?.textContent).toContain('保留你明确选择');expect(workspace.graphSelection).toBe('explicit')
    root.querySelector<HTMLButtonElement>('.demo-graph-context button')!.click();await nextTick();expect(selectedGraphId()).toBe('mvtec-paired');expect(root.querySelector('.loaded-demo-input')?.textContent).toContain('推荐样例输入');expect(root.querySelector('.input-kind-options button.active')?.textContent).toContain('Evidence')
  })
  it('preserves a route-selected strict graph when a recommended sample is loaded',async()=>{
    configureDemoWorkspace();await mount('/evidence?intent=new-analysis&graph=strict-source');await vi.waitFor(()=>expect(root.querySelector('.analysis-setup')).not.toBeNull());await loadRecommended('mvtec');expect(selectedGraphId()).toBe('strict-source');expect(workspace.graphSelection).toBe('explicit')
  })
  it('does not silently fall back to a same-scene graph when the paired graph is missing',async()=>{
    configureDemoWorkspace({graph_id:null,state:'missing',available:false,note:'请导入配套知识包'});await mount();await vi.waitFor(()=>expect(root.querySelector('.analysis-setup')).not.toBeNull());await loadRecommended('mvtec');expect(selectedGraphId()).toBe('');expect(root.querySelector('.demo-graph-context')?.textContent).toContain('请导入配套知识包');expect(Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(button=>button.textContent?.trim()==='开始分析')!.disabled).toBe(true)
  })
  it('keeps a cross-scene explicit graph until the user accepts the paired-graph action',async()=>{
    configureDemoWorkspace();await mount('/evidence?intent=new-analysis&graph=strict-source');await vi.waitFor(()=>expect(root.querySelector('.analysis-setup')).not.toBeNull());await loadRecommended('tep');expect(selectedGraphId()).toBe('strict-source');expect(root.querySelector('.demo-graph-context')?.textContent).toContain('保留你明确选择');expect(Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(button=>button.textContent?.trim()==='开始分析')!.disabled).toBe(true)
  })
  it('can adopt a newly available exact pairing after metadata refresh without clearing the input',async()=>{
    configureDemoWorkspace({graph_id:null,state:'missing',available:false});await mount();await vi.waitFor(()=>expect(root.querySelector('.analysis-setup')).not.toBeNull());await loadRecommended('mvtec');expect(selectedGraphId()).toBe('');workspace.demos={demos:[demo('mvtec'),demo('tep'),demo('wafer')],samples:[]};await nextTick();await nextTick();expect(selectedGraphId()).toBe('mvtec-paired');expect(root.querySelector('.loaded-demo-input')?.textContent).toContain('推荐样例输入');expect(root.querySelector('.input-kind-options button.active')?.textContent).toContain('Evidence')
  })
  it('does not let a later graph-list refresh replace an explicit choice or clear the loaded sample',async()=>{
    configureDemoWorkspace();await mount();await vi.waitFor(()=>expect(root.querySelector('.analysis-setup')).not.toBeNull());await loadRecommended('mvtec');chooseWorkingGraph('strict-source');await nextTick();workspace.graphs=[...workspace.graphs].reverse();await nextTick();expect(selectedGraphId()).toBe('strict-source');expect(root.querySelector('.loaded-demo-input')?.textContent).toContain('推荐样例输入')
  })
})
