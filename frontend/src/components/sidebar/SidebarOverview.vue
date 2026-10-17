<script setup lang="ts">
import { NTag, NProgress, NIcon, NButton, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { PlayOutline, CodeSlashOutline, ChatbubbleEllipsesOutline } from '@vicons/ionicons5'
import { useWorkspaceStore } from '../../stores/workspace'
import { useLayoutStore } from '../../stores/layout'
import { pipelineApi } from '../../api/client'

const wsStore = useWorkspaceStore()
const message = useMessage()
const layout = useLayoutStore()

const statusMap: Record<string, { label: string; type: string }> = {
  INIT: { label: '初始化', type: 'default' },
  DECOMPOSED: { label: '已拆解', type: 'info' },
  MODELED: { label: '已建模', type: 'info' },
  CODED: { label: '已编码', type: 'warning' },
  WRITTEN: { label: '已写作', type: 'warning' },
  REVIEWED: { label: '已审查', type: 'success' },
  CHECKED: { label: '已检查', type: 'success' },
  IMPROVED: { label: '已改进', type: 'success' },
  PACKED: { label: '已打包', type: 'success' },
  FINISHED: { label: '已完成', type: 'success' },
}

const currentStatus = computed(() => {
  if (!wsStore.current) return null
  return statusMap[wsStore.current.status] || { label: wsStore.current.status, type: 'default' }
})

const progress = computed(() => {
  if (!wsStore.dashboard?.progress) return 0
  return wsStore.dashboard.progress
})

const stages = computed(() => {
  if (!wsStore.dashboard) return { done: 0, total: 0 }
  return { done: wsStore.dashboard.completed_stages || 0, total: wsStore.dashboard.total_stages || 0 }
})

// Workflow wizard with human confirmation nodes
const workflowSteps = [
  { id: 'decompose', label: '上传赛题 & 拆题', hint: '上传 PDF 后执行 decompose', stage: 'decompose' },
  { id: 'model-select', label: '模型选择', hint: '根据拆题结果推荐模型', stage: 'model-select', confirm: true, confirmLabel: '确认模型选择' },
  { id: 'preprocess', label: '数据预处理', hint: '清洗数据 + EDA 可视化', stage: 'preprocess' },
  { id: 'paper-ref', label: '范文参考', hint: '检索同类型获奖论文', stage: 'paper-ref' },
  { id: 'code-gen', label: '代码生成 & 运行', hint: '生成并运行求解代码', stage: 'code-gen', confirm: true, confirmLabel: '确认代码结果' },
  { id: 'validate', label: '验证分析', hint: '敏感性分析/蒙特卡洛', stage: 'validate' },
  { id: 'figures', label: '图表生成', hint: '生成论文所需图表', stage: 'figures', confirm: true, confirmLabel: '确认图表' },
  { id: 'write', label: '论文写作', hint: '基于结果自动生成论文', stage: 'write', confirm: true, confirmLabel: '确认论文初稿' },
  { id: 'compile', label: 'LaTeX 编译', hint: '编译生成 PDF', stage: 'compile' },
  { id: 'format-check', label: '格式检查', hint: '检查竞赛格式规范', stage: 'format-check' },
  { id: 'claim-audit', label: '数值审计', hint: '验证论文数值声明', stage: 'claim-audit' },
  { id: 'review', label: '对抗审查', hint: '红蓝对抗审查论文', stage: 'review' },
  { id: 'auto-improve', label: '自动改进', hint: '根据审查修复论文', stage: 'auto-improve' },
  { id: 'pack', label: '提交打包', hint: '生成最终提交材料', stage: 'pack', confirm: true, confirmLabel: '确认提交' },
]

function stepStatus(stepId: string): string {
  const statusToStep: Record<string, number> = {
    'INIT': -1, 'DECOMPOSED': 0, 'MODELED': 3, 'CODED': 6, 'WRITTEN': 8,
    'REVIEWED': 11, 'CHECKED': 9, 'IMPROVED': 12, 'PACKED': 13, 'FINISHED': 13,
  }
  const stepOrder = workflowSteps.map(s => s.id)
  const currentIdx = statusToStep[wsStore.current?.status || 'INIT'] ?? -1
  const stepIdx = stepOrder.indexOf(stepId)
  if (stepIdx < currentIdx) return 'done'
  if (stepIdx === currentIdx) return 'current'
  return 'pending'
}

const nextStep = computed(() => {
  const current = wsStore.current?.status || 'INIT'
  const nextMap: Record<string, { label: string; action: string; stage: string }> = {
    'INIT': { label: '拆题', action: '执行 decompose 拆解赛题', stage: 'decompose' },
    'DECOMPOSED': { label: '模型选择', action: '执行 model-select 推荐模型', stage: 'model-select' },
    'MODELED': { label: '代码生成', action: '执行 code-gen 生成求解代码', stage: 'code-gen' },
    'CODED': { label: '论文写作', action: '执行 write 生成论文', stage: 'write' },
    'WRITTEN': { label: '审查论文', action: '执行 review 对抗审查', stage: 'review' },
    'REVIEWED': { label: '格式检查', action: '执行 format-check 检查格式', stage: 'format-check' },
    'CHECKED': { label: '打包提交', action: '执行 pack 生成提交包', stage: 'pack' },
    'IMPROVED': { label: '打包提交', action: '执行 pack 生成提交包', stage: 'pack' },
  }
  return nextMap[current] || null
})

function handleNextStep() {
  if (nextStep.value) {
    layout.toggleBottom('pipeline')
  }
}

async function handleApprove() {
  if (!wsStore.currentId) return
  try {
    await pipelineApi.approve(wsStore.currentId)
    message.success('已确认，继续下一步')
    wsStore.fetchDashboard()
  } catch { message.error('确认失败') }
}

async function handleReject() {
  if (!wsStore.currentId) return
  try {
    await pipelineApi.reject(wsStore.currentId, '需要人工修改')
    message.warning('已标记需要修改')
  } catch { message.error('操作失败') }
}
</script>

<template>
  <div class="sidebar-overview">
    <!-- Current Workspace -->
    <div v-if="wsStore.current" class="ov-section">
      <div class="ov-label">当前工作区</div>
      <div class="ov-ws-card">
        <div class="ov-ws-title">{{ wsStore.current.title }}</div>
        <div class="ov-ws-meta">
          <NTag v-if="currentStatus" :type="currentStatus.type as any" size="tiny" :bordered="false">
            {{ currentStatus.label }}
          </NTag>
          <NTag v-if="wsStore.current.question_id" size="tiny" :bordered="false" type="default">
            {{ wsStore.current.question_id }}
          </NTag>
          <NTag v-if="wsStore.current.problem_type" size="tiny" :bordered="false" type="default">
            {{ wsStore.current.problem_type }}
          </NTag>
        </div>
        <div class="ov-progress" v-if="stages.total > 0">
          <NProgress type="line" :percentage="progress" :show-indicator="false" :height="4" :border-radius="2" />
          <span class="ov-progress-text">{{ stages.done }}/{{ stages.total }} 阶段</span>
        </div>
      </div>
    </div>

    <!-- Workflow Wizard -->
    <div v-if="wsStore.current" class="ov-section">
      <div class="ov-label">竞赛流程</div>
      <div class="ov-wizard">
        <div v-for="(step, idx) in workflowSteps" :key="step.id"
          class="ov-step" :class="stepStatus(step.id)">
          <div class="ov-step-indicator">
            <span v-if="stepStatus(step.id) === 'done'" class="ov-step-check">✓</span>
            <span v-else-if="stepStatus(step.id) === 'current'" class="ov-step-current">{{ idx + 1 }}</span>
            <span v-else class="ov-step-pending">{{ idx + 1 }}</span>
          </div>
          <div class="ov-step-content">
            <span class="ov-step-label">{{ step.label }}</span>
            <span class="ov-step-hint" v-if="stepStatus(step.id) === 'current'">{{ step.hint }}</span>
            <!-- Human confirmation node -->
            <div v-if="step.confirm && stepStatus(step.id) === 'current'" class="ov-step-confirm">
              <button class="ov-confirm-btn" @click="handleApprove">
                ✓ {{ step.confirmLabel || '确认继续' }}
              </button>
              <button class="ov-reject-btn" @click="handleReject">
                ✗ 需要修改
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Next Action -->
    <div v-if="nextStep" class="ov-section">
      <div class="ov-label">下一步</div>
      <button class="ov-next-btn" @click="handleNextStep">
        <NIcon :size="14"><PlayOutline /></NIcon>
        {{ nextStep.action }}
      </button>
    </div>

    <!-- Quick Actions -->
    <div class="ov-section">
      <div class="ov-label">快速操作</div>
      <div class="ov-actions">
        <button class="ov-action" @click="layout.toggleBottom('pipeline')">
          <NIcon :size="14"><PlayOutline /></NIcon>
          执行流水线
        </button>
        <button class="ov-action" @click="layout.openEditorTab('editor'); layout.toggleRightSidebar('chat')">
          <NIcon :size="14"><ChatbubbleEllipsesOutline /></NIcon>
          AI 对话
        </button>
        <button class="ov-action" @click="layout.openEditorTab('editor')">
          <NIcon :size="14"><CodeSlashOutline /></NIcon>
          编辑论文
        </button>
      </div>
    </div>

    <!-- Workspace List -->
    <div class="ov-section">
      <div class="ov-label">所有工作区 ({{ wsStore.workspaces.length }})</div>
      <div class="ov-ws-list">
        <div
          v-for="ws in wsStore.workspaces" :key="ws.id"
          class="ov-ws-item" :class="{ active: ws.id === wsStore.currentId }"
          @click="wsStore.selectWorkspace(ws.id)"
        >
          <span class="ov-ws-name">{{ ws.title }}</span>
          <NTag :type="(statusMap[ws.status]?.type || 'default') as any" size="tiny" :bordered="false">
            {{ statusMap[ws.status]?.label || ws.status }}
          </NTag>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sidebar-overview {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.ov-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ov-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--fg-3);
  padding: 0 4px;
}

