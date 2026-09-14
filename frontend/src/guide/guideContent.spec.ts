import { describe, expect, it } from 'vitest'
import { guideChapters, guideSections, guideTierGroups } from './guideContent'
import { GUIDE_TIERS } from './guideTiers'

const LOCALES = ['en', 'zh-CN'] as const

const CHAPTER_SOURCES = import.meta.glob('./*/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const ASSET_URLS = import.meta.glob('./assets/**/*.{svg,png,jpg,jpeg,webp,gif}', {
  query: '?url',
  import: 'default',
  eager: true,
}) as Record<string, string>

/** Code fences and inline code may legitimately contain markup examples. */
function stripCode(body: string): string {
  return body.replace(/```[\s\S]*?```/g, '').replace(/`[^`]*`/g, '')
}

function headingLevels(body: string): number[] {
  const levels: number[] = []
  for (const line of body.split('\n')) {
    const match = /^(#{2,3})\s+\S/.exec(line)
    if (match) levels.push(match[1].length)
  }
  return levels
}

function imageTargets(body: string): string[] {
  const targets: string[] = []
  for (const match of body.matchAll(/!\[[^\]]*\]\(([^)\s]+)\)/g)) targets.push(match[1])
  return targets
}

/** Markdown links to bundled assets, e.g. the feature map opened at full size. */
function assetLinks(body: string): string[] {
  const targets: string[] = []
  for (const match of body.matchAll(/(?<!!)\[[^\]]*\]\((assets\/[^)\s]+)\)/g)) targets.push(match[1])
  return targets
}

describe('guide content', () => {
  it('exposes the same chapters in both locales', () => {
    const [reference, ...rest] = LOCALES.map((locale) =>
      guideChapters(locale).map((chapter) => chapter.slug),
    )

    expect(reference.length).toBeGreaterThan(0)
    for (const slugs of rest) expect(slugs).toEqual(reference)
  })

  it('orders user chapters before admin chapters and labels both sections', () => {
    for (const locale of LOCALES) {
      const sections = guideSections(locale)
      expect(sections.map((section) => section.key)).toEqual(['user', 'admin'])

      const userOrders = sections[0].chapters.map((chapter) => chapter.order)
      const adminOrders = sections[1].chapters.map((chapter) => chapter.order)
      expect(Math.max(...userOrders)).toBeLessThan(Math.min(...adminOrders))
    }
  })

  it('gives every chapter a title and a numeric reading order', () => {
    for (const locale of LOCALES) {
      for (const chapter of guideChapters(locale)) {
        expect(chapter.title.trim(), `${locale}/${chapter.slug} title`).not.toBe('')
        expect(Number.isInteger(chapter.order), `${locale}/${chapter.slug} order`).toBe(true)
        expect(chapter.body.trim().length, `${locale}/${chapter.slug} body`).toBeGreaterThan(200)
      }
    }
  })

  it('mirrors the mandatory h2 outline in both locales', () => {
    // The contract fixes the `##` outline per chapter and explicitly allows
    // locale-specific `###` sub-structure, so only the h2 sequence has to match.
    const h2Count = (body: string) => headingLevels(body).filter((level) => level === 2).length
    for (const chapter of guideChapters('en')) {
      const translated = guideChapters('zh-CN').find((entry) => entry.slug === chapter.slug)
      expect(translated, `zh-CN/${chapter.slug} is missing`).toBeTruthy()
      expect(h2Count(translated!.body), `${chapter.slug} h2 outline drifted between locales`).toBe(
        h2Count(chapter.body),
      )
    }
  })

  it('declares only title, section, and tier in front matter', () => {
    for (const [path, source] of Object.entries(CHAPTER_SOURCES)) {
      const matter = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(source)
      expect(matter, `${path} has no front matter`).toBeTruthy()
      const keys = matter![1]
        .split('\n')
        .map((line) => line.split(':')[0].trim())
        .filter(Boolean)
      expect(keys.sort(), `${path} front matter keys`).toEqual(['section', 'tier', 'title'])
    }
  })

  it('assigns every chapter a tier and groups them in reading order', () => {
    for (const locale of LOCALES) {
      const byTier = new Map<string, string>()
      for (const chapter of guideChapters(locale)) byTier.set(chapter.slug, chapter.tier)
      for (const [slug, tier] of byTier) {
        expect(GUIDE_TIERS, `${locale}/${slug} tier`).toContain(tier)
      }

      const groups = guideTierGroups(locale)
      expect(groups.length, `${locale} tier groups`).toBeGreaterThan(0)
      const grouped = groups.flatMap((group) => group.chapters)
      expect(grouped.map((chapter) => chapter.slug), `${locale} grouping loses no chapter`).toEqual(
        guideChapters(locale).map((chapter) => chapter.slug),
      )

      // A section's tiers run core -> deep -> tips, and each tier's chapters are
      // contiguous, because the sidebar renders the groups in this order.
      for (const section of guideSections(locale)) {
        const tiers = groups
          .filter((group) => group.section === section.key)
          .map((group) => group.tier)
        expect(tiers, `${locale}/${section.key} tier order`).toEqual(
          GUIDE_TIERS.filter((tier) => tiers.includes(tier)),
        )
      }
    }
  })

  it('gives each chapter the same tier in both locales', () => {
    for (const chapter of guideChapters('en')) {
      const translated = guideChapters('zh-CN').find((entry) => entry.slug === chapter.slug)
      expect(translated, `zh-CN/${chapter.slug} is missing`).toBeTruthy()
      expect(translated!.tier, `${chapter.slug} tier drifted between locales`).toBe(chapter.tier)
    }
  })

  it('renders no raw HTML outside code samples', () => {
    for (const locale of LOCALES) {
      for (const chapter of guideChapters(locale)) {
        const prose = stripCode(chapter.body)
        const tag = /<\/?[a-z][a-z0-9-]*(\s|>|\/)/i.exec(prose)
        expect(tag?.[0] ?? null, `${locale}/${chapter.slug} contains raw HTML: ${tag?.[0]}`).toBeNull()
      }
    }
  })

  it('references only assets that exist', () => {
    for (const locale of LOCALES) {
      for (const chapter of guideChapters(locale)) {
        for (const target of [...imageTargets(chapter.body), ...assetLinks(chapter.body)]) {
          expect(
            ASSET_URLS[`./${target.replace(/^\.\//, '')}`],
            `${locale}/${chapter.slug} references missing asset ${target}`,
          ).toBeTruthy()
        }
      }
    }
  })

  it('ships every locale with the same asset references', () => {
    // Diagram files live in a per-locale directory, so compare the paths with
    // the locale segment normalized away.
    const localeNeutral = (target: string) =>
      target.replace(/^assets\/diagrams\/(zh-CN|en)\//, 'assets/diagrams/<locale>/')
    const targets = (body: string) =>
      [...imageTargets(body), ...assetLinks(body)].map(localeNeutral)

    for (const chapter of guideChapters('en')) {
      const translated = guideChapters('zh-CN').find((entry) => entry.slug === chapter.slug)!
      expect(targets(translated.body), `${chapter.slug} assets drifted between locales`).toEqual(
        targets(chapter.body),
      )
    }
  })

  it('pins every diagram to its intrinsic size', () => {
    // d2 omits width/height on the root <svg>, and an <img> that embeds such a
    // file falls back to a default intrinsic size, so the diagram is drawn at
    // the wrong aspect ratio. scripts/guide/render-diagrams.py pins the viewBox
    // size onto the root element; this fails if a bare `d2` render is committed.
    const diagrams = import.meta.glob('./assets/diagrams/*/*.svg', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>

    const paths = Object.keys(diagrams)
    expect(paths.length, 'no diagram assets found').toBeGreaterThan(0)

    for (const [path, svg] of Object.entries(diagrams)) {
      const rootTag = /<svg\b[^>]*>/.exec(svg)?.[0] ?? ''
      const viewBox = /viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(rootTag)
      expect(viewBox, `${path} has no '0 0 W H' viewBox`).toBeTruthy()
      expect(rootTag, `${path} is missing its intrinsic size`).toContain(
        `width="${viewBox![1]}" height="${viewBox![2]}"`,
      )
    }
  })

  it('uses bundled diagrams rather than mermaid fences', () => {
    // The guide standardized on pre-rendered d2 SVGs. A mermaid fence would
    // silently render as a plain code block instead of a diagram.
    for (const locale of LOCALES) {
      for (const chapter of guideChapters(locale)) {
        expect(
          chapter.body.includes('```mermaid'),
          `${locale}/${chapter.slug} still contains a mermaid fence; use a d2 diagram in assets/diagrams/ instead`,
        ).toBe(false)
      }
    }
  })
})
