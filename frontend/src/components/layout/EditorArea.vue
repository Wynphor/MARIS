<script setup lang="ts">
import { NIcon } from 'naive-ui'
import { computed, defineAsyncComponent } from 'vue'
import { CodeSlashOutline, AnalyticsOutline, CloseOutline } from '@vicons/ionicons5'
import { useLayoutStore } from '../../stores/layout'

const layout = useLayoutStore()

const tabInfo: Record<string, { label: string; icon: any }> = {
  editor: { label: '编辑器', icon: CodeSlashOutline },
  data: { label: '数据探索', icon: AnalyticsOutline },
}

const panels: Record<string, any> = {
  editor: defineAsyncComponent(() => import('../../pages/Editor.vue')),
  data: defineAsyncComponent(() => import('../../pages/DataExplorer.vue')),
}

const activeComponent = computed(() => panels[layout.activeEditorTab])

function closeTab(tab: string) {
  layout.closeEditorTab(tab as any)
}
</script>

<template>
  <div class="editor-area">
    <!-- Tab bar -->
    <div class="ea-tabs">
      <div
        v-for="tab in layout.editorTabs" :key="tab"
        class="ea-tab" :class="{ active: layout.activeEditorTab === tab }"
        @click="layout.activeEditorTab = tab"
      >
        <NIcon :size="13"><component :is="tabInfo[tab]?.icon || CodeSlashOutline" /></NIcon>
        <span>{{ tabInfo[tab]?.label || tab }}</span>
        <button
          v-if="layout.editorTabs.length > 1"
          class="ea-tab-close"
          @click.stop="closeTab(tab)"
        >
          <NIcon :size="10"><CloseOutline /></NIcon>
        </button>
      </div>
      <div class="ea-spacer"></div>
    </div>

    <!-- Editor content -->
    <div class="ea-body">
      <component :is="activeComponent" />
    </div>
  </div>
</template>

<style scoped>
.editor-area {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  min-width: 0;
}

.ea-tabs {
  display: flex;
  align-items: center;
  height: 34px;
  min-height: 34px;
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
  padding: 0;
  overflow-x: auto;
}

.ea-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 0 14px;
  height: 100%;
  font-size: 11px;
  color: var(--fg-3);
  cursor: pointer;
  border-right: 1px solid var(--border);
  border-bottom: 2px solid transparent;
  transition: all 0.1s;
  white-space: nowrap;
  position: relative;
}

.ea-tab:hover {
  color: var(--fg-2);
  background: var(--bg-hover);
}

.ea-tab.active {
  color: var(--fg-1);
  background: var(--bg-0);
  border-bottom-color: var(--orange);
}

.ea-tab-close {
  background: transparent;
  border: none;
  color: var(--fg-3);
  cursor: pointer;
  padding: 2px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  margin-left: 4px;
  opacity: 0;
  transition: opacity 0.1s;
}

.ea-tab:hover .ea-tab-close {
  opacity: 1;
}

.ea-tab-close:hover {
  background: var(--bg-3);
  color: var(--fg-1);
}

.ea-spacer {
  flex: 1;
  border-bottom: 2px solid transparent;
}

.ea-body {
  flex: 1;
  overflow: hidden;
  background: var(--bg-0);
}
</style>
