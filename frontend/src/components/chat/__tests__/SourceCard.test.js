import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SourceCard from '../SourceCard.vue'

describe('SourceCard', () => {
  it('does not invent a relevance label when it is missing', () => {
    const wrapper = mount(SourceCard, {
      props: { source: { title: '문서', url: 'https://example.com/a' } },
    })

    expect(wrapper.find('.relevance').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('높음')
  })

  it('does not render unsafe source URLs as links', () => {
    const wrapper = mount(SourceCard, {
      props: { source: { title: '위험 링크', url: 'javascript:alert(1)' } },
    })

    expect(wrapper.find('a').exists()).toBe(false)
  })
})
