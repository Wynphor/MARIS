<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { useLayoutStore } from '../../stores/layout'
import SplitHandle from './SplitHandle.vue'
import SidebarOverview from '../sidebar/SidebarOverview.vue'
import SidebarFiles from '../sidebar/SidebarFiles.vue'
import SidebarSettings from '../sidebar/SidebarSettings.vue'

const layout = useLayoutStore()

const panels: Record<string, any> = {
  overview: SidebarOverview,
  files: SidebarFiles,
  settings: SidebarSettings,
}

const activeComponent = computed(() => panels[layout.sidebarPanel])

function onResize(delta: number) {
  layout.sidebarWidth = Math.max(180, Math.min(500, layout.sidebarWidth + delta))
  layout.saveSizes()
}
</script>

<template>
  <div v-if="layout.sidebarOpen" class="primary-sidebar" :style="{ width: layout.sidebarWidth + 'px' }">
    <div class="ps-content">
      <component :is="activeComponent" />
    </div>
    <SplitHandle direction="horizontal" @resize="onResize" />
  </div>
</template>

<style scoped>
.primary-sidebar {
  display: flex;
  flex-shrink: 0;
  background: var(--bg-1);
  border-right: 1px solid var(--border);
  overflow: hidden;
}

.ps-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}
</style>
