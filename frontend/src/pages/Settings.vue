<script setup lang="ts">
import {
  NCard, NForm, NFormItem, NInput, NSelect, NButton, NSpace,
  NSwitch, NInputNumber, NTag, NIcon, useMessage,
} from 'naive-ui'
import { ref, onMounted, watch } from 'vue'
import {
  CheckmarkCircleOutline, AlertCircleOutline, ServerOutline,
  KeyOutline, SettingsOutline, CloudOutline,
} from '@vicons/ionicons5'
import { healthApi, systemApi } from '../api/client'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const message = useMessage()
const saving = ref(false)
const sysSaving = ref(false)

// Health
const health = ref<any>(null)

// System config
const sysConfig = ref<any>(null)
const defaultModel = ref('')

// Competition config
const localConfig = ref<any>({})

// Provider editing
const editingProvider = ref<string | null>(null)
const providerKey = ref('')
const providerUrl = ref('')

const compTypes = [
  { label: 'CUMCM 国赛', value: '国赛' },
  { label: 'MCM/ICM 美赛', value: '美赛' },
  { label: '研究生数模', value: '研赛' },
  { label: '省赛', value: '省赛' },
]
const langOptions = [{ label: '中文', value: 'zh' }, { label: 'English', value: 'en' }]

const llmModels = [
  { label: 'Auto (自动选择)', value: 'auto' },
  { label: 'DeepSeek Chat', value: 'deepseek-chat' },
  { label: 'DeepSeek Reasoner', value: 'deepseek-reasoner' },
  { label: 'Gemini 1.5 Pro', value: 'gemini-1.5-pro-002' },
  { label: 'Gemini 2.0 Flash', value: 'gemini-2.0-flash' },
  { label: 'GPT-4o', value: 'gpt-4o' },
  { label: 'GPT-4o Mini', value: 'gpt-4o-mini' },
  { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet-20241022' },
  { label: 'Claude 3 Haiku', value: 'claude-3-haiku-20240307' },
  { label: 'Grok 2', value: 'grok-2' },
  { label: 'MIMO (小米)', value: 'mimo' },
]

async function loadHealth() {
  try { const { data } = await healthApi.ready(); health.value = data }
  catch { health.value = { ready: false, checks: { database: '异常', llm_keys: '未配置' } } }
}

async function loadSysConfig() {
  try {
    const { data } = await systemApi.getConfig()
    sysConfig.value = data
    defaultModel.value = data.default_model || ''
  } catch { sysConfig.value = null }
}

async function loadWsConfig() {
  if (!store.currentId) return
  await store.fetchConfig()
  localConfig.value = { ...store.config }
}

async function saveWsConfig() {
  if (!store.currentId) return; saving.value = true
  try {
    await store.updateConfig(localConfig.value)
    message.success('竞赛配置已保存')
  } catch { message.error('保存失败') }
  finally { saving.value = false }
}

async function saveSysConfig() {
  sysSaving.value = true
  try {
    await systemApi.updateConfig({ default_model: defaultModel.value })
    message.success('系统配置已保存')
    await loadSysConfig()
  } catch { message.error('保存失败') }
  finally { sysSaving.value = false }
}

function startEditProvider(p: any) {
  editingProvider.value = p.id
  providerKey.value = ''
  providerUrl.value = p.base_url
}

async function saveProvider() {
  if (!editingProvider.value) return
  try {
    const data: any = { base_url: providerUrl.value }
    if (providerKey.value) data.api_key = providerKey.value
    await systemApi.updateProvider(editingProvider.value, data)
    message.success('Provider 已更新')
    editingProvider.value = null
    providerKey.value = ''
    await loadSysConfig()
  } catch { message.error('更新失败') }
}

function cancelEditProvider() {
  editingProvider.value = null
  providerKey.value = ''
  providerUrl.value = ''
}

watch(() => store.currentId, () => { loadWsConfig() }, { immediate: true })
onMounted(() => { loadHealth(); loadSysConfig(); if (store.currentId) loadWsConfig() })
</script>

<template>
  <div class="settings-page">
    <!-- System Health -->
    <NCard size="small">
      <template #header>
        <div class="card-header">
          <NIcon :size="14"><ServerOutline /></NIcon>
          系统状态
        </div>
      </template>
      <NSpace align="center" :size="12">
        <NTag :type="health?.ready ? 'success' : 'error'" size="small">
          <NIcon :size="12" style="margin-right: 4px;">
            <component :is="health?.ready ? CheckmarkCircleOutline : AlertCircleOutline" />
          </NIcon>
          {{ health?.ready ? '系统就绪' : '系统异常' }}
        </NTag>
        <NTag v-if="sysConfig" size="small" :bordered="false" type="default">
          {{ sysConfig.configured_count }}/{{ sysConfig.total_providers }} LLM 提供商已配置
        </NTag>
        <span style="font-size: 12px; color: var(--fg-3);">
          DB: {{ health?.checks?.database }}
        </span>
        <span style="font-size: 12px; color: var(--fg-3);">
          LLM: {{ health?.checks?.llm_keys }}
        </span>
      </NSpace>
    </NCard>

    <!-- LLM Providers -->
    <NCard size="small" v-if="sysConfig" style="margin-top: 12px">
      <template #header>
        <div class="card-header">
          <NIcon :size="14"><KeyOutline /></NIcon>
          LLM 提供商配置
        </div>
      </template>
      <div class="provider-list">
        <div v-for="p in sysConfig.providers" :key="p.id" class="provider-row">
          <div class="provider-info">
            <span class="provider-name">{{ p.name }}</span>
            <NTag size="tiny" :type="p.configured ? 'success' : 'default'" :bordered="false">
              {{ p.configured ? '已配置' : '未配置' }}
            </NTag>
            <span v-if="p.configured" class="provider-key">{{ p.key_masked }}</span>
          </div>
          <div class="provider-actions">
            <div v-if="editingProvider === p.id" class="provider-edit">
              <NInput v-model:value="providerKey" size="small" type="password"
                show-password-on="click" placeholder="API Key (留空不修改)" style="flex: 1" />
              <NInput v-model:value="providerUrl" size="small" placeholder="Base URL" style="flex: 1" />
              <NButton size="small" @click="cancelEditProvider">取消</NButton>
              <NButton size="small" type="primary" @click="saveProvider">保存</NButton>
            </div>
            <NButton v-else size="tiny" @click="startEditProvider(p)">编辑</NButton>
          </div>
        </div>
      </div>
    </NCard>

    <!-- System Settings -->
    <NCard size="small" style="margin-top: 12px">
      <template #header>
        <div class="card-header">
          <NIcon :size="14"><SettingsOutline /></NIcon>
          系统设置
        </div>
      </template>
      <NForm label-placement="left" label-width="100" size="small">
        <NFormItem label="默认模型">
          <NSelect v-model:value="defaultModel" :options="llmModels" filterable tag />
        </NFormItem>
        <NFormItem label="数据目录" v-if="sysConfig">
          <NInput :value="sysConfig.data_dir" disabled />
        </NFormItem>
        <NFormItem label="数据库" v-if="sysConfig">
          <NInput :value="sysConfig.database_url" disabled />
        </NFormItem>
        <NFormItem label=".env 文件" v-if="sysConfig">
          <NInput :value="sysConfig.env_file || '未找到'" disabled />
        </NFormItem>
      </NForm>
      <NSpace justify="end" style="margin-top: 8px">
        <NButton type="primary" @click="saveSysConfig" :loading="sysSaving" size="small">保存系统设置</NButton>
      </NSpace>
    </NCard>

    <!-- Competition Config -->
    <NCard v-if="store.current" size="small" style="margin-top: 12px">
      <template #header>
        <div class="card-header">
          <NIcon :size="14"><CloudOutline /></NIcon>
          竞赛配置 · {{ store.current.title }}
        </div>
      </template>
      <NForm label-placement="left" label-width="100" size="small">
        <NFormItem label="竞赛类型">
          <NSelect v-model:value="localConfig.competition_type" :options="compTypes" />
        </NFormItem>
        <NFormItem label="题目名称">
          <NInput v-model:value="localConfig.problem_title" placeholder="例：自驾行程规划" />
        </NFormItem>
        <NFormItem label="团队名称">
          <NInput v-model:value="localConfig.team_name" />
        </NFormItem>
        <NFormItem label="论文语言">
          <NSelect v-model:value="localConfig.language" :options="langOptions" />
        </NFormItem>
        <NFormItem label="最大页数">
          <NInputNumber v-model:value="localConfig.max_pages" :min="1" :max="50" />
        </NFormItem>
        <NFormItem label="审查轮数">
          <NInputNumber v-model:value="localConfig.review_rounds" :min="1" :max="5" />
        </NFormItem>
        <NFormItem label="首选模型">
          <NSelect v-model:value="localConfig.preferred_llm" :options="llmModels" filterable tag />
        </NFormItem>
        <NFormItem label="自动编译">
          <NSwitch v-model:value="localConfig.auto_compile" />
        </NFormItem>
        <NFormItem label="运行生成代码">
          <NSwitch v-model:value="localConfig.run_code_on_generate" />
        </NFormItem>
        <NFormItem label="截止时间">
          <NInput v-model:value="localConfig.deadline" placeholder="2025-09-15 20:00" />
        </NFormItem>
        <NFormItem label="导师">
          <NInput v-model:value="localConfig.mentor" />
        </NFormItem>
        <NFormItem label="LaTeX模板">
          <NSelect v-model:value="localConfig.latex_template" :options="[
            { label: '默认', value: 'default' },
            { label: 'CUMCM 国赛模板', value: 'cumcm' },
          ]" />
        </NFormItem>
        <NFormItem label="备注">
          <NInput v-model:value="localConfig.notes" type="textarea" :rows="3" />
        </NFormItem>
      </NForm>
      <NSpace justify="end" style="margin-top: 8px">
        <NButton type="primary" @click="saveWsConfig" :loading="saving" size="small">保存竞赛配置</NButton>
      </NSpace>
    </NCard>

    <div v-if="!store.current" style="text-align: center; padding: 40px 0; color: var(--fg-3); font-size: 13px;">
      选择工作区后可配置竞赛参数
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 16px 20px;
  overflow-y: auto;
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--fg-1);
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.provider-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 4px;
  gap: 12px;
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.provider-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--fg-1);
  min-width: 100px;
}

.provider-key {
  font-size: 10px;
  font-family: var(--mono);
  color: var(--fg-3);
}

.provider-actions {
  display: flex;
  align-items: center;
}

.provider-edit {
  display: flex;
  gap: 6px;
  align-items: center;
  flex: 1;
}
</style>
