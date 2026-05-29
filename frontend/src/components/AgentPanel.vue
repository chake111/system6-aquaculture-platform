<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { ChatDotRound, Loading, Promotion, Delete, Cpu } from '@element-plus/icons-vue'

import { useAgentStore } from '@/stores/agent'
import type { ChatMessage, StructuredAdvice } from '@/stores/agent'

const agent = useAgentStore()

const inputText = ref('')
const chatContainer = ref<HTMLElement | null>(null)

const quickActions = [
  { label: '水质分析', message: '帮我分析一下当前水质情况' },
  { label: '投喂建议', message: '今天投喂量怎么调整？' },
  { label: '病害防治', message: '最近需要关注哪些病害？' },
  { label: '密度评估', message: '当前养殖密度合理吗？' },
]

const riskColors: Record<string, string> = {
  low: '#67c23a',
  medium: '#e6a23c',
  high: '#f56c6c',
  critical: '#c00000',
}

const riskLabels: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '紧急',
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

watch(
  () => agent.messages.length,
  () => scrollToBottom(),
)
watch(
  () => agent.messages.map((m) => m.content.length).join(','),
  () => scrollToBottom(),
)

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || agent.isStreaming) return
  inputText.value = ''
  await agent.sendMessage(text)
}

function handleQuickAction(message: string) {
  if (agent.isStreaming) return
  agent.sendMessage(message)
}

