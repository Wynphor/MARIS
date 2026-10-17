<script setup lang="ts">
import { NSelect } from 'naive-ui'
import { ref, onMounted, onUnmounted } from 'vue'
import { healthApi } from '../../api/client'
import { useWorkspaceStore } from '../../stores/workspace'

const wsStore = useWorkspaceStore()
const backendOk = ref(false)
let poll: ReturnType<typeof setInterval> | null = null

async function check() {
  try {
    const { data } = await healthApi.check()
    backendOk.value = data.status === 'healthy'
  } catch { backendOk.value = false }
}

onMounted(() => { check(); poll = setInterval(check, 15000) })
onUnmounted(() => { if (poll) clearInterval(poll) })

defineExpose({ backendOk })
</script>

<template>
  <header class="titlebar">
    <div class="tb-left">
      <div class="logo-badge">M</div>
      <span class="tb-title">MathModel</span>
    </div>
    <div class="tb-center">
      <NSelect
        v-if="wsStore.workspaces.length"
        :value="wsStore.currentId"
        :options="wsStore.workspaces.map(w => ({ label: w.title, value: w.id }))"
        size="tiny"
        placeholder="选择工作区"
        @update:value="(v: string) => wsStore.selectWorkspace(v)"
        class="tb-ws"
      />
    </div>
    <div class="tb-right">
      <span class="health-dot" :class="backendOk ? 'on' : 'off'"></span>
    </div>
  </header>
</template>

<style scoped>
.titlebar {
  height: 36px;
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
  -webkit-app-region: drag;
  user-select: none;
}

.tb-left {
  display: flex;
  align-items: center;
  gap: 8px;
  -webkit-app-region: no-drag;
}

.logo-badge {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  background: linear-gradient(135deg, var(--orange), #f0a060);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 11px;
  font-family: var(--mono);
}

.tb-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--fg-1);
}

.tb-center {
  flex: 1;
  display: flex;
  justify-content: center;
  -webkit-app-region: no-drag;
}

.tb-ws {
  width: 260px;
}

.tb-right {
  display: flex;
  align-items: center;
  -webkit-app-region: no-drag;
}

.health-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: block;
}

.health-dot.on {
  background: var(--green);
  box-shadow: 0 0 6px rgba(61, 214, 140, 0.4);
}

.health-dot.off {
  background: var(--red);
}
</style>
