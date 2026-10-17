<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NButton, NSpace, NText, NTag, NModal, NForm, NFormItem, NInput, NSelect, NEmpty, useMessage } from 'naive-ui'
import { useWorkspaceStore, type Workspace } from '../stores/workspace'

const store = useWorkspaceStore()
const message = useMessage()
const showModal = ref(false)
const creating = ref(false)
const newTitle = ref('')
const newQuestionId = ref('')
const newType = ref('国赛')

const typeOptions = [
  { label: '国赛 (CUMCM)', value: '国赛' },
  { label: '美赛 (MCM/ICM)', value: '美赛' },
  { label: '研究生数模', value: '研赛' },
  { label: '省赛', value: '省赛' },
]

function statusLabel(s: string): string {
  const m: Record<string, string> = {
    INIT: '初始化', DECOMPOSED: '已拆解', MODELED: '已建模', CODED: '已编码',
    WRITTEN: '已写作', REVIEWED: '已审查', CHECKED: '已检查', IMPROVED: '已改进',
    PACKED: '已打包', FINISHED: '已完成',
  }
  return m[s] || s
}

onMounted(() => store.fetchWorkspaces())

async function create() {
  if (!newTitle.value) return
  creating.value = true
  try {
    await store.createWorkspace(newTitle.value, newQuestionId.value, newType.value)
    message.success('工作区创建成功')
    showModal.value = false; newTitle.value = ''; newQuestionId.value = ''
  } catch (e: any) { message.error(e.message) }
  finally { creating.value = false }
}
</script>

<template>
  <div style="padding: 16px 20px">
    <div class="page-header">
      <div><h2 class="page-title">工作区</h2><p class="page-desc">创建和管理竞赛工作区</p></div>
      <NButton type="primary" @click="showModal = true">+ 新建工作区</NButton>
    </div>

    <NEmpty v-if="!store.workspaces.length" description="暂无工作区" style="margin-top: 60px">
      <template #extra><NButton type="primary" @click="showModal = true">创建工作区</NButton></template>
    </NEmpty>

    <div v-else class="card-grid">
      <div v-for="ws in store.workspaces" :key="ws.id" class="ws-card" :class="{ active: ws.id === store.currentId }" @click="store.selectWorkspace(ws.id)">
        <div class="ws-top">
          <div class="ws-name">{{ ws.title }}</div>
          <NTag v-if="ws.id === store.currentId" size="tiny" type="warning">当前</NTag>
        </div>
        <div class="ws-meta">
          <NTag size="tiny">{{ ws.problem_type }}</NTag>
          <NTag v-if="ws.question_id" size="tiny" type="info">题号 {{ ws.question_id }}</NTag>
          <NTag size="tiny">{{ statusLabel(ws.status) }}</NTag>
        </div>
        <div class="ws-date">{{ ws.created_at ? new Date(ws.created_at).toLocaleDateString('zh-CN') : '' }}</div>
      </div>
    </div>

    <NModal v-model:show="showModal" preset="card" title="新建工作区" style="max-width: 480px; background: var(--bg-surface)">
      <NForm label-placement="left" label-width="80">
        <NFormItem label="题目"><NInput v-model:value="newTitle" placeholder="例：自驾行程规划" /></NFormItem>
        <NFormItem label="题号"><NInput v-model:value="newQuestionId" placeholder="C / D / E" /></NFormItem>
        <NFormItem label="类型"><NSelect v-model:value="newType" :options="typeOptions" /></NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showModal = false">取消</NButton>
          <NButton type="primary" @click="create" :loading="creating" :disabled="!newTitle">创建</NButton>
        </NSpace>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
.ws-card {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 16px; cursor: pointer; transition: border-color 0.15s;
}
.ws-card:hover { border-color: var(--text-muted); }
.ws-card.active { border-color: var(--accent); }
.ws-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.ws-name { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.ws-meta { display: flex; gap: 6px; margin-bottom: 10px; }
.ws-date { font-size: 11px; color: var(--text-muted); }
</style>
