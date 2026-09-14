import { parse as parseYaml } from 'yaml'
import type { AppLocale } from '../i18n'
import { GUIDE_TIERS, isGuideTier, type GuideTier } from './guideTiers'

/** The two guide audiences; both are rendered from the same chapter list. */
export type GuideSectionKey = 'user' | 'admin'

export interface GuideChapter {
  /** ASCII route slug, e.g. `30-create-task`. */
  slug: string
  /** Numeric prefix of the file name; also the reading order. */
  order: number
  section: GuideSectionKey
  /** How strongly a reader should read this chapter, before per-heading overrides. */
  tier: GuideTier
  title: string
  /** Markdown body with the front matter removed. */
  body: string
}

export interface GuideSection {
  key: GuideSectionKey
  chapters: GuideChapter[]
}

/** One audience section's tier band, in reading order, for the sidebar. */
export interface GuideTierGroup {
  section: GuideSectionKey
  tier: GuideTier
  chapters: GuideChapter[]
}

/**
 * Markdown sources are inlined at build time: the guide ships inside the SPA
 * bundle, so it works offline and inherits the app's session instead of
 * needing a separately served (and separately authorised) docs site.
 */
const CHAPTER_SOURCES = import.meta.glob('./*/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const SOURCE_PATH = /^\.\/([^/]+)\/(\d+)-([^/]+)\.md$/
const FRONT_MATTER = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/
const SECTION_KEYS: Record<string, GuideSectionKey> = {
  'User Guide': 'user',
  'Admin Guide': 'admin',
}

function fail(path: string, reason: string): never {
  throw new Error(`Guide chapter ${path} is invalid: ${reason}`)
}

function parseChapter(path: string, source: string): { locale: AppLocale, chapter: GuideChapter } {
  const match = SOURCE_PATH.exec(path)
  if (!match) fail(path, 'file name must look like <locale>/<order>-<slug>.md')

  const [, localeName, orderText, slug] = match
  if (localeName !== 'en' && localeName !== 'zh-CN') {
    fail(path, `unknown locale directory "${localeName}"`)
  }

  const matter = FRONT_MATTER.exec(source)
  if (!matter) fail(path, 'missing YAML front matter block')

  const meta = (parseYaml(matter[1]) ?? {}) as Record<string, unknown>
  const title = meta.title
  const sectionLabel = meta.section
  const tierLabel = meta.tier
  if (typeof title !== 'string' || !title.trim()) fail(path, 'front matter needs a non-empty "title"')
  if (typeof sectionLabel !== 'string') fail(path, 'front matter needs a "section"')
  const section = SECTION_KEYS[sectionLabel]
  if (!section) fail(path, `unknown section "${sectionLabel}"`)
  if (!isGuideTier(tierLabel)) fail(path, `front matter needs a "tier" of ${GUIDE_TIERS.join(', ')}`)

  return {
    locale: localeName,
    chapter: {
      slug: `${orderText}-${slug}`,
      order: Number(orderText),
      section,
      tier: tierLabel,
      title: title.trim(),
      body: source.slice(matter[0].length),
    },
  }
}

const byLocale = new Map<AppLocale, GuideChapter[]>()

for (const [path, source] of Object.entries(CHAPTER_SOURCES)) {
  const { locale, chapter } = parseChapter(path, source)
  const chapters = byLocale.get(locale) ?? []
  if (chapters.some((existing) => existing.order === chapter.order)) {
    fail(path, `order ${chapter.order} is already used in ${locale}`)
  }
  chapters.push(chapter)
  byLocale.set(locale, chapters)
}

for (const chapters of byLocale.values()) {
  chapters.sort((a, b) => a.order - b.order)
}

export function guideChapters(locale: AppLocale): GuideChapter[] {
  return byLocale.get(locale) ?? []
}

/** Sections in reading order, so a new section only needs a front matter label. */
export function guideSections(locale: AppLocale): GuideSection[] {
  const sections: GuideSection[] = []
  for (const chapter of guideChapters(locale)) {
    const section = sections.find((entry) => entry.key === chapter.section)
    if (section) {
      section.chapters.push(chapter)
    } else {
      sections.push({ key: chapter.section, chapters: [chapter] })
    }
  }
  return sections
}

/**
 * Chapters grouped by audience, then by tier, both in reading order. The tier
 * numbering is tier-major inside a section, so the sidebar's groups come out in
 * the order the reader is meant to meet them.
 */
export function guideTierGroups(locale: AppLocale): GuideTierGroup[] {
  const groups: GuideTierGroup[] = []
  for (const chapter of guideChapters(locale)) {
    const group = groups.find((entry) => entry.section === chapter.section && entry.tier === chapter.tier)
    if (group) {
      group.chapters.push(chapter)
    } else {
      groups.push({ section: chapter.section, tier: chapter.tier, chapters: [chapter] })
    }
  }
  return groups
}
