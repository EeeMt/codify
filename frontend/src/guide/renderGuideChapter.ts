import { createMarkdownRenderer, highlightCode } from '../utils/markdown'

export interface GuideHeading {
  id: string
  text: string
  level: 2 | 3
}

export interface RenderedGuideChapter {
  html: string
  headings: GuideHeading[]
}

export interface GuideRenderEnv {
  /** Label rendered on the per-code-block copy button. */
  copyLabel: string
  /** Token indices of paragraphs that hold nothing but an image. */
  figureParagraphs: Set<number>
  /** True while rendering inside a figure paragraph, so the image can caption itself. */
  inFigure: boolean
}

const md = createMarkdownRenderer({ breaks: false })

const ASSET_URLS = import.meta.glob('./assets/**/*.{svg,png,jpg,jpeg,webp,gif}', {
  query: '?url',
  import: 'default',
  eager: true,
}) as Record<string, string>

function resolveAsset(source: string): string | null {
  if (/^[a-z]+:/i.test(source) || source.startsWith('/')) return null
  return ASSET_URLS[`./${source.replace(/^\.\//, '')}`] ?? null
}

/** Keeps CJK letters so headings in both locales get a stable, readable anchor. */
function slugify(text: string): string {
  const base = text
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
  return base || 'section'
}

function uniqueId(base: string, seen: Map<string, number>): string {
  const count = seen.get(base) ?? 0
  seen.set(base, count + 1)
  return count === 0 ? base : `${base}-${count + 1}`
}

function codeBlock(env: GuideRenderEnv, source: string, lang: string): string {
  return [
    '<div class="guide-code">',
    `<button type="button" class="guide-code__copy" data-guide-copy="${md.utils.escapeHtml(env.copyLabel)}">${md.utils.escapeHtml(env.copyLabel)}</button>`,
    highlightCode(md, source, lang),
    '</div>',
  ].join('')
}

md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const info = token.info.trim().split(/\s+/)[0]?.toLowerCase() ?? ''
  if (info) return codeBlock(env as GuideRenderEnv, token.content, info)
  return self.renderToken(tokens, idx, options)
}

md.renderer.rules.image = (tokens, idx, options, env, self) => {
  const guideEnv = env as GuideRenderEnv
  const token = tokens[idx]
  const source = token.attrGet('src') ?? ''
  const resolved = resolveAsset(source)
  if (resolved) token.attrSet('src', resolved)

  // Deliberately not lazy: a lazily loaded figure reserves no space, so the
  // chapter shifts under the reader as diagrams arrive. The SVGs are 15-25 kB.
  const image = self.renderToken(tokens, idx, options)
  const caption = token.content.trim()
  if (!guideEnv.inFigure || !caption) return image
  return `${image}<figcaption class="guide-figure__caption">${md.utils.escapeHtml(caption)}</figcaption>`
}

md.renderer.rules.link_open = (tokens, idx, options, _env, self) => {
  const href = tokens[idx].attrGet('href') ?? ''
  const asset = resolveAsset(href)
  if (asset) {
    // Bundled guides assets (the feature map) are opened on their own so the
    // reader gets the full-resolution diagram.
    tokens[idx].attrSet('href', asset)
    tokens[idx].attrSet('target', '_blank')
    tokens[idx].attrSet('rel', 'noopener noreferrer')
    return self.renderToken(tokens, idx, options)
  }
  if (/^https?:\/\//i.test(href)) {
    tokens[idx].attrSet('target', '_blank')
    tokens[idx].attrSet('rel', 'noopener noreferrer')
  }
  return self.renderToken(tokens, idx, options)
}

/**
 * A paragraph holding nothing but an image is a figure, not prose: it must not
 * inherit the prose measure, or the diagram gets scaled down inside the text
 * column. Those paragraphs become a <figure> whose caption is the alt text.
 */
md.renderer.rules.paragraph_open = (tokens, idx, options, env, self) => {
  const guideEnv = env as GuideRenderEnv
  if (!guideEnv.figureParagraphs.has(idx)) return self.renderToken(tokens, idx, options)
  guideEnv.inFigure = true
  return '<figure class="guide-figure">'
}

md.renderer.rules.paragraph_close = (tokens, idx, options, env, self) => {
  const guideEnv = env as GuideRenderEnv
  if (!guideEnv.figureParagraphs.has(idx - 2)) return self.renderToken(tokens, idx, options)
  guideEnv.inFigure = false
  return '</figure>'
}

/**
 * Parse and render in one pass so the table of contents and the rendered
 * headings always carry the same generated ids.
 */
export function renderGuideChapter(markdown: string, options: { copyLabel: string }): RenderedGuideChapter {
  if (!markdown) return { html: '', headings: [] }

  const env: GuideRenderEnv = { copyLabel: options.copyLabel, figureParagraphs: new Set(), inFigure: false }
  const tokens = md.parse(markdown, env)
  const headings: GuideHeading[] = []
  const seen = new Map<string, number>()

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index]

    if (token.type === 'paragraph_open') {
      const inline = tokens[index + 1]
      const children = inline?.type === 'inline' ? inline.children ?? [] : []
      if (tokens[index + 2]?.type === 'paragraph_close' && children.length === 1 && children[0].type === 'image') {
        env.figureParagraphs.add(index)
      }
      continue
    }

    if (token.type !== 'heading_open') continue
    const level = Number(token.tag.slice(1))
    if (level !== 2 && level !== 3) continue

    const inline = tokens[index + 1]
    const text = (inline?.children ?? [])
      .map((child) => {
        if (child.type === 'text' || child.type === 'code_inline') return child.content
        if (child.type === 'softbreak' || child.type === 'hardbreak') return ' '
        return ''
      })
      .join('') || inline?.content || ''
    const id = uniqueId(slugify(text), seen)
    token.attrSet('id', id)
    headings.push({ id, text, level })
  }

  return { html: md.renderer.render(tokens, md.options, env), headings }
}
