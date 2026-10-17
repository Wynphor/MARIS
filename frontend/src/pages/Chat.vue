<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { NButton, NEmpty } from 'naive-ui'
import { useWorkspaceStore } from '../stores/workspace'
import { BASE_URL } from '../api/client'
import { streamSSE } from '../api/sse'

const store = useWorkspaceStore()
interface Msg { role: 'user' | 'assistant'; content: string }
const messages = ref<Msg[]>([])
const input = ref('')
const streaming = ref(false)
const chatRef = ref<HTMLElement | null>(null)
let abort: AbortController | null = null

async function send() {
  if (!input.value.trim() || !store.currentId || streaming.value) return
  const text = input.value.trim()
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  streaming.value = true
  messages.value.push({ role: 'assistant', content: '' })
  abort = new AbortController()

  const history = messages.value.slice(0, -1).map(m => `${m.role === 'user' ? '用户' : 'AI'}: ${m.content}`).join('\n')

  try {
    for await (const msg of streamSSE(`${BASE_URL}/api/v1/pipeline/execute`, {
      workspace_id: store.currentId, stage: 'review', mode: 'API',
      keywords: `对话上下文:\n${history}\n\n用户问题: ${text}`,
    }, { signal: abort.signal })) {
      if (msg.type === 'content') {
        messages.value[messages.value.length - 1].content += msg.text + '\n'
        nextTick(() => { if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight })
      }
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') messages.value[messages.value.length - 1].content += `\n[错误] ${e.message}`
  } finally { streaming.value = false; abort = null }
}

function cancel() { abort?.abort() }
function clear() { messages.value = [] }

function renderMd(t: string): string {
  return t
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="cb">$2</pre>')
    .replace(/`([^`]+)`/g, '<code class="ic">$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}
</script>

<template>
  <div class="chat-page">
    <!-- Messages -->
    <div ref="chatRef" class="chat-body">
      <div v-if="!messages.length" class="chat-empty">
        <div class="empty-icon">M</div>
        <div class="empty-text">开始与 AI 对话</div>
        <div class="empty-hint">讨论建模方案、请求代码修改、分析数据</div>
      </div>

      <div v-for="(msg, i) in messages" :key="i" class="msg" :class="msg.role">
        <div class="msg-avatar">{{ msg.role === 'user' ? '>' : 'M' }}</div>
        <div class="msg-content">
          <div v-if="msg.role === 'assistant'" class="msg-text" v-html="renderMd(msg.content)"></div>
          <div v-else class="msg-text">{{ msg.content }}</div>
        </div>
      </div>

      <div v-if="streaming" class="typing">
        <span class="typing-dot">●</span>
      </div>
    </div>

    <!-- Input -->
    <div class="chat-input-area">
      <div class="input-box">
        <textarea
          v-model="input"
          placeholder="输入问题... (Enter 发送)"
          @keydown.enter.exact.prevent="send"
          :disabled="streaming || !store.currentId"
          rows="1"
          class="chat-textarea"
        ></textarea>
        <div class="input-actions">
          <NButton v-if="streaming" size="tiny" type="error" @click="cancel">停止</NButton>
          <NButton v-else size="tiny" type="primary" :disabled="!input.trim() || !store.currentId" @click="send">
            发送
          </NButton>
        </div>
      </div>
      <div class="input-hint">
        {{ store.current ? store.current.title : '未选择工作区' }} · {{ streaming ? 'AI 正在回复...' : '就绪' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page { display: flex; flex-direction: column; height: 100%; }

.chat-body {
  flex: 1; overflow-y: auto; padding: 12px 16px;
  display: flex; flex-direction: column; gap: 10px;
}

.chat-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 8px;
}
.empty-icon {
  width: 48px; height: 48px; border-radius: 12px;
  background: linear-gradient(135deg, #e87a35, #f0a060);
  color: white; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 22px; font-family: var(--font-mono);
  margin-bottom: 8px;
}
.empty-text { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.empty-hint { font-size: 12px; color: var(--text-muted); }

/* Messages */
.msg { display: flex; gap: 10px; max-width: 100%; }
.msg.user { align-self: flex-end; flex-direction: row-reverse; }
.msg-avatar {
  width: 28px; height: 28px; min-width: 28px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 12px; font-family: var(--font-mono);
}
.msg.assistant .msg-avatar { background: var(--accent-glow); color: var(--accent); }
.msg.user .msg-avatar { background: var(--bg-active); color: var(--text-secondary); }
.msg-content { flex: 1; }
.msg-text {
  padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.7;
  white-space: pre-wrap;
}
.msg.assistant .msg-text { background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-primary); }
.msg.user .msg-text { background: var(--accent-glow); color: var(--text-primary); border: 1px solid transparent; }

.typing { display: flex; gap: 10px; max-width: 100%; }
.typing-dot { color: var(--accent); animation: blink 1s infinite; font-size: 14px; margin-left: 40px; }

/* Code blocks inside messages */
:deep(.cb) {
  background: var(--bg-base); color: #c8c8c8; padding: 12px; border-radius: 6px;
  font-family: var(--font-mono); font-size: 12px; overflow-x: auto;
  margin: 8px 0; border: 1px solid var(--border);
}
:deep(.ic) {
  background: var(--bg-active); padding: 2px 5px; border-radius: 3px;
  font-family: var(--font-mono); font-size: 12px;
}

/* Input area */
.chat-input-area { padding: 6px 12px 8px; border-top: 1px solid var(--border); }
.input-box {
  display: flex; align-items: flex-end; gap: 8px;
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: 8px 12px;
  transition: border-color 0.15s;
}
.input-box:focus-within { border-color: var(--accent); }
.chat-textarea {
  flex: 1; background: transparent; border: none; outline: none;
  color: var(--text-primary); font-family: var(--font-sans); font-size: 13px;
  resize: none; line-height: 1.5; min-height: 20px; max-height: 120px;
}
.chat-textarea::placeholder { color: var(--text-muted); }
.input-actions { display: flex; gap: 4px; }
.input-hint { font-size: 10px; color: var(--text-muted); margin-top: 6px; padding: 0 4px; }
</style>
