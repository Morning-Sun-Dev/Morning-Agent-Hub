<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { createMessage, createProgress } from '../../models/chatModels'
import {
  createFolder,
  deleteFile,
  findFolders,
  getCapabilities,
  getFileDownloadAction,
  getFileInfo,
  getReportTemplates,
  listFiles,
  streamChat,
  updateFileName,
  uploadFile,
} from '../../api'
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
const driveFiles = ref([])
const folders = ref([])
const capabilities = ref([])
const reportTemplates = ref([])
const selectedTemplateId = ref('')
const selectedCapabilityIds = ref([])
const fileNotice = ref('')
const folderNotice = ref('')
const error = ref(null)
const sessionId = ref(null)
const lastRequest = ref(null)

let stopStream = null

const capabilityPromptMap = {
  route_request: '이 요청을 적절한 에이전트 실행 계획으로 분해해줘.',
  web_search: '이 주제의 최신 정보를 출처와 함께 검색해줘.',
  news_search: '이 주제의 최신 뉴스와 핵심 변화를 출처와 함께 요약해줘.',
  url_fetch: '다음 URL 내용을 가져와 핵심 내용을 요약해줘:\nhttps://',
  rag_vector_search: '사내 문서에서 이 주제와 관련된 근거를 찾아 답변해줘.',
  rag_sql_search: '문서 유형, 날짜, 작성자 같은 메타데이터 조건으로 관련 문서를 찾아줘.',
  rag_index: '선택한 Drive 파일을 인덱싱하고 검색 가능 상태로 만들어줘.',
  upload_file: '이 내용을 Google Drive 파일로 저장해줘.',
  download_file: 'Drive 파일을 다운로드 가능한 링크로 준비해줘.\n파일 ID 또는 gdrive://file/: ',
  get_file_info: 'Drive 파일의 이름, 크기, 형식, 수정일 정보를 확인해줘.\n파일 ID 또는 gdrive://file/: ',
  find_folder: 'Google Drive에서 다음 폴더를 찾아줘:\n폴더명: ',
  list_files: 'Google Drive 파일 목록을 보여줘.',
  delete_file: '다음 Drive 파일을 휴지통으로 이동해줘.\n파일 ID 또는 gdrive://file/: ',
  update_file: '다음 Drive 파일의 이름이나 내용을 업데이트해줘.\n파일 ID 또는 gdrive://file/: ',
  create_folder: 'Google Drive에 새 폴더를 만들어줘.\n폴더명: ',
  write_report: '수집한 정보를 Markdown 보고서로 작성해줘.',
  format_report: '다음 내용을 선택한 보고서 양식에 맞춰 정리해줘.',
  list_templates: '사용 가능한 보고서 양식 목록과 각 용도를 알려줘.',
}

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

const selectedReportTemplate = computed(() =>
  reportTemplates.value.find((template) => template.id === selectedTemplateId.value) || null,
)

const panelFiles = computed(() => {
  if (generatedFiles.value.length) return generatedFiles.value
  if (attachments.value.length) return attachments.value
  return driveFiles.value
})

function applyPrompt(prompt) {
  draft.value = prompt
}

function applyCapability(capability) {
  const capabilityId = capability?.capabilityId
  if (!capabilityId) return

  selectedCapabilityIds.value = [capabilityId]
  draft.value = capabilityPromptMap[capabilityId] || `${capability.label || '선택한 기능'}을 사용해줘.`
  activePanel.value = 'capabilities'
}

function startNewChat() {
  stopStream?.()
  stopStream = null
  messages.value = []
  draft.value = ''
  attachments.value = []
  sources.value = []
  generatedFiles.value = []
  folders.value = []
  progress.value = []
  fileNotice.value = ''
  folderNotice.value = ''
  error.value = null
  runState.value = 'idle'
  sessionId.value = null
  lastRequest.value = null
  selectedTemplateId.value = ''
  selectedCapabilityIds.value = []
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
  const reportTemplate = selectedReportTemplate.value
  const extraCapabilities = [...selectedCapabilityIds.value]
  const transportText = withReportTemplateInstruction(requestText, reportTemplate)
  dispatchRequest({
    text: transportText,
    displayText: requestText,
    attachments: requestAttachments,
    capabilities: requestedCapabilities({ attachments: requestAttachments, reportTemplate, extraCapabilities }),
    preservedDraft: draft.value,
    reportTemplate,
  })
  selectedCapabilityIds.value = []
}

