<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { NCard, NButton, NSpace, NText, NEmpty, NInput, NModal } from 'naive-ui'
import { useWorkspaceStore } from '../stores/workspace'
import { pipelineApi, BASE_URL } from '../api/client'
import { streamSSE, type SSEMessage } from '../api/sse'

const store = useWorkspaceStore()
interface StageInfo { name: string; description: string; ai_required: boolean; depends_on: string[] }

const stages = ref<StageInfo[]>([])
const lines = ref<string[]>([])
const isRunning = ref(false)
const currentStage = ref('')
const stageStatus = ref<Record<string, 'ok' | 'err' | 'run'>>({})
const consoleRef = ref<HTMLElement | null>(null)
let abort: AbortController | null = null

const showReject = ref(false)
const rejectFeedback = ref('')

onMounted(async () => {
  const { data } = await pipelineApi.stages()
  stages.value = data.stages
  await store.fetchWorkspaces()
})

async function run(stage: StageInfo) {
  if (!store.currentId || isRunning.value) return
  isRunning.value = true; currentStage.value = stage.name
  stageStatus.value[stage.name] = 'run'
  push(`\n━━━ ${stage.name} ━━━  ${stage.description}`)
  abort = new AbortController()
  try {
    for await (const m of streamSSE(`${BASE_URL}/api/v1/pipeline/execute`,
      { workspace_id: store.currentId, stage: stage.name, mode: 'API' },
      { signal: abort.signal })) { push(m.text || m.raw) }
    stageStatus.value[stage.name] = 'ok'
  } catch (e: any) {
    if (e.name !== 'AbortError') { push(`[ERROR] ${e.message}`); stageStatus.value[stage.name] = 'err' }
  } finally { isRunning.value = false; currentStage.value = ''; abort = null }
}

async function runAll() {
  if (!store.currentId || isRunning.value) return
  isRunning.value = true; currentStage.value = 'run-all'
  push('\n━━━ 全流程 ━━━'); abort = new AbortController()
  try {
    for await (const m of streamSSE(`${BASE_URL}/api/v1/pipeline/run-all?workspace_id=${store.currentId}`, {},
      { signal: abort.signal })) { push(m.text || m.raw) }
  } catch (e: any) { if (e.name !== 'AbortError') push(`[ERROR] ${e.message}`) }
  finally { isRunning.value = false; currentStage.value = ''; abort = null }
}

function cancel() { abort?.abort() }
async function approve() { if (store.currentId) { await pipelineApi.approve(store.currentId); push('[OK] 已审批') } }
async function reject() { if (store.currentId) { await pipelineApi.reject(store.currentId, rejectFeedback.value); push(`[REJECT] ${rejectFeedback.value}`); showReject.value = false; rejectFeedback.value = '' } }
function push(s: string) { lines.value.push(s); nextTick(() => { if (consoleRef.value) consoleRef.value.scrollTop = consoleRef.value.scrollHeight }) }
function cls(s: StageInfo) { return stageStatus.value[s.name] === 'ok' ? 'done' : stageStatus.value[s.name] === 'err' ? 'fail' : stageStatus.value[s.name] === 'run' ? 'running' : '' }
</script>

<template>
  <div style="padding: 8px 12px; height: 100%; display: flex; flex-direction: column; gap: 8px;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <NSpace align="center" :size="6">
        <NButton v-if="isRunning" type="error" size="tiny" @click="cancel">■ 停止</NButton>
        <NButton v-else type="primary" size="tiny" :disabled="!store.currentId" @click="runAll">▶ 全流程</NButton>
        <NButton size="tiny" :disabled="!store.currentId" @click="approve">✓</NButton>
        <NButton size="tiny" :disabled="!store.currentId" @click="showReject = true">✗</NButton>
        <NButton size="tiny" :disabled="isRunning" @click="lines = []">清空</NButton>
      </NSpace>
      <span style="font-size: 10px; color: var(--fg-3)">{{ isRunning ? currentStage : '就绪' }}</span>
    </div>

    <NEmpty v-if="!store.currentId" description="请先选择工作区" style="margin-top: 60px" />

    <div v-else style="display: flex; flex-direction: column; gap: 12px">
      <!-- Stage Grid -->
      <div class="stage-grid">
        <button v-for="s in stages" :key="s.name" class="stage-btn" :class="cls(s)"
          :disabled="isRunning" @click="run(s)">
          <span class="sn">{{ s.name }}</span>
          <span class="sd">{{ s.description }}</span>
        </button>
      </div>

      <!-- Console -->
      <div class="console-box" style="flex: 1; min-height: 200px; display: flex; flex-direction: column;">
        <div class="console-header">
          <span>输出</span>
          <span v-if="isRunning" class="blink">●</span>
        </div>
        <div ref="consoleRef" class="console-body" style="flex: 1; height: auto;">
          <div v-if="!lines.length" class="console-empty">$ 等待执行...</div>
          <div v-for="(l, i) in lines" :key="i" :class="{
            'c-err': /\[ERROR\]/.test(l), 'c-ok': /\[SUCCESS\]/.test(l),
            'c-warn': /\[WARNING\]/.test(l), 'c-info': /\[INFO\]/.test(l),
            'c-hdr': l.startsWith('━━━'),
          }">{{ l }}</div>
          <span v-if="isRunning" class="cursor">▌</span>
        </div>
      </div>
    </div>

    <NModal v-model:show="showReject" preset="card" title="拒绝原因" style="max-width: 400px; background: var(--bg-surface)">
      <NInput v-model:value="rejectFeedback" type="textarea" :rows="3" placeholder="输入拒绝原因..." />
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showReject = false">取消</NButton>
          <NButton type="error" @click="reject">拒绝</NButton>
        </NSpace>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.stage-grid { display: flex; gap: 4px; flex-wrap: wrap; }
.stage-btn {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px;
  padding: 5px 10px; cursor: pointer; text-align: left; transition: all 0.12s;
  display: flex; align-items: center; gap: 6px;
}
.stage-btn:hover:not(:disabled) { border-color: var(--accent); background: var(--accent-glow); }
.stage-btn.running { border-color: var(--accent); background: var(--accent-glow); animation: glow 1.5s infinite; }
.stage-btn.done { border-color: var(--success); }
.stage-btn.done .sn { color: var(--success); }
.stage-btn.fail { border-color: var(--error); }
.stage-btn.fail .sn { color: var(--error); }
.stage-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.sn { font-size: 11px; font-weight: 600; font-family: var(--font-mono); color: var(--text-primary); }
.sd { font-size: 9px; color: var(--text-muted); display: none; }
@keyframes glow { 0%,100% { box-shadow: 0 0 0 0 transparent } 50% { box-shadow: 0 0 8px var(--accent-glow) } }

.console-box { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; }
.console-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
}
.console-body {
  padding: 14px; height: 400px; overflow-y: auto;
  font-family: var(--font-mono); font-size: 12px; line-height: 1.7;
  white-space: pre-wrap; word-break: break-all; color: #b0b0b0;
}
.console-empty { color: var(--text-muted); }
.c-err { color: var(--error); }
.c-ok { color: var(--success); }
.c-warn { color: var(--warning); }
.c-info { color: var(--info); }
.c-hdr { color: var(--accent); font-weight: 600; }
.cursor { color: var(--accent); animation: blink 0.8s infinite; }
@keyframes blink { 0%,100% { opacity:1 } 50% { opacity:0 } }
.blink { color: var(--accent); animation: blink 1s infinite; }
</style>
