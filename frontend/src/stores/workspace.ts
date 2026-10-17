/**
 * Workspace 全局状态
 * - currentId 持久化到 localStorage
 * - selectWorkspace 自动获取 dashboard
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { workspaceApi } from '../api/client'

export interface Workspace {
  id: string
  title: string
  question_id: string
  problem_type: string
  status: string
  created_at: string
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const workspaces = ref<Workspace[]>([])
  const currentId = ref<string>(localStorage.getItem('mathmodel_ws_id') || '')
  const dashboard = ref<any>(null)
  const config = ref<any>(null)
  const loading = ref(false)

  const current = computed(() =>
    workspaces.value.find((w) => w.id === currentId.value),
  )

  // 持久化 currentId
  watch(currentId, (v) => {
    if (v) localStorage.setItem('mathmodel_ws_id', v)
    else localStorage.removeItem('mathmodel_ws_id')
  })

  async function fetchWorkspaces() {
    loading.value = true
    try {
      const { data } = await workspaceApi.list()
      workspaces.value = data
      // 如果 currentId 不在列表中，选第一个
      if (data.length > 0 && !data.find((w: Workspace) => w.id === currentId.value)) {
        currentId.value = data[0].id
      }
    } finally {
      loading.value = false
    }
  }

  async function createWorkspace(title: string, questionId: string, problemType: string) {
    const { data } = await workspaceApi.create({
      title, question_id: questionId, problem_type: problemType,
    })
    workspaces.value.unshift(data)
    currentId.value = data.id
    return data
  }

  async function fetchDashboard() {
    if (!currentId.value) return
    try {
      const { data } = await workspaceApi.dashboard(currentId.value)
      dashboard.value = data
    } catch { dashboard.value = null }
  }

  async function fetchConfig() {
    if (!currentId.value) return
    try {
      const { data } = await workspaceApi.getConfig(currentId.value)
      config.value = data
    } catch { config.value = null }
  }

  function selectWorkspace(id: string) {
    currentId.value = id
    dashboard.value = null
    config.value = null
    fetchDashboard()
  }

  async function updateConfig(updates: Record<string, any>) {
    if (!currentId.value) return
    const { data } = await workspaceApi.updateConfig(currentId.value, updates)
    config.value = data
    return data
  }

  return {
    workspaces, currentId, current, dashboard, config, loading,
    fetchWorkspaces, createWorkspace, fetchDashboard, fetchConfig, selectWorkspace, updateConfig,
  }
})