function dispatchRequest({
  text,
  displayText = text,
  attachments: requestAttachments,
  capabilities,
  preservedDraft,
  reportTemplate = null,
}) {
  lastRequest.value = {
    text,
    displayText,
    attachments: requestAttachments,
    capabilities,
    preservedDraft,
    reportTemplate,
  }
  messages.value.push(createMessage({
    role: 'user',
    content: displayText,
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

function requestedCapabilities({
  includeWebSearch = true,
  attachments: requestAttachments = attachments.value,
  reportTemplate = selectedReportTemplate.value,
  extraCapabilities = selectedCapabilityIds.value,
} = {}) {
  const nextCapabilities = []
  if (includeWebSearch) nextCapabilities.push('web_search')
  if (requestAttachments.length) nextCapabilities.push('upload_file', 'rag_vector_search', 'get_file_info')
  if (reportTemplate) nextCapabilities.push('write_report', 'format_report', 'list_templates')
  nextCapabilities.push(...extraCapabilities.filter(Boolean))
  return [...new Set(nextCapabilities)]
}

function withReportTemplateInstruction(text, reportTemplate) {
  if (!reportTemplate) return text
  return [
    text,
    '',
    '[보고서 양식]',
    `template_id: ${reportTemplate.id}`,
    `template_name: ${reportTemplate.name}`,
  ].join('\n')
}

function retryFailedStep() {
  if (!lastRequest.value || isBusy()) return
  dispatchRequest(lastRequest.value)
}

function continueWithFilesOnly() {
  if (isBusy()) return
  const previous = lastRequest.value
  const requestAttachments = previous?.attachments?.length ? previous.attachments : [...attachments.value]
  const reportTemplate = previous?.reportTemplate || selectedReportTemplate.value
  const baseText = previous?.displayText || previous?.text || draft.value.trim() || '첨부 파일을 분석해줘.'
  const displayText = `${baseText}\n\n웹 검색 없이 첨부 파일 기준으로만 계속해줘.`
  const text = withReportTemplateInstruction(displayText, reportTemplate)
  dispatchRequest({
    text,
    displayText,
    attachments: requestAttachments,
    capabilities: requestedCapabilities({ includeWebSearch: false, attachments: requestAttachments, reportTemplate }),
    preservedDraft: displayText,
    reportTemplate,
  })
}

function isBusy() {
  return runState.value === 'running' || runState.value === 'uploading'
}

function updateDriveFile(fileId, updates) {
  const applyUpdates = (file) => {
    if (fileActionId(file) !== fileId) return file
    return { ...file, ...updates }
  }
  driveFiles.value = driveFiles.value.map(applyUpdates)
  attachments.value = attachments.value.map(applyUpdates)
  generatedFiles.value = generatedFiles.value.map(applyUpdates)
}

function fileActionId(file) {
  return file?.fileId || file?.file_id || file?.storageRef || file?.storage_ref || file?.id
}

async function inspectFile(fileId) {
  try {
    const file = await getFileInfo(fileId)
    updateDriveFile(fileId, file)
    fileNotice.value = `${file.name || '파일'} 상세 정보를 확인했습니다.`
    activePanel.value = 'files'
  } catch (err) {
    fileNotice.value = err.message || '파일 상세 정보를 확인하지 못했습니다.'
  }
}

async function prepareFileDownload(fileId) {
  try {
    const action = await getFileDownloadAction(fileId)
    if (!action.available) {
      fileNotice.value = '다운로드 링크가 아직 준비되지 않았습니다.'
      return
    }
    updateDriveFile(fileId, { downloadUrl: action.url, openUrl: action.fallbackOpenUrl })
    fileNotice.value = '다운로드 링크가 준비됐습니다.'
    activePanel.value = 'files'
  } catch (err) {
    fileNotice.value = err.message || '다운로드 링크를 준비하지 못했습니다.'
  }
}

async function renameDriveFile(fileId) {
  const currentFile = [...driveFiles.value, ...attachments.value, ...generatedFiles.value]
    .find((file) => fileActionId(file) === fileId)
  const nextName = globalThis.prompt
    ? globalThis.prompt('새 파일 이름', currentFile?.name || '')
    : ''
  const trimmedName = nextName?.trim()
  if (!trimmedName || trimmedName === currentFile?.name) return

  try {
    const file = await updateFileName(fileId, trimmedName)
    updateDriveFile(fileId, file)
    fileNotice.value = '파일 이름을 변경했습니다.'
    activePanel.value = 'files'
  } catch (err) {
    fileNotice.value = err.message || '파일 이름을 변경하지 못했습니다.'
    activePanel.value = 'files'
  }
}

async function deleteDriveFile(fileId) {
  const confirmed = globalThis.confirm ? globalThis.confirm('이 Drive 파일을 휴지통으로 이동할까요?') : true
  if (!confirmed) return

  try {
    await deleteFile(fileId)
    driveFiles.value = driveFiles.value.filter((file) => fileActionId(file) !== fileId)
    attachments.value = attachments.value.filter((file) => fileActionId(file) !== fileId)
    generatedFiles.value = generatedFiles.value.filter((file) => fileActionId(file) !== fileId)
    fileNotice.value = '파일을 휴지통으로 이동했습니다.'
    activePanel.value = 'files'
  } catch (err) {
    fileNotice.value = err.message || '파일을 삭제하지 못했습니다.'
    activePanel.value = 'files'
  }
}

async function findDriveFolder(name) {
  try {
    folders.value = await findFolders(name)
    folderNotice.value = folders.value.length
      ? `${folders.value.length}개 폴더를 찾았습니다.`
      : '일치하는 폴더가 없습니다.'
    activePanel.value = 'files'
  } catch (err) {
    folderNotice.value = err.message || '폴더를 조회하지 못했습니다.'
    activePanel.value = 'files'
  }
}

async function createDriveFolder(name) {
  try {
    const folder = await createFolder(name)
    folders.value = [folder, ...folders.value.filter((item) => item.id !== folder.id)]
    folderNotice.value = '폴더를 생성했습니다.'
    activePanel.value = 'files'
  } catch (err) {
    folderNotice.value = err.message || '폴더를 생성하지 못했습니다.'
    activePanel.value = 'files'
  }
}

onMounted(async () => {
  const [capabilityResult, templateResult, fileResult] = await Promise.allSettled([
    getCapabilities(),
    getReportTemplates(),
    listFiles(),
  ])
  capabilities.value = capabilityResult.status === 'fulfilled' ? capabilityResult.value : []
  reportTemplates.value = templateResult.status === 'fulfilled' ? templateResult.value : []
  driveFiles.value = fileResult.status === 'fulfilled' ? fileResult.value : []
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
          :files="panelFiles"
          :folders="folders"
          :progress="progress"
          :capabilities="capabilities"
          :file-notice="fileNotice"
          :folder-notice="folderNotice"
          @inspect-file="inspectFile"
          @prepare-download="prepareFileDownload"
          @rename-file="renameDriveFile"
          @delete-file="deleteDriveFile"
          @find-folder="findDriveFolder"
          @create-folder="createDriveFolder"
          @select-capability="applyCapability"
        />

        <div class="composer-wrap">
          <MessageComposer
            v-model="draft"
            :attachments="attachments"
            :sending="runState === 'running' || runState === 'uploading'"
            :error="error"
            :report-templates="reportTemplates"
            :selected-template-id="selectedTemplateId"
            @update:selected-template-id="selectedTemplateId = $event"
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
        :files="panelFiles"
        :folders="folders"
        :progress="progress"
        :capabilities="capabilities"
        :file-notice="fileNotice"
        :folder-notice="folderNotice"
        @inspect-file="inspectFile"
        @prepare-download="prepareFileDownload"
        @rename-file="renameDriveFile"
        @delete-file="deleteDriveFile"
        @find-folder="findDriveFolder"
        @create-folder="createDriveFolder"
        @select-capability="applyCapability"
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
