<script setup>
import AttachmentChip from './AttachmentChip.vue'

defineProps({
  message: { type: Object, required: true },
})
</script>

<template>
  <article class="message" :class="message.role" :data-status="message.status">
    <div class="bubble">
      <div class="message-meta">
        <strong>{{ message.role === 'user' ? '나' : 'Morning Agent' }}</strong>
        <span v-if="message.status === 'running'">작성 중</span>
        <span v-else-if="message.status === 'failed'">실패</span>
      </div>
      <p class="message-content">{{ message.content }}</p>
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
