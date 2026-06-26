<script setup>
import { computed, ref } from 'vue'
import GeneratedFileRow from './GeneratedFileRow.vue'
import ProgressTrace from './ProgressTrace.vue'
import SourceCard from './SourceCard.vue'

const props = defineProps({
  sources: { type: Array, default: () => [] },
  files: { type: Array, default: () => [] },
  folders: { type: Array, default: () => [] },
  progress: { type: Array, default: () => [] },
  capabilities: { type: Array, default: () => [] },
  fileNotice: { type: String, default: '' },
  folderNotice: { type: String, default: '' },
  activeTab: { type: String, default: 'sources' },
  mobileCollapsed: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:activeTab',
  'inspect-file',
  'prepare-download',
  'rename-file',
  'delete-file',
  'find-folder',
  'create-folder',
  'select-capability',
  'run-capability',
])
const expanded = ref(false)
const folderName = ref('')
const newsQuery = ref('')
const urlValue = ref('')
const capabilityValues = ref({})
const showMobileSummary = computed(() => props.mobileCollapsed && !expanded.value)
const itemCount = computed(() => (
  props.sources.length + props.files.length + props.folders.length + props.progress.length + props.capabilities.length
))
const canRunNews = computed(() => Boolean(newsQuery.value.trim()) && !props.busy)
const canRunUrl = computed(() => isHttpUrl(urlValue.value.trim()) && !props.busy)
const noValueQuickRunCapabilities = new Set(['list_files', 'list_templates'])
const capabilityInputCopy = {
  route_request: {
    label: '요청 내용',
    placeholder: '예: 업로드한 문서를 요약하고 최신 뉴스와 비교해줘',
    help: '오케스트레이터가 필요한 에이전트 실행 계획을 만듭니다.',
  },
  web_search: {
    label: '검색 주제',
    placeholder: '예: AI 에이전트 시장',
    help: '웹 검색을 켜고 출처가 포함된 답변을 요청합니다.',
  },
  news_search: {
    label: '뉴스 주제',
    placeholder: '예: AI 에이전트 투자 동향',
    help: '최신 뉴스성 정보를 우선 검색합니다.',
  },
  url_fetch: {
    label: '분석할 URL',
    placeholder: 'https://example.com/report',
    help: 'URL 본문을 가져와 핵심 내용을 요약합니다.',
  },
  rag_vector_search: {
    label: '문서 검색 질문',
    placeholder: '예: 휴가 규정에서 승인 절차 찾아줘',
    help: '인덱싱된 내부 문서에서 의미 기반 근거를 찾습니다.',
  },
  rag_sql_search: {
    label: '메타데이터 조건',
    placeholder: '예: 2026년 PDF 문서',
    help: '문서 유형, 날짜, 작성자 같은 조건으로 문서를 찾습니다.',
  },
  rag_index: {
    label: 'Drive 파일 ID',
    placeholder: 'gdrive://file/... 또는 파일 ID',
    help: 'Drive 파일을 검색 가능한 문서로 인덱싱합니다.',
  },
  upload_file: {
    label: '저장할 내용',
    placeholder: 'Drive에 저장할 Markdown 또는 텍스트',
    help: '입력 내용을 새 Drive 파일로 저장하도록 요청합니다.',
  },
  download_file: {
    label: 'Drive 파일 ID',
    placeholder: 'gdrive://file/... 또는 파일 ID',
    help: '해당 파일의 다운로드 또는 열기 링크를 준비합니다.',
  },
  get_file_info: {
    label: 'Drive 파일 ID',
    placeholder: 'gdrive://file/... 또는 파일 ID',
    help: '파일명, 크기, 형식, 링크 같은 메타데이터를 조회합니다.',
  },
  find_folder: {
    label: '폴더명',
    placeholder: '예: 주간 보고서',
    help: 'Drive에서 이름이 일치하거나 포함된 폴더를 찾습니다.',
  },
  list_files: {
    label: '필터 조건',
    placeholder: '검색어 또는 폴더명 (비워도 실행 가능)',
    help: '비워두면 Drive 파일 목록을 조회합니다.',
  },
  delete_file: {
    label: 'Drive 파일 ID',
    placeholder: 'gdrive://file/... 또는 파일 ID',
    help: '해당 Drive 파일을 휴지통으로 이동하도록 요청합니다.',
  },
  update_file: {
    label: '변경 요청',
    placeholder: '예: fileId=... name=새파일명.pdf',
    help: '파일 이름 또는 내용을 바꾸는 요청을 보냅니다.',
  },
  create_folder: {
    label: '폴더명',
    placeholder: '예: 2026 리서치 자료',
    help: 'Drive에 새 폴더를 생성하도록 요청합니다.',
  },
  write_report: {
    label: '문서 내용',
    placeholder: '보고서로 정리할 내용이나 주제',
    help: 'Markdown 문서 형태로 구조화하도록 요청합니다.',
  },
  format_report: {
    label: '정리할 내용',
    placeholder: '양식에 맞춰 정리할 원문 또는 주제',
    help: '선택된 보고서 양식이 있으면 함께 전달합니다.',
  },
  list_templates: {
    label: '추가 조건',
    placeholder: '비워도 실행 가능',
    help: '사용 가능한 보고서 양식 목록과 용도를 조회합니다.',
  },
}

