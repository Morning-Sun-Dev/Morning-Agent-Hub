<script setup>
import { computed } from 'vue'
import { safeUrl } from '../../models/chatModels'

const props = defineProps({
  file: { type: Object, required: true },
})

const downloadUrl = computed(() => safeUrl(props.file.downloadUrl || props.file.download_url))
const openUrl = computed(() => safeUrl(props.file.openUrl || props.file.open_url))
</script>

<template>
  <article class="file-row">
    <span class="file-type">{{ file.name?.split('.').pop()?.slice(0, 3) || 'doc' }}</span>
    <div>
      <h3>{{ file.name || file.filename || '생성 파일' }}</h3>
      <p>{{ file.detail || file.status || '다운로드 가능' }}</p>
    </div>
    <a v-if="downloadUrl" :href="downloadUrl">다운로드</a>
    <a v-else-if="openUrl" :href="openUrl" target="_blank" rel="noreferrer">열기</a>
  </article>
</template>

<style scoped>
.file-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  align-items: center;
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

a {
  min-width: 74px;
  padding: 8px 10px;
  border: 1px solid var(--m001-border-strong);
  border-radius: var(--m001-radius-control);
  color: var(--m001-text);
  font-size: 12px;
  font-weight: 800;
  text-align: center;
  text-decoration: none;
}
</style>
