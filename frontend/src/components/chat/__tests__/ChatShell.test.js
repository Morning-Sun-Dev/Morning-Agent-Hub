import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { streamChat, uploadFile } from '../../../api'
import ChatShell from '../ChatShell.vue'

vi.mock('../../../api', () => ({
  uploadFile: vi.fn(),
  streamChat: vi.fn(),
}))

describe('ChatShell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    streamChat.mockImplementation((_message, _sessionId, handlers) => {
      handlers.onProgress({ stage: 'orchestrator', message: '작업 중', state: 'working' })
      handlers.onAnswer({ sessionId: 's1', content: '응답입니다.', sources: [], files: [], progress: [] })
      handlers.onDone()
      return vi.fn()
    })
  })

  it('sends a draft and renders assistant answer', async () => {
    const wrapper = mount(ChatShell)
    await wrapper.get('textarea').setValue('휴가 규정 알려줘')
    await wrapper.get('[data-testid="send-button"]').trigger('click')

    expect(wrapper.text()).toContain('휴가 규정 알려줘')
    expect(wrapper.text()).toContain('응답입니다.')
  })

  it('passes uploaded attachments and requested capabilities to the stream', async () => {
    uploadFile.mockResolvedValue({
      id: 'gdrive://file/a',
      name: 'policy.pdf',
      status: 'ready',
      storageRef: 'gdrive://file/a',
    })
    const wrapper = mount(ChatShell)
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['x'], 'policy.pdf', { type: 'application/pdf' })],
      configurable: true,
    })

    await input.trigger('change')
    await flushPromises()
    await wrapper.get('textarea').setValue('휴가 규정 요약')
    await wrapper.get('[data-testid="send-button"]').trigger('click')

    expect(streamChat).toHaveBeenCalledWith(
      '휴가 규정 요약',
      null,
      expect.any(Object),
      expect.objectContaining({
        attachments: [expect.objectContaining({ storageRef: 'gdrive://file/a' })],
        requestedCapabilities: expect.arrayContaining(['web_search', 'rag_vector_search']),
      }),
    )
  })

  it('keeps the original request available for retry after partial failure', async () => {
    streamChat.mockImplementation((_message, _sessionId, handlers) => {
      handlers.onAnswer({
        sessionId: 's1',
        content: '부분 답변',
        status: 'partial_failure',
        error: '웹 검색 실패',
        sources: [],
        files: [],
        progress: [],
      })
      handlers.onDone()
      return vi.fn()
    })
    const wrapper = mount(ChatShell)

    await wrapper.get('textarea').setValue('최신 정책 알려줘')
    await wrapper.get('[data-testid="send-button"]').trigger('click')
    expect(wrapper.get('textarea').element.value).toBe('최신 정책 알려줘')

    const retryButton = wrapper.findAll('button').find((button) => button.text() === '실패 단계 재시도')
    await retryButton.trigger('click')

    expect(streamChat).toHaveBeenCalledTimes(2)
    expect(streamChat.mock.calls[1][0]).toBe('최신 정책 알려줘')
  })

  it('removes web search capability when continuing with files only', async () => {
    uploadFile.mockResolvedValue({
      id: 'gdrive://file/a',
      name: 'policy.pdf',
      status: 'ready',
      storageRef: 'gdrive://file/a',
    })
    streamChat.mockImplementation((_message, _sessionId, handlers) => {
      handlers.onAnswer({
        sessionId: 's1',
        content: '부분 답변',
        status: 'partial_failure',
        error: '웹 검색 실패',
        sources: [],
        files: [],
        progress: [],
      })
      handlers.onDone()
      return vi.fn()
    })
    const wrapper = mount(ChatShell)
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['x'], 'policy.pdf', { type: 'application/pdf' })],
      configurable: true,
    })

    await input.trigger('change')
    await flushPromises()
    await wrapper.get('textarea').setValue('휴가 규정 요약')
    await wrapper.get('[data-testid="send-button"]').trigger('click')

    const fileOnlyButton = wrapper.findAll('button').find((button) => button.text() === '파일만 사용')
    await fileOnlyButton.trigger('click')

    const options = streamChat.mock.calls.at(-1)[3]
    expect(options.requestedCapabilities).not.toContain('web_search')
    expect(options.requestedCapabilities).toEqual(expect.arrayContaining(['rag_vector_search']))
  })
})
