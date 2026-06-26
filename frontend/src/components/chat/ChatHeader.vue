<script setup>
defineProps({
  state: { type: String, default: 'idle' },
})

defineEmits(['new-chat'])

const labels = {
  idle: '작업 준비됨',
  running: '실행 중',
  uploading: '업로드 중',
  'partial-failure': '확인 필요',
}
</script>

<template>
  <header class="chat-header">
    <div class="brand">Morning Agent Hub</div>
    <div class="title-group">
      <h1>새 요청 시작</h1>
      <p>텍스트 요청, 파일 첨부, 출처 확인, 산출물 액션을 한 화면에서 처리합니다.</p>
    </div>
    <div class="actions">
      <span class="state-badge" :data-state="state">{{ labels[state] || state }}</span>
      <button type="button" class="secondary-button" @click="$emit('new-chat')">새 대화</button>
    </div>
  </header>
</template>

<style scoped>
.chat-header {
  display: grid;
  grid-template-columns: 184px minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  height: 56px;
  padding: 0 24px;
  background: var(--m001-surface);
  border-bottom: 1px solid var(--m001-border);
}

.brand {
  font-size: 14px;
  font-weight: 800;
  color: var(--m001-text);
}

.title-group {
  min-width: 0;
}

h1 {
  margin: 0;
  font-size: 16px;
  line-height: 21px;
  font-weight: 800;
  color: var(--m001-text);
}

p {
  margin: 0;
  font-size: 11px;
  line-height: 15px;
  color: var(--m001-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.state-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 104px;
  height: 24px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--m001-success-soft);
  color: var(--m001-success);
  font-size: 12px;
  font-weight: 700;
}

.state-badge[data-state="running"],
.state-badge[data-state="uploading"] {
  background: var(--m001-warning-soft);
  color: var(--m001-warning);
}

.state-badge[data-state="partial-failure"] {
  background: var(--m001-danger-soft);
  color: var(--m001-danger);
}

.secondary-button {
  height: 36px;
  padding: 0 14px;
  border: 1px solid var(--m001-border-strong);
  border-radius: var(--m001-radius-control);
  background: var(--m001-surface);
  color: var(--m001-text);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

@media (max-width: 720px) {
  .chat-header {
    grid-template-columns: minmax(0, 1fr) auto;
    padding: 0 16px;
  }

  .title-group {
    display: none;
  }

  .state-badge {
    min-width: 88px;
  }
}
</style>
