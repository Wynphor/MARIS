<script setup lang="ts">
import { NIcon } from 'naive-ui'
import { defineAsyncComponent } from 'vue'
import { ChevronUpOutline, CloseOutline } from '@vicons/ionicons5'
import { useLayoutStore } from '../../stores/layout'
import SplitHandle from './SplitHandle.vue'

const layout = useLayoutStore()

const tabs = [
  { id: 'pipeline', label: '流水线' },
  { id: 'terminal', label: '终端' },
  { id: 'output', label: '输出' },
  { id: 'problems', label: '问题' },
]

const tabLabels: Record<string, string> = Object.fromEntries(tabs.map(t => [t.id, t.label]))

const panels: Record<string, any> = {
  pipeline: defineAsyncComponent(() => import('../../pages/Pipeline.vue')),
}

function onResize(delta: number) {
  layout.bottomHeight = Math.max(120, Math.min(600, layout.bottomHeight - delta))
  layout.saveSizes()
}
</script>

<template>
  <!-- Collapsed state -->
  <div v-if="!layout.bottomOpen" class="bp-collapsed" @click="layout.bottomOpen = true">
    <NIcon :size="10"><ChevronUpOutline /></NIcon>
    <span class="bp-collapsed-tabs">
      <button
        v-for="tab in tabs" :key="tab.id"
        class="bp-collapsed-tab"
        :class="{ active: layout.bottomTab === tab.id }"
        @click.stop="layout.bottomTab = tab.id as any; layout.bottomOpen = true"
      >
        {{ tab.label }}
      </button>
    </span>
  </div>

  <!-- Expanded state -->
  <template v-else>
    <SplitHandle direction="vertical" @resize="onResize" />
    <div class="bp-panel" :style="{ height: layout.bottomHeight + 'px' }">
      <!-- Tab bar -->
      <div class="bp-header">
        <div class="bp-tabs">
          <button
            v-for="tab in tabs" :key="tab.id"
            class="bp-tab" :class="{ active: layout.bottomTab === tab.id }"
            @click="layout.bottomTab = tab.id as any"
          >
            {{ tab.label }}
          </button>
        </div>
        <button class="bp-close" @click="layout.bottomOpen = false" title="关闭面板">
          <NIcon :size="13"><CloseOutline /></NIcon>
        </button>
      </div>

      <!-- Content -->
      <div class="bp-body">
        <component v-if="panels[layout.bottomTab]" :is="panels[layout.bottomTab]" />
        <div v-else class="bp-placeholder">
          <span v-if="layout.bottomTab === 'terminal'" class="bp-ph-text">终端功能开发中...</span>
          <span v-else-if="layout.bottomTab === 'output'" class="bp-ph-text">输出面板开发中...</span>
          <span v-else-if="layout.bottomTab === 'problems'" class="bp-ph-text">问题面板开发中...</span>
        </div>
      </div>
    </div>
  </template>
</template>

<style scoped>
.bp-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-1);
  flex-shrink: 0;
  overflow: hidden;
  border-top: 1px solid var(--border);
}

.bp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  min-height: 32px;
  padding: 0 8px;
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
}

.bp-tabs {
  display: flex;
  gap: 0;
}

.bp-tab {
  background: transparent;
  border: none;
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 500;
  color: var(--fg-3);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.1s;
}

.bp-tab:hover {
  color: var(--fg-2);
}

.bp-tab.active {
  color: var(--orange);
  border-bottom-color: var(--orange);
}

.bp-close {
  background: transparent;
  border: none;
  color: var(--fg-3);
  cursor: pointer;
  padding: 4px;
  border-radius: 3px;
  display: flex;
  align-items: center;
}

.bp-close:hover {
  background: var(--bg-hover);
  color: var(--fg-1);
}

.bp-body {
  flex: 1;
  overflow: hidden;
}

.bp-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--fg-3);
  font-size: 12px;
}

.bp-ph-text {
  opacity: 0.6;
}

/* Collapsed state */
.bp-collapsed {
  height: 24px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  background: var(--bg-1);
  border-top: 1px solid var(--border);
  cursor: pointer;
  color: var(--fg-3);
  transition: background 0.1s;
}

.bp-collapsed:hover {
  background: var(--bg-2);
  color: var(--fg-2);
}

.bp-collapsed-tabs {
  display: flex;
  gap: 0;
}

.bp-collapsed-tab {
  background: transparent;
  border: none;
  padding: 2px 8px;
  font-size: 10px;
  color: var(--fg-3);
  cursor: pointer;
}

.bp-collapsed-tab:hover {
  color: var(--fg-2);
}

.bp-collapsed-tab.active {
  color: var(--orange);
}
</style>
