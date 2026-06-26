import { describe, expect, it } from 'vitest'
import {
  createAttachment,
  createMessage,
  createProgress,
  normalizeChatPayload,
  serializeAttachment,
} from '../chatModels'

describe('chat UI models', () => {
  it('creates a complete assistant message with safe defaults', () => {
    const message = createMessage({ content: '답변입니다.' })

    expect(message.role).toBe('assistant')
    expect(message.content).toBe('답변입니다.')
    expect(message.sources).toEqual([])
    expect(message.files).toEqual([])
    expect(message.progress).toEqual([])
    expect(message.error).toBeNull()
  })

  it('normalizes upload results into attachment chips', () => {
    const attachment = createAttachment(
      {
        filename: '휴가규정_2026.pdf',
        storage_ref: 'gdrive://file/abc',
        index_status: 'success',
        index_message: '12개 청크 저장 완료',
      },
      new File(['x'], '휴가규정_2026.pdf', { type: 'application/pdf' }),
    )

    expect(attachment.name).toBe('휴가규정_2026.pdf')
    expect(attachment.storageRef).toBe('gdrive://file/abc')
    expect(attachment.status).toBe('ready')
    expect(attachment.detail).toBe('12개 청크 저장 완료')
  })

  it('creates progress trace items', () => {
    expect(createProgress('web_search', '검색 중', 'working')).toEqual({
      stage: 'web_search',
      message: '검색 중',
      state: 'working',
    })
  })

  it('serializes uploaded attachments into backend file contract fields', () => {
    expect(serializeAttachment({
      id: 'gdrive://file/a',
      name: 'a.pdf',
      mimeType: 'application/pdf',
      size: 10,
      storageRef: 'gdrive://file/a',
      status: 'ready',
    })).toEqual({
      id: 'gdrive://file/a',
      name: 'a.pdf',
      kind: 'uploaded',
      status: 'indexed',
      storage_ref: 'gdrive://file/a',
      mime_type: 'application/pdf',
      size: 10,
      open_url: null,
      download_url: null,
      message: '',
    })
  })

  it('normalizes expanded chat payloads for UI components', () => {
    const payload = normalizeChatPayload({
      session_id: 's1',
      status: 'partial_failure',
      content: '답변',
      progress: [{ label: '웹 검색', message: '검색 완료', status: 'completed' }],
      files: [{ id: 'f1', name: 'report.md', status: 'downloadable', download_url: '/download/f1' }],
      sources: [{ title: '출처', source_type: 'web', url: 'https://example.com', snippet: '요약' }],
      error: '일부 실패',
    })

    expect(payload.sessionId).toBe('s1')
    expect(payload.progress[0]).toEqual({ stage: '웹 검색', message: '검색 완료', state: 'completed' })
    expect(payload.files[0].downloadUrl).toBe('/download/f1')
    expect(payload.sources[0].sourceType).toBe('web')
    expect(payload.error).toBe('일부 실패')
  })
})
