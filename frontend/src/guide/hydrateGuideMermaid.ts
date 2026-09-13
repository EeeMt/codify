import { getMermaidRenderer } from '../vendor/mermaid'

const PENDING_SELECTOR = '[data-guide-mermaid-state="pending"]'

function replaceWithError(element: HTMLElement, source: string, error: unknown): void {
  element.dataset.guideMermaidState = 'error'
  element.replaceChildren()

  const message = document.createElement('p')
  message.className = 'guide-mermaid__error'
  message.textContent = error instanceof Error ? error.message : String(error)

  const pre = document.createElement('pre')
  pre.className = 'md-code-block hljs'
  const code = document.createElement('code')
  code.textContent = source
  pre.append(code)

  element.append(message, pre)
}

/**
 * Diagrams are injected into already-rendered markdown rather than rendered by
 * Vue: mermaid is a lazily loaded bundle that writes its own SVG, exactly like
 * the task summary viewer. Rendering is sequential so a failure never leaves a
 * half-drawn diagram in a later block.
 */
export async function hydrateGuideMermaid(root: HTMLElement | null): Promise<void> {
  if (!root) return

  const pending = Array.from(root.querySelectorAll<HTMLElement>(PENDING_SELECTOR))
  if (!pending.length) return

  let mermaid
  try {
    mermaid = await getMermaidRenderer()
  } catch (error) {
    for (const element of pending) {
      replaceWithError(element, element.dataset.guideMermaidSource ?? '', error)
    }
    return
  }

  let rendered = 0
  for (const element of pending) {
    if (!element.isConnected || element.dataset.guideMermaidState !== 'pending') continue

    const source = element.dataset.guideMermaidSource ?? ''
    rendered += 1
    const renderId = `guide-mermaid-${rendered}`

    try {
      const { svg } = await mermaid.render(renderId, source)
      element.innerHTML = svg
      element.dataset.guideMermaidState = 'done'
    } catch (error) {
      replaceWithError(element, source, error)
      // mermaid leaves its measuring element behind when parsing fails.
      document.getElementById(`d${renderId}`)?.remove()
    }
  }
}
