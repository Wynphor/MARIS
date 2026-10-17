<script setup lang="ts">
import { ref, onMounted, watch, computed, onUnmounted } from 'vue'
import { NButton, NSpace, NSelect, NInput, NTag, useMessage } from 'naive-ui'
import { useWorkspaceStore } from '../stores/workspace'
import { editorApi, workspaceApi } from '../api/client'

const store = useWorkspaceStore()
const message = useMessage()
const filePath = ref('paper/main.tex')
const content = ref('')
const originalContent = ref('')
const diffResult = ref<any>(null)
const aiInstruction = ref('')
const isEditing = ref(false)
const isSaving = ref(false)
const isLoading = ref(false)
const isCompiling = ref(false)
const compileResult = ref<any>(null)
const fileOptions = ref<{ label: string; value: string }[]>([
  { label: 'paper/main.tex', value: 'paper/main.tex' },
  { label: 'src/solve_all.py', value: 'src/solve_all.py' },
])

const hasChanges = computed(() => content.value !== originalContent.value)

async function loadFile() {
  if (!store.currentId) return; isLoading.value = true
  try {
    const { data } = await editorApi.readFile(store.currentId, filePath.value)
    content.value = data.content || ''; originalContent.value = data.content || ''
  } catch { content.value = ''; originalContent.value = '' }
  finally { isLoading.value = false }
}

async function saveFile() {
  if (!store.currentId) return; isSaving.value = true
  try {
    await editorApi.saveFile(store.currentId, filePath.value, content.value)
    originalContent.value = content.value; message.success('已保存')
  } finally { isSaving.value = false }
}

async function loadDiff() {
  if (!store.currentId) return
  const { data } = await editorApi.diff(store.currentId, filePath.value); diffResult.value = data
}

async function aiEdit() {
  if (!store.currentId || !aiInstruction.value) return; isEditing.value = true
  try {
    await editorApi.aiEdit(store.currentId, filePath.value, aiInstruction.value)
    await loadFile(); aiInstruction.value = ''; message.success('AI 修改完成')
  } finally { isEditing.value = false }
}

async function compile() {
  if (!store.currentId) return; isCompiling.value = true; compileResult.value = null
  try {
    const { data } = await editorApi.compile(store.currentId)
    compileResult.value = data
    message.success(data.status === 'success' ? '编译成功' : '编译失败')
  } catch (e: any) { message.error(e.message) }
  finally { isCompiling.value = false }
}

async function loadFileTree() {
  if (!store.currentId) return
  try {
    const { data } = await workspaceApi.tree(store.currentId)
    const files = data?.files || data || []
    const opts = Array.isArray(files)
      ? files.filter((f: string) => /\.(tex|py|md|json|txt|csv)$/i.test(f)).map((f: string) => ({ label: f, value: f }))
      : []
    if (opts.length) fileOptions.value = opts
  } catch {}
}

function onOpenFile(e: Event) {
  const detail = (e as CustomEvent).detail
  if (detail && typeof detail === 'string') {
    filePath.value = detail
    loadFile()
  }
}

watch(filePath, () => loadFile())
watch(() => store.currentId, () => { if (store.currentId) { loadFile(); loadFileTree() } })
onMounted(() => {
  if (store.currentId) { loadFile(); loadFileTree() }
  window.addEventListener('open-file', onOpenFile)
})
onUnmounted(() => { window.removeEventListener('open-file', onOpenFile) })
</script>

<template>
  <div class="editor-page">
    <NEmpty v-if="!store.currentId" description="请先选择工作区" style="margin-top: 60px" />

    <div v-else class="editor-content">
      <!-- Toolbar -->
      <div class="toolbar">
        <NSelect v-model:value="filePath" :options="fileOptions" size="small" style="min-width: 180px; max-width: 300px;" />
        <NButton size="tiny" @click="loadFile" :loading="isLoading">刷新</NButton>
        <NButton size="tiny" type="primary" @click="saveFile" :loading="isSaving" :disabled="!hasChanges">保存</NButton>
        <NButton size="tiny" @click="loadDiff">Diff</NButton>
        <NButton size="tiny" type="success" @click="compile" :loading="isCompiling">编译</NButton>
        <NTag v-if="hasChanges" size="tiny" type="warning">未保存</NTag>
        <NTag v-if="compileResult?.status === 'success'" size="tiny" type="success">编译成功</NTag>
      </div>

      <!-- Editor -->
      <div class="editor-wrap">
        <textarea v-model="content" class="editor-area" spellcheck="false" />
      </div>

      <!-- AI Edit -->
      <div class="ai-bar">
        <NInput v-model:value="aiInstruction" placeholder="AI 修改指令，例如：在第三章加入灵敏度分析" size="small" />
        <NButton type="primary" :loading="isEditing" :disabled="!aiInstruction" @click="aiEdit" size="small">AI 修改</NButton>
      </div>

      <!-- Diff -->
      <div v-if="diffResult" class="diff-panel">
        <div class="diff-header">变更对比</div>
        <pre v-if="diffResult.has_changes" class="diff-body">{{ diffResult.diff }}</pre>
        <div v-else class="diff-body" style="color: var(--fg-3)">无变更</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.editor-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 12px;
  flex: 1;
  overflow: hidden;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 4px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.editor-wrap {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
  min-height: 0;
}

.editor-area {
  width: 100%;
  height: 100%;
  padding: 12px;
  background: var(--bg-0);
  color: #c8c8c8;
  border: none;
  outline: none;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.65;
  resize: none;
}

.ai-bar {
  display: flex;
  gap: 6px;
  padding: 6px 10px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 4px;
  flex-shrink: 0;
}

.diff-panel {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
  max-height: 200px;
}

.diff-header {
  padding: 4px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 10px;
  font-weight: 600;
  color: var(--fg-3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.diff-body {
  padding: 10px;
  max-height: 160px;
  overflow: auto;
  font-family: var(--mono);
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: #b0b0b0;
}
</style>
