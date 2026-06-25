const BASE = '/api'

// ── 채팅 ────────────────────────────────────────────

export async function sendChat(message, sessionId = null) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`채팅 오류: ${res.status}`)
  return res.json()
}

/**
 * SSE 스트리밍 채팅
 * onStatus(state) — 진행 상태 콜백
 * onAnswer(text, sessionId) — 답변 텍스트 콜백
 * onDone() — 완료 콜백
 */
export function streamChat(message, sessionId, { onStatus, onAnswer, onDone, onError }) {
  const params = new URLSearchParams({ message })
  if (sessionId) params.append('session_id', sessionId)

  const es = new EventSource(`${BASE}/chat/stream?${params}`)

  es.onmessage = (e) => {
    if (e.data === '[DONE]') {
      es.close()
      onDone?.()
      return
    }
    try {
      const payload = JSON.parse(e.data)
      if (payload.type === 'status') onStatus?.(payload.state)
      if (payload.type === 'answer') onAnswer?.(payload.content, payload.session_id)
      if (payload.type === 'error') {
        es.close()
        onError?.(payload.content)
      }
    } catch {}
  }

  es.onerror = () => {
    es.close()
    onError?.('연결이 끊겼습니다')
  }

  return () => es.close() // 취소 함수 반환
}

// ── 세션 ────────────────────────────────────────────

export async function getSessions() {
  const res = await fetch(`${BASE}/sessions`)
  if (!res.ok) throw new Error(`세션 조회 오류: ${res.status}`)
  return res.json()
}

export async function getMessages(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`)
  if (!res.ok) throw new Error(`메시지 조회 오류: ${res.status}`)
  return res.json()
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`세션 삭제 오류: ${res.status}`)
  return res.json()
}

// ── 파일 ────────────────────────────────────────────

export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE}/files/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `업로드 오류: ${res.status}`)
  }
  return res.json()
}
