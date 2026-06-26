function fallbackId(prefix) {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

export function createMessage(overrides = {}) {
  return {
    id: fallbackId('msg'),
    role: 'assistant',
    content: '',
    createdAt: new Date().toISOString(),
    status: 'complete',
    sources: [],
    files: [],
    progress: [],
    error: null,
    ...overrides,
  }
}

export function createAttachment(uploadResult = {}, file = null) {
  const status = normalizeFileStatus(uploadResult.index_status || uploadResult.status)

  return {
    id: uploadResult.storage_ref || uploadResult.id || fallbackId('file'),
    name: uploadResult.filename || uploadResult.name || file?.name || '파일',
    kind: uploadResult.kind || 'uploaded',
    mimeType: file?.type || uploadResult.mime_type || 'application/octet-stream',
    size: file?.size || uploadResult.size || 0,
    storageRef: uploadResult.storage_ref || uploadResult.storageRef || null,
    status,
    detail: uploadResult.index_message || uploadResult.message || uploadResult.detail || '',
    openUrl: safeUrl(uploadResult.web_view_link || uploadResult.open_url || uploadResult.openUrl),
    downloadUrl: safeUrl(uploadResult.download_url || uploadResult.downloadUrl),
  }
}

export function createProgress(stage, message, state = 'working') {
  return { stage, message, state }
}

export function normalizeSource(source = {}) {
  return {
    title: source.title || source.url || '출처',
    sourceType: source.source_type || source.sourceType || 'web',
    url: safeUrl(source.url),
    snippet: source.snippet || '',
    agentId: source.agent_id || source.agentId || null,
    metadata: source.metadata || {},
  }
}

export function normalizeFileArtifact(file = {}) {
  return createAttachment({
    id: file.id,
    name: file.name || file.filename,
    kind: file.kind || 'uploaded',
    status: file.status,
    storage_ref: file.storage_ref || file.storageRef,
    mime_type: file.mime_type || file.mimeType,
    size: file.size,
    open_url: safeUrl(file.open_url || file.openUrl || file.web_view_link),
    download_url: safeUrl(file.download_url || file.downloadUrl),
    message: file.message,
    detail: file.detail,
  })
}

export function normalizeProgress(item = {}) {
  const rawState = item.state || item.status || 'working'
  const state = {
    queued: 'pending',
    running: 'working',
    completed: 'completed',
    warning: 'warning',
    failed: 'failed',
    skipped: 'skipped',
  }[rawState] || rawState

  return createProgress(
    item.stage || item.label || item.agent_id || item.agentId || 'agent',
    item.message || item.label || '작업 중',
    state,
  )
}

export function normalizeChatPayload(payload = {}) {
  return {
    sessionId: payload.session_id || payload.sessionId || null,
    runId: payload.run_id || payload.runId || null,
    status: payload.status || 'completed',
    content: payload.answer || payload.content || '',
    sources: (payload.sources || []).map(normalizeSource),
    files: (payload.files || []).map(normalizeFileArtifact),
    progress: (payload.progress || []).map(normalizeProgress),
    error: payload.error || null,
  }
}

export function serializeAttachment(attachment = {}) {
  return {
    id: attachment.storageRef || attachment.storage_ref || attachment.id || fallbackId('file'),
    name: attachment.name || attachment.filename || '파일',
    kind: attachment.kind || 'uploaded',
    status: toContractFileStatus(attachment.status),
    storage_ref: attachment.storageRef || attachment.storage_ref || null,
    mime_type: attachment.mimeType || attachment.mime_type || null,
    size: Number.isFinite(attachment.size) ? attachment.size : null,
    open_url: safeUrl(attachment.openUrl || attachment.open_url),
    download_url: safeUrl(attachment.downloadUrl || attachment.download_url),
    message: attachment.detail || attachment.message || '',
  }
}

export function normalizeSessionMessage(row) {
  return createMessage({
    id: row.id,
    role: row.role,
    content: row.content || '',
    createdAt: row.created_at,
  })
}

function normalizeFileStatus(status) {
  if (status === 'error' || status === 'failed') return 'error'
  if (status === 'success' || status === 'indexed' || status === 'uploaded' || status === 'downloadable') {
    return 'ready'
  }
  return status || 'ready'
}

function toContractFileStatus(status) {
  if (status === 'error' || status === 'failed') return 'failed'
  if (status === 'downloadable') return 'downloadable'
  if (status === 'uploaded') return 'uploaded'
  return 'indexed'
}

export function safeUrl(value) {
  const raw = typeof value === 'string' ? value.trim() : ''
  if (!raw) return null

  try {
    const base = globalThis.location?.origin || 'http://localhost'
    const parsed = new URL(raw, base)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
    return raw
  } catch {
    return null
  }
}
