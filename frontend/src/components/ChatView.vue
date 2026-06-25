<template>
  <div class="chat-wrap">
    <!-- 메시지 목록 -->
    <div class="messages" ref="messagesEl">
      <div v-if="messages.length === 0" class="empty">
        질문을 입력하거나 파일을 업로드하세요.
      </div>
      <div v-for="(msg, i) in messages" :key="i" class="msg" :class="msg.role">
        <div class="bubble">
          <span class="text" v-html="formatText(msg.content)"></span>
        </div>
      </div>
      <div v-if="streaming" class="msg assistant">
        <div class="bubble">
          <span class="text" v-html="formatText(streamBuffer)"></span>
          <span class="cursor">▍</span>
        </div>
      </div>
    </div>

    <!-- 입력 영역 -->
    <div class="input-area">
      <FileUpload @uploaded="onFileUploaded" />
      <div class="input-row">
        <textarea
          v-model="input"
          placeholder="메시지를 입력하세요 (Enter로 전송, Shift+Enter로 줄바꿈)"
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
import { ref, watch, nextTick } from 'vue'
import { streamChat } from '../api'
import FileUpload from './FileUpload.vue'

const props = defineProps({
  sessionId: { type: String, default: null },
  initialMessages: { type: Array, default: () => [] },
})

const emit = defineEmits(['session-created'])

const messages = ref([])
const input = ref('')
const streaming = ref(false)
const streamBuffer = ref('')
const currentSessionId = ref(props.sessionId)
const messagesEl = ref(null)
const textareaEl = ref(null)

// 세션 변경 시 메시지 초기화
watch(() => props.sessionId, (newId) => {
  currentSessionId.value = newId
})

watch(() => props.initialMessages, (msgs) => {
  messages.value = msgs.map(m => ({ role: m.role, content: m.content }))
  nextTick(scrollBottom)
}, { immediate: true })

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
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
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
  if (textareaEl.value) textareaEl.value.style.height = 'auto'
  streamBuffer.value = ''
  streaming.value = true
  await scrollBottom()

  streamChat(text, currentSessionId.value, {
    onStatus() {},
    onAnswer(content, sid) {
      if (sid && !currentSessionId.value) {
        currentSessionId.value = sid
        emit('session-created', sid)
      }
      streamBuffer.value += content
      scrollBottom()
    },
    onDone() {
      messages.value.push({ role: 'assistant', content: streamBuffer.value })
      streamBuffer.value = ''
      streaming.value = false
      scrollBottom()
    },
    onError(err) {
      messages.value.push({ role: 'assistant', content: `오류: ${err}` })
      streamBuffer.value = ''
      streaming.value = false
    },
  })
}

function onFileUploaded(data) {
  messages.value.push({
    role: 'assistant',
    content: `📄 ${data.filename} 파일이 인덱싱됐습니다. 이제 이 파일에 대해 질문할 수 있어요.`,
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
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty {
  text-align: center;
  color: #9ca3af;
  font-size: 14px;
  margin-top: 80px;
}

.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }

.bubble {
  max-width: 72%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
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

.cursor {
  display: inline-block;
  animation: blink 0.8s step-start infinite;
  color: #6366f1;
}

@keyframes blink { 50% { opacity: 0; } }

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

textarea:focus { border-color: #6366f1; }
textarea:disabled { background: #f9fafb; color: #9ca3af; }

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

button:hover:not(:disabled) { background: #4f46e5; }
button:disabled { background: #c7d2fe; cursor: not-allowed; }
</style>
