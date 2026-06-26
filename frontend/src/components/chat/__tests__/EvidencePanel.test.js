import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EvidencePanel from '../EvidencePanel.vue'

describe('EvidencePanel', () => {
  it('shows empty state when no sources or files exist', () => {
    const wrapper = mount(EvidencePanel, {
      props: { sources: [], files: [], progress: [], activeTab: 'sources' },
    })

    expect(wrapper.text()).toContain('아직 표시할 근거가 없습니다')
  })

  it('shows progress failures', () => {
    const wrapper = mount(EvidencePanel, {
      props: {
        sources: [],
        files: [],
        progress: [{ stage: 'web_search', message: '연결 실패', state: 'failed' }],
        activeTab: 'progress',
      },
    })

    expect(wrapper.text()).toContain('연결 실패')
  })

  it('expands the mobile summary into the active panel content', async () => {
    const wrapper = mount(EvidencePanel, {
      props: {
        sources: [],
        files: [],
        progress: [{ stage: 'chat', message: '답변 생성 중', state: 'working' }],
        activeTab: 'progress',
        mobileCollapsed: true,
      },
    })

    expect(wrapper.text()).toContain('근거 패널 펼치기')
    await wrapper.get('.mobile-summary').trigger('click')

    expect(wrapper.text()).toContain('답변 생성 중')
  })

  it('does not render unsafe file URLs as links', () => {
    const wrapper = mount(EvidencePanel, {
      props: {
        sources: [],
        files: [{ id: 'f1', name: 'report.md', downloadUrl: 'javascript:alert(1)' }],
        progress: [],
        activeTab: 'files',
      },
    })

    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('emits file management actions from file rows', async () => {
    const wrapper = mount(EvidencePanel, {
      props: {
        sources: [],
        files: [{
          id: 'gdrive://file/a',
          fileId: 'drive-file-1',
          kind: 'drive',
          name: 'brief.md',
          downloadUrl: 'https://drive.example/download/a',
        }],
        progress: [],
        activeTab: 'files',
      },
    })

    await wrapper.get('[data-testid="file-info-button"]').trigger('click')
    await wrapper.get('[data-testid="file-download-button"]').trigger('click')
    await wrapper.get('[data-testid="file-rename-button"]').trigger('click')
    await wrapper.get('[data-testid="file-delete-button"]').trigger('click')

    expect(wrapper.emitted('inspect-file')).toEqual([['drive-file-1']])
    expect(wrapper.emitted('prepare-download')).toEqual([['drive-file-1']])
    expect(wrapper.emitted('rename-file')).toEqual([['drive-file-1']])
    expect(wrapper.emitted('delete-file')).toEqual([['drive-file-1']])
  })

  it('emits folder search and create actions from the file panel', async () => {
    const wrapper = mount(EvidencePanel, {
      props: {
        sources: [],
        files: [],
        folders: [{
          id: 'gdrive://file/folder-1',
          folderId: 'folder-1',
          name: 'reports',
          openUrl: 'https://drive.example/folders/folder-1',
        }],
        progress: [],
        activeTab: 'files',
        folderNotice: '1개 폴더를 찾았습니다.',
      },
    })

    await wrapper.get('[data-testid="folder-name-input"]').setValue('reports')
    await wrapper.get('[data-testid="folder-find-button"]').trigger('click')
    await wrapper.get('[data-testid="folder-create-button"]').trigger('click')

    expect(wrapper.text()).toContain('reports')
    expect(wrapper.text()).toContain('1개 폴더를 찾았습니다.')
    expect(wrapper.emitted('find-folder')).toEqual([['reports']])
    expect(wrapper.emitted('create-folder')).toEqual([['reports']])
  })

  it('emits capability quick actions from the capability panel', async () => {
    const capability = {
      agentId: 'file_management',
      capabilityId: 'delete_file',
      label: 'Drive 파일 삭제',
      description: '파일을 휴지통으로 이동합니다.',
      enabled: true,
      uiStatus: 'available',
      uiSurface: '파일 패널',
    }
    const wrapper = mount(EvidencePanel, {
      props: {
        sources: [],
        files: [],
        progress: [],
        capabilities: [capability],
        activeTab: 'capabilities',
      },
    })

    await wrapper.get('[data-testid="capability-request-button"]').trigger('click')

    expect(wrapper.emitted('select-capability')).toEqual([[capability]])
  })

  it('emits web capability quick-run inputs from the capability panel', async () => {
    const wrapper = mount(EvidencePanel, {
      props: {
        sources: [],
        files: [],
        progress: [],
        capabilities: [],
        activeTab: 'capabilities',
      },
    })

    await wrapper.get('[data-testid="news-query-input"]').setValue('AI 에이전트 시장')
    await wrapper.get('[data-testid="news-search-button"]').trigger('click')

    await wrapper.get('[data-testid="url-fetch-input"]').setValue('https://example.com/report')
    await wrapper.get('[data-testid="url-fetch-button"]').trigger('click')

    expect(wrapper.emitted('run-capability')).toEqual([
      [{ capabilityId: 'news_search', value: 'AI 에이전트 시장' }],
      [{ capabilityId: 'url_fetch', value: 'https://example.com/report' }],
    ])
  })

  it('emits card-level capability quick runs for partial capabilities', async () => {
    const wrapper = mount(EvidencePanel, {
      props: {
        sources: [],
        files: [],
        progress: [],
        capabilities: [
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
        ],
        activeTab: 'capabilities',
      },
    })

    const inputs = wrapper.findAll('[data-testid="capability-run-input"]')
    const buttons = wrapper.findAll('[data-testid="capability-run-button"]')

    expect(inputs.at(0).attributes('placeholder')).toBe('예: 2026년 PDF 문서')
    expect(wrapper.text()).toContain('메타데이터 조건')
    expect(wrapper.text()).toContain('사용 가능한 보고서 양식 목록과 용도를 조회합니다.')

    await inputs.at(0).setValue('2026년 PDF 문서')
    await buttons.at(0).trigger('click')
    await buttons.at(1).trigger('click')

    expect(wrapper.emitted('run-capability')).toEqual([
      [{ capabilityId: 'rag_sql_search', value: '2026년 PDF 문서' }],
      [{ capabilityId: 'list_templates', value: '' }],
    ])
  })
})
