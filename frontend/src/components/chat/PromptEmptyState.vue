<script setup>
import PromptSuggestions from './PromptSuggestions.vue'

defineEmits(['select-prompt'])
</script>

<template>
  <div class="empty-state">
    <div>
      <h2>무엇을 맡길까요?</h2>
      <p>파일을 올리거나 최신 웹 검색을 켜고, 필요한 산출물 형식을 함께 적어주세요.</p>
    </div>
    <PromptSuggestions @select="$emit('select-prompt', $event)" />
  </div>
</template>

<style scoped>
.empty-state {
  display: grid;
  align-content: center;
  gap: 42px;
  min-height: 500px;
  padding: 36px;
  text-align: center;
}

h2 {
  margin: 0 0 12px;
  color: var(--m001-text);
  font-size: 28px;
  line-height: 38px;
  font-weight: 900;
}

p {
  margin: 0;
  color: var(--m001-muted);
  font-size: 14px;
  line-height: 22px;
}

@media (max-width: 720px) {
  .empty-state {
    min-height: auto;
    padding: 26px 18px 22px;
    gap: 26px;
  }

  h2 {
    font-size: 26px;
    line-height: 40px;
  }
}
</style>
