<script setup>
import { computed } from 'vue'
import AttachmentChip from './AttachmentChip.vue'
import { renderMarkdown } from '../../models/markdownRenderer'

const props = defineProps({
  message: { type: Object, required: true },
})

const isAssistant = computed(() => props.message.role !== 'user')
const renderedContent = computed(() => renderMarkdown(props.message.content || ''))
</script>

<template>
  <article class="message" :class="message.role" :data-status="message.status">
    <div class="bubble">
      <div class="message-meta">
        <strong>{{ message.role === 'user' ? '나' : 'Morning Agent' }}</strong>
        <span v-if="message.status === 'running'">작성 중</span>
        <span v-else-if="message.status === 'failed'">실패</span>
      </div>
      <div
        v-if="isAssistant"
        class="message-content message-markdown"
        data-testid="message-markdown"
        v-html="renderedContent"
      />
      <p v-else class="message-content">{{ message.content }}</p>
      <div v-if="message.sources?.length || message.files?.length" class="message-chips">
        <span v-if="message.sources?.length" class="info-chip">출처 {{ message.sources.length }}개</span>
        <span v-if="message.files?.length" class="info-chip purple">파일 {{ message.files.length }}개</span>
      </div>
      <div v-if="message.files?.length" class="message-files">
        <AttachmentChip v-for="file in message.files" :key="file.id || file.name" :attachment="file" />
      </div>
    </div>
  </article>
</template>

<style scoped>
.message {
  display: flex;
}

.message.user {
  justify-content: flex-end;
}

.bubble {
  width: min(700px, 78%);
  padding: 14px 16px;
  border-radius: var(--m001-radius-panel);
  border: 1px solid var(--m001-border);
  background: var(--m001-surface);
}

.message.user .bubble {
  border: 0;
  background: var(--m001-primary-soft);
}

.message[data-status="failed"] .bubble {
  border-color: var(--m001-danger);
  background: var(--m001-danger-soft);
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--m001-ai);
  font-size: 12px;
}

.message.user .message-meta {
  color: var(--m001-primary);
}

.message-content {
  margin: 0;
  white-space: pre-wrap;
  color: var(--m001-text);
  font-size: 14px;
  line-height: 23px;
}

.message-markdown {
  white-space: normal;
}

.message-markdown :deep(*) {
  margin-top: 0;
}

.message-markdown :deep(*:last-child) {
  margin-bottom: 0;
}

.message-markdown :deep(p),
.message-markdown :deep(ul),
.message-markdown :deep(ol),
.message-markdown :deep(blockquote),
.message-markdown :deep(pre),
.message-markdown :deep(table) {
  margin-bottom: 12px;
}

.message-markdown :deep(h1),
.message-markdown :deep(h2),
.message-markdown :deep(h3) {
  margin-bottom: 10px;
  color: var(--m001-text);
  font-weight: 900;
  line-height: 1.25;
}

.message-markdown :deep(h1) {
  font-size: 18px;
}

.message-markdown :deep(h2) {
  font-size: 16px;
}

.message-markdown :deep(h3) {
  font-size: 15px;
}

.message-markdown :deep(a) {
  color: var(--m001-primary);
  font-weight: 800;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.message-markdown :deep(ul),
.message-markdown :deep(ol) {
  padding-left: 22px;
}

.message-markdown :deep(li + li) {
  margin-top: 4px;
}

.message-markdown :deep(blockquote) {
  padding-left: 12px;
  border-left: 3px solid var(--m001-border-strong);
  color: var(--m001-muted);
}

.message-markdown :deep(code) {
  padding: 2px 5px;
  border-radius: 5px;
  background: var(--m001-surface-alt);
  font-size: 13px;
}

.message-markdown :deep(pre) {
  overflow-x: auto;
  padding: 12px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-card);
  background: var(--m001-surface-alt);
}

.message-markdown :deep(pre code) {
  padding: 0;
  background: transparent;
}

.message-markdown :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
}

.message-markdown :deep(th),
.message-markdown :deep(td) {
  padding: 8px 10px;
  border: 1px solid var(--m001-border);
  text-align: left;
  vertical-align: top;
}

.message-markdown :deep(th) {
  background: var(--m001-surface-alt);
  font-weight: 900;
}

.message-chips,
.message-files {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.info-chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 14px;
  border-radius: 999px;
  background: var(--m001-primary-soft);
  color: var(--m001-primary);
  font-size: 12px;
  font-weight: 800;
}

.info-chip.purple {
  background: var(--m001-purple-soft);
  color: var(--m001-purple);
}

@media (max-width: 720px) {
  .bubble {
    width: 100%;
  }
}
</style>
