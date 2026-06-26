import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: true,
})

const defaultLinkOpen = markdown.renderer.rules.link_open

markdown.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen
    ? defaultLinkOpen(tokens, idx, options, env, self)
    : self.renderToken(tokens, idx, options)
}

const SANITIZE_CONFIG = {
  ALLOWED_TAGS: [
    'a',
    'blockquote',
    'br',
    'code',
    'del',
    'em',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'hr',
    'li',
    'ol',
    'p',
    'pre',
    's',
    'strong',
    'table',
    'tbody',
    'td',
    'th',
    'thead',
    'tr',
    'ul',
  ],
  ALLOWED_ATTR: ['align', 'colspan', 'href', 'rel', 'rowspan', 'target', 'title'],
  FORBID_TAGS: ['button', 'embed', 'form', 'iframe', 'input', 'object', 'script', 'style'],
  FORBID_ATTR: ['style'],
}

export function renderMarkdown(markdownText = '') {
  const raw = typeof markdownText === 'string' ? markdownText : ''
  return DOMPurify.sanitize(markdown.render(removeUnsafeMarkdownLinks(raw)), SANITIZE_CONFIG)
}

function removeUnsafeMarkdownLinks(markdownText) {
  return markdownText.replace(
    /\[([^\]]+)]\(\s*(?:javascript|data|vbscript):[^)]*\)/gi,
    '$1',
  )
}
