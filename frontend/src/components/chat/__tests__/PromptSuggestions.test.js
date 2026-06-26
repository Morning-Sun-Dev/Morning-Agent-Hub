import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PromptSuggestions from '../PromptSuggestions.vue'

describe('PromptSuggestions', () => {
  it('emits selected prompt text', async () => {
    const wrapper = mount(PromptSuggestions)

    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('select')?.[0]?.[0]).toContain('요약')
  })
})
