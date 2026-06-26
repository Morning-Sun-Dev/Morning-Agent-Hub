<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { createMessage, createProgress } from '../../models/chatModels'
import { getCapabilities, streamChat, uploadFile } from '../../api'
import ChatHeader from './ChatHeader.vue'
import EvidencePanel from './EvidencePanel.vue'
import MessageComposer from './MessageComposer.vue'
import MessageList from './MessageList.vue'
import RecoveryBanner from './RecoveryBanner.vue'

const messages = ref([])
const draft = ref('')
const attachments = ref([])
const activePanel = ref('sources')
const runState = ref('idle')
const progress = ref([])
const sources = ref([])
const generatedFiles = ref([])
const capabilities = ref([])
const error = ref(null)
const sessionId = ref(null)
const lastRequest = ref(null)

let stopStream = null

const runningMessage = computed(() => {
  if (runState.value !== 'running') return null
  return createMessage({
    id: 'running',
    role: 'assistant',
    content: '요청을 처리하고 있습니다. 완료되면 답변과 근거가 표시됩니다.',
    status: 'running',
    progress: progress.value,
  })
})

function applyPrompt(prompt) {
  draft.value = prompt
}

function startNewChat() {
  stopStream?.()
  stopStream = null
  messages.value = []
  draft.value = ''
  attachments.value = []
  sources.value = []
  generatedFiles.value = []
  progress.value = []
  error.value = null
  runState.value = 'idle'
  sessionId.value = null
  lastRequest.value = null
  activePanel.value = 'sources'
}

async function uploadAttachment(file) {
  runState.value = 'uploading'
  error.value = null
  activePanel.value = 'progress'
  progress.value = [createProgress('file_upload', '파일 업로드 중', 'working')]

  try {
    const attachment = await uploadFile(file)
    attachments.value = [...attachments.value, attachment]
    progress.value = [
      createProgress(
        'file_upload',
        attachment.detail || '파일 업로드 완료',
        attachment.status === 'error' ? 'failed' : 'completed',
      ),
    ]
    runState.value = attachment.status === 'error' ? 'partial-failure' : 'idle'
    if (attachment.status === 'error') error.value = attachment.detail || '파일 인덱싱에 실패했습니다.'
  } catch (err) {
    error.value = err.message
    progress.value = [createProgress('file_upload', err.message, 'failed')]
    runState.value = 'partial-failure'
  }
}

function removeAttachment(id) {
  attachments.value = attachments.value.filter((attachment) => attachment.id !== id)
}

function sendDraft() {
  const messageText = draft.value.trim()
  const requestText = messageText || '첨부 파일을 분석해줘.'
  if ((!messageText && attachments.value.length === 0) || isBusy()) return

  const requestAttachments = [...attachments.value]
  dispatchRequest({
    text: requestText,
    attachments: requestAttachments,
    capabilities: requestedCapabilities({ attachments: requestAttachments }),
    preservedDraft: draft.value,
  })
}

function dispatchRequest({ text, attachments: requestAttachments, capabilities, preservedDraft }) {
  lastRequest.value = {
    text,
    attachments: requestAttachments,
    capabilities,
    preservedDraft,
  }
  messages.value.push(createMessage({
    role: 'user',
    content: text,
    files: requestAttachments,
  }))
  draft.value = ''
  runState.value = 'running'
  error.value = null
  activePanel.value = 'progress'
  progress.value = [createProgress('orchestrator', '요청을 분석 중입니다', 'working')]

  stopStream?.()
  stopStream = streamChat(text, sessionId.value, {
    onProgress(item) {
      progress.value = [...progress.value, item]
    },
    onAnswer(payload) {
      sessionId.value = payload.sessionId || sessionId.value
      const answerFiles = payload.files || []
      const answerSources = payload.sources || []
      const answerProgress = payload.progress || []
      messages.value.push(createMessage({
        role: 'assistant',
        content: payload.content,
        sources: answerSources,
        files: answerFiles,
        progress: answerProgress,
        error: payload.error,
      }))
      sources.value = answerSources
      generatedFiles.value = answerFiles
      if (answerProgress.length) progress.value = answerProgress
      if (payload.status === 'partial_failure' || payload.error) {
        error.value = payload.error || '일부 작업이 실패했습니다.'
        draft.value = preservedDraft
        runState.value = 'partial-failure'
      }
      if (answerSources.length) activePanel.value = 'sources'
      else if (answerFiles.length) activePanel.value = 'files'
    },
    onError(message) {
      error.value = message
      draft.value = preservedDraft
      runState.value = 'partial-failure'
      progress.value = [...progress.value, createProgress('chat', message, 'failed')]
      activePanel.value = 'progress'
    },
    onDone() {
      if (!error.value) runState.value = 'idle'
      stopStream = null
    },
  }, {
    attachments: requestAttachments,
    requestedCapabilities: capabilities,
  })
}

