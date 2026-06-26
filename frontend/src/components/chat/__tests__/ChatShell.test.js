import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createFolder,
  deleteFile,
  findFolders,
  getCapabilities,
  getFileDownloadAction,
  getFileInfo,
  getReportTemplates,
  listFiles,
  streamChat,
  updateFileName,
  uploadFile,
} from '../../../api'
import ChatShell from '../ChatShell.vue'

vi.mock('../../../api', () => ({
  createFolder: vi.fn(),
  deleteFile: vi.fn(),
  findFolders: vi.fn(),
  getCapabilities: vi.fn(),
  getFileDownloadAction: vi.fn(),
  getFileInfo: vi.fn(),
  getReportTemplates: vi.fn(),
  listFiles: vi.fn(),
  uploadFile: vi.fn(),
  streamChat: vi.fn(),
  updateFileName: vi.fn(),
}))

describe('ChatShell', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

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
        uiStatus: 'available',
        uiSurface: '파일 패널',
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
    listFiles.mockResolvedValue([
      {
        id: 'gdrive://file/a',
        fileId: 'drive-file-1',
        name: 'brief.md',
        kind: 'drive',
        status: 'ready',
        downloadUrl: 'https://drive.example/download/a',
      },
    ])
    getFileInfo.mockResolvedValue({
      id: 'gdrive://file/a',
      fileId: 'drive-file-1',
      name: 'brief.md',
      detail: 'text/markdown',
    })
    getFileDownloadAction.mockResolvedValue({
      available: true,
      method: 'open_url',
      url: 'https://drive.example/download/a',
      fallbackOpenUrl: null,
    })
    deleteFile.mockResolvedValue({
      file_id: 'drive-file-1',
      deleted: true,
    })
    updateFileName.mockResolvedValue({
      id: 'gdrive://file/a',
      fileId: 'drive-file-1',
      name: 'renamed.md',
      kind: 'drive',
      status: 'ready',
    })
    findFolders.mockResolvedValue([
      {
        id: 'gdrive://file/folder-1',
        folderId: 'folder-1',
        name: 'reports',
        openUrl: 'https://drive.example/folders/folder-1',
      },
    ])
    createFolder.mockResolvedValue({
      id: 'gdrive://file/folder-2',
      folderId: 'folder-2',
      name: 'new reports',
      openUrl: null,
    })
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

  it('does not expose internal module ids in the chat workspace', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    expect(wrapper.text()).toContain('단일 챗봇')
    expect(wrapper.text()).not.toContain('M-001')
  })

  it('shows agent capability coverage in the evidence panel', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '기능').trigger('click')

    expect(getCapabilities).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('웹 검색')
    expect(wrapper.text()).toContain('채팅 입력')
    expect(wrapper.text()).toContain('Drive 파일 삭제')
    expect(wrapper.text()).toContain('파일 패널')
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

  it('keeps ordinary answers as the default when no report template is selected', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    expect(wrapper.get('[data-testid="report-template-select"]').element.value).toBe('')
    expect(wrapper.get('[data-testid="report-template-select"]').text()).toContain('일반 답변')

    await wrapper.get('textarea').setValue('AI 에이전트 트렌드 알려줘')
    await wrapper.get('[data-testid="send-button"]').trigger('click')

    const [, , , options] = streamChat.mock.calls.at(-1)
    expect(options.requestedCapabilities).not.toContain('write_report')
    expect(options.requestedCapabilities).not.toContain('format_report')
    expect(options.requestedCapabilities).not.toContain('list_templates')
  })

  it('loads drive files and handles file management actions', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '파일').trigger('click')
    expect(listFiles).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('brief.md')

    await wrapper.get('[data-testid="file-info-button"]').trigger('click')
    expect(getFileInfo).toHaveBeenCalledWith('drive-file-1')
    expect(wrapper.text()).toContain('brief.md 상세 정보를 확인했습니다.')

    await wrapper.get('[data-testid="file-download-button"]').trigger('click')
    expect(getFileDownloadAction).toHaveBeenCalledWith('drive-file-1')
    expect(wrapper.text()).toContain('다운로드 링크가 준비됐습니다.')
  })

  it('deletes a drive file from the file panel after confirmation', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '파일').trigger('click')
    expect(wrapper.text()).toContain('brief.md')

    await wrapper.get('[data-testid="file-delete-button"]').trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalledWith('이 Drive 파일을 휴지통으로 이동할까요?')
    expect(deleteFile).toHaveBeenCalledWith('drive-file-1')
    expect(wrapper.text()).toContain('파일을 휴지통으로 이동했습니다.')
    expect(wrapper.text()).not.toContain('brief.md')
  })

  it('renames a drive file from the file panel after confirmation', async () => {
    vi.stubGlobal('prompt', vi.fn(() => 'renamed.md'))
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '파일').trigger('click')
    await wrapper.get('[data-testid="file-rename-button"]').trigger('click')
    await flushPromises()

    expect(prompt).toHaveBeenCalledWith('새 파일 이름', 'brief.md')
    expect(updateFileName).toHaveBeenCalledWith('drive-file-1', 'renamed.md')
    expect(wrapper.text()).toContain('파일 이름을 변경했습니다.')
    expect(wrapper.text()).toContain('renamed.md')
  })

  it('finds and creates Drive folders from the file panel', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '파일').trigger('click')
    await wrapper.get('[data-testid="folder-name-input"]').setValue('reports')
    await wrapper.get('[data-testid="folder-find-button"]').trigger('click')
    await flushPromises()

    expect(findFolders).toHaveBeenCalledWith('reports')
    expect(wrapper.text()).toContain('1개 폴더를 찾았습니다.')
    expect(wrapper.text()).toContain('reports')

    await wrapper.get('[data-testid="folder-name-input"]').setValue('new reports')
    await wrapper.get('[data-testid="folder-create-button"]').trigger('click')
    await flushPromises()

    expect(createFolder).toHaveBeenCalledWith('new reports')
    expect(wrapper.text()).toContain('폴더를 생성했습니다.')
    expect(wrapper.text()).toContain('new reports')
  })

  it('turns a capability quick action into a requested chat capability', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '기능').trigger('click')
    const quickActions = wrapper.findAll('[data-testid="capability-request-button"]')
    await quickActions.at(1).trigger('click')

    expect(wrapper.get('textarea').element.value).toContain('휴지통')

    await wrapper.get('[data-testid="send-button"]').trigger('click')

    const [, , , options] = streamChat.mock.calls.at(-1)
    expect(options.requestedCapabilities).toEqual(expect.arrayContaining(['delete_file']))
  })

  it('runs web capability quick inputs with explicit requested capabilities', async () => {
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '기능').trigger('click')
    await wrapper.get('[data-testid="news-query-input"]').setValue('AI 에이전트 시장')
    await wrapper.get('[data-testid="news-search-button"]').trigger('click')

    const [newsMessage, , , newsOptions] = streamChat.mock.calls.at(-1)
    expect(newsMessage).toContain('AI 에이전트 시장')
    expect(newsOptions.requestedCapabilities).toEqual(expect.arrayContaining(['web_search', 'news_search']))

    await wrapper.findAll('button').find((button) => button.text() === '기능').trigger('click')
    await wrapper.get('[data-testid="url-fetch-input"]').setValue('https://example.com/report')
    await wrapper.get('[data-testid="url-fetch-button"]').trigger('click')

    const [urlMessage, , , urlOptions] = streamChat.mock.calls.at(-1)
    expect(urlMessage).toContain('https://example.com/report')
    expect(urlOptions.requestedCapabilities).toEqual(expect.arrayContaining(['web_search', 'url_fetch']))
  })

  it('runs partial capability card actions without adding unrelated web search', async () => {
    getCapabilities.mockResolvedValue([
      {
        agentId: 'internal_rag',
        capabilityId: 'rag_sql_search',
        label: '문서 메타데이터 검색',
        description: '메타데이터 조건으로 문서를 검색합니다.',
        enabled: true,
        uiStatus: 'partial',
        uiSurface: '기능 패널 요청 초안',
      },
      {
        agentId: 'report_writing',
        capabilityId: 'list_templates',
        label: '보고서 양식 조회',
        description: '사용 가능한 보고서 양식을 조회합니다.',
        enabled: true,
        uiStatus: 'partial',
        uiSurface: '채팅 입력',
      },
    ])
    const wrapper = mount(ChatShell)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '기능').trigger('click')
    await wrapper.findAll('[data-testid="capability-run-input"]').at(0).setValue('2026년 PDF 문서')
    await wrapper.findAll('[data-testid="capability-run-button"]').at(0).trigger('click')

    const [ragMessage, , , ragOptions] = streamChat.mock.calls.at(-1)
    expect(ragMessage).toContain('2026년 PDF 문서')
    expect(ragOptions.requestedCapabilities).toEqual(expect.arrayContaining(['rag_sql_search']))
    expect(ragOptions.requestedCapabilities).not.toContain('web_search')

    await wrapper.findAll('button').find((button) => button.text() === '기능').trigger('click')
    await wrapper.findAll('[data-testid="capability-run-button"]').at(1).trigger('click')

    const [templateMessage, , , templateOptions] = streamChat.mock.calls.at(-1)
    expect(templateMessage).toContain('보고서 양식 목록')
    expect(templateOptions.requestedCapabilities).toEqual(expect.arrayContaining(['list_templates']))
    expect(templateOptions.requestedCapabilities).not.toContain('write_report')
  })
})
