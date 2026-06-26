<script setup>
defineProps({
  attachment: { type: Object, required: true },
  removable: { type: Boolean, default: false },
})

defineEmits(['remove'])
</script>

<template>
  <span class="attachment-chip" :data-status="attachment.status">
    <span class="file-mark">{{ attachment.name.split('.').pop()?.slice(0, 3) || 'file' }}</span>
    <span class="file-name">{{ attachment.name }}</span>
    <button v-if="removable" type="button" aria-label="첨부 파일 제거" @click="$emit('remove')">×</button>
  </span>
</template>

<style scoped>
.attachment-chip {
  display: inline-flex;
  align-items: center;
  max-width: 240px;
  height: 30px;
  gap: 8px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--m001-primary-soft);
  color: var(--m001-primary);
  font-size: 12px;
  font-weight: 700;
}

.attachment-chip[data-status="error"] {
  background: var(--m001-danger-soft);
  color: var(--m001-danger);
}

.file-mark {
  text-transform: uppercase;
  font-size: 11px;
}

.file-name {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

button {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: transparent;
  color: currentColor;
  cursor: pointer;
  font-size: 16px;
  line-height: 20px;
}
</style>
