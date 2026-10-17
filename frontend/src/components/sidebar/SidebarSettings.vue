<script setup lang="ts">
import {
  NSelect, NSwitch, NInputNumber, NTag, NButton, NIcon, NInput, useMessage,
} from 'naive-ui'
import { ref, onMounted, watch } from 'vue'
import {
  CheckmarkCircleOutline, AlertCircleOutline, ServerOutline,
  KeyOutline, SettingsOutline, CloudOutline,
  ChevronDownOutline, ChevronForwardOutline,
} from '@vicons/ionicons5'
import { healthApi, systemApi } from '../../api/client'
import { useWorkspaceStore } from '../../stores/workspace'

const wsStore = useWorkspaceStore()
const message = useMessage()
const saving = ref(false)
const sysSaving = ref(false)

// Collapsible sections
const showProviders = ref(false)
const showCompConfig = ref(true)

// Health
const healthData = ref<any>(null)

// System config
const sysConfig = ref<any>(null)
const defaultModel = ref('')

// Competition config
const config = ref<any>({})

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

const langOptions = [
  { label: '中文', value: 'zh' },
  { label: 'English', value: 'en' },
]

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
  try {
    const { data } = await healthApi.ready()
    healthData.value = data
  } catch {
    healthData.value = { ready: false, checks: { database: 'unreachable', llm_keys: 'unknown' } }
  }
}

async function loadSysConfig() {
  try {
    const { data } = await systemApi.getConfig()
    sysConfig.value = data
    defaultModel.value = data.default_model || 'auto'
  } catch {
    sysConfig.value = null
  }
}

async function loadWsConfig() {
  if (!wsStore.currentId) { config.value = {}; return }
  try {
    await wsStore.fetchConfig()
    config.value = { ...wsStore.config }
  } catch { config.value = {} }
}

async function saveWsConfig() {
  if (!wsStore.currentId) return
  saving.value = true
  try {
    await wsStore.updateConfig(config.value)
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

watch(() => wsStore.currentId, () => { loadWsConfig() })

onMounted(() => {
  loadHealth()
  loadSysConfig()
  if (wsStore.currentId) loadWsConfig()
})
</script>

<template>
  <div class="sidebar-settings">
    <!-- 1. System Health -->
      <div class="ss-section">
        <div class="ss-label">
          <NIcon :size="12"><ServerOutline /></NIcon>
          <span>系统状态</span>
        </div>
        <div class="ss-card">
          <div class="ss-health-row">
            <span class="ss-dot" :class="healthData?.ready ? 'on' : 'off'"></span>
            <span class="ss-health-text">{{ healthData?.ready ? '系统就绪' : '系统异常' }}</span>
            <NTag v-if="sysConfig" size="tiny" :bordered="false" type="default">
              {{ sysConfig.configured_count }}/{{ sysConfig.total_providers }} LLM
            </NTag>
          </div>
          <div class="ss-checks" v-if="healthData?.checks">
            <span class="ss-check" :class="healthData.checks.database === 'ok' ? 'ok' : 'err'">
              DB {{ healthData.checks.database }}
            </span>
            <span class="ss-check" :class="healthData.checks.llm_keys === 'ok' ? 'ok' : 'warn'">
              LLM {{ healthData.checks.llm_keys === 'ok' ? '已配置' : '未配置' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 2. LLM Providers (collapsible) -->
      <div class="ss-section" v-if="sysConfig">
        <div class="ss-toggle" @click="showProviders = !showProviders">
          <NIcon :size="10">
            <component :is="showProviders ? ChevronDownOutline : ChevronForwardOutline" />
          </NIcon>
          <NIcon :size="12"><KeyOutline /></NIcon>
          <span>LLM 提供商</span>
        </div>
        <div v-if="showProviders" class="ss-card">
          <div v-for="p in sysConfig.providers" :key="p.id" class="ss-provider">
            <div class="ss-provider-row" @click="startEditProvider(p)">
              <span class="ss-provider-name">{{ p.name }}</span>
              <span class="ss-provider-status" :class="p.configured ? 'on' : 'off'">
                {{ p.configured ? '✓' : '—' }}
              </span>
            </div>
            <!-- Inline edit -->
            <div v-if="editingProvider === p.id" class="ss-provider-edit">
              <div class="ss-field">
                <label>API Key {{ p.configured ? '(' + p.key_masked + ')' : '' }}</label>
                <NInput v-model:value="providerKey" size="tiny" type="password"
                  show-password-on="click" placeholder="留空不修改" />
              </div>
              <div class="ss-field">
                <label>Base URL</label>
                <NInput v-model:value="providerUrl" size="tiny" />
              </div>
              <div class="ss-btn-row">
                <NButton size="tiny" @click="cancelEditProvider">取消</NButton>
                <NButton size="tiny" type="primary" @click="saveProvider">保存</NButton>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. System Settings -->
      <div class="ss-section">
        <div class="ss-label">
          <NIcon :size="12"><SettingsOutline /></NIcon>
          <span>系统设置</span>
        </div>
        <div class="ss-card">
          <div class="ss-field">
            <label>默认模型</label>
            <NSelect v-model:value="defaultModel" :options="llmModels" size="small" filterable tag />
          </div>
          <div class="ss-field" v-if="sysConfig">
            <label>数据目录</label>
            <div class="ss-readonly">{{ sysConfig.data_dir }}</div>
          </div>
          <div class="ss-field" v-if="sysConfig">
            <label>数据库</label>
            <div class="ss-readonly">{{ sysConfig.database_url }}</div>
          </div>
          <NButton type="primary" size="small" :loading="sysSaving" @click="saveSysConfig" block>
            保存系统设置
          </NButton>
        </div>
      </div>

      <!-- 4. Competition Config -->
      <div class="ss-section" v-if="wsStore.current">
        <div class="ss-toggle" @click="showCompConfig = !showCompConfig">
          <NIcon :size="10">
            <component :is="showCompConfig ? ChevronDownOutline : ChevronForwardOutline" />
          </NIcon>
          <NIcon :size="12"><CloudOutline /></NIcon>
          <span>竞赛配置 · {{ wsStore.current.title }}</span>
        </div>
        <div v-if="showCompConfig" class="ss-card">
          <div class="ss-field">
            <label>竞赛类型</label>
            <NSelect v-model:value="config.competition_type" :options="compTypes" size="small" />
          </div>
          <div class="ss-field">
            <label>题目名称</label>
            <NInput v-model:value="config.problem_title" size="tiny" placeholder="例：自驾行程规划" />
          </div>
          <div class="ss-field">
            <label>团队名称</label>
            <NInput v-model:value="config.team_name" size="tiny" />
          </div>
          <div class="ss-field">
            <label>论文语言</label>
            <NSelect v-model:value="config.language" :options="langOptions" size="small" />
          </div>
          <div class="ss-field">
            <label>最大页数</label>
            <NInputNumber v-model:value="config.max_pages" :min="1" :max="50" size="small" />
          </div>
          <div class="ss-field">
            <label>审查轮数</label>
            <NInputNumber v-model:value="config.review_rounds" :min="1" :max="5" size="small" />
          </div>
          <div class="ss-field">
            <label>首选模型</label>
            <NSelect v-model:value="config.preferred_llm" :options="llmModels" size="small" filterable tag />
          </div>
          <div class="ss-row">
            <div class="ss-field ss-half">
              <label>自动编译</label>
              <NSwitch v-model:value="config.auto_compile" size="small" />
            </div>
            <div class="ss-field ss-half">
              <label>运行代码</label>
              <NSwitch v-model:value="config.run_code_on_generate" size="small" />
            </div>
          </div>
          <div class="ss-field">
            <label>截止时间</label>
            <NInput v-model:value="config.deadline" size="tiny" placeholder="2025-09-15 20:00" />
          </div>
          <div class="ss-field">
            <label>备注</label>
            <NInput v-model:value="config.notes" size="tiny" type="textarea" :rows="2" placeholder="团队备忘..." />
          </div>
          <NButton type="primary" size="small" :loading="saving" @click="saveWsConfig" block>
            保存竞赛配置
          </NButton>
        </div>
      </div>

      <!-- Hint when no workspace -->
      <div v-if="!wsStore.current" class="ss-hint">
        选择工作区后可配置竞赛参数
      </div>
  </div>
</template>

<style scoped>
.sidebar-settings {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 100%;
}

.ss-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: var(--fg-3);
  font-size: 12px;
}

/* Section */
.ss-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ss-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--fg-3);
  padding: 0 2px;
  display: flex;
  align-items: center;
  gap: 5px;
}

/* Collapsible header */
.ss-toggle {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--fg-3);
  padding: 4px 2px;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  border-radius: 3px;
  transition: color 0.1s;
}

