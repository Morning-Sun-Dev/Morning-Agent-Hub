<script setup>
import { computed } from 'vue'
import { safeUrl } from '../../models/chatModels'

const props = defineProps({
  file: { type: Object, required: true },
})

const emit = defineEmits(['inspect', 'prepare-download', 'rename', 'delete'])

const downloadUrl = computed(() => safeUrl(props.file.downloadUrl || props.file.download_url))
const openUrl = computed(() => safeUrl(props.file.openUrl || props.file.open_url))
const fileActionId = computed(() => props.file.fileId || props.file.file_id || props.file.storageRef || props.file.id)
const canDelete = computed(() => ['drive', 'uploaded'].includes(props.file.kind))
const metadataRows = computed(() => {
  const rows = []
  addMetadataRow(rows, '파일 ID', fileActionId.value)
  addMetadataRow(rows, '형식', props.file.mimeType || props.file.mime_type)
  addMetadataRow(rows, '크기', formatFileSize(props.file.size))
  addMetadataRow(rows, '수정일', formatDate(props.file.modifiedAt || props.file.modified_at || props.file.modifiedTime))
  addMetadataRow(rows, '생성일', formatDate(props.file.createdAt || props.file.created_at || props.file.createdTime))
  addMetadataRow(rows, '상태', props.file.isTrashed ? '휴지통' : props.file.status)
  addMetadataRow(rows, '저장 위치', props.file.storageRef || props.file.storage_ref)
  return rows
})
const showMetadata = computed(() => Boolean(props.file.detailChecked && metadataRows.value.length))

function addMetadataRow(rows, label, value) {
  if (value === null || value === undefined || value === '') return
  rows.push({ label, value: String(value) })
}

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatFileSize(size) {
  const bytes = Number(size)
  if (!Number.isFinite(bytes) || bytes <= 0) return ''
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`
}
</script>

<template>
  <article class="file-row">
    <span class="file-type">{{ file.name?.split('.').pop()?.slice(0, 3) || 'doc' }}</span>
    <div>
      <h3>{{ file.name || file.filename || '생성 파일' }}</h3>
      <p>{{ file.detail || file.status || '다운로드 가능' }}</p>
    </div>
    <div class="file-actions">
      <button
        type="button"
        data-testid="file-info-button"
        :disabled="!fileActionId"
        @click="emit('inspect', fileActionId)"
      >
        상세
      </button>
      <button
        type="button"
        data-testid="file-download-button"
        :disabled="!fileActionId"
        @click="emit('prepare-download', fileActionId)"
      >
        다운로드 준비
      </button>
      <a v-if="downloadUrl" :href="downloadUrl">열기</a>
      <a v-else-if="openUrl" :href="openUrl" target="_blank" rel="noreferrer">열기</a>
      <button
        v-if="canDelete"
        type="button"
        data-testid="file-rename-button"
        :disabled="!fileActionId"
        @click="emit('rename', fileActionId)"
      >
        이름 변경
      </button>
      <button
        v-if="canDelete"
        type="button"
        class="danger"
        data-testid="file-delete-button"
        :disabled="!fileActionId"
        @click="emit('delete', fileActionId)"
      >
        삭제
      </button>
    </div>
    <dl v-if="showMetadata" class="file-metadata" data-testid="file-metadata">
      <div v-for="row in metadataRows" :key="row.label">
        <dt>{{ row.label }}</dt>
        <dd>{{ row.value }}</dd>
      </div>
    </dl>
  </article>
</template>

<style scoped>
.file-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  align-items: start;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-panel);
  background: var(--m001-surface);
}

.file-type {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--m001-radius-panel);
  background: var(--m001-ai-soft);
  color: var(--m001-ai);
  text-transform: uppercase;
  font-size: 11px;
  font-weight: 900;
}

h3,
p {
  margin: 0;
}

h3 {
  overflow: hidden;
  color: var(--m001-text);
  font-size: 13px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

p {
  color: var(--m001-muted);
  font-size: 12px;
  line-height: 18px;
}

.file-actions {
  grid-column: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.file-metadata {
  grid-column: 2;
  display: grid;
  gap: 6px;
  margin: 2px 0 0;
  padding: 10px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-control);
  background: var(--m001-panel-subtle);
}

.file-metadata div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
}

.file-metadata dt,
.file-metadata dd {
  margin: 0;
  min-width: 0;
  font-size: 11px;
  line-height: 16px;
}

.file-metadata dt {
  color: var(--m001-muted);
  font-weight: 900;
}

.file-metadata dd {
  overflow-wrap: anywhere;
  color: var(--m001-text);
  font-weight: 700;
}

a,
button {
  min-width: 74px;
  padding: 8px 10px;
  border: 1px solid var(--m001-border-strong);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 800;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
}

button:disabled {
  color: var(--m001-muted);
  cursor: not-allowed;
}

button.danger {
  border-color: var(--m001-danger);
  color: var(--m001-danger);
}
</style>
