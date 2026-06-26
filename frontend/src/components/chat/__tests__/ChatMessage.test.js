import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatMessage from '../ChatMessage.vue'

describe('ChatMessage', () => {
  it('renders assistant answers as sanitized Markdown', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          role: 'assistant',
          status: 'complete',
          content: [
            '# 요약',
            '',
            '**중요:** [공식 문서](https://example.com/docs)를 확인하세요.',
            '',
            '| 항목 | 값 |',
            '| --- | --- |',
            '| 상태 | 완료 |',
            '',
            '<script>alert("xss")</script>',
            '[위험 링크](javascript:alert(1))',
          ].join('\n'),
        },
      },
    })

    const markdown = wrapper.get('[data-testid="message-markdown"]')

    expect(markdown.get('h1').text()).toBe('요약')
    expect(markdown.get('strong').text()).toBe('중요:')
    expect(markdown.get('a[href="https://example.com/docs"]').text()).toBe('공식 문서')
    expect(markdown.get('table').text()).toContain('상태')
    expect(wrapper.html()).not.toContain('<script')
    expect(wrapper.html()).not.toContain('javascript:alert')
  })

  it('keeps user messages as plain text instead of rendering Markdown', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          role: 'user',
          status: 'complete',
          content: '**그대로 보여줘**',
        },
      },
    })

    expect(wrapper.find('[data-testid="message-markdown"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('**그대로 보여줘**')
    expect(wrapper.find('.message-content strong').exists()).toBe(false)
  })
})
