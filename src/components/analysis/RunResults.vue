<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { IconDownload, IconArrowRight, IconInfoCircle, IconCheckCircle } from '@arco-design/web-vue/es/icon'
import type { AnalysisRun } from '@/api/workbench'
import { apiUrl } from '@/api/workbench'
import { workspace } from '@/services/workspace'
import { record, rows, text, texts, friendly, dateTime, datasetShort, outcomeLabel, downloadJson } from '@/services/presentation'
import { knowledgeOf } from '@/services/knowledge'
import { queriesFor, caseLabel, evaluationCandidates, displayLabels, normalGateClosed } from '@/services/analysis'
import EvidenceInspector from '@/components/analysis/EvidenceInspector.vue'
import ProofPanel from '@/components/analysis/ProofPanel.vue'
const props = defineProps<{ run: AnalysisRun }>()
defineEmits<{ newAnalysis: [] }>()
const caseIndex = ref(0), queryIndex = ref(0), selectedCandidateId = ref(''), focusObsId = ref('')
const currentCase = computed(() => props.run.cases[caseIndex.value] ?? props.run.cases[0])
const queries = computed(() => currentCase.value ? queriesFor(currentCase.value) : [])
const query = computed(() => queries.value[queryIndex.value] ?? queries.value[0])
const candidates = computed(() => evaluationCandidates(query.value?.result ?? {}))
const selectedCandidate = computed(() => candidates.value.find((c) => c.candidate_id === selectedCandidateId.value) ?? candidates.value[0] ?? null)
const names = computed(() => displayLabels(props.run, query.value?.result))
const knowledge = computed(() => knowledgeOf(props.run.working_graph_snapshot))
const rootkgd = computed(() => props.run.reasoner_id === 'tep_rootkgd')
const supports = computed(() => texts(selectedCandidate.value?.support_obs_ids))
const counters = computed(() => texts(selectedCandidate.value?.counter_obs_ids))
const usedIds = computed(() => {
  const ids = rows(query.value?.result.grounded_facts).flatMap((f) => texts(f.source_obs_ids))
  return [...new Set([...ids, ...supports.value, ...counters.value])]
})
const outcome = computed(() => text(query.value?.result.outcome))
const normalWindow = computed(() => normalGateClosed(query.value?.result ?? {}))
const outcomeDescription = computed(() => {
  if (normalWindow.value) return '本窗口未越过配套正常参考的异常门，不启动候选排名。完整窗口与52通道观测仍可检查。'
  if (rootkgd.value && ['supported','ambiguous'].includes(outcome.value)) return '按图传播与完整贡献向量的结构相容性排序；同分候选保留并列。'
  if (outcome.value === 'ambiguous') return '当前观测支持多个并列候选，还需要区分性观测。'
  if (outcome.value === 'supported') return '已有完整观测支持。这里呈现候选解释，而非已验证根因。'
  if (outcome.value === 'no_match') return '现有图谱条件没有形成完整支持。检查冲突、缺测和模型输出。'
  if (outcome.value === 'insufficient_evidence') return '关键观测缺失或不确定，不能用其他局部匹配代替完整支持。'
  return '逐项查看本次实际观测、知识条件与候选解释。'
})
const allFrames = computed(() => props.run.cases.flatMap((c) => c.evidence_frames ?? []))
function resetQuery() { selectedCandidateId.value = ''; focusObsId.value = ''; queryIndex.value = 0 }
function initialFocus(item: unknown) {
  const candidate = record(item), ids = texts(candidate.support_obs_ids)
  const observations = rows(query.value?.frame.observations).filter((o) => ids.includes(text(o.obs_id)))
  const contributions = observations.filter((o) => o.feature_id === 'residual.contribution').sort((a,b) => Number(record(b.value).number) - Number(record(a.value).number))
  return text((contributions[0] ?? observations.find((o) => o.feature_id === 'appearance.semantic_candidates') ?? observations[0])?.obs_id, texts(candidate.counter_obs_ids)[0] ?? '')
}
function chooseCandidate(id: string) { selectedCandidateId.value = id; focusObsId.value = initialFocus(candidates.value.find((c) => c.candidate_id === id)) }
function downloadEvidence() { downloadJson(`${props.run.title || '本次分析'}-Evidence.json`, allFrames.value.length === 1 ? allFrames.value[0] : { frames: allFrames.value }) }
watch(() => props.run.run_id, () => { caseIndex.value = 0; resetQuery() }, { immediate: true })
watch(caseIndex, resetQuery)
watch(() => query.value?.id, () => { selectedCandidateId.value = ''; focusObsId.value = initialFocus(candidates.value[0]) }, { immediate: true })
</script>
<template>
  <div class="run-results"><section class="analysis-run-bar panel"><div class="analysis-run-title"><span class="status-dot status-dot--green">已保存分析</span><h2>{{ friendly(run.title, '样本分析') }}</h2><p>{{ datasetShort[run.dataset] }} <span>·</span> {{ rootkgd ? 'TEP RootKGD 图传播' : '统一约束推理' }} <span>·</span> {{ dateTime(run.created_at) }}</p></div><div class="analysis-graph-context"><span class="section-kicker">本次图谱快照</span><strong>{{ friendly(run.graph_title, '运行时知识图谱') }}</strong><small>与后续图谱修改独立保存</small></div><div class="button-row"><a v-if="run.evidence_download_url" class="button button--secondary" :href="apiUrl(workspace.baseUrl,text(run.evidence_download_url))" download><IconDownload />下载本次 Evidence</a><button v-else class="button button--secondary" :disabled="!allFrames.length" @click="downloadEvidence"><IconDownload /> 下载本次 Evidence</button><button class="button button--ghost" @click="$emit('newAnalysis')">新建分析 <IconArrowRight /></button></div></section>
    <div v-if="run.cases.length > 1" class="analysis-case-tabs"><button v-for="(item,index) in run.cases" :key="item.case_id" :class="{ active: caseIndex === index }" @click="caseIndex = index"><span>{{ String(index + 1).padStart(2,'0') }}</span>{{ caseLabel(item,index) }}<i :class="queriesFor(item).some((q) => ['supported','ambiguous'].includes(text(q.result.outcome))) ? 'has-support' : ''" /></button></div>
    <div v-if="queries.length > 1" class="query-tabs"><span>关注区域</span><button v-for="(item,index) in queries" :key="item.id" :class="{ active: queryIndex === index }" @click="queryIndex = index">{{ item.label }}</button></div>
    <template v-if="query && currentCase"><section class="outcome-strip" :class="{ 'outcome-strip--supported': ['supported','ambiguous'].includes(outcome), 'outcome-strip--insufficient': outcome === 'insufficient_evidence' }"><IconCheckCircle v-if="['supported','ambiguous'].includes(outcome)" /><IconInfoCircle v-else /><div class="grow"><strong>{{ normalWindow ? '未越过正常参考异常门' : outcomeLabel(outcome) }}</strong><span>{{ outcomeDescription }}</span></div><span class="tag">{{ query.label }}</span></section><div class="analysis-evidence-grid"><EvidenceInspector :key="query.id" :case-item="currentCase" :frame="query.frame" :focus-obs-id="focusObsId" :support-obs-ids="supports" :counter-obs-ids="counters" :used-obs-ids="usedIds" @focus="focusObsId = $event" /><ProofPanel :result="query.result" :frame="query.frame" :knowledge="knowledge" :names="names" :selected-candidate-id="text(selectedCandidate?.candidate_id)" :focus-obs-id="focusObsId" :rootkgd="rootkgd" @candidate="chooseCandidate" @focus="focusObsId = $event" /></div></template>
    <div v-else class="panel empty-state"><h3>本次分析没有返回问题级结果</h3><p>输入和运行记录已保存，请检查后端任务的处理记录。</p></div>
    <details class="technical"><summary>本次运行引用与完整存档</summary><dl><dt>运行 ID</dt><dd><code>{{ run.run_id }}</code></dd><dt>图谱 ID</dt><dd><code>{{ run.graph_id }}</code></dd><dt>推理器</dt><dd>{{ run.reasoner_id }}</dd></dl><button class="button button--secondary button--small" @click="downloadJson(`${run.title}-完整分析.json`, run)">下载完整分析存档</button><pre>{{ JSON.stringify({ run_id: run.run_id, input_mode: run.input_mode, working_graph_snapshot: run.working_graph_snapshot },null,2) }}</pre></details>
  </div>
