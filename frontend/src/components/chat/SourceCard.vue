<script setup>
import { computed } from 'vue'
import { safeUrl } from '../../models/chatModels'

const props = defineProps({
  source: { type: Object, required: true },
})

const sourceUrl = computed(() => safeUrl(props.source.url))

function host(url) {
  const checkedUrl = safeUrl(url)
  if (!checkedUrl) return '출처'

  try {
    return new URL(checkedUrl, globalThis.location?.origin || 'http://localhost').host
  } catch {
    return '출처'
  }
}
</script>

<template>
  <article class="source-card">
    <div>
      <h3>{{ source.title || '출처' }}</h3>
      <p>{{ host(source.url) }}<span v-if="source.date"> · {{ source.date }}</span></p>
    </div>
    <span v-if="source.relevance" class="relevance">{{ source.relevance }}</span>
    <p v-if="source.snippet" class="snippet">{{ source.snippet }}</p>
    <a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noreferrer">열기</a>
  </article>
</template>

<style scoped>
.source-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 12px;
  padding: 14px 16px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-panel);
  background: var(--m001-surface);
}

h3,
p {
  margin: 0;
}

h3 {
  font-size: 13px;
  line-height: 18px;
  color: var(--m001-text);
}

p {
  color: var(--m001-muted);
  font-size: 12px;
  line-height: 18px;
}

.relevance {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--m001-success-soft);
  color: var(--m001-success);
  font-size: 12px;
  font-weight: 800;
}

.snippet {
  grid-column: 1 / -1;
}

a {
  color: var(--m001-primary);
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}
</style>
