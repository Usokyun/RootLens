<script setup lang="ts">
import { computed, ref } from 'vue'
import { IconPlus, IconRefresh, IconDelete } from '@arco-design/web-vue/es/icon'
import { candidateConditionsApi, type CandidateConditionCatalog, type CandidateConditionInput } from '@/api/candidate-conditions'
import type { RecordValue } from '@/api/workbench'
import { workspace } from '@/services/workspace'
import { emptyCandidateCondition, selectConditionFeature, candidateConditionIssues } from '@/services/candidate-conditions'
import { rows, text, friendly, materialLocator, conditionText, channelLabel } from '@/services/presentation'
import ConditionPredicateEditor from '@/components/graphs/ConditionPredicateEditor.vue'
const props=defineProps<{graphId:string;candidateId:string;candidateName:string;knowledge:RecordValue;disabled:boolean}>()
const emit=defineEmits<{changed:[]}>()
const open=ref(false),loading=ref(false),saving=ref(false),removing=ref(''),error=ref('')
const catalog=ref<CandidateConditionCatalog|null>(null)
const form=ref<CandidateConditionInput>(emptyCandidateCondition(props.candidateId))
const existing=computed(()=>catalog.value?.conditions.filter(row=>row.candidate_id===props.candidateId)??[])
const features=computed(()=>catalog.value?.features.map(row=>({...row,producerDeclared:true,registered:true}))??[])
const selectedFeature=computed(()=>catalog.value?.features.find(row=>row.feature_id===form.value.feature_id))
const issues=computed(()=>catalog.value?candidateConditionIssues(form.value,catalog.value):[])
const sources=computed(()=>rows(props.knowledge.source_assertions))
async function load() {
  loading.value=true;error.value=''
  try{catalog.value=await candidateConditionsApi(workspace.baseUrl,props.graphId).catalog()}
  catch(e){error.value=e instanceof Error?e.message:String(e)}
  finally{loading.value=false}
}
function begin(){form.value=emptyCandidateCondition(props.candidateId);catalog.value=null;open.value=true;void load()}
function updateCondition(next:RecordValue){
  if(!catalog.value)return
  if(next.feature_id!==form.value.feature_id)form.value=selectConditionFeature(form.value,text(next.feature_id),catalog.value)
  else form.value={...form.value,op:text(next.op),operand:next.operand as RecordValue}
}
function toggleSource(id:string){const selected=form.value.source_assertion_ids;form.value.source_assertion_ids=selected.includes(id)?selected.filter(value=>value!==id):[...selected,id]}
async function add(){
  if(!catalog.value||issues.value.length)return
  saving.value=true;error.value=''
  try{await candidateConditionsApi(workspace.baseUrl,props.graphId).add(form.value);open.value=false;emit('changed')}
  catch(e){error.value=e instanceof Error?e.message:String(e)}
  finally{saving.value=false}
}
async function remove(id:string){
  if(!window.confirm('撤销这条专属条件及其独立关系？只影响后续新分析，已有运行保留原快照。'))return
  removing.value=id;error.value=''
  try{await candidateConditionsApi(workspace.baseUrl,props.graphId).remove(id);open.value=false;emit('changed')}
  catch(e){error.value=e instanceof Error?e.message:String(e)}
  finally{removing.value=''}
}
</script>
<template>
  <div class="candidate-condition-entry"><button type="button" class="button button--secondary button--small" :disabled="disabled" @click="begin"><IconPlus />新增诊断条件</button><small>{{ disabled ? '先保存当前修改，再添加候选专属条件。' : '也可查看 / 撤销本入口新增的专属条件' }}</small></div>
  <a-modal v-model:visible="open" title="候选专属诊断条件" :footer="false" width="760px" :mask-closable="!saving && !removing" :closable="!saving && !removing">
    <div class="condition-wizard"><header><span class="section-kicker">仅连接当前候选</span><h3>{{ candidateName }}</h3><p>创建独立观测条件、联合现象与期待关系，不修改其他候选共享的机制。新条件与本图已有异常门联合；缺少有效门控时无法创建。</p></header>
      <div v-if="loading" class="loading-inline"><IconRefresh class="is-spinning" />读取合法特征与已绑定变量…</div>
      <p v-if="error" class="error-text" role="alert">{{ error }} <button type="button" class="text-button" :disabled="loading || saving" @click="load">重读目录</button></p>
      <template v-if="catalog && !loading">
        <details v-if="existing.length" class="condition-existing" open><summary>本候选已添加的专属条件（{{ existing.length }}）</summary><article v-for="condition in existing" :key="condition.condition_id"><div><strong>{{ condition.label }}</strong><p>{{ conditionText(condition as unknown as RecordValue) }} · {{ friendly(condition.mode) }}</p><small>{{ condition.subject_entity_id ? catalog.subjects.find(subject=>subject.entity_id===condition.subject_entity_id)?.label : '当前关注对象' }}<span v-if="condition.zone"> · {{ friendly(condition.zone) }}</span></small><p v-if="condition.can_delete===false" class="error-text">{{ condition.delete_blocker || '此条件已有共享依赖，不能通过专属操作撤销。' }}</p></div><button type="button" class="text-button danger" :disabled="saving || !!removing || condition.can_delete===false" @click="remove(condition.condition_id)"><IconDelete />{{ removing===condition.condition_id?'正在撤销…':'撤销条件' }}</button></article></details>
        <form class="form-stack" @submit.prevent="add">
          <label class="field">条件名称<input v-model="form.label" aria-label="诊断条件名称" required placeholder="描述要检查的实际表现" /></label>
          <ConditionPredicateEditor :condition="form as unknown as RecordValue" :features="features" @update="updateCondition" />
          <label v-if="selectedFeature?.subject_kind==='variable'" class="field">已绑定过程变量<select v-model="form.subject_entity_id" aria-label="诊断条件变量" required><option :value="null" disabled>选择已有绑定的通道</option><option v-for="subject in catalog.subjects" :key="subject.entity_id" :value="subject.entity_id">{{ subject.external_id ? channelLabel(subject.external_id) : friendly(subject.label) }}</option></select><small>这里只能选本图已有变量。未知变量先在图谱中核对绑定，不会猜测通道或制造测量。</small></label>
          <label v-if="catalog.zones.length" class="field">适用晶圆区域<select v-model="form.zone" aria-label="诊断条件区域" required><option :value="null" disabled>选择区域</option><option v-for="zone in catalog.zones" :key="zone" :value="zone">{{ friendly(zone) }}</option></select></label>
          <label class="field">期待关系<select v-model="form.mode" aria-label="诊断条件关系"><option value="expected">预期表现 · 不满足按已有冲突代价处理</option><option value="necessary">必要条件 · 不满足或缺测阻止支持排名</option><option value="possible">可能表现 · 不要求一定出现</option></select></label>
          <label class="field">条件说明<textarea v-model="form.description" aria-label="诊断条件说明" rows="2" placeholder="说明依据、适用范围与阈值理由" /></label>
          <details class="condition-sources"><summary>选择已有资料依据（可选）</summary><p>未选择资料时，后端明确记录为人工演示条件，不伪造文献或原文定位。</p><article v-for="(source,index) in sources" :key="text(source.assertion_id)"><label class="checkbox-label"><input type="checkbox" :checked="form.source_assertion_ids.includes(text(source.assertion_id))" @change="toggleSource(text(source.assertion_id))" />{{ friendly(source.origin) }} · {{ source.locator?materialLocator(source.locator):`来源 ${index+1}` }}</label><details><summary>查看依据正文</summary><p>{{ source.text }}</p></details></article><p v-if="!sources.length">本图暂无可选择的资料断言。</p></details>
          <p class="wizard-engine-note">RootKGD 按图传播与贡献结构评分，不执行条件阈值；新增 / 删除图关系可能改变结构评分。这里的阈值与期待模式主验收使用统一约束推理。</p>
          <ul v-if="issues.length" class="wizard-issues"><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul>
          <footer class="button-row"><button type="button" class="button button--secondary" :disabled="saving || !!removing" @click="open=false">取消</button><button type="submit" class="button button--primary" :disabled="saving || !!removing || !!issues.length">{{ saving?'保存专属条件…':'保存并仅连接此候选' }}</button></footer>
        </form>
      </template>
    </div>
  </a-modal>
