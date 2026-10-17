<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { useLayoutStore } from '../../stores/layout'
import TitleBar from './TitleBar.vue'
import ActivityBar from './ActivityBar.vue'
import PrimarySidebar from './PrimarySidebar.vue'
import EditorArea from './EditorArea.vue'
import SecondarySidebar from './SecondarySidebar.vue'
import BottomPanel from './BottomPanel.vue'
import StatusBar from './StatusBar.vue'

const wsStore = useWorkspaceStore()
const layout = useLayoutStore()
const titleBarRef = ref<InstanceType<typeof TitleBar> | null>(null)

onMounted(() => {
  wsStore.fetchWorkspaces()
  layout.loadSizes()
})
</script>

<template>
  <div class="ide-shell">
    <!-- Title Bar -->
    <TitleBar ref="titleBarRef" />

    <!-- Main Body -->
    <div class="ide-body">
      <!-- Activity Bar (left icon strip) -->
      <ActivityBar />

      <!-- Primary Sidebar (left — overview/files/settings) -->
      <PrimarySidebar />

      <!-- Center Area (editor + bottom panel) -->
      <div class="ide-center">
        <!-- Editor Area with tabs -->
        <EditorArea />

        <!-- Bottom Panel (pipeline/terminal/output/problems) -->
        <BottomPanel />
      </div>

      <!-- Secondary Sidebar (right — AI chat / data) -->
      <SecondarySidebar />
    </div>

    <!-- Status Bar -->
    <StatusBar :backend-ok="titleBarRef?.backendOk ?? false" />
  </div>
</template>

<style scoped>
.ide-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.ide-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.ide-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}
</style>
