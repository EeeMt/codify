import { describe, expect, it } from 'vitest'
import { indexGuideChapter, renderGuideChapter } from './renderGuideChapter'

const ENV = { copyLabel: 'Copy' }

describe('renderGuideChapter', () => {
  it('collects h2 and h3 headings into a table of contents', () => {
    const { headings } = renderGuideChapter(
      ['## First', 'text', '### Nested', 'text', '#### Too deep'].join('\n\n'),
      ENV,
    )

    expect(headings.map((heading) => heading.text)).toEqual(['First', 'Nested'])
    expect(headings.map((heading) => heading.level)).toEqual([2, 3])
  })

  it('uses the same ids in the table of contents and the rendered html', () => {
    const { html, headings } = renderGuideChapter('## Task lifecycle\n\n## Task lifecycle', ENV)

    expect(headings.map((heading) => heading.id)).toEqual(['task-lifecycle', 'task-lifecycle-2'])
    for (const heading of headings) expect(html).toContain(`id="${heading.id}"`)
  })

  it('derives a stable anchor from a Chinese heading', () => {
    const { headings } = renderGuideChapter('## 任务状态机', ENV)

    expect(headings[0]?.id).toBe('任务状态机')
  })

  it('indexes the same anchors the renderer generates', () => {
    const markdown = '## Task lifecycle\n\nBody text here.\n\n### Cancel a task\n\nMore.'
    const { headings: rendered } = renderGuideChapter(markdown, { copyLabel: 'Copy' })
    const { headings: indexed, text } = indexGuideChapter(markdown)

    expect(indexed).toEqual(rendered)
    expect(text).toContain('Body text here.')
    expect(text).toContain('More.')
  })

  it('de-duplicates heading anchors in the index exactly as rendering does', () => {
    const { headings } = indexGuideChapter('## Retry\n\n## Retry')

    expect(headings.map((heading) => heading.id)).toEqual(['retry', 'retry-2'])
  })

  it('returns an empty index for an empty chapter', () => {
    expect(indexGuideChapter('')).toEqual({ headings: [], text: '' })
  })

  it('renders a standalone image as a captioned figure', () => {
    // A figure must not inherit the prose measure, or the diagram is scaled
    // down inside the text column; the alt text becomes its caption.
    const { html } = renderGuideChapter('![Where a task waits](assets/diagrams/en/task-lifecycle.svg)', ENV)

    expect(html).toContain('<figure class="guide-figure">')
    expect(html).toContain('<figcaption class="guide-figure__caption">Where a task waits</figcaption>')
    expect(html).not.toContain('<p><img')
  })

  it('keeps an image inline when it sits inside a sentence', () => {
    const { html } = renderGuideChapter('See ![diagram](assets/diagrams/en/task-lifecycle.svg) for details.', ENV)

    expect(html).toContain('<p>')
    expect(html).not.toContain('<figure')
  })

  it('renders semantic callouts without exposing the markdown marker', () => {
    const { html } = renderGuideChapter('> [!tip] **Tip** — keep one Issue for one line of work.', ENV)

    expect(html).toContain('class="guide-callout guide-callout--tip"')
    expect(html).toContain('data-guide-callout="tip"')
    expect(html).toContain('<strong>Tip</strong>')
    expect(html).not.toContain('[!tip]')
  })

  it('wraps guide tables so wide reference rows can scroll independently', () => {
    const { html } = renderGuideChapter('| Field | Meaning |\n| --- | --- |\n| Issue | Work unit |', ENV)

    expect(html).toContain('<div class="guide-table"><table>')
    expect(html).toContain('</table></div>')
  })

  it('wraps a code fence with a copy button and escapes its content', () => {
    const { html } = renderGuideChapter('```bash\nmake test-unit\n```\n', ENV)

    expect(html).toContain('data-guide-copy="Copy"')
    expect(html).toContain('make test-unit')
    expect(html).toContain('md-code-block')
  })

  it('marks external links to open in a new tab', () => {
    const { html } = renderGuideChapter('[docs](https://example.com/a)', ENV)

    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('leaves internal links untouched', () => {
    const { html } = renderGuideChapter('[tasks](/tasks)', ENV)

    expect(html).toContain('href="/tasks"')
    expect(html).not.toContain('target="_blank"')
  })

  it('opens a bundled asset link on its own', () => {
    const { html } = renderGuideChapter('[map](assets/diagrams/en/task-lifecycle.svg)', ENV)

    expect(html).toContain('task-lifecycle')
    expect(html).toContain('target="_blank"')
    expect(html).not.toContain('href="assets/diagrams/en/task-lifecycle.svg"')
  })

  it('returns an empty render for an empty chapter', () => {
    expect(renderGuideChapter('', ENV)).toEqual({ html: '', headings: [] })
  })
})
