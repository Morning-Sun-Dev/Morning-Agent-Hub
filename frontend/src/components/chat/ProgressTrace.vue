<script setup>
defineProps({
  progress: { type: Array, default: () => [] },
})

const marks = {
  pending: '-',
  working: '...',
  completed: '완',
  warning: '!',
  failed: '!',
  skipped: '-',
}
</script>

<template>
  <ol class="progress-trace" aria-label="진행 상태">
    <li v-for="item in progress" :key="`${item.stage}-${item.message}`" :data-state="item.state">
      <span class="mark">{{ marks[item.state] || '...' }}</span>
      <div>
        <strong>{{ item.stage }}</strong>
        <p>{{ item.message }}</p>
      </div>
    </li>
  </ol>
</template>

<style scoped>
.progress-trace {
  display: grid;
  gap: 18px;
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--m001-radius-panel);
  background: var(--m001-panel);
  color: var(--m001-muted);
  font-size: 11px;
  font-weight: 900;
}

li[data-state="completed"] .mark {
  background: var(--m001-success-soft);
  color: var(--m001-success);
}

li[data-state="working"] .mark {
  background: var(--m001-warning-soft);
  color: var(--m001-warning);
}

li[data-state="failed"] .mark {
  background: var(--m001-danger-soft);
  color: var(--m001-danger);
}

li[data-state="warning"] .mark,
li[data-state="skipped"] .mark {
  background: var(--m001-panel);
  color: var(--m001-muted);
}

strong {
  display: block;
  color: var(--m001-text);
  font-size: 13px;
  line-height: 18px;
}

p {
  margin: 3px 0 0;
  color: var(--m001-muted);
  font-size: 12px;
  line-height: 18px;
}
</style>
