<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { NDataTable, NEmpty, NIcon } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { GridOutline } from '@vicons/ionicons5'
import { useWorkspaceStore } from '../stores/workspace'
import { workspaceApi } from '../api/client'

const store = useWorkspaceStore()
const preview = ref<any>(null)

async function loadPreview() {
  if (!store.currentId) return
  try { const { data } = await workspaceApi.dataPreview(store.currentId); preview.value = data }
  catch { preview.value = null }
}

onMounted(() => { if (store.currentId) loadPreview() })
watch(() => store.currentId, () => { if (store.currentId) loadPreview() })

function getColumns(): DataTableColumns<any> {
  if (!preview.value?.columns) return []
  return preview.value.columns.map((c: any) => ({ title: c.name, key: c.name, ellipsis: { tooltip: true } }))
}
</script>

<template>
  <div class="data-page">
    <NEmpty v-if="!store.currentId" description="请先选择工作区" size="small">
      <template #icon><NIcon :size="28"><GridOutline /></NIcon></template>
    </NEmpty>
    <NEmpty v-else-if="!preview" description="未找到数据文件" size="small">
      <template #icon><NIcon :size="28"><GridOutline /></NIcon></template>
    </NEmpty>
    <div v-else class="data-content">
      <div class="info-bar">
        <span class="info-file">{{ preview.file }}</span>
        <span class="info-meta">{{ preview.rows }} 行 × {{ preview.columns?.length }} 列</span>
      </div>
      <div class="col-section">
        <div class="section-label">列信息</div>
        <div v-for="col in preview.columns" :key="col.name" class="col-row">
          <span class="col-name">{{ col.name }}</span>
          <span class="col-type">{{ col.dtype }}</span>
          <span class="col-null">null: {{ col.null_count }} ({{ col.null_pct }}%)</span>
          <span class="col-uniq">唯一: {{ col.unique }}</span>
        </div>
      </div>
      <div class="table-section">
        <div class="section-label">数据预览</div>
        <NDataTable :columns="getColumns()" :data="preview.sample || []" :bordered="false" size="small" :scroll-x="600" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.data-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.data-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 14px;
  overflow-y: auto;
  flex: 1;
}

.info-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 4px;
}

.info-file {
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--orange);
}

.info-meta {
  font-size: 11px;
  color: var(--fg-3);
}

.col-section, .table-section {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 10px;
}

.section-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--fg-3);
  margin-bottom: 6px;
}

.col-row {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px solid var(--border);
  font-size: 11px;
}

.col-row:last-child { border-bottom: none; }
.col-name { min-width: 120px; font-weight: 500; color: var(--fg-1); font-family: var(--mono); font-size: 11px; }
.col-type { min-width: 60px; color: var(--orange); font-family: var(--mono); }
.col-null, .col-uniq { color: var(--fg-3); font-size: 10px; }
</style>