function requestedCapabilities({ includeWebSearch = true, attachments: requestAttachments = attachments.value } = {}) {
  const capabilities = []
  if (includeWebSearch) capabilities.push('web_search')
  if (requestAttachments.length) capabilities.push('upload_file', 'rag_vector_search', 'get_file_info')
  return capabilities
}

function retryFailedStep() {
  if (!lastRequest.value || isBusy()) return
  dispatchRequest(lastRequest.value)
}

function continueWithFilesOnly() {
  if (isBusy()) return
  const previous = lastRequest.value
  const requestAttachments = previous?.attachments?.length ? previous.attachments : [...attachments.value]
  const baseText = previous?.text || draft.value.trim() || '첨부 파일을 분석해줘.'
  const text = `${baseText}\n\n웹 검색 없이 첨부 파일 기준으로만 계속해줘.`
  dispatchRequest({
    text,
    attachments: requestAttachments,
    capabilities: requestedCapabilities({ includeWebSearch: false, attachments: requestAttachments }),
    preservedDraft: text,
  })
}

function isBusy() {
  return runState.value === 'running' || runState.value === 'uploading'
}

onMounted(async () => {
  try {
    capabilities.value = await getCapabilities()
  } catch {
    capabilities.value = []
  }
})

onBeforeUnmount(() => {
  stopStream?.()
})
</script>

<template>
  <div class="m001-shell">
    <ChatHeader :state="runState" @new-chat="startNewChat" />
    <main class="m001-main">
      <section class="chat-workspace" aria-label="단일 챗봇">
        <header class="workspace-heading">
          <div>
            <h2>단일 챗봇</h2>
            <p>텍스트 요청, 파일 첨부, 웹 근거 확인, 산출물 다운로드를 한 화면에서 처리합니다.</p>
          </div>
          <span>M-001</span>
        </header>

        <MessageList
          :messages="messages"
          :running-message="runningMessage"
          @select-prompt="applyPrompt"
        />

        <RecoveryBanner
          v-if="error"
          :message="error"
          @retry="retryFailedStep"
          @continue-with-files="continueWithFilesOnly"
        />

        <EvidencePanel
          v-model:active-tab="activePanel"
          class="mobile-evidence"
          mobile-collapsed
          :sources="sources"
          :files="generatedFiles.length ? generatedFiles : attachments"
          :progress="progress"
          :capabilities="capabilities"
        />

        <div class="composer-wrap">
          <MessageComposer
            v-model="draft"
            :attachments="attachments"
            :sending="runState === 'running' || runState === 'uploading'"
            :error="error"
            @submit="sendDraft"
            @pick-file="uploadAttachment"
            @remove-attachment="removeAttachment"
            @retry="retryFailedStep"
          />
        </div>
      </section>

      <EvidencePanel
        v-model:active-tab="activePanel"
        class="desktop-evidence"
        :sources="sources"
        :files="generatedFiles.length ? generatedFiles : attachments"
        :progress="progress"
        :capabilities="capabilities"
      />

    </main>
  </div>
</template>

<style scoped>
.m001-shell {
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100vh;
  min-width: 0;
  background: var(--m001-bg);
}

.m001-main {
  display: grid;
  flex: 1;
  min-height: 0;
  grid-template-columns: minmax(0, 1fr) 424px;
  gap: 32px;
  padding: 32px;
}

.chat-workspace {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-panel);
  background: var(--m001-surface);
  box-shadow: var(--m001-shadow-panel);
}

.workspace-heading {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--m001-border);
}

h2,
p {
  margin: 0;
}

h2 {
  color: var(--m001-text);
  font-size: 18px;
  line-height: 26px;
  font-weight: 900;
}

p {
  margin-top: 3px;
  color: var(--m001-muted);
  font-size: 12px;
  line-height: 18px;
}

.workspace-heading span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 24px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--m001-primary-soft);
  color: var(--m001-primary);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.composer-wrap {
  padding: 0 24px 22px;
}

.mobile-evidence {
  display: none;
}

@media (max-width: 1024px) {
  .m001-main {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 22px 16px;
    min-height: 0;
    overflow: hidden;
  }

  .chat-workspace {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .desktop-evidence {
    display: none;
  }

  .mobile-evidence {
    display: flex;
    margin: 0 16px 14px;
  }

  .composer-wrap {
    position: sticky;
    bottom: 0;
    z-index: 2;
    padding: 0 16px 16px;
    background: var(--m001-surface);
  }
}

@media (max-width: 560px) {
  .m001-main {
    padding: 22px 16px;
  }

  .workspace-heading {
    padding: 20px 18px 16px;
  }
}
</style>