const tabs = [
  { id: 'sources', label: '출처' },
  { id: 'files', label: '파일' },
  { id: 'progress', label: '진행' },
  { id: 'capabilities', label: '기능' },
]

const uiStatusLabel = {
  available: '사용 가능',
  partial: '부분 지원',
  planned: '예정',
}

function statusLabel(status) {
  return uiStatusLabel[status] || '예정'
}

function submitFolderSearch() {
  const name = folderName.value.trim()
  if (name) emit('find-folder', name)
}

function submitFolderCreate() {
  const name = folderName.value.trim()
  if (name) emit('create-folder', name)
}

function submitNewsSearch() {
  const value = newsQuery.value.trim()
  if (!value || props.busy) return
  emit('run-capability', { capabilityId: 'news_search', value })
}

function submitUrlFetch() {
  const value = urlValue.value.trim()
  if (!isHttpUrl(value) || props.busy) return
  emit('run-capability', { capabilityId: 'url_fetch', value })
}

function capabilityInputConfig(capability) {
  return capabilityInputCopy[capability?.capabilityId] || {
    label: '실행 입력',
    placeholder: '요청할 주제나 조건',
    help: '입력값과 함께 해당 기능을 바로 실행합니다.',
  }
}

function capabilityInputLabel(capability) {
  return capabilityInputConfig(capability).label
}

function capabilityPlaceholder(capability) {
  return capabilityInputConfig(capability).placeholder
}

function capabilityHelp(capability) {
  return capabilityInputConfig(capability).help
}

function updateCapabilityValue(capabilityId, event) {
  capabilityValues.value = {
    ...capabilityValues.value,
    [capabilityId]: event.target.value,
  }
}

function canRunCapability(capability) {
  if (!capability?.enabled || props.busy) return false
  const capabilityId = capability.capabilityId
  if (noValueQuickRunCapabilities.has(capabilityId)) return true
  return Boolean((capabilityValues.value[capabilityId] || '').trim())
}

function runCapability(capability) {
  if (!canRunCapability(capability)) return
  const capabilityId = capability.capabilityId
  emit('run-capability', {
    capabilityId,
    value: (capabilityValues.value[capabilityId] || '').trim(),
  })
}

function isHttpUrl(value) {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}
</script>

