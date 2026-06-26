<script setup>
import { computed, ref } from 'vue'
import AttachmentChip from './AttachmentChip.vue'

const props = defineProps({
  modelValue: { type: String, required: true },
  attachments: { type: Array, default: () => [] },
  sending: { type: Boolean, default: false },
  error: { type: String, default: null },
})

const emit = defineEmits(['update:modelValue', 'submit', 'pick-file', 'remove-attachment', 'retry'])

const fileInput = ref(null)
const canSend = computed(() => {
  const hasDraft = props.modelValue.trim().length > 0
  return (hasDraft || props.attachments.length > 0) && !props.sending
})

function onFileChange(event) {
  const file = event.target.files?.[0]
  if (file) emit('pick-file', file)
  event.target.value = ''
}

function onEnter(event) {
  if (!event.shiftKey) {
    event.preventDefault()
    if (canSend.value) emit('submit')
  }
}
</script>

<template>
  <form class="composer" :class="{ 'has-error': error }" @submit.prevent="canSend && emit('submit')">
    <div v-if="attachments.length" class="attachment-row" aria-label="첨부 파일">
      <AttachmentChip
        v-for="attachment in attachments"
        :key="attachment.id"
        :attachment="attachment"
        removable
        @remove="emit('remove-attachment', attachment.id)"
      />
      <span class="search-chip">웹 검색 켜짐</span>
    </div>

    <textarea
      :value="modelValue"
      rows="3"
      placeholder="요청을 입력하세요. 파일은 첨부 버튼으로 올릴 수 있습니다."
      :disabled="sending"
      @input="emit('update:modelValue', $event.target.value)"
      @keydown.enter="onEnter"
    />

    <div class="composer-footer">
      <div class="composer-actions">
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,.txt,.md"
          class="sr-only"
          tabindex="-1"
          aria-hidden="true"
          @change="onFileChange"
        >
        <button type="button" class="tool-button" aria-label="파일 첨부" @click="fileInput?.click()">첨부</button>
        <span class="tool-chip">웹 검색</span>
        <span class="tool-chip">출처 포함</span>
      </div>
      <button
        data-testid="send-button"
        class="send-button"
        type="button"
        :disabled="!canSend"
        @click="canSend && emit('submit')"
      >
        {{ sending ? '처리 중' : '전송' }}
      </button>
    </div>

    <div v-if="error" class="composer-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="emit('retry')">재시도</button>
    </div>
  </form>
</template>

<style scoped>
.composer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-panel);
  background: var(--m001-panel-subtle);
}

.composer.has-error {
  border-color: var(--m001-danger);
  background: var(--m001-danger-soft);
}

.attachment-row,
.composer-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

textarea {
  width: 100%;
  min-height: 54px;
  max-height: 140px;
  resize: vertical;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--m001-text);
  font-size: 14px;
  line-height: 22px;
}

textarea::placeholder {
  color: var(--m001-muted);
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.tool-button,
.tool-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 26px;
  padding: 0 12px;
  border: 1px solid var(--m001-border);
  border-radius: 999px;
  background: var(--m001-surface);
  color: var(--m001-muted);
  font-size: 11px;
  font-weight: 700;
}

.tool-button {
  cursor: pointer;
}

.search-chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--m001-ai-soft);
  color: var(--m001-ai);
  font-size: 12px;
  font-weight: 800;
}

.send-button {
  min-width: 64px;
  height: 36px;
  border-radius: var(--m001-radius-control);
  background: var(--m001-primary);
  color: white;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}

.send-button:disabled {
  background: var(--m001-border);
  color: var(--m001-muted);
  cursor: not-allowed;
}

.composer-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--m001-danger);
  font-size: 12px;
  font-weight: 700;
}

.composer-error button {
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--m001-danger);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-danger);
  cursor: pointer;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

@media (max-width: 560px) {
  .composer-footer {
    align-items: flex-end;
  }

  .composer-actions {
    gap: 6px;
  }
}
</style>
