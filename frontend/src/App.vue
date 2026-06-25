<template>
  <div class="app">
    <header>
      <h1>🤖 Morning Agent Hub</h1>
    </header>
    <main>
      <ChatView />
    </main>
  </div>
</template>

<script setup>
import ChatView from './components/ChatView.vue'
</script>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f9fafb;
  color: #111827;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

header {
  padding: 14px 24px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
}

header h1 {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
  background: white;
  box-shadow: 0 0 0 1px #e5e7eb;
}
</style>
