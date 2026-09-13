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

/** The subset of an inline token this module reads; keeps the helper type-free. */
interface InlineLike {
  children?: { type: string; content: string }[] | null
  content?: string
}

type GuideCalloutKind = 'info' | 'tip' | 'warning' | 'success' | 'route'

const CALLOUT_MARKER = /^\[!(info|note|tip|warning|success|route)\]\s*/i

function calloutKind(inline: InlineLike | undefined): { kind: GuideCalloutKind; length: number } | null {
  const match = CALLOUT_MARKER.exec(inline?.content ?? '')
  if (!match) return null
  const rawKind = match[1].toLowerCase()
  return {
    kind: rawKind === 'note' ? 'info' : (rawKind as GuideCalloutKind),
    length: match[0].length,
  }
}

function removeCalloutMarker(inline: InlineLike, length: number): void {
  inline.content = (inline.content ?? '').slice(length)
  let remaining = length
  for (const child of inline.children ?? []) {
    if (remaining <= 0) break
    if (child.type !== 'text') continue
    const removed = Math.min(remaining, child.content.length)
    child.content = child.content.slice(removed)
    remaining -= removed
  }
}

/** Plain text of a heading, with inline markup flattened to its text. */
function inlineText(token: InlineLike | undefined): string {
  const children = token?.children
  if (!children || !children.length) return token?.content ?? ''
  let text = ''
  for (const child of children) {
    if (child.type === 'text' || child.type === 'code_inline') text += child.content
    else if (child.type === 'softbreak' || child.type === 'hardbreak') text += ' '
  }
  return text
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
  const fullSizeImage = resolved
    ? `<a class="guide-figure__image-link" href="${md.utils.escapeHtml(resolved)}" target="_blank" rel="noopener noreferrer" aria-label="${md.utils.escapeHtml(caption)}">${image}</a>`
    : image
  return `${fullSizeImage}<figcaption class="guide-figure__caption">${md.utils.escapeHtml(caption)}</figcaption>`
}

md.renderer.rules.blockquote_open = (tokens, idx, options, _env, self) => {
  const inline = tokens[idx + 2] as unknown as InlineLike | undefined
  const marker = calloutKind(inline)
  if (marker && inline) {
    removeCalloutMarker(inline, marker.length)
    const existing = tokens[idx].attrGet('class')
    tokens[idx].attrSet(
      'class',
      [existing, 'guide-callout', `guide-callout--${marker.kind}`].filter(Boolean).join(' '),
    )
    tokens[idx].attrSet('data-guide-callout', marker.kind)
  }
  return self.renderToken(tokens, idx, options)
}

md.renderer.rules.table_open = () => '<div class="guide-table"><table>'
md.renderer.rules.table_close = () => '</table></div>'

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

    const text = inlineText(tokens[index + 1])
    const id = uniqueId(slugify(text), seen)
    token.attrSet('id', id)
    headings.push({ id, text, level })
  }

  return { html: md.renderer.render(tokens, md.options, env), headings }
}

export interface GuideChapterIndex {
  /** The same anchors the renderer generates, so a hit can be linked to. */
  headings: GuideHeading[]
  /** Raw plain text of the chapter, for body matches and snippets. */
  text: string
}

/**
 * Build a chapter's search index. Headings go through the same slug and
 * de-duplication path as rendering, so a search hit links to the exact anchor
 * the chapter renders.
 */
export function indexGuideChapter(markdown: string): GuideChapterIndex {
  if (!markdown) return { headings: [], text: '' }

  const env: GuideRenderEnv = { copyLabel: '', figureParagraphs: new Set(), inFigure: false }
  const tokens = md.parse(markdown, env)
  const headings: GuideHeading[] = []
  const seen = new Map<string, number>()
  const text: string[] = []

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index]
    if (token.type === 'heading_open') {
      const level = Number(token.tag.slice(1))
      if (level !== 2 && level !== 3) continue
      const headingText = inlineText(tokens[index + 1])
      headings.push({ id: uniqueId(slugify(headingText), seen), text: headingText, level })
      continue
    }
    if (token.type === 'inline') text.push(token.content)
  }

  return { headings, text: text.join(' ') }
}
