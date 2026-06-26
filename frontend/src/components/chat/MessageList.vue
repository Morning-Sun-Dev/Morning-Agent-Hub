<script setup>
import ChatMessage from './ChatMessage.vue'
import PromptEmptyState from './PromptEmptyState.vue'

defineProps({
  messages: { type: Array, default: () => [] },
  runningMessage: { type: Object, default: null },
})

defineEmits(['select-prompt'])
</script>

<template>
  <section class="message-list" aria-label="대화 메시지">
    <PromptEmptyState
      v-if="messages.length === 0 && !runningMessage"
      @select-prompt="$emit('select-prompt', $event)"
    />
    <template v-else>
      <ChatMessage v-for="message in messages" :key="message.id" :message="message" />
      <ChatMessage v-if="runningMessage" :message="runningMessage" />
    </template>
  </section>
</template>

<style scoped>
.message-list {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 28px;
  overflow-y: auto;
  padding: 40px 72px 32px;
}

@media (max-width: 900px) {
  .message-list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 0 18px 18px;
  }
}
</style>
