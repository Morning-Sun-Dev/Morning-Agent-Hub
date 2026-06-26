import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getCapabilities, getReportTemplates, streamChat, uploadFile } from '../../../api'
import ChatShell from '../ChatShell.vue'

vi.mock('../../../api', () => ({
  getCapabilities: vi.fn(),
  getReportTemplates: vi.fn(),
  uploadFile: vi.fn(),
  streamChat: vi.fn(),
}))

describe('ChatShell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getCapabilities.mockResolvedValue([
      {
        agentId: 'web_research',
        capabilityId: 'web_search',
        label: '웹 검색',
        description: '최신 정보를 검색합니다.',
        enabled: true,
        uiStatus: 'available',
        uiSurface: '채팅 입력',
      },
      {
        agentId: 'file_management',
        capabilityId: 'delete_file',
        label: 'Drive 파일 삭제',
        description: 'Google Drive 파일을 삭제합니다.',
        enabled: true,
        uiStatus: 'planned',
        uiSurface: '',
      },
    ])
    getReportTemplates.mockResolvedValue([
      {
        id: 'research_report',
        name: 'Research Report',
        description: '조사 보고서',
        sectionCount: 5,
      },
    ])
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

  it('shows agent capability coverage in the evidence panel', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '기능').trigger('click')

    expect(getCapabilities).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('웹 검색')
    expect(wrapper.text()).toContain('채팅 입력')
    expect(wrapper.text()).toContain('Drive 파일 삭제')
    expect(wrapper.text()).toContain('예정')
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

  it('sends selected report template instructions and capabilities', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.get('[data-testid="report-template-select"]').setValue('research_report')
    await wrapper.get('textarea').setValue('시장 동향 정리해줘')
    await wrapper.get('[data-testid="send-button"]').trigger('click')

    const [message, , , options] = streamChat.mock.calls.at(-1)
    expect(message).toContain('시장 동향 정리해줘')
    expect(message).toContain('template_id: research_report')
    expect(message).toContain('template_name: Research Report')
    expect(options.requestedCapabilities).toEqual(expect.arrayContaining([
      'write_report',
      'format_report',
      'list_templates',
    ]))
  })
})
