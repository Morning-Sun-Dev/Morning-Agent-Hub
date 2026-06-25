<template>
  <div class="chat-wrap">
    <!-- 메시지 목록 -->
    <div class="messages" ref="messagesEl">
      <div v-if="messages.length === 0" class="empty">
        질문을 입력하면 AI가 사내 문서를 검색해서 답변합니다.
      </div>
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="msg"
        :class="msg.role"
      >
        <div class="bubble">
          <span class="text" v-html="formatText(msg.content)"></span>
          <span v-if="msg.status" class="status-badge">{{ statusLabel(msg.status) }}</span>
        </div>
      </div>
      <!-- 스트리밍 중 표시 -->
      <div v-if="streaming" class="msg assistant">
        <div class="bubble streaming">
          <span class="text" v-html="formatText(streamBuffer)"></span>
          <span class="cursor">▍</span>
        </div>
      </div>
    </div>

    <!-- 파일 업로드 -->
    <div class="input-area">
      <FileUpload @uploaded="onFileUploaded" />

      <!-- 입력창 -->
      <div class="input-row">
        <textarea
          v-model="input"
          placeholder="메시지를 입력하세요 (Shift+Enter로 줄바꿈)"
          rows="1"
          @keydown.enter.exact.prevent="send"
          @input="autoResize"
          ref="textareaEl"
          :disabled="streaming"
        />
        <button @click="send" :disabled="streaming || !input.trim()">
          {{ streaming ? '⏳' : '전송' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { streamChat } from '../api'
import FileUpload from './FileUpload.vue'

const messages = ref([])
const input = ref('')
const streaming = ref(false)
const streamBuffer = ref('')
const sessionId = ref(null)
const messagesEl = ref(null)
const textareaEl = ref(null)

const STATUS_LABELS = {
  working: '🔍 검색 중',
  completed: '완료',
  failed: '실패',
}

function statusLabel(s) {
  return STATUS_LABELS[s] || s
}

function formatText(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

async function scrollBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

function autoResize() {
  const el = textareaEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

async function send() {
  const text = input.value.trim()
  if (!text || streaming.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  textareaEl.value.style.height = 'auto'
  streamBuffer.value = ''
  streaming.value = true
  await scrollBottom()

  let currentStatus = null

  const cancel = streamChat(text, sessionId.value, {
    onStatus(state) {
      currentStatus = state
    },
    onAnswer(content, sid) {
      if (sid) sessionId.value = sid
      streamBuffer.value += content
      scrollBottom()
    },
    onDone() {
      messages.value.push({
        role: 'assistant',
        content: streamBuffer.value,
        status: currentStatus,
      })
      streamBuffer.value = ''
      streaming.value = false
      scrollBottom()
    },
    onError(err) {
      messages.value.push({ role: 'assistant', content: `오류: ${err}` })
      streamBuffer.value = ''
      streaming.value = false
      scrollBottom()
    },
  })
}

function onFileUploaded(data) {
  messages.value.push({
    role: 'assistant',
    content: `📄 **${data.filename}** 파일이 업로드되어 인덱싱됐습니다. 이제 이 파일에 대해 질문할 수 있어요.`,
  })
  scrollBottom()
}
</script>

<style scoped>
.chat-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty {
  text-align: center;
  color: #9ca3af;
  font-size: 14px;
  margin-top: 60px;
}

.msg {
  display: flex;
}

.msg.user {
  justify-content: flex-end;
}

.msg.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  position: relative;
}

.msg.user .bubble {
  background: #6366f1;
  color: white;
  border-bottom-right-radius: 4px;
}

.msg.assistant .bubble {
  background: #f3f4f6;
  color: #111827;
  border-bottom-left-radius: 4px;
}

.bubble.streaming {
  background: #f3f4f6;
}

.cursor {
  display: inline-block;
  animation: blink 0.8s step-start infinite;
  color: #6366f1;
  margin-left: 2px;
}

@keyframes blink {
  50% { opacity: 0; }
}

.status-badge {
  display: block;
  font-size: 11px;
  color: #9ca3af;
  margin-top: 4px;
}

/* 입력 영역 */
.input-area {
  border-top: 1px solid #e5e7eb;
  padding: 12px 16px;
  background: white;
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

textarea {
  flex: 1;
  resize: none;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
  overflow-y: hidden;
}

textarea:focus {
  border-color: #6366f1;
}

textarea:disabled {
  background: #f9fafb;
  color: #9ca3af;
}

button {
  padding: 10px 20px;
  background: #6366f1;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.2s;
}

button:hover:not(:disabled) {
  background: #4f46e5;
}

button:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
}
</style>