</template>
<style scoped>
.candidate-condition-entry{border-top:1px solid #e5eaf3;padding-top:15px;display:flex;flex-direction:column;gap:8px;}.candidate-condition-entry small{font-size:11px;color:#8292aa;line-height:1.7;}.condition-wizard{max-height:74vh;overflow:auto;padding:0 4px 3px;}.condition-wizard header{margin-bottom:20px;}.condition-wizard header h3{font-size:17px;color:#465f85;margin:7px 0;}.condition-wizard p{font-size:12px;color:#7c8da6;line-height:1.8;}.condition-wizard .form-stack{gap:17px;}.condition-wizard :deep(.field){font-size:13px;}.condition-existing{margin-bottom:22px;font-size:13px;color:#647b9d;}.condition-existing>article{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:13px 0;border-bottom:1px solid #edf0f6;}.condition-existing strong{font-size:13px;font-weight:500;}.condition-existing p{margin:5px 0;}.condition-existing small{font-size:11px;color:#8a98ab;}.danger{color:#b77678;}.condition-sources{font-size:12px;color:#7186a5;}.condition-sources>article{margin:10px 0;padding:10px 12px;background:#f8faff;border-radius:5px;}.condition-sources summary{cursor:pointer;}.condition-sources article details{margin-top:8px;color:#8b9ab0;}.condition-sources article p{color:#62748d;}.wizard-engine-note{padding:12px;background:#f6f8fc;border-radius:5px;}.wizard-issues{font-size:12px;line-height:1.8;color:#ad7d7d;margin:0;padding-left:20px;}.condition-wizard footer{justify-content:flex-end;position:sticky;bottom:-3px;background:white;padding:14px 0 3px;border-top:1px solid #edf1f6;}
</style>
