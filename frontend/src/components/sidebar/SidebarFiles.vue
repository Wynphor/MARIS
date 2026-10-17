<script setup lang="ts">
import { NIcon, NEmpty } from 'naive-ui'
import { ref, watch, computed } from 'vue'
import {
  DocumentTextOutline, CodeSlashOutline, FolderOutline,
  FolderOpenOutline, ImageOutline, GridOutline,
} from '@vicons/ionicons5'
import { workspaceApi } from '../../api/client'
import { useWorkspaceStore } from '../../stores/workspace'
import { useLayoutStore } from '../../stores/layout'

const wsStore = useWorkspaceStore()
const layout = useLayoutStore()
const files = ref<string[]>([])
const loading = ref(false)
const expandedDirs = ref<Set<string>>(new Set(['paper', 'src', 'data']))

interface FileNode {
  name: string
  path: string
  isDir: boolean
  children: FileNode[]
  ext?: string
}

const tree = computed<FileNode[]>(() => {
  const root: FileNode[] = []
  const map = new Map<string, FileNode>()

  for (const f of files.value) {
    const parts = f.replace(/\\/g, '/').split('/')
    let current = root
    let builtPath = ''

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      builtPath += (builtPath ? '/' : '') + part
      const isLast = i === parts.length - 1

      let existing = current.find(n => n.name === part)
      if (!existing) {
        existing = {
          name: part,
          path: builtPath,
          isDir: !isLast,
          children: [],
          ext: isLast ? part.split('.').pop() : undefined,
        }
        current.push(existing)
        map.set(builtPath, existing)
      }
      if (!isLast) {
        existing.isDir = true
        current = existing.children
      }
    }
  }
  return root
})

function getIcon(node: FileNode) {
  if (node.isDir) return expandedDirs.value.has(node.path) ? FolderOpenOutline : FolderOutline
  const ext = node.ext?.toLowerCase()
  if (ext === 'tex' || ext === 'cls' || ext === 'bib') return DocumentTextOutline
  if (ext === 'py' || ext === 'json' || ext === 'yaml') return CodeSlashOutline
  if (ext === 'png' || ext === 'jpg' || ext === 'pdf') return ImageOutline
  if (ext === 'csv' || ext === 'xlsx') return GridOutline
  return DocumentTextOutline
}

function toggleDir(path: string) {
  if (expandedDirs.value.has(path)) expandedDirs.value.delete(path)
  else expandedDirs.value.add(path)
}

function openFile(node: FileNode) {
  if (node.isDir) {
    toggleDir(node.path)
    return
  }
  // Switch to editor tab and set the file
  layout.openEditorTab('editor')
  // Emit a global event so Editor can pick it up
  window.dispatchEvent(new CustomEvent('open-file', { detail: node.path }))
}

async function loadFiles() {
  if (!wsStore.currentId) return
  loading.value = true
  try {
    const { data } = await workspaceApi.tree(wsStore.currentId)
    files.value = data?.files || []
  } catch { files.value = [] }
  loading.value = false
}

watch(() => wsStore.currentId, loadFiles, { immediate: true })
</script>

<template>
  <div class="sidebar-files">
    <div class="sf-header">
      <span class="sf-title">文件资源管理器</span>
      <span class="sf-count" v-if="files.length">{{ files.length }}</span>
    </div>

    <div v-if="loading" class="sf-loading">加载中...</div>

    <NEmpty v-else-if="!files.length" description="无文件" size="small" />

    <div v-else class="sf-tree">
      <template v-for="node in tree" :key="node.path">
        <div
          class="sf-item"
          :class="{ 'is-dir': node.isDir, 'expanded': expandedDirs.has(node.path) }"
          @click="openFile(node)"
        >
          <NIcon :size="14" class="sf-icon"><component :is="getIcon(node)" /></NIcon>
          <span class="sf-name">{{ node.name }}</span>
        </div>
        <template v-if="node.isDir && expandedDirs.has(node.path)">
          <div
            v-for="child in node.children" :key="child.path"
            class="sf-item sf-child"
            :class="{ 'is-dir': child.isDir }"
            @click="openFile(child)"
          >
            <NIcon :size="13" class="sf-icon"><component :is="getIcon(child)" /></NIcon>
            <span class="sf-name">{{ child.name }}</span>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.sidebar-files {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.sf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}

.sf-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--fg-3);
}

.sf-count {
  font-size: 9px;
  color: var(--fg-3);
  background: var(--bg-3);
  padding: 1px 5px;
  border-radius: 8px;
  font-family: var(--mono);
}

.sf-loading {
  padding: 20px;
  text-align: center;
  color: var(--fg-3);
  font-size: 11px;
}

.sf-tree {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.sf-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 12px;
  cursor: pointer;
  transition: background 0.1s;
  font-size: 12px;
  color: var(--fg-2);
}

.sf-item:hover {
  background: var(--bg-hover);
  color: var(--fg-1);
}

.sf-child {
  padding-left: 28px;
}

.sf-icon {
  flex-shrink: 0;
  color: var(--fg-3);
}

.sf-item.is-dir .sf-icon {
  color: var(--orange-dim);
}

.sf-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
