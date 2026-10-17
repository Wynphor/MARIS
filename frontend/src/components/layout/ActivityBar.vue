<script setup lang="ts">
import { NIcon, NTooltip } from 'naive-ui'
import {
  HomeOutline, FolderOpenOutline, PlayOutline, CodeSlashOutline,
  ChatbubbleEllipsesOutline, AnalyticsOutline, SettingsOutline,
} from '@vicons/ionicons5'
import { useLayoutStore } from '../../stores/layout'

const layout = useLayoutStore()

const topItems = [
  { id: 'overview', icon: HomeOutline, label: '概览', panel: 'sidebar' as const },
  { id: 'files', icon: FolderOpenOutline, label: '文件', panel: 'sidebar' as const },
  { id: 'pipeline', icon: PlayOutline, label: '流水线', panel: 'bottom' as const },
  { id: 'chat', icon: ChatbubbleEllipsesOutline, label: '对话', panel: 'right' as const },
  { id: 'data', icon: AnalyticsOutline, label: '数据', panel: 'right' as const },
  { id: 'settings', icon: SettingsOutline, label: '设置', panel: 'sidebar' as const },
]

function isActive(id: string, panel: string): boolean {
  if (panel === 'sidebar') return layout.sidebarOpen && layout.sidebarPanel === id
  if (panel === 'right') return layout.rightSidebarOpen && layout.rightSidebarPanel === id
  if (panel === 'bottom') return layout.bottomOpen && layout.bottomTab === id
  return false
}

function handleClick(item: typeof topItems[0]) {
  if (item.panel === 'sidebar') layout.toggleSidebar(item.id as any)
  else if (item.panel === 'right') layout.toggleRightSidebar(item.id as any)
  else if (item.panel === 'bottom') layout.toggleBottom(item.id as any)
}
</script>

<template>
  <aside class="activity-bar">
    <div class="ab-top">
      <NTooltip v-for="item in topItems" :key="item.id" placement="right" trigger="hover">
        <template #trigger>
          <button
            class="ab-btn"
            :class="{ active: isActive(item.id, item.panel) }"
            @click="handleClick(item)"
          >
            <NIcon :size="22"><component :is="item.icon" /></NIcon>
            <!-- Active indicator bar -->
            <div v-if="isActive(item.id, item.panel)" class="ab-indicator"></div>
          </button>
        </template>
        {{ item.label }}
      </NTooltip>
    </div>
  </aside>
</template>

<style scoped>
.activity-bar {
  width: 48px;
  min-width: 48px;
  display: flex;
  flex-direction: column;
  background: var(--bg-0);
  border-right: 1px solid var(--border);
  z-index: 10;
}

.ab-top {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 4px;
  gap: 2px;
}

.ab-btn {
  width: 48px;
  height: 48px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--fg-3);
  position: relative;
  transition: color 0.15s;
}

.ab-btn:hover {
  color: var(--fg-1);
  background: var(--bg-hover);
}

.ab-btn.active {
  color: var(--fg-1);
}

.ab-indicator {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--orange);
  border-radius: 0 1px 1px 0;
}
</style>
