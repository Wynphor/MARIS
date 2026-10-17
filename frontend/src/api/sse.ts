/**
 * SSE 流式客户端 — 处理 Pipeline 实时输出
 * 支持 AbortController 取消 + 空闲超时
 */

export interface SSEMessage {
  type: 'content' | 'system' | 'task' | 'error' | 'done'
  text: string
  raw: string
}

export interface SSEOptions {
  signal?: AbortSignal        // 用于取消
  idleTimeout?: number        // 空闲超时 (ms)，默认 60000
}

/**
 * 连接 SSE 流，返回 AsyncGenerator 逐条 yield 消息。
 */
export async function* streamSSE(
  url: string,
  body: Record<string, any>,
  options: SSEOptions = {},
): AsyncGenerator<SSEMessage> {
  const { signal, idleTimeout = 60000 } = options

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    yield { type: 'error', text: `HTTP ${response.status}`, raw: '' }
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    yield { type: 'error', text: 'No response body', raw: '' }
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let lastDataTime = Date.now()

  // 空闲超时检测
  const checkIdle = () => {
    if (Date.now() - lastDataTime > idleTimeout) {
      reader.cancel()
      return { type: 'error' as const, text: `[ERROR] 连接超时 (${idleTimeout / 1000}s 无数据)`, raw: '' }
    }
    return null
  }

  try {
    while (true) {
      // 检查取消信号
      if (signal?.aborted) {
        yield { type: 'error', text: '[已取消] 用户中止了操作', raw: '' }
        return
      }

      // 带超时的读取
      const readPromise = reader.read()
      const timeoutPromise = new Promise<never>((_, reject) => {
        const timer = setTimeout(() => {
          const idle = checkIdle()
          if (idle) reject(new Error('idle_timeout'))
        }, Math.min(idleTimeout, 10000))
        signal?.addEventListener('abort', () => {
          clearTimeout(timer)
          reject(new Error('aborted'))
        })
      })

      let result: ReadableStreamReadResult<Uint8Array>
      try {
        result = await Promise.race([readPromise, timeoutPromise]) as any
      } catch (e: any) {
        if (e.message === 'idle_timeout') {
          yield { type: 'error', text: `[ERROR] 连接超时 (${idleTimeout / 1000}s 无数据)`, raw: '' }
          return
        }
        if (e.message === 'aborted') {
          yield { type: 'error', text: '[已取消] 用户中止了操作', raw: '' }
          return
        }
        throw e
      }

      const { done, value } = result
      if (done) break

      lastDataTime = Date.now()
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6)
        if (!raw.trim()) continue

        const msg = parseMessage(raw)
        yield msg

        if (msg.type === 'done') return
      }
    }

    // Process remaining buffer
    if (buffer.startsWith('data: ')) {
      const raw = buffer.slice(6)
      if (raw.trim()) yield parseMessage(raw)
    }
  } finally {
    reader.releaseLock()
  }
}

function parseMessage(raw: string): SSEMessage {
  const trimmed = raw.trim()
  if (trimmed === '[DONE]') return { type: 'done', text: '', raw }
  if (trimmed.startsWith('[TASK]')) return { type: 'task', text: trimmed, raw }
  if (trimmed.startsWith('[ERROR]')) return { type: 'error', text: trimmed, raw }
  if (trimmed.startsWith('[')) return { type: 'system', text: trimmed, raw }
  return { type: 'content', text: trimmed, raw }
}

/**
 * 简化版：一次性收集所有 content 类型的文本
 */
export async function collectStream(
  url: string,
  body: Record<string, any>,
  onMessage?: (msg: SSEMessage) => void,
  options?: SSEOptions,
): Promise<string> {
  const parts: string[] = []
  for await (const msg of streamSSE(url, body, options)) {
    onMessage?.(msg)
    if (msg.type === 'content') parts.push(msg.text)
  }
  return parts.join('\n')
}
