import { afterEach, describe, expect, it, vi } from 'vitest'
import { getCapabilities, sendChat, streamChat, uploadFile } from '../api'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('api adapter', () => {
  it('posts chat payload and normalizes answer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({
          answer: '완료',
          session_id: 's1',
          progress: [{ label: '요청 분석', message: '완료', status: 'completed' }],
          files: [{ id: 'f1', name: 'result.md', status: 'downloadable', download_url: '/download/f1' }],
        }), { status: 200 }),
      ),
    )

    const result = await sendChat('안녕', null, {
      attachments: [{ id: 'gdrive://file/a', name: 'a.pdf', status: 'ready', storageRef: 'gdrive://file/a' }],
      requestedCapabilities: ['web_search'],
    })

    expect(fetch).toHaveBeenCalledWith('/api/chat', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({
        message: '안녕',
        session_id: null,
        attachments: [{
          id: 'gdrive://file/a',
          name: 'a.pdf',
          kind: 'uploaded',
          status: 'indexed',
          storage_ref: 'gdrive://file/a',
          mime_type: null,
          size: null,
          open_url: null,
          download_url: null,
          message: '',
        }],
        requested_capabilities: ['web_search'],
      }),
    }))
    expect(result.sessionId).toBe('s1')
    expect(result.message.content).toBe('완료')
    expect(result.message.progress[0].stage).toBe('요청 분석')
    expect(result.message.files[0].downloadUrl).toBe('/download/f1')
  })

  it('normalizes upload response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            filename: 'a.pdf',
            storage_ref: 'gdrive://file/a',
            index_status: 'success',
            index_message: '1개 청크 저장 완료',
          }),
          { status: 200 },
        ),
      ),
    )

    const attachment = await uploadFile(new File(['x'], 'a.pdf', { type: 'application/pdf' }))

    expect(attachment.name).toBe('a.pdf')
    expect(attachment.status).toBe('ready')
  })

  it('normalizes stream answer payloads and serializes request options', () => {
    let instance
    class EventSourceMock {
      constructor(url) {
        this.url = url
        instance = this
      }

      close = vi.fn()
    }
    vi.stubGlobal('EventSource', EventSourceMock)
    const onAnswer = vi.fn()

    const stop = streamChat('상태 알려줘', null, { onAnswer }, {
      attachments: [{ id: 'gdrive://file/a', name: 'a.pdf', status: 'ready', storageRef: 'gdrive://file/a' }],
      requestedCapabilities: ['web_search'],
    })
    instance.onmessage({
      data: JSON.stringify({
        type: 'answer',
        session_id: 's1',
        content: '완료',
        progress: [{ label: '웹 검색', message: '완료', status: 'completed' }],
        files: [{ id: 'f1', name: 'result.md', status: 'downloadable', download_url: '/download/f1' }],
      }),
    })
    stop()

    expect(instance.url).toContain('/api/chat/stream?message=%EC%83%81%ED%83%9C+%EC%95%8C%EB%A0%A4%EC%A4%98')
    expect(instance.url).toContain('attachments=')
    expect(instance.url).toContain('requested_capabilities=')
    expect(instance.close).toHaveBeenCalled()
    expect(onAnswer).toHaveBeenCalledWith(expect.objectContaining({
      sessionId: 's1',
      content: '완료',
      progress: [{ stage: '웹 검색', message: '완료', state: 'completed' }],
      files: [expect.objectContaining({ downloadUrl: '/download/f1' })],
    }))
  })

  it('calls onDone when the stream sends DONE', () => {
    let instance
    class EventSourceMock {
      constructor(url) {
        this.url = url
        instance = this
      }

      close = vi.fn()
    }
    vi.stubGlobal('EventSource', EventSourceMock)
    const onDone = vi.fn()

    const stop = streamChat('상태 알려줘', null, { onDone })
    instance.onmessage({ data: '[DONE]' })
    stop()

    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('loads and normalizes capability descriptors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify([
          {
            agent_id: 'web_research',
            capability_id: 'web_search',
            label: '웹 검색',
            description: '최신 정보를 검색합니다.',
            enabled: true,
            ui_status: 'available',
            ui_surface: '채팅 입력',
          },
        ]), { status: 200 }),
      ),
    )

    const capabilities = await getCapabilities()

    expect(fetch).toHaveBeenCalledWith('/api/capabilities')
    expect(capabilities).toEqual([
      {
        agentId: 'web_research',
        capabilityId: 'web_search',
        label: '웹 검색',
        description: '최신 정보를 검색합니다.',
        enabled: true,
        uiStatus: 'available',
        uiSurface: '채팅 입력',
      },
    ])
  })
})
