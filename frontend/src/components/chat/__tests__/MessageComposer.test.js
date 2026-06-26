import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MessageComposer from '../MessageComposer.vue'

describe('MessageComposer', () => {
  it('disables send when draft is empty', () => {
    const wrapper = mount(MessageComposer, {
      props: { modelValue: '', attachments: [], sending: false, error: null },
    })

    expect(wrapper.get('[data-testid="send-button"]').attributes('disabled')).toBeDefined()
  })

  it('emits submit with trimmed draft', async () => {
    const wrapper = mount(MessageComposer, {
      props: { modelValue: '요약해줘', attachments: [], sending: false, error: null },
    })

    await wrapper.get('[data-testid="send-button"]').trigger('click')

    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('allows sending an attachment-only request', async () => {
    const wrapper = mount(MessageComposer, {
      props: {
        modelValue: '',
        attachments: [{ id: 'f1', name: 'policy.pdf', status: 'ready' }],
        sending: false,
        error: null,
      },
    })

    await wrapper.get('[data-testid="send-button"]').trigger('click')

    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('emits selected report template changes', async () => {
    const wrapper = mount(MessageComposer, {
      props: {
        modelValue: '보고서로 작성해줘',
        attachments: [],
        sending: false,
        error: null,
        reportTemplates: [
          {
            id: 'research_report',
            name: 'Research Report',
            description: '조사 보고서',
            sectionCount: 5,
          },
        ],
        selectedTemplateId: '',
      },
    })

    await wrapper.get('[data-testid="report-template-select"]').setValue('research_report')

    expect(wrapper.emitted('update:selectedTemplateId')).toEqual([['research_report']])
  })
})
