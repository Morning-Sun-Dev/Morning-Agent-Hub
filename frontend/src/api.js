import {
  createAttachment,
  createMessage,
  normalizeCapability,
  normalizeChatPayload,
  normalizeFileArtifact,
  normalizeProgress,
  normalizeReportTemplate,
  normalizeSessionMessage,
  safeUrl,
  serializeAttachment,
} from './models/chatModels'

const BASE = '/api'

async function parseJson(res) {
  const payload = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(payload.detail || payload.message || `요청 실패: ${res.status}`)
  }
  return payload
}

export async function sendChat(message, sessionId = null, options = {}) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      attachments: (options.attachments || []).map(serializeAttachment),
      requested_capabilities: options.requestedCapabilities || [],
    }),
  })
  const payload = normalizeChatPayload(await parseJson(res))
  return {
    sessionId: payload.sessionId,
    message: createMessage({
      role: 'assistant',
      content: payload.content,
      sources: payload.sources,
      files: payload.files,
      progress: payload.progress,
      error: payload.error,
    }),
  }
}

export function streamChat(message, sessionId, handlers = {}, options = {}) {
  const params = new URLSearchParams({ message })
  if (sessionId) params.append('session_id', sessionId)
  if (options.attachments?.length) {
    params.append('attachments', JSON.stringify(options.attachments.map(serializeAttachment)))
  }
  if (options.requestedCapabilities?.length) {
    params.append('requested_capabilities', JSON.stringify(options.requestedCapabilities))
  }

  const es = new EventSource(`${BASE}/chat/stream?${params}`)

  es.onmessage = (e) => {
    if (e.data === '[DONE]') {
      es.close()
      handlers.onDone?.()
      return
    }
    try {
      const payload = JSON.parse(e.data)
      if (payload.type === 'status') {
        handlers.onProgress?.(
          normalizeProgress({
            stage: payload.stage || 'orchestrator',
            message: payload.message || '작업 중',
            state: payload.state || 'working',
          }),
        )
      }
      if (payload.type === 'answer') {
        handlers.onAnswer?.(normalizeChatPayload(payload))
      }
      if (payload.type === 'error') {
        es.close()
        handlers.onError?.(payload.content || '연결이 끊겼습니다')
      }
    } catch {
      handlers.onError?.('응답을 해석하지 못했습니다')
    }
  }

  es.onerror = () => {
    es.close()
    handlers.onError?.('연결이 끊겼습니다')
  }

  return () => es.close()
}

export async function getSessions() {
  const res = await fetch(`${BASE}/sessions`)
  return parseJson(res)
}

export async function getMessages(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`)
  const rows = await parseJson(res)
  return rows.map(normalizeSessionMessage)
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  return parseJson(res)
}

export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE}/files/upload`, {
    method: 'POST',
    body: formData,
  })
  return createAttachment(await parseJson(res), file)
}

export async function listFiles() {
  const payload = await parseJson(await fetch(`${BASE}/files`))
  return (payload.files || []).map(normalizeFileArtifact)
}

export async function getFileInfo(fileId) {
  const payload = await parseJson(await fetch(`${BASE}/files/${encodeURIComponent(fileId)}`))
  return normalizeFileArtifact(payload.file || {})
}

export async function getFileDownloadAction(fileId) {
  const payload = await parseJson(await fetch(`${BASE}/files/${encodeURIComponent(fileId)}/download`))
  const download = payload.download || {}
  return {
    available: Boolean(download.available && safeUrl(download.url)),
    method: download.method || 'open_url',
    url: safeUrl(download.url),
    fallbackOpenUrl: safeUrl(download.fallback_open_url || download.fallbackOpenUrl),
  }
}

export async function getCapabilities() {
  const payload = await parseJson(await fetch(`${BASE}/capabilities`))
  return (payload || []).map(normalizeCapability)
}

export async function getReportTemplates() {
  const payload = await parseJson(await fetch(`${BASE}/report-templates`))
  return (payload || []).map(normalizeReportTemplate).filter((template) => template.id)
}
