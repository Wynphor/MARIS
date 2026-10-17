<script setup lang="ts">
import { computed } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { useLayoutStore } from '../../stores/layout'

const props = defineProps<{ backendOk: boolean }>()
const wsStore = useWorkspaceStore()
const layout = useLayoutStore()

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    INIT: '初始化', DECOMPOSED: '已拆解', MODELED: '已建模', CODED: '已编码',
    WRITTEN: '已写作', REVIEWED: '已审查', CHECKED: '已检查', IMPROVED: '已改进',
    PACKED: '已打包', FINISHED: '已完成',
  }
  return map[wsStore.current?.status || ''] || wsStore.current?.status || ''
})
</script>

<template>
  <footer class="statusbar">
    <span class="sb-item sb-branch">
      <span class="sb-dot" :class="backendOk ? 'on' : 'off'"></span>
      {{ backendOk ? '已连接' : '离线' }}
    </span>
    <span class="sb-sep">│</span>
    <span class="sb-item" v-if="wsStore.current">
      {{ wsStore.current.title }}
    </span>
    <span class="sb-sep" v-if="wsStore.current">│</span>
    <span class="sb-item" v-if="statusLabel">{{ statusLabel }}</span>

    <span class="sb-spacer"></span>

    <span class="sb-item sb-click" @click="layout.toggleBottom()">
      流水线
    </span>
    <span class="sb-sep">│</span>
    <span class="sb-item">UTF-8</span>
    <span class="sb-sep">│</span>
    <span class="sb-item">MathModel v2.0</span>
  </footer>
</template>

<style scoped>
.statusbar {
  height: 22px;
  min-height: 22px;
  display: flex;
  align-items: center;
  padding: 0 10px;
  gap: 6px;
  background: #1a1a2e;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--fg-3);
  font-family: var(--mono);
  user-select: none;
}

.sb-item {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.sb-click {
  cursor: pointer;
  padding: 0 4px;
}

.sb-click:hover {
  background: rgba(255,255,255,0.08);
  color: var(--fg-2);
}

.sb-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.sb-dot.on {
  background: var(--green);
}

.sb-dot.off {
  background: var(--red);
}

.sb-sep {
  color: var(--border-l);
  font-size: 10px;
}

.sb-spacer {
  flex: 1;
}
</style>