function handleKeydown(e: Event | KeyboardEvent) {
  if ('key' in e && e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function renderContent(content: string): string {
  // Simple markdown: **bold**, > quote
  return content
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/\n/g, '<br>')
}
</script>

<template>
  <el-card shadow="hover" class="agent-panel" aria-label="智能体对话">
    <template #header>
      <div class="panel-header">
        <div class="header-left">
          <el-icon :size="20" class="agent-icon" aria-hidden="true"><Cpu /></el-icon>
          <h3>渔智 · 智能养殖助手</h3>
          <el-tag
            v-if="agent.agentStatus !== 'unknown'"
            :type="agent.agentStatus === 'online' ? 'success' : 'info'"
            size="small"
          >
            {{ agent.agentStatus === 'online' ? 'AI 在线' : '规则引擎' }}
          </el-tag>
        </div>
        <el-button
          v-if="agent.hasMessages"
          text
          size="small"
          :icon="Delete"
          @click="agent.clearSession()"
        >
          清空对话
        </el-button>
      </div>
    </template>

    <!-- Chat messages -->
    <div ref="chatContainer" class="chat-container">
      <!-- Empty state -->
      <div v-if="!agent.hasMessages" class="empty-state">
        <el-icon :size="48" class="empty-icon" aria-hidden="true"><ChatDotRound /></el-icon>
        <p class="empty-title">你好，我是渔智</p>
        <p class="empty-desc">你的智能养殖顾问，可以帮你分析水质、提供建议、回答养殖问题。</p>
        <div class="quick-actions">
          <el-button
            v-for="action in quickActions"
            :key="action.label"
            plain
            size="small"
            round
            @click="handleQuickAction(action.message)"
          >
            {{ action.label }}
          </el-button>
        </div>
      </div>

      <!-- Messages -->
      <div v-else class="messages">
        <div
          v-for="msg in agent.messages"
          :key="msg.id"
          class="message-row"
          :class="msg.role"
        >
          <!-- User message -->
          <div v-if="msg.role === 'user'" class="bubble user-bubble">
            <p>{{ msg.content }}</p>
            <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
          </div>

          <!-- Assistant message -->
          <div v-else-if="msg.role === 'assistant'" class="bubble assistant-bubble">
            <!-- Structured advice card -->
            <div v-if="msg.structured" class="advice-card">
              <div class="advice-header">
                <span
                  class="risk-badge"
                  :style="{ backgroundColor: riskColors[msg.structured.riskLevel] }"
                >
                  {{ riskLabels[msg.structured.riskLevel] }}
                </span>
                <span class="advice-category">{{ msg.structured.category }}</span>
              </div>
              <p class="advice-summary">{{ msg.structured.summary }}</p>
              <p class="advice-explanation">{{ msg.structured.explanation }}</p>
              <div v-if="msg.structured.actions.length" class="advice-actions">
                <p class="actions-title">建议操作：</p>
                <ul>
                  <li v-for="(action, i) in msg.structured.actions" :key="i">
                    {{ action }}
                  </li>
                </ul>
              </div>
            </div>

            <!-- Plain text message -->
            <div v-else v-html="renderContent(msg.content)" />

            <!-- Streaming cursor -->
            <span v-if="agent.isStreaming && msg === agent.messages[agent.messages.length - 1]" class="streaming-cursor" />

            <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
          </div>
        </div>

        <!-- Streaming indicator -->
        <div v-if="agent.isStreaming && !agent.messages.some(m => m.role === 'assistant' && m.content)" class="message-row assistant">
          <div class="bubble assistant-bubble streaming-indicator">
            <el-icon class="is-loading" aria-hidden="true"><Loading /></el-icon>
            <span>思考中...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <p v-if="agent.error" class="error-msg" role="alert">{{ agent.error }}</p>

    <!-- Input area -->
    <div class="input-area">
      <div v-if="agent.hasMessages" class="quick-actions-inline">
        <el-button
          v-for="action in quickActions"
          :key="action.label"
          text
          size="small"
          :disabled="agent.isStreaming"
          @click="handleQuickAction(action.message)"
        >
          {{ action.label }}
        </el-button>
      </div>
      <div class="input-row">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="1"
          autosize
          placeholder="输入养殖问题..."
          :disabled="agent.isStreaming"
          data-test="agent-input"
          @keydown="handleKeydown"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          circle
          :loading="agent.isStreaming"
          :disabled="!inputText.trim() || agent.isStreaming"
          data-test="agent-send"
          @click="handleSend"
        />
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.agent-panel {
  display: flex;
  flex-direction: column;
  border-top: 3px solid var(--accent, #409eff);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--sp-2, 8px);
}

.header-left h3 {
  margin: 0;
  font-size: var(--font-base, 14px);
}

.agent-icon {
  color: var(--accent, #409eff);
}

/* Chat container */
.chat-container {
  min-height: 200px;
  max-height: 500px;
  overflow-y: auto;
  padding: var(--sp-2, 8px) 0;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--sp-8, 32px) 0;
  text-align: center;
}

.empty-icon {
  color: var(--muted, #909399);
  margin-bottom: var(--sp-3, 12px);
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 var(--sp-1, 4px);
  color: var(--text, #303133);
}

.empty-desc {
  color: var(--muted, #909399);
  margin: 0 0 var(--sp-4, 16px);
  font-size: var(--font-sm, 13px);
}

.quick-actions {
  display: flex;
  gap: var(--sp-2, 8px);
  flex-wrap: wrap;
  justify-content: center;
}

/* Messages */
.messages {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3, 12px);
  padding: var(--sp-2, 8px);
}

.message-row {
  display: flex;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 80%;
  padding: var(--sp-3, 12px) var(--sp-4, 16px);
  border-radius: 12px;
  position: relative;
  line-height: 1.6;
  font-size: var(--font-base, 14px);
}

.bubble :deep(strong) {
  font-weight: 600;
}

.bubble :deep(blockquote) {
  margin: var(--sp-2, 8px) 0;
  padding: var(--sp-2, 8px) var(--sp-3, 12px);
  border-left: 3px solid var(--accent, #409eff);
  background: rgba(64, 158, 255, 0.05);
  border-radius: 4px;
  font-size: var(--font-sm, 13px);
}

.user-bubble {
  background: var(--accent, #409eff);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.assistant-bubble {
  background: var(--bg-card, #f4f4f5);
  color: var(--text, #303133);
  border-bottom-left-radius: 4px;
}

.msg-time {
  display: block;
  font-size: 11px;
  opacity: 0.6;
  margin-top: var(--sp-1, 4px);
  text-align: right;
}

/* Structured advice card */
.advice-card {
  border: 1px solid var(--border, #dcdfe6);
  border-radius: 8px;
  padding: var(--sp-3, 12px);
  background: var(--bg-page, #fff);
}

.advice-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2, 8px);
  margin-bottom: var(--sp-2, 8px);
}

.risk-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.advice-category {
  font-size: 12px;
  color: var(--muted, #909399);
  background: var(--bg-card, #f4f4f5);
  padding: 2px 8px;
  border-radius: 4px;
}

.advice-summary {
  font-weight: 600;
  margin: 0 0 var(--sp-2, 8px);
}

.advice-explanation {
  font-size: var(--font-sm, 13px);
  color: var(--muted, #909399);
  margin: 0 0 var(--sp-2, 8px);
}

.actions-title {
  font-weight: 600;
  font-size: var(--font-sm, 13px);
  margin: 0 0 var(--sp-1, 4px);
}

.advice-actions ul {
  margin: 0;
  padding-left: var(--sp-4, 16px);
}

.advice-actions li {
  font-size: var(--font-sm, 13px);
  margin-bottom: var(--sp-1, 4px);
  color: var(--text, #303133);
}

/* Streaming cursor */
.streaming-cursor::after {
  content: '';
  display: inline-block;
  width: 6px;
  height: 16px;
  background: var(--accent, #409eff);
  margin-left: 2px;
  animation: blink 0.8s infinite;
  vertical-align: text-bottom;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.streaming-indicator {
  display: flex;
  align-items: center;
  gap: var(--sp-2, 8px);
  color: var(--muted, #909399);
}

/* Error */
.error-msg {
  color: var(--el-color-danger, #f56c6c);
  font-size: var(--font-sm, 13px);
  margin: var(--sp-2, 8px) 0 0;
}

/* Input area */
.input-area {
  border-top: 1px solid var(--border, #dcdfe6);
  padding-top: var(--sp-3, 12px);
  margin-top: var(--sp-2, 8px);
}

.quick-actions-inline {
  display: flex;
  gap: var(--sp-1, 4px);
  margin-bottom: var(--sp-2, 8px);
  flex-wrap: wrap;
}

.input-row {
  display: flex;
  gap: var(--sp-2, 8px);
  align-items: flex-end;
}

.input-row .el-textarea {
  flex: 1;
}
</style>
