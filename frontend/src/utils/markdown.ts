import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import yaml from 'highlight.js/lib/languages/yaml'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import sql from 'highlight.js/lib/languages/sql'
import go from 'highlight.js/lib/languages/go'
import rust from 'highlight.js/lib/languages/rust'
import java from 'highlight.js/lib/languages/java'
import cpp from 'highlight.js/lib/languages/cpp'
import plaintext from 'highlight.js/lib/languages/plaintext'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('go', go)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('java', java)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('c', cpp)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('text', plaintext)

export interface MarkdownRendererOptions {
  /**
   * Render single newlines as hard breaks. Task output relies on this; prose
   * documents such as the in-app guide must keep newlines soft so a wrapped
   * source line does not become a visual break.
   */
  breaks: boolean
}

export function highlightCode(md: MarkdownIt, source: string, lang: string): string {
  if (lang && hljs.getLanguage(lang)) {
    try {
      const highlighted = hljs.highlight(source, { language: lang, ignoreIllegals: true }).value
      return `<pre class="md-code-block hljs"><code class="language-${lang}">${highlighted}</code></pre>`
    } catch {
      // Fall through to the escaped plain-text block below.
    }
  }
  return `<pre class="md-code-block hljs"><code>${md.utils.escapeHtml(source)}</code></pre>`
}

/**
 * Build a markdown-it renderer with inline HTML disabled. Every markdown
 * surface in the app renders untrusted or mixed-origin text, so raw HTML stays
 * escaped and the highlighter output is the only markup the renderer emits.
 */
export function createMarkdownRenderer(options: MarkdownRendererOptions): MarkdownIt {
  const md = new MarkdownIt({
    html: false,
    breaks: options.breaks,
    linkify: true,
  })
  // Assigned after construction so the fallback path can reuse this instance's
  // escapeHtml without keeping a second renderer around.
  md.options.highlight = (source: string, lang: string) => highlightCode(md, source, lang)
  return md
}
