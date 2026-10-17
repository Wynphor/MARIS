<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { NIcon } from 'naive-ui'
import { CloseOutline } from '@vicons/ionicons5'
import { useLayoutStore } from '../../stores/layout'
import SplitHandle from './SplitHandle.vue'

const layout = useLayoutStore()

const panels: Record<string, any> = {
  chat: defineAsyncComponent(() => import('../../pages/Chat.vue')),
  data: defineAsyncComponent(() => import('../../pages/DataExplorer.vue')),
}

const tabLabels: Record<string, string> = {
  chat: 'AI 助手',
  data: '数据预览',
}

const activeComponent = computed(() => panels[layout.rightSidebarPanel])

function onResize(delta: number) {
  layout.rightSidebarWidth = Math.max(260, Math.min(700, layout.rightSidebarWidth - delta))
  layout.saveSizes()
}
</script>

<template>
  <div v-if="layout.rightSidebarOpen" class="secondary-sidebar" :style="{ width: layout.rightSidebarWidth + 'px' }">
    <SplitHandle direction="horizontal" @resize="onResize" />
    <div class="ss-inner">
      <!-- Tab bar -->
      <div class="ss-tabs">
        <button
          v-for="(label, key) in tabLabels" :key="key"
          class="ss-tab" :class="{ active: layout.rightSidebarPanel === key }"
          @click="layout.rightSidebarPanel = key as any"
        >
          {{ label }}
        </button>
        <div class="ss-spacer"></div>
        <button class="ss-close" @click="layout.rightSidebarOpen = false">
          <NIcon :size="14"><CloseOutline /></NIcon>
        </button>
      </div>
      <!-- Content -->
      <div class="ss-body">
        <component :is="activeComponent" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.secondary-sidebar {
  display: flex;
  flex-shrink: 0;
  background: var(--bg-1);
  overflow: hidden;
}

.ss-inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid var(--border);
}

.ss-tabs {
  display: flex;
  align-items: center;
  height: 32px;
  min-height: 32px;
  padding: 0 4px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-2);
  gap: 0;
}

.ss-tab {
  background: transparent;
  border: none;
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 500;
  color: var(--fg-3);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.1s;
  white-space: nowrap;
}

.ss-tab:hover {
  color: var(--fg-2);
}

.ss-tab.active {
  color: var(--orange);
  border-bottom-color: var(--orange);
}

.ss-spacer {
  flex: 1;
}

.ss-close {
  background: transparent;
  border: none;
  color: var(--fg-3);
  cursor: pointer;
  padding: 4px;
  border-radius: 3px;
  display: flex;
  align-items: center;
}

.ss-close:hover {
  background: var(--bg-hover);
  color: var(--fg-1);
}

.ss-body {
  flex: 1;
  overflow: hidden;
}
</style>