<template>
  <aside class="evidence-panel" :class="{ collapsed: mobileCollapsed }" aria-label="작업 근거">
    <template v-if="showMobileSummary">
      <button type="button" class="mobile-summary" aria-expanded="false" @click="expanded = true">
        <span>근거 패널 펼치기</span>
        <strong>{{ itemCount }}</strong>
      </button>
    </template>

    <template v-else>
      <header>
        <div>
          <h2>작업 근거</h2>
          <p>출처, 파일, 진행 상태를 탭별로 분리합니다.</p>
        </div>
        <button
          v-if="mobileCollapsed"
          type="button"
          class="collapse-button"
          aria-label="근거 패널 접기"
          @click="expanded = false"
        >
          접기
        </button>
      </header>
      <nav class="panel-tabs" aria-label="근거 패널 탭">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          :class="{ active: activeTab === tab.id }"
          @click="emit('update:activeTab', tab.id)"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div class="panel-body">
        <div v-if="activeTab === 'sources'" class="panel-stack">
          <div v-if="sources.length === 0" class="empty-panel">
            <span>i</span>
            <strong>아직 표시할 근거가 없습니다</strong>
            <p>답변이 생성되면 인용 출처, 참조한 파일, 실행 단계가 이 영역에 표시됩니다.</p>
          </div>
          <SourceCard v-for="source in sources" v-else :key="source.url || source.title" :source="source" />
        </div>

        <div v-if="activeTab === 'files'" class="panel-stack">
          <form class="folder-tools" aria-label="Drive 폴더 작업" @submit.prevent="submitFolderSearch">
            <input
              v-model="folderName"
              type="text"
              placeholder="폴더명"
              aria-label="폴더명"
              data-testid="folder-name-input"
            >
            <button type="button" data-testid="folder-find-button" @click="submitFolderSearch">
              폴더 조회
            </button>
            <button type="button" data-testid="folder-create-button" @click="submitFolderCreate">
              폴더 생성
            </button>
          </form>
          <div v-if="folderNotice" class="file-notice" role="status">{{ folderNotice }}</div>
          <div v-if="folders.length" class="folder-results" aria-label="폴더 결과">
            <article v-for="folder in folders" :key="folder.id || folder.name" class="folder-row">
              <div>
                <strong>{{ folder.name }}</strong>
                <span>{{ folder.folderId || folder.storageRef }}</span>
              </div>
              <a v-if="folder.openUrl" :href="folder.openUrl" target="_blank" rel="noreferrer">열기</a>
            </article>
          </div>
          <div v-if="fileNotice" class="file-notice" role="status">{{ fileNotice }}</div>
          <div v-if="files.length === 0" class="empty-panel">
            <span>f</span>
            <strong>아직 표시할 파일이 없습니다</strong>
            <p>생성 파일이나 첨부 파일 링크가 준비되면 여기에 표시됩니다.</p>
          </div>
          <GeneratedFileRow
            v-for="file in files"
            v-else
            :key="file.id || file.name"
            :file="file"
            @inspect="emit('inspect-file', $event)"
            @prepare-download="emit('prepare-download', $event)"
            @rename="emit('rename-file', $event)"
            @delete="emit('delete-file', $event)"
          />
        </div>

        <div v-if="activeTab === 'progress'" class="panel-stack">
          <div v-if="progress.length === 0" class="empty-panel">
            <span>p</span>
            <strong>진행 중인 작업이 없습니다</strong>
            <p>요청을 보내면 업로드, 분석, 응답 단계가 표시됩니다.</p>
          </div>
          <ProgressTrace v-else :progress="progress" />
        </div>

        <div v-if="activeTab === 'capabilities'" class="panel-stack">
          <section class="capability-tools" aria-label="웹 기능 빠른 실행">
            <form class="capability-tool" @submit.prevent="submitNewsSearch">
              <label>
                <span>뉴스 주제</span>
                <input
                  v-model="newsQuery"
                  type="text"
                  placeholder="AI 에이전트 시장"
                  data-testid="news-query-input"
                >
              </label>
              <button
                type="button"
                data-testid="news-search-button"
                :disabled="!canRunNews"
                @click="submitNewsSearch"
              >
                뉴스 검색
              </button>
            </form>
            <form class="capability-tool" @submit.prevent="submitUrlFetch">
              <label>
                <span>URL</span>
                <input
                  v-model="urlValue"
                  type="url"
                  placeholder="https://example.com/report"
                  data-testid="url-fetch-input"
                >
              </label>
              <button
                type="button"
                data-testid="url-fetch-button"
                :disabled="!canRunUrl"
                @click="submitUrlFetch"
              >
                URL 분석
              </button>
            </form>
          </section>
          <div v-if="capabilities.length === 0" class="empty-panel">
            <span>c</span>
            <strong>기능 정보를 불러오지 못했습니다</strong>
            <p>연결이 복구되면 에이전트 기능과 UI 지원 상태가 표시됩니다.</p>
          </div>
          <article
            v-for="capability in capabilities"
            v-else
            :key="`${capability.agentId}:${capability.capabilityId}`"
            class="capability-card"
          >
            <div>
              <strong>{{ capability.label }}</strong>
              <span>{{ capability.agentId }}</span>
            </div>
            <p>{{ capability.description }}</p>
            <footer>
              <span :data-status="capability.uiStatus">{{ statusLabel(capability.uiStatus) }}</span>
              <small v-if="capability.uiSurface">{{ capability.uiSurface }}</small>
            </footer>
            <form class="capability-card-runner" @submit.prevent="runCapability(capability)">
              <label class="capability-run-field">
                <span>{{ capabilityInputLabel(capability) }}</span>
                <input
                  :value="capabilityValues[capability.capabilityId] || ''"
                  type="text"
                  :placeholder="capabilityPlaceholder(capability)"
                  :aria-label="`${capability.label} 실행 입력`"
                  data-testid="capability-run-input"
                  @input="updateCapabilityValue(capability.capabilityId, $event)"
                >
                <small>{{ capabilityHelp(capability) }}</small>
              </label>
              <button
                type="button"
                data-testid="capability-run-button"
                :disabled="!canRunCapability(capability)"
                @click="runCapability(capability)"
              >
                실행
              </button>
            </form>
            <button
              type="button"
              class="capability-action"
              data-testid="capability-request-button"
              :disabled="!capability.enabled"
              @click="emit('select-capability', capability)"
            >
              요청 초안
            </button>
          </article>
        </div>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.evidence-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-panel);
  background: var(--m001-surface);
  box-shadow: var(--m001-shadow-panel);
  overflow: hidden;
}

