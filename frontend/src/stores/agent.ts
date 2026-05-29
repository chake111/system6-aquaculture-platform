import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

import { useAuthStore } from './auth'
import { DEFAULT_POND_ID } from '@/utils/constants'

export interface StructuredAdvice {
  summary: string
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  category: string
  actions: string[]
  explanation: string
  dataRefs: Record<string, unknown>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: string
  toolCall?: { name: string; args: Record<string, unknown>; result?: unknown }
  structured?: StructuredAdvice
}

interface AgentStatusResponse {
  status: 'online' | 'fallback'
  model: string
  provider: string
}

interface StructuredAdviceResponse {
  summary: string
  risk_level: string
  category: string
  actions: string[]
  explanation: string
  data_refs: Record<string, unknown>
}

interface ChatHistoryResponse {
  session_id: string
  messages: Array<{
    role: string
    content: string
    tool_call_id?: string
    tool_calls?: Array<{ id: string; function: { name: string; arguments: string } }>
    name?: string
  }>
}

let _msgId = 0
function nextMsgId(): string {
  return `msg-${Date.now()}-${++_msgId}`
}

export const useAgentStore = defineStore('agent', () => {
  const auth = useAuthStore()

  // --- state ---
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const agentStatus = ref<'online' | 'fallback' | 'unknown'>('unknown')
  const structuredAdvice = ref<StructuredAdvice | null>(null)
  const error = ref<string | null>(null)
  const analyzeLoading = ref(false)

  // --- computed ---
  const hasMessages = computed(() => messages.value.length > 0)

  // --- helpers ---
  function addMessage(msg: Omit<ChatMessage, 'id' | 'timestamp'>): ChatMessage {
    const full: ChatMessage = {
      ...msg,
      id: nextMsgId(),
      timestamp: new Date().toISOString(),
    }
    messages.value.push(full)
    return full
  }

  // --- actions ---
  async function checkStatus() {
    try {
      const result = await auth.request<AgentStatusResponse>('/api/v1/agent/status')
      agentStatus.value = result.status
    } catch {
      agentStatus.value = 'unknown'
    }
  }

  async function sendMessage(userMessage: string, pondId: string = DEFAULT_POND_ID) {
    error.value = null
    addMessage({ role: 'user', content: userMessage })

    const assistantMsg = addMessage({ role: 'assistant', content: '' })
    isStreaming.value = true

    try {
      const token = auth.accessToken
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) headers.Authorization = `Bearer ${token}`

      const response = await fetch('/api/v1/agent/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          session_id: `dashboard-${pondId}`,
          message: userMessage,
          pond_id: pondId,
        }),
      })

      if (!response.ok) {
        throw new Error(`请求失败 (${response.status})`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法读取响应流')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') continue

          try {
            const event = JSON.parse(payload)
            if (event.type === 'token' && event.content) {
              assistantMsg.content += event.content
            } else if (event.type === 'tool_call') {
              // Show tool call indicator
              assistantMsg.content += `\n\n> 🔍 查询 ${event.name}...`
            } else if (event.type === 'tool_result') {
              // Remove the tool call indicator and add result context
              assistantMsg.content = assistantMsg.content.replace(
                /\n\n> 🔍 查询 .+\.\.\.$/,
                '',
              )
            }
          } catch {
            /* skip malformed events */
          }
        }
      }
    } catch (e) {
      assistantMsg.content =
        '抱歉，智能体暂时无法响应。请稍后重试。'
      error.value = e instanceof Error ? e.message : '智能体响应失败'
    } finally {
      isStreaming.value = false
    }
  }

  async function analyzeWater(pondId: string = DEFAULT_POND_ID) {
    error.value = null
    analyzeLoading.value = true
    try {
      const result = await auth.request<StructuredAdviceResponse>('/api/v1/agent/analyze', {
        method: 'POST',
        body: JSON.stringify({ pond_id: pondId }),
      })
      const advice: StructuredAdvice = {
        summary: result.summary,
        riskLevel: result.risk_level as StructuredAdvice['riskLevel'],
        category: result.category,
        actions: result.actions,
        explanation: result.explanation,
        dataRefs: result.data_refs,
      }
      structuredAdvice.value = advice

      // Also add to chat as a structured message
      addMessage({
        role: 'assistant',
        content: '',
        structured: advice,
      })
    } catch (e) {
      error.value = e instanceof Error ? e.message : '水质分析失败'
    } finally {
      analyzeLoading.value = false
    }
  }

  async function clearSession() {
    try {
      await auth.request(`/api/v1/agent/sessions/dashboard-${DEFAULT_POND_ID}`, {
        method: 'DELETE',
      })
    } catch {
      /* best effort */
    }
    messages.value = []
    structuredAdvice.value = null
    error.value = null
  }

  return {
    // state
    messages,
    isStreaming,
    agentStatus,
    structuredAdvice,
    error,
    analyzeLoading,
    // computed
    hasMessages,
    // actions
    checkStatus,
    sendMessage,
    analyzeWater,
    clearSession,
    addMessage,
  }
})
