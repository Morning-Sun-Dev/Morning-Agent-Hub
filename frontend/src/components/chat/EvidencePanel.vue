<script setup>
import { computed, ref } from 'vue'
import GeneratedFileRow from './GeneratedFileRow.vue'
import ProgressTrace from './ProgressTrace.vue'
import SourceCard from './SourceCard.vue'

const props = defineProps({
  sources: { type: Array, default: () => [] },
  files: { type: Array, default: () => [] },
  progress: { type: Array, default: () => [] },
  activeTab: { type: String, default: 'sources' },
  mobileCollapsed: { type: Boolean, default: false },
})

const emit = defineEmits(['update:activeTab'])
const expanded = ref(false)
const showMobileSummary = computed(() => props.mobileCollapsed && !expanded.value)
const itemCount = computed(() => props.sources.length + props.files.length + props.progress.length)

const tabs = [
  { id: 'sources', label: '출처' },
  { id: 'files', label: '파일' },
  { id: 'progress', label: '진행' },
]
</script>

<template>
  <aside class="evidence-panel" :class="{ collapsed: mobileCollapsed }" aria-label="작업 근거">
    <template v-if="showMobileSummary">
      <button type="button" class="mobile-summary" aria-expanded="false" @click="expanded = true">
        <span>근거 패널 펼치기</span>
        <strong>{{ itemCount }}</strong>
      </button>
    </template>

    <template v-else>
      <header>
        <div>
          <h2>작업 근거</h2>
          <p>출처, 파일, 진행 상태를 탭별로 분리합니다.</p>
        </div>
        <button
          v-if="mobileCollapsed"
          type="button"
          class="collapse-button"
          aria-label="근거 패널 접기"
          @click="expanded = false"
        >
          접기
        </button>
      </header>
      <nav class="panel-tabs" aria-label="근거 패널 탭">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          :class="{ active: activeTab === tab.id }"
          @click="emit('update:activeTab', tab.id)"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div class="panel-body">
        <div v-if="activeTab === 'sources'" class="panel-stack">
          <div v-if="sources.length === 0" class="empty-panel">
            <span>i</span>
            <strong>아직 표시할 근거가 없습니다</strong>
            <p>답변이 생성되면 인용 출처, 참조한 파일, 실행 단계가 이 영역에 표시됩니다.</p>
          </div>
          <SourceCard v-for="source in sources" v-else :key="source.url || source.title" :source="source" />
        </div>

        <div v-if="activeTab === 'files'" class="panel-stack">
          <div v-if="files.length === 0" class="empty-panel">
            <span>f</span>
            <strong>아직 표시할 파일이 없습니다</strong>
            <p>생성 파일이나 첨부 파일 링크가 준비되면 여기에 표시됩니다.</p>
          </div>
          <GeneratedFileRow v-for="file in files" v-else :key="file.id || file.name" :file="file" />
        </div>

        <div v-if="activeTab === 'progress'" class="panel-stack">
          <div v-if="progress.length === 0" class="empty-panel">
            <span>p</span>
            <strong>진행 중인 작업이 없습니다</strong>
            <p>요청을 보내면 업로드, 분석, 응답 단계가 표시됩니다.</p>
          </div>
          <ProgressTrace v-else :progress="progress" />
        </div>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.evidence-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-panel);
  background: var(--m001-surface);
  box-shadow: var(--m001-shadow-panel);
  overflow: hidden;
}

header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
  padding: 20px;
  border-bottom: 1px solid var(--m001-border);
}

h2,
p {
  margin: 0;
}

h2 {
  color: var(--m001-text);
  font-size: 16px;
  line-height: 24px;
}

p {
  margin-top: 4px;
  color: var(--m001-muted);
  font-size: 12px;
  line-height: 18px;
}

.panel-tabs {
  display: flex;
  gap: 8px;
  padding: 16px 20px 6px;
}

.panel-tabs button {
  width: 72px;
  height: 32px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-muted);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.panel-tabs button.active {
  border-color: var(--m001-primary-soft);
  background: var(--m001-primary-soft);
  color: var(--m001-primary);
}

.panel-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 20px 20px;
}

.panel-stack {
  display: grid;
  gap: 16px;
  padding-top: 10px;
}

.empty-panel {
  display: grid;
  justify-items: center;
  align-content: center;
  min-height: 460px;
  text-align: center;
}

.empty-panel span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--m001-radius-panel);
  background: var(--m001-panel);
  color: var(--m001-muted);
  font-size: 13px;
  font-weight: 900;
}

.empty-panel strong {
  margin-top: 18px;
  color: var(--m001-text);
  font-size: 16px;
}

.empty-panel p {
  max-width: 300px;
}

.mobile-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 54px;
  padding: 0 16px;
  border: 0;
  background: white;
  color: var(--m001-text);
  cursor: pointer;
}

.mobile-summary span {
  font-size: 13px;
  font-weight: 700;
}

.mobile-summary strong {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 999px;
  background: var(--m001-panel);
  color: var(--m001-muted);
  font-size: 12px;
}

.collapse-button {
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--m001-border);
  border-radius: var(--m001-radius-control);
  background: white;
  color: var(--m001-muted);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

@media (max-width: 1024px) {
  .panel-body {
    max-height: 280px;
  }

  .empty-panel {
    min-height: 160px;
  }
}
</style>
