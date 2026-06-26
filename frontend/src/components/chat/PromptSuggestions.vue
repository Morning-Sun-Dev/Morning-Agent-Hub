<script setup>
const emit = defineEmits(['select'])

const suggestions = [
  {
    title: '문서 요약',
    body: '업로드한 문서를 핵심 쟁점과 액션으로 정리',
    prompt: '첨부한 문서를 핵심 내용과 해야 할 일 중심으로 요약해줘.',
  },
  {
    title: '최신 웹 확인',
    body: '최근 변경된 정책, 뉴스, 제품 정보를 출처와 함께 확인',
    prompt: '이 주제의 최신 정보를 출처와 함께 확인해줘.',
  },
  {
    title: '보고서 초안',
    body: '출처 인용과 다운로드 가능한 문서 초안 생성',
    prompt: '조사 결과를 보고서 초안 형태로 작성해줘.',
  },
  {
    title: '파일 비교',
    body: '여러 파일 차이점과 누락된 항목을 표로 정리',
    prompt: '첨부 파일들의 차이점과 누락된 항목을 표로 정리해줘.',
  },
]
</script>

<template>
  <section class="prompt-suggestions" aria-label="추천 요청">
    <button
      v-for="item in suggestions"
      :key="item.title"
      type="button"
      class="prompt-card"
      @click="emit('select', item.prompt)"
    >
      <span class="prompt-icon">{{ item.title.slice(0, 1) }}</span>
      <strong>{{ item.title }}</strong>
      <span>{{ item.body }}</span>
    </button>
  </section>
</template>

<style scoped>
.prompt-suggestions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 196px));
  justify-content: center;
  gap: 24px 36px;
}

.prompt-card {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  grid-template-rows: auto auto;
  gap: 8px 12px;
  min-height: 104px;
  padding: 14px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-panel);
  background: var(--m001-surface);
  color: var(--m001-text);
  text-align: left;
  cursor: pointer;
}

.prompt-card:hover {
  border-color: var(--m001-primary);
  box-shadow: var(--m001-shadow-panel);
}

.prompt-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--m001-radius-panel);
  background: var(--m001-primary-soft);
  color: var(--m001-primary);
  font-size: 12px;
  font-weight: 800;
}

strong {
  align-self: center;
  font-size: 13px;
  line-height: 18px;
}

.prompt-card > span:last-child {
  grid-column: 1 / -1;
  font-size: 12px;
  line-height: 18px;
  color: var(--m001-muted);
}

@media (max-width: 560px) {
  .prompt-suggestions {
    grid-template-columns: minmax(0, 196px);
    gap: 16px;
  }

  .prompt-card:nth-of-type(n + 3) {
    display: none;
  }
}
</style>
