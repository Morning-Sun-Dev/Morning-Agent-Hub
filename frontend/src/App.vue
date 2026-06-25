<template>
  <div class="app">
    <!-- 사이드바 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="logo">🤖 Morning Agent</span>
        <button class="new-chat-btn" @click="newChat">+ 새 채팅</button>
      </div>

      <div class="session-list">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="loadSession(session.id)"
        >
          <span class="session-title">{{ session.title || '새 대화' }}</span>
          <span class="session-date">{{ formatDate(session.created_at) }}</span>
          <button class="delete-btn" @click.stop="deleteSession(session.id)">✕</button>
        </div>
        <div v-if="sessions.length === 0" class="no-sessions">채팅 기록이 없습니다</div>
      </div>
    </aside>

    <!-- 채팅 영역 -->
    <main class="main">
      <ChatView
        :session-id="currentSessionId"
        :initial-messages="currentMessages"
        @session-created="onSessionCreated"
      />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ChatView from './components/ChatView.vue'
import { getSessions, getMessages, deleteSession as apiDeleteSession } from './api'

const sessions = ref([])
const currentSessionId = ref(null)
const currentMessages = ref([])

async function fetchSessions() {
  try {
    sessions.value = await getSessions()
  } catch {}
}

async function loadSession(id) {
  currentSessionId.value = id
  try {
    currentMessages.value = await getMessages(id)
  } catch {
    currentMessages.value = []
  }
}

function newChat() {
  currentSessionId.value = null
  currentMessages.value = []
}

async function deleteSession(id) {
  try {
    await apiDeleteSession(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSessionId.value === id) newChat()
  } catch {}
}

function onSessionCreated(id) {
  currentSessionId.value = id
  fetchSessions()
}

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

onMounted(fetchSessions)
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f9fafb;
  color: #111827;
}

.app {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ── 사이드바 ── */
.sidebar {
  width: 240px;
  min-width: 240px;
  background: #1e1e2e;
  display: flex;
  flex-direction: column;
  color: #e2e8f0;
}

.sidebar-header {
  padding: 16px 12px;
  border-bottom: 1px solid #2d2d3f;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.logo {
  font-size: 14px;
  font-weight: 600;
  color: #a5b4fc;
}

.new-chat-btn {
  background: #6366f1;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: background 0.2s;
}

.new-chat-btn:hover { background: #4f46e5; }

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  position: relative;
  margin-bottom: 2px;
  transition: background 0.15s;
}

.session-item:hover { background: #2d2d3f; }
.session-item.active { background: #2d2d3f; }

.session-title {
  display: block;
  font-size: 13px;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 20px;
}

.session-date {
  display: block;
  font-size: 11px;
  color: #6b7280;
  margin-top: 2px;
}

.delete-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.session-item:hover .delete-btn { opacity: 1; }
.delete-btn:hover { color: #f87171; }

.no-sessions {
  text-align: center;
  color: #4b5563;
  font-size: 12px;
  margin-top: 24px;
}

/* ── 메인 ── */
.main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: white;
}
</style>
