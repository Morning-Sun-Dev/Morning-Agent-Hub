<script setup>
import { computed } from 'vue'
import { safeUrl } from '../../models/chatModels'

const props = defineProps({
  file: { type: Object, required: true },
})

const emit = defineEmits(['inspect', 'prepare-download', 'delete'])

const downloadUrl = computed(() => safeUrl(props.file.downloadUrl || props.file.download_url))
const openUrl = computed(() => safeUrl(props.file.openUrl || props.file.open_url))
const fileActionId = computed(() => props.file.fileId || props.file.file_id || props.file.storageRef || props.file.id)
const canDelete = computed(() => ['drive', 'uploaded'].includes(props.file.kind))
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
        class="danger"
        data-testid="file-delete-button"
        :disabled="!fileActionId"
        @click="emit('delete', fileActionId)"
      >
        삭제
      </button>
    </div>
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