.ov-ws-card {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ov-ws-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--fg-1);
}

.ov-ws-meta {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.ov-progress {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.ov-progress-text {
  font-size: 10px;
  color: var(--fg-3);
  font-family: var(--mono);
}

.ov-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ov-action {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--fg-2);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.1s;
  text-align: left;
  width: 100%;
}

.ov-action:hover {
  background: var(--bg-hover);
  color: var(--fg-1);
}

.ov-ws-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ov-ws-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.1s;
  gap: 8px;
}

.ov-ws-item:hover {
  background: var(--bg-hover);
}

.ov-ws-item.active {
  background: var(--orange-glow);
  border-left: 2px solid var(--orange);
}

.ov-ws-name {
  font-size: 12px;
  color: var(--fg-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

/* Workflow Wizard */
.ov-wizard {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ov-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 4px;
  transition: background 0.1s;
}

.ov-step.done {
  opacity: 0.7;
}

.ov-step.current {
  background: var(--orange-glow);
  border-left: 2px solid var(--orange);
}

.ov-step-indicator {
  width: 18px;
  height: 18px;
  min-width: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
  margin-top: 1px;
}

.ov-step.done .ov-step-indicator {
  background: var(--green);
  color: white;
}

.ov-step.current .ov-step-indicator {
  background: var(--orange);
  color: white;
}

.ov-step.pending .ov-step-indicator {
  background: var(--bg-3);
  color: var(--fg-3);
  border: 1px solid var(--border);
}

.ov-step-check {
  font-size: 10px;
}

.ov-step-current, .ov-step-pending {
  font-size: 9px;
}

.ov-step-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.ov-step-label {
  font-size: 11px;
  color: var(--fg-1);
  font-weight: 500;
}

.ov-step.done .ov-step-label {
  color: var(--fg-3);
  text-decoration: line-through;
}

.ov-step-hint {
  font-size: 9px;
  color: var(--orange);
}

/* Next Action Button */
.ov-next-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: var(--orange-glow);
  border: 1px solid var(--orange);
  border-radius: var(--r);
  color: var(--orange);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.ov-next-btn:hover {
  background: var(--orange);
  color: white;
}

/* Confirmation buttons */
.ov-step-confirm {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}

.ov-confirm-btn {
  flex: 1;
  padding: 4px 8px;
  background: rgba(61, 214, 140, 0.12);
  border: 1px solid var(--green);
  border-radius: 3px;
  color: var(--green);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.ov-confirm-btn:hover {
  background: var(--green);
  color: white;
}

.ov-reject-btn {
  padding: 4px 8px;
  background: rgba(240, 96, 96, 0.08);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--fg-3);
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.ov-reject-btn:hover {
  border-color: var(--red);
  color: var(--red);
}
</style>
