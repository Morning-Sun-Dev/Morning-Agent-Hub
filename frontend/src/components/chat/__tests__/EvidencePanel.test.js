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
          name: 'brief.md',
          downloadUrl: 'https://drive.example/download/a',
        }],
        progress: [],
        activeTab: 'files',
      },
    })

    await wrapper.get('[data-testid="file-info-button"]').trigger('click')
    await wrapper.get('[data-testid="file-download-button"]').trigger('click')

    expect(wrapper.emitted('inspect-file')).toEqual([['drive-file-1']])
    expect(wrapper.emitted('prepare-download')).toEqual([['drive-file-1']])
  })
})