header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
  padding: 20px;
  border-bottom: 1px solid var(--m001-border);
}

h2,
p {
  margin: 0;
}

h2 {
  color: var(--m001-text);
  font-size: 16px;
  line-height: 24px;
}

p {
  margin-top: 4px;
  color: var(--m001-muted);
  font-size: 12px;
  line-height: 18px;
}

.panel-tabs {
  display: flex;
  gap: 8px;
  padding: 16px 20px 6px;
}

.panel-tabs button {
  flex: 1 1 0;
  min-width: 0;
  height: 32px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-muted);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.panel-tabs button.active {
  border-color: var(--m001-primary-soft);
  background: var(--m001-primary-soft);
  color: var(--m001-primary);
}

.panel-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 20px 20px;
}

.panel-stack {
  display: grid;
  gap: 16px;
  padding-top: 10px;
}

.empty-panel {
  display: grid;
  justify-items: center;
  align-content: center;
  min-height: 460px;
  text-align: center;
}

.empty-panel span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--m001-radius-panel);
  background: var(--m001-panel);
  color: var(--m001-muted);
  font-size: 13px;
  font-weight: 900;
}

.empty-panel strong {
  margin-top: 18px;
  color: var(--m001-text);
  font-size: 16px;
}

.empty-panel p {
  max-width: 300px;
}

.capability-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-card);
  background: white;
}

