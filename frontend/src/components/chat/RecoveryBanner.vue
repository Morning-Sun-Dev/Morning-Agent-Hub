<script setup>
defineProps({
  message: { type: String, required: true },
})

defineEmits(['retry', 'continue-with-files'])
</script>

<template>
  <section class="recovery" role="alert">
    <div>
      <h2>작업을 이어갈 수 있습니다</h2>
      <p>{{ message }}</p>
    </div>
    <div class="recovery-actions">
      <button type="button" class="primary" @click="$emit('retry')">실패 단계 재시도</button>
      <button type="button" @click="$emit('continue-with-files')">파일만 사용</button>
    </div>
  </section>
</template>

<style scoped>
.recovery {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 0 24px 12px;
  padding: 16px;
  border: 1px solid var(--m001-danger);
  border-radius: var(--m001-radius-panel);
  background: var(--m001-danger-soft);
}

h2,
p {
  margin: 0;
}

h2 {
  color: var(--m001-danger);
  font-size: 15px;
  line-height: 22px;
}

p {
  margin-top: 4px;
  color: var(--m001-text);
  font-size: 13px;
  line-height: 20px;
}

.recovery-actions {
  display: flex;
  gap: 8px;
}

button {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--m001-border-strong);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-text);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
}

button.primary {
  border-color: var(--m001-primary);
  background: var(--m001-primary);
  color: white;
}

@media (max-width: 720px) {
  .recovery {
    align-items: stretch;
    flex-direction: column;
    margin: 0 16px 12px;
  }
}
</style>
