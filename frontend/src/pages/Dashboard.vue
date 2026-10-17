<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  NGrid, NGi, NCard, NProgress, NTag,
  NSpace, NText, NButton, NEmpty, NSpin, useMessage,
} from 'naive-ui'
import { useWorkspaceStore } from '../stores/workspace'
import { useRouter } from 'vue-router'
import { workspaceApi } from '../api/client'

const store = useWorkspaceStore()
const router = useRouter()
const message = useMessage()
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

onMounted(async () => {
  await store.fetchWorkspaces()
  if (store.currentId) await store.fetchDashboard()
})

const statusColors: Record<string, string> = {
  INIT: '#666', DECOMPOSED: '#60a0f0', MODELED: '#a78bfa', CODED: '#38bdf8',
  WRITTEN: '#3dd68c', REVIEWED: '#f0b040', CHECKED: '#3dd68c', IMPROVED: '#3dd68c',
  PACKED: '#f06060', FINISHED: '#3dd68c',
}

function statusLabel(s: string): string {
  const m: Record<string, string> = {
    INIT: '初始化', DECOMPOSED: '已拆解', MODELED: '已建模', CODED: '已编码',
    WRITTEN: '已写作', REVIEWED: '已审查', CHECKED: '已检查', IMPROVED: '已改进',
    PACKED: '已打包', FINISHED: '已完成',
  }
  return m[s] || s
}

function downloadPdf(id: string) { window.open(workspaceApi.downloadPdf(id), '_blank') }
function downloadZip(id: string) { window.open(workspaceApi.downloadZip(id), '_blank') }

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length || !store.currentId) return
  uploading.value = true
  try {
    const fd = new FormData()
    for (let i = 0; i < input.files.length; i++) fd.append('files', input.files[i])
    await workspaceApi.upload(store.currentId, fd)
    message.success(`上传 ${input.files.length} 个文件成功`)
    store.fetchDashboard()
  } catch (e: any) { message.error(e.message) }
  finally { uploading.value = false; input.value = '' }
}
</script>

<template>
  <div style="padding: 16px 20px">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h2 class="page-title">仪表盘</h2>
        <p class="page-desc">MathModel-Engine · 数学建模竞赛全流程自动化</p>
      </div>
      <NSpace>
        <input ref="fileInput" type="file" multiple style="display:none"
          accept=".pdf,.csv,.xlsx,.xls,.txt,.md,.py" @change="handleUpload" />
        <NButton :loading="uploading" :disabled="!store.currentId" @click="fileInput?.click()">
          上传文件
        </NButton>
        <NButton type="primary" @click="router.push('/workspace')">+ 新建</NButton>
      </NSpace>
    </div>

    <NSpin :show="store.loading">
      <NEmpty v-if="!store.workspaces.length" description="还没有工作区" style="margin-top: 60px">
        <template #extra>
          <NButton type="primary" @click="router.push('/workspace')">创建工作区</NButton>
        </template>
      </NEmpty>

      <div v-else>
        <!-- 当前工作区概览 -->
        <div v-if="store.dashboard" class="overview">
          <div class="overview-grid">
            <div class="stat">
              <div class="stat-label">工作区</div>
              <div class="stat-value">{{ store.dashboard.workspace.title }}</div>
            </div>
            <div class="stat">
              <div class="stat-label">状态</div>
              <div class="stat-value" :style="{ color: statusColors[store.dashboard.workspace.status] }">
                {{ statusLabel(store.dashboard.workspace.status) }}
              </div>
            </div>
            <div class="stat">
              <div class="stat-label">进度</div>
              <div class="stat-value accent">{{ store.dashboard.progress.percentage }}%</div>
            </div>
            <div class="stat">
              <div class="stat-label">阶段</div>
              <div class="stat-value">{{ store.dashboard.progress.completed_stages }}/{{ store.dashboard.progress.total_stages }}</div>
            </div>
          </div>
          <NProgress type="line" :percentage="store.dashboard.progress.percentage" :show-indicator="false" :color="'#e87a35'" style="margin-top: 12px" />
        </div>

        <!-- 工作区卡片 -->
        <div class="section-label" style="margin: 24px 0 12px">工作区</div>
        <div class="card-grid">
          <div v-for="ws in store.workspaces" :key="ws.id" class="ws-card" :class="{ active: ws.id === store.currentId }" @click="store.selectWorkspace(ws.id)">
            <div class="ws-card-top">
              <div class="ws-name">{{ ws.title }}</div>
              <NTag size="tiny" :style="{ background: statusColors[ws.status] + '20', color: statusColors[ws.status], border: 'none' }">
                {{ statusLabel(ws.status) }}
              </NTag>
            </div>
            <div class="ws-card-meta">
              <span v-if="ws.question_id">题号 {{ ws.question_id }}</span>
              <span>{{ ws.problem_type }}</span>
            </div>
            <div class="ws-card-actions" @click.stop>
              <NButton size="tiny" @click.stop="store.selectWorkspace(ws.id); router.push('/pipeline')">执行</NButton>
              <NButton size="tiny" @click.stop="store.selectWorkspace(ws.id); router.push('/editor')">编辑</NButton>
              <NButton size="tiny" @click.stop="store.selectWorkspace(ws.id); router.push('/chat')">对话</NButton>
              <NButton size="tiny" type="success" @click.stop="downloadPdf(ws.id)">PDF</NButton>
              <NButton size="tiny" @click.stop="downloadZip(ws.id)">ZIP</NButton>
            </div>
          </div>
        </div>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
.overview {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
}
.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.stat-value { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.stat-value.accent { color: var(--accent); }
.section-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text-muted); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
.ws-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.ws-card:hover { border-color: var(--text-muted); }
.ws-card.active { border-color: var(--accent); }
.ws-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.ws-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.ws-card-meta { display: flex; gap: 8px; margin-bottom: 12px; }
.ws-card-meta span { font-size: 11px; color: var(--text-muted); background: var(--bg-hover); padding: 2px 6px; border-radius: 3px; }
.ws-card-actions { display: flex; gap: 6px; }
</style>