.ss-toggle:hover {
  color: var(--fg-2);
  background: var(--bg-hover);
}

/* Card */
.ss-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Health */
.ss-health-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--fg-1);
}

.ss-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ss-dot.on { background: var(--green); }
.ss-dot.off { background: var(--red); }

.ss-health-text { flex: 1; }

.ss-checks {
  display: flex;
  gap: 6px;
}

.ss-check {
  font-size: 10px;
  font-family: var(--mono);
  padding: 1px 6px;
  border-radius: 3px;
}

.ss-check.ok { background: rgba(61, 214, 140, 0.1); color: var(--green); }
.ss-check.err { background: rgba(240, 96, 96, 0.1); color: var(--red); }
.ss-check.warn { background: rgba(232, 192, 80, 0.1); color: var(--yellow); }

/* Providers */
.ss-provider {
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
}

.ss-provider:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.ss-provider-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.1s;
}

.ss-provider-row:hover {
  background: var(--bg-hover);
}

.ss-provider-name {
  font-size: 11px;
  color: var(--fg-1);
}

.ss-provider-status {
  font-size: 11px;
  font-weight: 600;
}

.ss-provider-status.on { color: var(--green); }
.ss-provider-status.off { color: var(--fg-3); }

.ss-provider-edit {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 6px;
  background: var(--bg-1);
  border-radius: 4px;
}

/* Fields */
.ss-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ss-field label {
  font-size: 10px;
  color: var(--fg-3);
  font-weight: 500;
}

.ss-readonly {
  font-size: 11px;
  font-family: var(--mono);
  color: var(--fg-2);
  background: var(--bg-1);
  padding: 4px 8px;
  border-radius: 3px;
  border: 1px solid var(--border);
}

.ss-row {
  display: flex;
  gap: 8px;
}

.ss-half { flex: 1; }

.ss-btn-row {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}

.ss-hint {
  text-align: center;
  color: var(--fg-3);
  font-size: 11px;
  padding: 20px 0;
}
</style>