</template>
<style scoped>
.analysis-run-bar{padding:20px 22px;display:flex;align-items:center;gap:25px;margin-bottom:23px;}.analysis-run-title{min-width:180px;flex:1;}.analysis-run-title>.status-dot{font-size:11px;}.analysis-run-title h2{font-size:17px;margin:8px 0;}.analysis-run-title p{font-size:12px;color:#7f8ca1;margin:0;}.analysis-run-title p>span{margin:0 8px;color:#ccd4e2;}.analysis-graph-context{max-width:240px;padding:0 24px;border-left:1px solid var(--border);border-right:1px solid var(--border);}.analysis-graph-context>.section-kicker{display:block;font-size:11px;margin-bottom:7px;}.analysis-graph-context strong{font-size:13px;font-weight:500;color:#6e81a0;display:block;line-height:1.7;}.analysis-graph-context small{font-size:11px;color:#7f8ca1;margin-top:5px;display:block;}.analysis-run-bar .button{font-size:13px;min-height:34px;}.analysis-case-tabs{display:flex;gap:8px;overflow-x:auto;margin-bottom:18px;padding-bottom:3px;}.analysis-case-tabs button{display:flex;align-items:center;gap:10px;padding:12px 17px;min-width:170px;border:1px solid #e2e7f0;background:white;border-radius:7px;font-size:13px;color:#8a98af;}.analysis-case-tabs button>span{font-size:11px;color:#7f8ca1;font-variant-numeric:tabular-nums;}.analysis-case-tabs button>i{width:4px;height:4px;background:#c1c9d6;border-radius:50%;margin-left:auto;}.analysis-case-tabs button>i.has-support{background:#74aa90;}.analysis-case-tabs button.active{border-color:#7f8ca1;background:#f3f7ff;color:#4e76b9;}.analysis-case-tabs button.active>span{color:#88a3d4;}.query-tabs{display:flex;gap:8px;align-items:center;margin:0 0 18px;font-size:13px;color:#7f8ca1;}.query-tabs>span{margin-right:8px;}.query-tabs button{background:white;border:1px solid #e5eaf3;padding:7px 11px;border-radius:5px;color:#8397b5;font-size:13px;}.query-tabs button.active{background:#edf3ff;color:#5c83c3;border-color:#7f8ca1;}.outcome-strip{padding:16px 20px;background:#eef2f8;border:1px solid #e2e8f2;border-radius:8px;display:flex;gap:12px;align-items:center;margin-bottom:21px;color:#8ba0be;}.outcome-strip>svg{font-size:20px;color:#7f8ca1;}.outcome-strip strong{font-size:12px;font-weight:550;display:block;color:#657e9f;}.outcome-strip .grow>span{font-size:12px;color:#7f8ca1;display:block;margin-top:5px;line-height:1.7;}.outcome-strip--supported{background:#f0f7f4;border-color:#d9e8e1;}.outcome-strip--supported>svg{color:#7cae94;}.outcome-strip--supported strong{color:#61937b;}.outcome-strip--supported .grow>span{color:#7f8ca1;}.outcome-strip--insufficient{background:#faf6ed;border-color:#ece2cd;}.outcome-strip--insufficient>svg,.outcome-strip--insufficient strong{color:#7f8ca1;}.analysis-evidence-grid>.evidence-inspector{position:sticky;top:18px;max-height:calc(100vh - 36px);overflow-y:auto;}.analysis-evidence-grid{display:grid;grid-template-columns:minmax(0,.95fr) minmax(0,1.05fr);gap:23px;align-items:start;}
@media(max-width:1300px){.analysis-run-bar{flex-wrap:wrap;}.analysis-run-bar>.button-row{margin-left:auto;}.analysis-graph-context{border-right:0;}.analysis-evidence-grid{gap:17px;}.analysis-run-title{flex:1;}.analysis-graph-context{max-width:230px;}}@media(max-width:1000px){.analysis-evidence-grid>.evidence-inspector{position:static;max-height:none;overflow:visible;}.analysis-evidence-grid{grid-template-columns:1fr;}.analysis-run-bar{gap:18px;}.analysis-graph-context{padding-left:18px;}.analysis-run-bar>.button-row{margin-left:0;}.outcome-strip>.tag{display:none;}}@media(max-width:650px){.analysis-run-bar{padding:18px;}.analysis-graph-context{border-left:0;padding:0;max-width:none;}.analysis-run-title{width:100%;flex:auto;}.analysis-case-tabs button{min-width:150px;}.outcome-strip{padding:14px;}}
</style>