.capability-tools {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-card);
  background: var(--m001-panel-subtle);
}

.capability-tool {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: end;
}

.capability-tool label {
  display: grid;
  min-width: 0;
  gap: 6px;
  color: var(--m001-muted);
  font-size: 11px;
  font-weight: 900;
}

.capability-tool input {
  min-width: 0;
  height: 34px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 700;
  padding: 0 10px;
}

.capability-tool button {
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--m001-border-strong);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.capability-tool button:disabled {
  color: var(--m001-muted);
  cursor: not-allowed;
}

.capability-card-runner {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
}

.capability-run-field {
  display: grid;
  min-width: 0;
  gap: 5px;
}

.capability-run-field span {
  color: var(--m001-muted);
  font-size: 11px;
  font-weight: 900;
}

.capability-card-runner input {
  min-width: 0;
  height: 32px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-control);
  background: var(--m001-panel-subtle);
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 700;
  padding: 0 10px;
}

.capability-run-field small {
  color: var(--m001-muted);
  font-size: 11px;
  line-height: 16px;
}

.capability-card-runner button {
  min-height: 32px;
  margin-top: 21px;
  padding: 0 10px;
  border: 1px solid var(--m001-border-strong);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.capability-card-runner button:disabled {
  color: var(--m001-muted);
  cursor: not-allowed;
}

.file-notice {
  padding: 10px 12px;
  border: 1px solid var(--m001-success-soft);
  border-radius: var(--m001-radius-control);
  background: var(--m001-success-soft);
  color: var(--m001-success);
  font-size: 12px;
  font-weight: 800;
}

.folder-tools {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 8px;
}

.folder-tools input {
  min-width: 0;
  height: 34px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 700;
  padding: 0 10px;
}

.folder-tools button,
.folder-row a {
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--m001-border-strong);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
  cursor: pointer;
}

.folder-results {
  display: grid;
  gap: 8px;
}

.folder-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-card);
  background: var(--m001-panel-subtle);
}

.folder-row div {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.folder-row strong {
  overflow: hidden;
  color: var(--m001-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-row span {
  overflow: hidden;
  color: var(--m001-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.capability-card > div,
.capability-card footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.capability-card strong {
  color: var(--m001-text);
  font-size: 13px;
  line-height: 18px;
}

.capability-card div span {
  color: var(--m001-muted);
  font-size: 11px;
  font-weight: 800;
}

.capability-card p {
  margin: 0;
}

.capability-card footer span {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--m001-panel);
  color: var(--m001-muted);
  font-size: 11px;
  font-weight: 900;
}

.capability-card footer span[data-status="available"] {
  background: var(--m001-success-soft);
  color: var(--m001-success);
}

.capability-card footer span[data-status="partial"] {
  background: var(--m001-warning-soft);
  color: var(--m001-warning);
}

.capability-action {
  justify-self: end;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--m001-border-strong);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.capability-action:disabled {
  color: var(--m001-muted);
  cursor: not-allowed;
}

.capability-card small {
  color: var(--m001-muted);
  font-size: 11px;
  line-height: 16px;
  text-align: right;
}

.mobile-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 54px;
  padding: 0 16px;
  border: 0;
  background: white;
  color: var(--m001-text);
  cursor: pointer;
}

.mobile-summary span {
  font-size: 13px;
  font-weight: 700;
}

.mobile-summary strong {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 999px;
  background: var(--m001-panel);
  color: var(--m001-muted);
  font-size: 12px;
}

.collapse-button {
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-muted);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

@media (max-width: 1024px) {
  .panel-body {
    max-height: 280px;
  }

  .empty-panel {
    min-height: 160px;
  }
}

@media (max-width: 520px) {
  .folder-tools,
  .capability-tool {
    grid-template-columns: minmax(0, 1fr);
  }

  .folder-tools button,
  .capability-tool button {
    width: 100%;
  }
}
</style>
