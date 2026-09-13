import { describe, expect, it } from 'vitest'
import { renderGuideChapter } from './renderGuideChapter'

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

  it('turns a mermaid fence into a placeholder carrying the diagram source', () => {
    const source = 'flowchart LR\n  A["创建 Issue"] --> B["任务"]'
    const { html } = renderGuideChapter(`\`\`\`mermaid\n${source}\n\`\`\`\n`, ENV)

    expect(html).toContain('data-guide-mermaid-state="pending"')
    expect(html).toContain('data-guide-mermaid-source=')
    expect(html).toContain('创建 Issue')
    expect(html).not.toContain('md-code-block')
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
    const { html } = renderGuideChapter('[map](assets/feature-map.svg)', ENV)

    expect(html).toContain('feature-map')
    expect(html).toContain('target="_blank"')
    expect(html).not.toContain('href="assets/feature-map.svg"')
  })

  it('returns an empty render for an empty chapter', () => {
    expect(renderGuideChapter('', ENV)).toEqual({ html: '', headings: [] })
  })
})
