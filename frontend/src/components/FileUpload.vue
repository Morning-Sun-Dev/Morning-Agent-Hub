<template>
  <div class="file-upload">
    <label class="upload-area" :class="{ dragging }" @dragover.prevent="dragging = true"
      @dragleave="dragging = false" @drop.prevent="onDrop">
      <input type="file" accept=".pdf,.txt,.md" @change="onSelect" hidden ref="inputRef" />
      <span v-if="!uploading" @click="inputRef.click()">
        📄 PDF, TXT, MD 파일을 드래그하거나 클릭해서 업로드
      </span>
      <span v-else>업로드 중...</span>
    </label>

    <div v-if="result" class="result" :class="result.index_status">
      <span v-if="result.index_status === 'success'">✅ {{ result.filename }} 인덱싱 완료</span>
      <span v-else-if="result.index_status === 'skipped'">⚠️ {{ result.filename }} 이미 인덱싱된 파일</span>
      <span v-else>❌ {{ result.index_message }}</span>
    </div>

    <div v-if="error" class="result error-msg">❌ {{ error }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadFile } from '../api'

const inputRef = ref(null)
const dragging = ref(false)
const uploading = ref(false)
const result = ref(null)
const error = ref(null)

const emit = defineEmits(['uploaded'])

async function handleFile(file) {
  if (!file) return
  uploading.value = true
  result.value = null
  error.value = null
  try {
    const data = await uploadFile(file)
    result.value = data
    emit('uploaded', data)
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}

function onSelect(e) {
  handleFile(e.target.files[0])
}

function onDrop(e) {
  dragging.value = false
  handleFile(e.dataTransfer.files[0])
}
</script>

<style scoped>
.file-upload {
  margin-bottom: 12px;
}

.upload-area {
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  font-size: 13px;
  color: #6b7280;
  transition: border-color 0.2s;
}

.upload-area:hover,
.upload-area.dragging {
  border-color: #6366f1;
  color: #6366f1;
}

.result {
  margin-top: 8px;
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 6px;
}

.result.success { background: #f0fdf4; color: #16a34a; }
.result.skipped { background: #fffbeb; color: #d97706; }
.result.error,
.error-msg     { background: #fef2f2; color: #dc2626; }
</style>
