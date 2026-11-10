import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import type { CandidateConditionCatalog } from '@/api/candidate-conditions'
const calls=vi.hoisted(()=>({catalog:vi.fn(),add:vi.fn(),remove:vi.fn()}))
vi.mock('@/api/candidate-conditions',()=>({candidateConditionsApi:()=>calls}))
vi.mock('@/services/workspace',()=>({workspace:{baseUrl:'http://127.0.0.1:8012'}}))
import Panel from './CandidateConditions.vue'
const catalog:CandidateConditionCatalog={conditions:[],features:[{feature_id:'statistics.slope_z',value_kind:'number',unit:'1/sample',definition:'保留正负方向的标准化斜率。',requires_reference:true,allowed_values:null,allowed_operators:['gte','lte'],subject_kind:'variable'}],subjects:[{entity_id:'e10',label:'冷却水阀',external_id:'xmv_10'}],zones:[]}
const Modal=defineComponent({props:['visible'],setup(props,{slots}){return()=>props.visible?h('div',slots.default?.()):null}})
let app:App|null=null,root:HTMLElement
function mount(disabled=false){root=document.createElement('div');document.body.append(root);app=createApp(Panel,{graphId:'graph',candidateId:'candidate:a',candidateName:'入口温度扰动',knowledge:{source_assertions:[]},disabled}).component('AModal',Modal);app.mount(root)}
async function open(){(root.querySelector('.candidate-condition-entry button')as HTMLButtonElement).click();await vi.waitFor(()=>expect(root.querySelector('.condition-wizard form')).not.toBeNull())}
async function input(selector:string,value:string,event='input'){const el=root.querySelector(selector) as HTMLInputElement;el.value=value;el.dispatchEvent(new Event(event,{bubbles:true}));await nextTick()}
beforeEach(()=>{vi.clearAllMocks();calls.catalog.mockResolvedValue(catalog);calls.add.mockResolvedValue({graph:{},conditions:[]});calls.remove.mockResolvedValue({graph:{},conditions:[]})})
afterEach(()=>{app?.unmount();app=null;document.body.innerHTML='';vi.unstubAllGlobals()})
describe('candidate-condition wizard',()=>{
  it('is lazy and blocks entry while other graph changes are unsaved',()=>{mount(true);expect((root.querySelector('button')as HTMLButtonElement).disabled).toBe(true);expect(calls.catalog).not.toHaveBeenCalled()})
  it('submits a typed condition for only the selected candidate using the actual variable and operator catalog',async()=>{
    mount();await open();await input('[aria-label="诊断条件名称"]','冷却水阀负方向变化')
    await input('[aria-label="测量特征"]','statistics.slope_z','change');await input('[aria-label="判断方式"]','lte','change');await input('[aria-label="条件值"]','-0.01');await input('[aria-label="诊断条件变量"]','e10','change')
    expect(Array.from(root.querySelectorAll<HTMLOptionElement>('[aria-label="判断方式"] option')).map(o=>o.value)).toEqual(['gte','lte'])
    expect((root.querySelector('button[type="submit"]')as HTMLButtonElement).disabled).toBe(false)
    root.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await vi.waitFor(()=>expect(calls.add).toHaveBeenCalledOnce())
    expect(calls.add).toHaveBeenCalledWith(expect.objectContaining({candidate_id:'candidate:a',feature_id:'statistics.slope_z',op:'lte',operand:{kind:'number',number:-.01,unit:'1/sample'},subject_entity_id:'e10',zone:null,source_assertion_ids:[]}))
  })
  it('does not offer an unsafe delete when the backend reports a shared dependency',async()=>{
    calls.catalog.mockResolvedValue({...catalog,conditions:[{condition_id:'own',candidate_id:'candidate:a',label:'已有条件',feature_id:'statistics.slope_z',op:'gte',operand:{kind:'number',number:1,unit:'1/sample'},subject_entity_id:'e10',mode:'expected',can_delete:false,delete_blocker:'此条件已被其他关系引用。'}]});mount();await open()
    const button=Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(b=>b.textContent?.includes('撤销条件'))!
    expect(button.disabled).toBe(true);expect(root.textContent).toContain('已被其他关系引用');expect(calls.remove).not.toHaveBeenCalled()
  })
})
