<template>
  <section class="guide-page">
    <header class="guide-page__header">
      <div class="guide-page__header-art" aria-hidden="true" />
      <div class="guide-page__header-content">
        <div class="guide-page__header-copy">
          <p class="guide-page__eyebrow">
            <span class="guide-page__eyebrow-mark" aria-hidden="true">
              <n-icon :component="BookOutline" size="15" />
            </span>
            {{ t('guide.tocLabel') }}
          </p>
          <h1 class="guide-page__title">{{ t('guide.title') }}</h1>
          <p class="guide-page__subtitle">{{ t('guide.subtitle') }}</p>
        </div>

        <div class="guide-page__header-tool">
          <span class="guide-search__label">{{ t('guide.searchPlaceholder') }}</span>
          <div class="guide-search">
            <n-input
              v-model:value="searchQuery"
              class="guide-search__input"
              size="small"
              clearable
              :aria-label="t('guide.searchPlaceholder')"
              :placeholder="t('guide.searchPlaceholder')"
              @focus="searchFocused = true"
              @blur="searchFocused = false"
              @keydown.enter="openFirstHit"
            >
              <template #prefix>
                <n-icon :component="SearchOutline" />
              </template>
            </n-input>

            <ul v-if="showSearchResults" class="guide-search__results">
              <li v-for="hit in searchHits" :key="`${hit.kind}:${hit.slug}:${hit.headingId ?? ''}`">
                <button type="button" class="guide-search__hit" @mousedown.prevent="openHit(hit)">
                  <span class="guide-search__hit-label">{{ hit.label }}</span>
                  <span class="guide-search__hit-meta">
                    {{ hit.kind === 'chapter' ? t('guide.searchChapter') : hit.chapterTitle }}
                  </span>
                  <span v-if="hit.snippet" class="guide-search__hit-snippet">{{ hit.snippet }}</span>
                </button>
              </li>
            </ul>

            <p v-else-if="searchActive" class="guide-search__empty">{{ t('guide.searchEmpty') }}</p>
          </div>
          <p class="guide-page__tool-hint">{{ activeChapter?.title }}</p>
        </div>
      </div>

      <div class="guide-page__header-rule" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </header>

    <div class="guide-page__body">
      <aside class="guide-nav" :aria-label="t('guide.tocLabel')">
        <div class="guide-nav__panel">
          <div class="guide-nav__topline">
            <n-icon class="guide-nav__topline-icon" :component="BookOutline" size="14" aria-hidden="true" />
            <span>{{ t('guide.tocLabel') }}</span>
          </div>
          <n-scrollbar class="guide-nav__scroll" trigger="hover" content-style="padding-right: 2px;">
            <template v-for="section in navSections" :key="section.key">
              <p class="guide-nav__section">{{ t(SECTION_LABEL[section.key]) }}</p>
              <template v-for="group in section.groups" :key="group.tier">
                <section class="guide-nav__tier-group">
                  <h3 class="guide-nav__tier">{{ t(TIER_LABEL[group.tier]) }}</h3>
                  <ul class="guide-nav__list">
                    <li v-for="chapter in group.chapters" :key="chapter.slug">
                      <RouterLink
                        class="guide-nav__chapter"
                        :class="{ 'guide-nav__chapter--active': chapter.slug === activeChapter?.slug }"
                        :to="{ name: 'Guide', params: { chapter: chapter.slug } }"
                      >
                        {{ chapter.title }}
                      </RouterLink>
                      <ul v-if="chapter.slug === activeChapter?.slug && headings.length" class="guide-nav__headings">
                        <li v-for="heading in headings" :key="heading.id">
                          <a
                            class="guide-nav__heading"
                            :class="`guide-nav__heading--level-${heading.level}`"
                            :href="`#${heading.id}`"
                            @click.prevent="revealHeading(heading.id)"
                          >
                            <span
                              class="guide-nav__heading-tier"
                              :data-guide-tier="heading.tier ?? undefined"
                              aria-hidden="true"
                            />
                            <span class="guide-nav__heading-text">{{ heading.text }}</span>
                          </a>
                        </li>
                      </ul>
                    </li>
                  </ul>
                </section>
              </template>
            </template>
          </n-scrollbar>
        </div>
      </aside>

      <article ref="contentRef" class="guide-content">
        <div class="guide-content__chapter-heading">
          <span class="guide-content__chapter-index" aria-hidden="true">
            <n-icon :component="activeChapterIcon" size="15" />
            <span>{{ activeChapterNumber }}</span>
          </span>
          <div>
            <p>{{ t('guide.title') }}</p>
            <h2>{{ activeChapter?.title }}</h2>
            <span
              v-if="activeChapter"
              class="guide-content__tier"
              :data-guide-tier="activeChapter.tier"
            >{{ t(TIER_LABEL[activeChapter.tier]) }}</span>
          </div>
        </div>
        <div v-if="activeSlidesVariant" class="guide-content__slides">
          <div class="guide-content__slides-heading">
            <span class="guide-content__slides-label">{{ t('guide.slides.label') }}</span>
            <span class="guide-content__slides-hint">{{ t('guide.slides.hint') }}</span>
          </div>
          <ProductSlides :key="`${activeChapter?.slug}:${currentLocale}`" :variant="activeSlidesVariant" compact />
        </div>
        <div
          class="guide-content__body markdown-content"
          @click="handleContentClick"
          v-html="html"
        />

        <nav class="guide-pager">
          <RouterLink
            v-if="previousChapter"
            class="guide-pager__link"
            :to="{ name: 'Guide', params: { chapter: previousChapter.slug } }"
          >
            <span class="guide-pager__direction">
              <n-icon :component="ArrowBackOutline" size="13" />
              {{ t('guide.previous') }}
            </span>
            <span class="guide-pager__title">{{ previousChapter.title }}</span>
          </RouterLink>
          <span v-else />
          <RouterLink
            v-if="nextChapter"
            class="guide-pager__link guide-pager__link--next"
            :to="{ name: 'Guide', params: { chapter: nextChapter.slug } }"
          >
            <span class="guide-pager__direction">
              {{ t('guide.next') }}<n-icon :component="ChevronForwardOutline" size="13" />
            </span>
            <span class="guide-pager__title">{{ nextChapter.title }}</span>
          </RouterLink>
        </nav>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NIcon, NInput, NScrollbar } from 'naive-ui'
import {
  ArrowBackOutline,
  BookOutline,
  ChevronForwardOutline,
  SearchOutline,
  SettingsOutline,
  SparklesOutline,
} from '@vicons/ionicons5'

import { currentLocale, type AppLocale } from '../i18n'
import ProductSlides, { type ProductSlidesVariant } from '../components/ProductSlides.vue'
import {
  guideChapters,
  guideTierGroups,
  type GuideSectionKey,
  type GuideTierGroup,
} from '../guide/guideContent'
import type { GuideTier } from '../guide/guideTiers'
import { indexGuideChapter, renderGuideChapter, type GuideChapterIndex, type GuideHeading } from '../guide/renderGuideChapter'

const SECTION_LABEL: Record<GuideSectionKey, string> = {
  user: 'guide.sections.user',
  admin: 'guide.sections.admin',
}

const TIER_LABEL: Record<GuideTier, string> = {
  core: 'guide.tiers.core',
  deep: 'guide.tiers.deep',
  tips: 'guide.tiers.tips',
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const contentRef = ref<HTMLElement | null>(null)
const searchQuery = ref('')
const searchFocused = ref(false)
const html = ref('')
const headings = ref<GuideHeading[]>([])

// Guards against a slower render of a previous chapter overwriting a newer one.
let renderToken = 0
let hasRendered = false

interface GuideSearchHit {
  slug: string
  chapterTitle: string
  kind: 'chapter' | 'heading' | 'text'
  label: string
  headingId?: string
  snippet?: string
}

const SEARCH_LIMIT = 12
const SEARCH_HEADINGS_PER_CHAPTER = 3
const SNIPPET_RADIUS = 42

/**
 * Search runs over chapter titles, section headings and body text. The index is
 * built once per locale on first use: it reuses the renderer's heading ids, so a
 * hit can be linked to the anchor the chapter actually renders.
 */
const searchIndexes = new Map<AppLocale, Map<string, GuideChapterIndex>>()

function chapterIndex(locale: AppLocale): Map<string, GuideChapterIndex> {
  let index = searchIndexes.get(locale)
  if (!index) {
    index = new Map()
    for (const chapter of guideChapters(locale)) {
      index.set(chapter.slug, indexGuideChapter(chapter.body))
    }
    searchIndexes.set(locale, index)
  }
  return index
}

function snippetAround(text: string, query: string): string {
  const at = text.toLowerCase().indexOf(query)
  if (at < 0) return ''
  const start = Math.max(0, at - SNIPPET_RADIUS)
  const end = Math.min(text.length, at + query.length + SNIPPET_RADIUS)
  return `${start > 0 ? '…' : ''}${text.slice(start, end).trim()}${end < text.length ? '…' : ''}`
}

const searchHits = computed<GuideSearchHit[]>(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return []

  const index = chapterIndex(currentLocale.value)
  const titleHits: GuideSearchHit[] = []
  const headingHits: GuideSearchHit[] = []
  const bodyHits: GuideSearchHit[] = []

  for (const chapter of chapters.value) {
    const entry = index.get(chapter.slug)
    const titleMatches = chapter.title.toLowerCase().includes(query)
    if (titleMatches) {
      titleHits.push({
        slug: chapter.slug,
        chapterTitle: chapter.title,
        kind: 'chapter',
        label: chapter.title,
      })
    }

    let matchedHeadings = 0
    for (const heading of entry?.headings ?? []) {
      if (matchedHeadings >= SEARCH_HEADINGS_PER_CHAPTER) break
      if (!heading.text.toLowerCase().includes(query)) continue
      matchedHeadings += 1
      headingHits.push({
        slug: chapter.slug,
        chapterTitle: chapter.title,
        kind: 'heading',
        label: heading.text,
        headingId: heading.id,
      })
    }

    if (!titleMatches && entry && entry.text.toLowerCase().includes(query)) {
      bodyHits.push({
        slug: chapter.slug,
        chapterTitle: chapter.title,
        kind: 'text',
        label: chapter.title,
        snippet: snippetAround(entry.text, query),
      })
    }
  }

  return [...titleHits, ...headingHits, ...bodyHits].slice(0, SEARCH_LIMIT)
})

const searchActive = computed(() => searchFocused.value && searchQuery.value.trim().length > 0)
const showSearchResults = computed(() => searchActive.value && searchHits.value.length > 0)

function openHit(hit: GuideSearchHit): void {
  searchFocused.value = false
  searchQuery.value = ''
  void router.push({
    name: 'Guide',
    params: { chapter: hit.slug },
    hash: hit.headingId ? `#${hit.headingId}` : '',
  })
}

function openFirstHit(): void {
  const first = searchHits.value[0]
  if (first) openHit(first)
}

const tierGroups = computed(() => guideTierGroups(currentLocale.value))
const navSections = computed(() => {
  const sections: { key: GuideSectionKey; groups: GuideTierGroup[] }[] = []
  for (const group of tierGroups.value) {
    const last = sections[sections.length - 1]
    if (last?.key === group.section) last.groups.push(group)
    else sections.push({ key: group.section, groups: [group] })
  }
  return sections
})
const chapters = computed(() => tierGroups.value.flatMap((group) => group.chapters))
const tierLabels = computed<Record<GuideTier, string>>(() => ({
  core: t(TIER_LABEL.core),
  deep: t(TIER_LABEL.deep),
  tips: t(TIER_LABEL.tips),
}))

function chapterParam(): string | undefined {
  const value = route.params.chapter
  return Array.isArray(value) ? value[0] : value
}

const activeChapter = computed(() => {
  const param = chapterParam()
  return chapters.value.find((chapter) => chapter.slug === param) ?? chapters.value[0] ?? null
})

const activeIndex = computed(() =>
  activeChapter.value
    ? chapters.value.findIndex((chapter) => chapter.slug === activeChapter.value?.slug)
    : -1,
)
const activeChapterNumber = computed(() => String(Math.max(activeIndex.value, 0) + 1).padStart(2, '0'))
const activeChapterIcon = computed(() =>
  activeChapter.value?.section === 'admin' ? SettingsOutline : SparklesOutline,
)
const previousChapter = computed(() =>
  activeIndex.value > 0 ? chapters.value[activeIndex.value - 1] : null,
)
const nextChapter = computed(() =>
  activeIndex.value >= 0 && activeIndex.value < chapters.value.length - 1
    ? chapters.value[activeIndex.value + 1]
    : null,
)
const activeSlidesVariant = computed<ProductSlidesVariant | null>(() => {
  switch (activeChapter.value?.slug) {
    case '10-quick-start':
      return 'quick-start'
    case '15-create-issue':
      return 'create-issue'
    case '58-how-it-works':
      return 'how-it-works'
    case '30-create-task':
      return 'create-task'
    case '50-delivery':
      return 'delivery'
    default:
      return null
  }
})

function findHeading(id: string): HTMLElement | null {
  const target = document.getElementById(id)
  return target && contentRef.value?.contains(target) ? target : null
}

function revealHeading(id: string): void {
  const target = findHeading(id)
  target?.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

function revealChapterStart(): void {
  const id = route.hash.replace(/^#/, '')
  const target = id ? findHeading(id) : null
  if (target) {
    target.scrollIntoView({ block: 'start' })
    return
  }
  // Keep the outer page position (the top bar may already be out of view), but
  // bring the newly selected right-hand chapter card back to the viewport top.
  if (hasRendered) contentRef.value?.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

async function writeClipboard(value: string, button: HTMLElement): Promise<void> {
  const restore = button.textContent
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
    } else {
      // The app is frequently served over plain HTTP, where the async clipboard
      // API is unavailable.
      const scratch = document.createElement('textarea')
      scratch.value = value
      scratch.setAttribute('readonly', '')
      scratch.style.position = 'fixed'
      scratch.style.opacity = '0'
      document.body.append(scratch)
      scratch.select()
      document.execCommand('copy')
      scratch.remove()
    }
    button.textContent = t('guide.copied')
  } catch {
    button.textContent = t('guide.copyFailed')
  }
  window.setTimeout(() => {
    button.textContent = restore
  }, 1500)
}

function handleContentClick(event: MouseEvent): void {
  const target = event.target as HTMLElement | null
  if (!target) return

  const copyButton = target.closest<HTMLElement>('[data-guide-copy]')
  if (copyButton) {
    const code = copyButton.parentElement?.querySelector('code')
    if (code) void writeClipboard(code.textContent ?? '', copyButton)
    return
  }

  const anchor = target.closest<HTMLAnchorElement>('a[href]')
  if (!anchor) return

  const href = anchor.getAttribute('href') ?? ''
  if (href.startsWith('#')) {
    event.preventDefault()
    revealHeading(href.slice(1))
    return
  }
  if (!href.startsWith('/')) return
  // Static assets and unknown paths belong to the browser; only real routes
  // are handled by the router.
  if (!router.resolve(href).matched.length) return
  event.preventDefault()
  void router.push(href)
}

// Keep the address bar canonical so a shared link always resolves to a chapter.
watch(
  [() => route.params.chapter, chapters],
  () => {
    const param = chapterParam()
    const first = chapters.value[0]
    if (!first) return
    if (param && chapters.value.some((chapter) => chapter.slug === param)) return
    void router.replace({ name: 'Guide', params: { chapter: first.slug } })
  },
  { immediate: true },
)

watch(
  [activeChapter, currentLocale],
  async () => {
    const chapter = activeChapter.value
    const token = (renderToken += 1)
    if (!chapter) {
      html.value = ''
      headings.value = []
      return
    }

    const rendered = renderGuideChapter(chapter.body, {
      copyLabel: t('guide.copyCode'),
      tierLabels: tierLabels.value,
    })
    if (token !== renderToken) return
    html.value = rendered.html
    headings.value = rendered.headings

    await nextTick()
    if (token !== renderToken) return
    revealChapterStart()
    hasRendered = true
  },
  { immediate: true },
)
</script>

<style scoped>
.guide-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  /* One measure for the whole page: the header subtitle would otherwise run to
     the shared 760px default and read as a second, wider column. */
  --app-page-subtitle-max-width: 560px;
}

.guide-page__header {
  position: relative;
  /* Above the chapter body: while pinned, content scrolls underneath it. */
  z-index: 3;
  background: #fff;
}

.guide-page__header--pinned {
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.07);
}

/* The title block wraps to two lines at this measure; centring the actions
   against it keeps the header from reading as a loose bar. */
.guide-page__header :deep(.page-header) {
  align-items: center;
}

.guide-search {
  position: relative;
  width: 260px;
}

.guide-search__results {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 5;
  width: 380px;
  max-height: 60vh;
  overflow-y: auto;
  margin: 0;
  padding: 6px;
  list-style: none;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.14);
}

.guide-search__hit {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.guide-search__hit:hover,
.guide-search__hit:focus-visible {
  background: rgba(148, 163, 184, 0.14);
}

.guide-search__hit-label {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.guide-search__hit-meta {
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(15, 23, 42, 0.45);
}

.guide-search__hit-snippet {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(15, 23, 42, 0.62);
}

.guide-search__empty {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  margin: 0;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.1);
  font-size: 12px;
  color: rgba(15, 23, 42, 0.55);
}

.guide-page__body {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 32px;
  align-items: start;
}

.guide-nav {
  /* Must span the full row height: the float's travel is bounded by how much
     taller the column is than the panel, so with `align-items: start` on the
     grid the panel could never move. The column itself stays invisible. */
  align-self: stretch;
  min-width: 0;
}

.guide-nav__panel {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 120px);
  padding: 12px 10px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.guide-page :deep(.guide-nav__scroll) {
  /* Keep the nav inside the card's flex track so Naive UI owns the scrollbar,
     while the page itself keeps one stable scrollport for sticky positioning. */
  flex: 1 1 auto;
  min-height: 0;
}

.guide-nav__section {
  margin: 12px 0 6px;
  padding: 0 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(15, 23, 42, 0.45);
}

.guide-nav__section:first-child {
  margin-top: 0;
}

/* A tier band inside an audience section: quieter than the section label, but
   still a heading so a reader can find the must-read group at a glance. */
.guide-nav__tier {
  margin: 8px 0 2px;
  padding: 0 12px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: rgba(15, 23, 42, 0.38);
}

.guide-nav__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.guide-nav__chapter {
  display: block;
  padding: 6px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.4;
  color: rgba(15, 23, 42, 0.72);
  text-decoration: none;
}

.guide-nav__chapter:hover {
  background: rgba(148, 163, 184, 0.14);
}

.guide-nav__chapter--active {
  background: linear-gradient(135deg, rgba(32, 128, 240, 0.18), rgba(32, 128, 240, 0.08));
  box-shadow: inset 0 0 0 1px rgba(32, 128, 240, 0.16);
  color: #1d4ed8;
  font-weight: 600;
}

.guide-nav__headings {
  margin: 2px 0 8px;
  padding: 0 0 0 12px;
  list-style: none;
  border-left: 1px solid rgba(15, 23, 42, 0.1);
}

.guide-nav__heading {
  display: block;
  padding: 3px 8px;
  font-size: 12px;
  line-height: 1.4;
  color: rgba(15, 23, 42, 0.6);
  text-decoration: none;
}

.guide-nav__heading:hover {
  color: #1d4ed8;
}

.guide-nav__heading--level-3 {
  padding-left: 18px;
  color: rgba(15, 23, 42, 0.5);
}

.guide-content {
  min-width: 0;
}

.guide-content__body {
  max-width: 860px;
}

.guide-pager {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  max-width: 860px;
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

.guide-pager__link {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 8px 12px;
  border-radius: 12px;
  text-decoration: none;
  color: inherit;
}

.guide-pager__link:hover {
  background: rgba(148, 163, 184, 0.14);
}

.guide-pager__link--next {
  align-items: flex-end;
  text-align: right;
}

.guide-pager__direction {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgba(15, 23, 42, 0.5);
}

.guide-pager__title {
  font-size: 13px;
  font-weight: 600;
  color: #1d4ed8;
}

@media (max-width: 1023px) {
  .guide-page__body {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .guide-nav__panel {
    max-height: none;
    box-shadow: none;
  }

  .guide-page :deep(.guide-nav__scroll) {
    max-height: 320px;
  }

  .guide-search {
    width: 100%;
  }

  .guide-search__results {
    width: min(92vw, 380px);
  }
}

/* The guide is a reading surface, not another settings form. Keep the
   navigation quiet and spend the visual contrast on the current chapter. */
.guide-page {
  --guide-ink: #13233f;
  --guide-blue: #3164e8;
  --guide-mint: #5eead4;
  --guide-line: rgba(19, 35, 63, 0.1);
  display: flex;
  flex-direction: column;
  gap: 28px;
  min-width: 0;
  color: var(--guide-ink);
}

.guide-page__header {
  position: relative;
  isolation: isolate;
  z-index: 2;
  overflow: visible;
  padding: 32px 34px 22px;
  border: 1px solid rgba(19, 35, 63, 0.16);
  border-radius: 24px;
  background: var(--guide-ink);
  box-shadow: 0 20px 44px rgba(19, 35, 63, 0.16);
  color: #fff;
}

.guide-page__header-art {
  position: absolute;
  inset: 0;
  z-index: -1;
  overflow: hidden;
  border-radius: inherit;
  pointer-events: none;
}

.guide-page__header-art::before {
  position: absolute;
  right: -100px;
  bottom: -180px;
  width: 560px;
  height: 560px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(49, 100, 232, 0.72) 0%, rgba(49, 100, 232, 0) 68%);
  content: '';
}

.guide-page__header-art::after {
  position: absolute;
  inset: 0 0 0 42%;
  background-image: linear-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 28px 28px;
  content: '';
  mask-image: linear-gradient(90deg, transparent, #000 35%);
  opacity: 0.7;
}

.guide-page__header-content {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
  gap: 48px;
  align-items: end;
}

.guide-page__header-copy {
  max-width: 700px;
}

.guide-page__eyebrow,
.guide-search__label,
.guide-page__tool-hint,
.guide-nav__topline,
.guide-content__chapter-heading p {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  line-height: 1.4;
  text-transform: uppercase;
}

.guide-page__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: rgba(255, 255, 255, 0.65);
}

.guide-page__eyebrow-mark {
  display: inline-grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border-radius: 7px;
  background: var(--guide-mint);
  color: var(--guide-ink);
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 0;
  line-height: 1;
}

.guide-page__title {
  margin: 16px 0 10px;
  color: #fff;
  font-size: clamp(36px, 4vw, 50px);
  font-weight: 700;
  letter-spacing: -0.045em;
  line-height: 1;
}

.guide-page__subtitle {
  max-width: 680px;
  margin: 0;
  color: rgba(255, 255, 255, 0.72);
  font-size: 14px;
  line-height: 1.7;
}

.guide-page__header-tool {
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-width: 0;
}

.guide-search__label {
  color: rgba(255, 255, 255, 0.58);
}

.guide-search {
  position: relative;
  width: 100%;
}

.guide-search__input :deep(.n-input) {
  --n-border: transparent !important;
  --n-border-hover: transparent !important;
  --n-border-focus: transparent !important;
  --n-box-shadow-focus: 0 0 0 3px rgba(94, 234, 212, 0.25) !important;
  min-height: 46px;
  border: 0;
  border-radius: 13px;
  background: #f7fbff;
  box-shadow: 0 8px 20px rgba(5, 15, 35, 0.16);
}

.guide-search__input :deep(.n-input__input-el) {
  color: var(--guide-ink);
  font-size: 14px;
  font-weight: 600;
}

.guide-search__input :deep(.n-input__placeholder) {
  color: rgba(19, 35, 63, 0.48);
}

.guide-search__input :deep(.n-input__prefix) {
  color: var(--guide-blue);
}

.guide-page__tool-hint {
  overflow: hidden;
  color: rgba(255, 255, 255, 0.5);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-overflow: ellipsis;
  text-transform: none;
  white-space: nowrap;
}

.guide-page__header-rule {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 6px;
  margin-top: 28px;
  padding-top: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.16);
}

.guide-page__header-rule span {
  display: block;
  width: 22px;
  height: 3px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.38);
}

.guide-page__header-rule span:first-child {
  width: 48px;
  background: var(--guide-mint);
}

.guide-search__results {
  top: calc(100% + 10px);
  right: 0;
  width: 100%;
  box-sizing: border-box;
  padding: 8px;
  border: 1px solid rgba(19, 35, 63, 0.1);
  border-radius: 14px;
  box-shadow: 0 18px 40px rgba(19, 35, 63, 0.2);
}

.guide-search__hit {
  padding: 10px 11px;
  border-radius: 9px;
}

.guide-search__hit:hover,
.guide-search__hit:focus-visible {
  background: #edf3ff;
}

.guide-search__hit-label {
  color: var(--guide-ink);
}

.guide-search__hit-meta {
  color: rgba(19, 35, 63, 0.48);
}

.guide-search__hit-snippet {
  color: rgba(19, 35, 63, 0.64);
}

.guide-search__empty {
  top: calc(100% + 10px);
  right: 0;
  border-color: rgba(19, 35, 63, 0.1);
  border-radius: 10px;
  color: rgba(19, 35, 63, 0.58);
}

.guide-page__body {
  grid-template-columns: 236px minmax(0, 1fr);
  gap: 44px;
}

.guide-nav__panel {
  position: sticky;
  top: 20px;
  height: calc(100vh - 40px);
  max-height: calc(100vh - 40px);
  box-sizing: border-box;
  padding: 17px 12px 14px;
  border: 1px solid var(--guide-line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 12px 28px rgba(19, 35, 63, 0.07);
}

.guide-nav__topline {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px 14px;
  border-bottom: 1px solid var(--guide-line);
  color: rgba(19, 35, 63, 0.56);
  font-size: 10px;
}

.guide-nav__topline-mark {
  width: 7px;
  height: 7px;
  border-radius: 2px;
  background: var(--guide-blue);
  box-shadow: 4px 0 0 rgba(94, 234, 212, 0.9);
}

.guide-page :deep(.guide-nav__scroll) {
  margin-top: 9px;
}

.guide-nav__section {
  margin: 16px 0 6px;
  padding: 0 10px;
  color: rgba(19, 35, 63, 0.42);
  font-size: 10px;
  letter-spacing: 0.1em;
}

.guide-nav__tier-group {
  margin: 14px 0 18px;
}

.guide-nav__tier {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 10px 7px;
  padding: 0;
  color: rgba(19, 35, 63, 0.48);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  line-height: 1.4;
}

.guide-nav__tier::before {
  width: 5px;
  height: 5px;
  flex: 0 0 5px;
  border-radius: 999px;
  background: var(--guide-blue);
  content: '';
}

.guide-nav__tier::after {
  height: 1px;
  flex: 1;
  background: var(--guide-line);
  content: '';
}

.guide-nav__list {
  margin: 0 0 0 10px;
  padding: 0 0 0 10px;
  border-left: 1px solid rgba(49, 100, 232, 0.14);
}

.guide-nav__chapter {
  position: relative;
  padding: 8px 10px;
  border-radius: 9px;
  color: rgba(19, 35, 63, 0.7);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  transition: color 0.15s ease, background-color 0.15s ease;
}

.guide-nav__chapter:hover {
  background: #f0f4fb;
  color: var(--guide-ink);
}

.guide-nav__chapter--active {
  background: #eaf0ff;
  box-shadow: none;
  color: var(--guide-blue);
  font-weight: 700;
}

.guide-nav__chapter--active::before {
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 3px;
  border-radius: 0 4px 4px 0;
  background: var(--guide-blue);
  content: '';
}

.guide-nav__headings {
  margin: 4px 0 10px 10px;
  padding-left: 10px;
  border-left-color: rgba(49, 100, 232, 0.2);
}

.guide-nav__heading {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  /* The dot band hangs into the list's left padding instead of pushing the text
     right: the row shifts back by the same amount it spends on the dot. */
  margin-left: -10px;
  padding: 4px 7px;
  border-radius: 6px;
  color: rgba(19, 35, 63, 0.55);
  font-size: 11.5px;
}

.guide-nav__heading:hover {
  background: #f4f7fc;
  color: var(--guide-blue);
}

.guide-nav__heading--level-3 {
  color: rgba(19, 35, 63, 0.44);
}

/* The tier dot sits in a fixed gutter, so every entry's text starts at the same
   x whether or not the heading carries a tier; the dot only colours in for a
   marked heading. 5px centres the 6px dot on the first line box (11.5px x 1.4). */
.guide-nav__heading-tier {
  flex: 0 0 6px;
  width: 6px;
  height: 6px;
  margin-top: 5px;
  border-radius: 999px;
  background: transparent;
}

.guide-nav__heading-tier[data-guide-tier='core'] {
  background: var(--guide-blue);
}

.guide-nav__heading-tier[data-guide-tier='deep'] {
  background: #64748b;
}

.guide-nav__heading-tier[data-guide-tier='tips'] {
  background: #c2801a;
}

.guide-nav__heading-text {
  min-width: 0;
}

.guide-content {
  min-width: 0;
  box-sizing: border-box;
  padding: 42px 50px 34px;
  border: 1px solid rgba(19, 35, 63, 0.08);
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 14px 34px rgba(19, 35, 63, 0.05);
}

.guide-content__slides {
  max-width: 860px;
  margin: 0 0 34px;
  padding: 14px;
  border: 1px solid rgba(49, 100, 232, 0.12);
  border-radius: 20px;
  background: linear-gradient(145deg, #f8fbff 0%, #f2f6ff 100%);
}

.guide-content__slides-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  padding: 2px 4px 12px;
}

.guide-content__slides-label {
  color: var(--guide-ink);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.guide-content__slides-hint {
  color: rgba(19, 35, 63, 0.48);
  font-size: 11px;
  text-align: right;
}

.guide-content__chapter-heading {
  display: flex;
  align-items: flex-start;
  gap: 15px;
  max-width: 860px;
  margin-bottom: 10px;
  padding-bottom: 26px;
  border-bottom: 1px solid var(--guide-line);
}

.guide-content__chapter-index {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 11px;
  background: #eaf0ff;
  color: var(--guide-blue);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.guide-content__chapter-heading p {
  margin: 2px 0 6px;
  color: rgba(19, 35, 63, 0.42);
  font-size: 10px;
}

.guide-content__chapter-heading h2 {
  margin: 0;
  color: var(--guide-ink);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.guide-content__tier {
  display: inline-block;
  margin-top: 9px;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(19, 35, 63, 0.06);
  color: rgba(19, 35, 63, 0.55);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.guide-content__tier[data-guide-tier='core'] {
  background: rgba(32, 128, 240, 0.12);
  color: #1d4ed8;
}

.guide-content__tier[data-guide-tier='deep'] {
  background: rgba(100, 116, 139, 0.16);
  color: #475569;
}

.guide-content__tier[data-guide-tier='tips'] {
  background: rgba(194, 128, 26, 0.14);
  color: #8a5a11;
}

.guide-pager {
  max-width: 860px;
  margin-top: 34px;
  padding-top: 20px;
  border-top-color: var(--guide-line);
}

.guide-pager__link {
  padding: 10px 12px;
  border-radius: 10px;
}

.guide-pager__link:hover {
  background: #f3f6fb;
}

.guide-pager__direction {
  color: rgba(19, 35, 63, 0.42);
}

.guide-pager__title {
  color: var(--guide-blue);
}

@media (max-width: 1023px) {
  .guide-page__body {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .guide-page__header-content {
    grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
    gap: 28px;
  }

  .guide-nav__panel {
    position: static;
    height: auto;
    max-height: none;
  }

  .guide-page :deep(.guide-nav__scroll) {
    height: 280px;
    max-height: 280px;
  }

  .guide-content {
    padding: 34px 36px 30px;
  }

  .guide-content__slides-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 5px;
  }

  .guide-content__slides-hint {
    text-align: left;
  }
}

@media (max-width: 767px) {
  .guide-page {
    gap: 20px;
  }

  .guide-page__header {
    padding: 26px 22px 19px;
    border-radius: 20px;
  }

  .guide-page__header-content {
    grid-template-columns: minmax(0, 1fr);
    gap: 27px;
  }

  .guide-page__title {
    font-size: 38px;
  }

  .guide-page__subtitle {
    font-size: 13px;
  }

  .guide-content {
    padding: 28px 20px 25px;
    border-radius: 20px;
  }

  .guide-content__chapter-heading h2 {
    font-size: 24px;
  }

  .guide-pager {
    flex-direction: column;
    gap: 6px;
  }

  .guide-pager__link--next {
    align-items: flex-start;
    text-align: left;
  }
}
</style>

<style>
/* v-html content is not scoped: chapter typography is owned here.
   The guide is a long read built from three shapes - prose, tables and figures
   - so each gets its own rhythm: sections separated by a rule, tables with
   horizontal rules only, figures presented as cards. */
.guide-content__body {
  /* Type size, not column width, sets the measure here: the diagrams are sized
     to the full 860px column and must stay at 1:1, so a comfortable line of
     prose (~85 characters) comes from 17.5px type rather than a narrower
     column. */
  font-size: 15.5px;
  line-height: 1.7;
  color: rgba(15, 23, 42, 0.82);
}

.guide-content__body > :first-child {
  margin-top: 0;
}

.guide-content__body h2 {
  margin: 44px 0 14px;
  padding-top: 22px;
  border-top: 1px solid rgba(15, 23, 42, 0.07);
  font-size: 24px;
  font-weight: 600;
  line-height: 1.28;
  letter-spacing: -0.012em;
  color: #0f172a;
}

.guide-content__body > h2:first-child {
  margin-top: 0;
  padding-top: 0;
  border-top: 0;
}

.guide-content__body h3 {
  margin: 30px 0 12px;
  font-size: 17.5px;
  font-weight: 600;
  line-height: 1.45;
  color: #0f172a;
}

.guide-content__body p {
  margin: 0 0 16px;
}

/* Keep prose aligned with the same reading column as tables and figures. The
   column itself is capped at 860px, so paragraphs use the available measure
   without leaving an artificial block of empty space on the right. */
.guide-content__body p,
.guide-content__body ul,
.guide-content__body ol,
.guide-content__body blockquote {
  max-width: 100%;
}

.guide-content__body ul,
.guide-content__body ol {
  margin: 0 0 18px;
  padding-left: 24px;
}

.guide-content__body li + li {
  margin-top: 5px;
}

.guide-content__body li::marker {
  color: rgba(15, 23, 42, 0.35);
}

.guide-content__body a {
  color: #1d4ed8;
  text-decoration-color: rgba(29, 78, 216, 0.3);
  text-underline-offset: 2px;
}

.guide-content__body a:hover {
  text-decoration-color: currentColor;
}

.guide-content__body strong {
  font-weight: 600;
  color: #0f172a;
}

/* Tables carry most of the reference material here; horizontal rules read
   cleaner than a full grid and keep wide tables scannable. */
.guide-content__body table {
  width: 100%;
  margin: 14px 0 24px;
  border-collapse: collapse;
  font-size: 13.5px;
  line-height: 1.6;
}

.guide-content__body th,
.guide-content__body td {
  padding: 9px 12px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid rgba(15, 23, 42, 0.07);
}

.guide-content__body th {
  border-bottom: 1px solid rgba(15, 23, 42, 0.16);
  background: rgba(148, 163, 184, 0.1);
  font-weight: 600;
  color: #0f172a;
}

.guide-content__body tbody tr:nth-child(even) {
  background: rgba(148, 163, 184, 0.045);
}

.guide-content__body code {
  padding: 1.5px 5px;
  border-radius: 5px;
  background: rgba(15, 23, 42, 0.06);
  font-size: 14px;
}

.guide-content__body blockquote {
  margin: 18px 0;
  padding: 10px 18px;
  border-left: 3px solid rgba(32, 128, 240, 0.4);
  border-radius: 0 10px 10px 0;
  background: rgba(32, 128, 240, 0.05);
  color: rgba(15, 23, 42, 0.78);
}

.guide-content__body blockquote p:last-child {
  margin-bottom: 0;
}

.guide-content__body hr {
  margin: 32px 0;
  border: 0;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

/* Figures: the diagrams are half the point of this guide, so they get a card
   with a caption rather than a bare bordered image. */
.guide-content__body figure.guide-figure {
  margin: 22px 0 30px;
}

.guide-content__body figure.guide-figure img {
  margin: 0 auto;
}

.guide-figure__caption {
  margin-top: 10px;
  font-size: 13.5px;
  line-height: 1.55;
  color: rgba(15, 23, 42, 0.55);
  text-align: center;
}

.guide-content__body img {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 20px auto 28px;
  padding: 10px;
  border: 1px solid rgba(15, 23, 42, 0.07);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.guide-code {
  position: relative;
  margin: 12px 0 20px;
}

.guide-code pre.md-code-block {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  background: #0f172a;
  overflow-x: auto;
}

.guide-code pre.md-code-block code {
  padding: 0;
  background: transparent;
  color: #e2e8f0;
  font-size: 12.5px;
  line-height: 1.6;
}

.guide-code__copy {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  border: 1px solid rgba(226, 232, 240, 0.24);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.6);
  color: #e2e8f0;
  font-size: 11px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.guide-code:hover .guide-code__copy,
.guide-code__copy:focus-visible {
  opacity: 1;
}

/* Naive UI places a second, non-scrolling scrollbar around page content. Let
   only that direct outer scrollbar remain visible so the sidebar's own
   n-scrollbar keeps its rail and scroll container intact. */
.app-shell--guide .app-shell__content,
.app-shell--guide .app-shell__content > .n-scrollbar,
.app-shell--guide .app-shell__content > .n-scrollbar > .n-scrollbar-container,
.app-shell--guide .app-shell__content > .n-scrollbar > .n-scrollbar-container > .n-scrollbar-content {
  overflow: visible !important;
}

.guide-content__body img,
.guide-content__body pre.md-code-block {
  box-sizing: border-box;
}

.guide-content__body table {
  max-width: 100%;
  overflow-x: auto;
}

.guide-content__body th,
.guide-content__body td {
  overflow-wrap: anywhere;
}

/* Small, intentional iconography helps the guide read like a product surface:
   the chapter badge names the audience, and navigation affordances stay quiet. */
.guide-nav__topline-icon {
  flex: 0 0 auto;
  color: var(--guide-blue);
}

.guide-content__chapter-index {
  height: 44px;
  width: 42px;
  gap: 1px;
  align-content: center;
  color: var(--guide-blue);
}

.guide-content__chapter-index > span {
  font-size: 11px;
  line-height: 1;
}

.guide-pager__direction {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

/* Figures are a distinct reading unit. The full-size link keeps dense diagrams
   useful without letting them create a second page-level scroll surface. */
.guide-content__body figure.guide-figure {
  position: relative;
  max-width: 860px;
  margin: 30px 0 36px;
  padding: 14px;
  border: 1px solid rgba(49, 100, 232, 0.13);
  border-radius: 18px;
  background: linear-gradient(145deg, #fbfdff 0%, #f5f8ff 100%);
  box-shadow: 0 12px 28px rgba(19, 35, 63, 0.06);
}

.guide-content__body figure.guide-figure::before {
  position: absolute;
  top: 12px;
  right: 16px;
  z-index: 1;
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border: 1px solid rgba(49, 100, 232, 0.16);
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.86);
  color: var(--guide-blue);
  content: '↗';
  font-size: 13px;
  line-height: 1;
}

.guide-figure__image-link {
  display: block;
  min-width: 0;
  overflow: hidden;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
}

.guide-figure__image-link:hover img {
  border-color: rgba(49, 100, 232, 0.28);
}

.guide-content__body figure.guide-figure img {
  width: 100%;
  max-width: 100%;
  margin: 0;
  padding: 10px;
  border: 1px solid rgba(19, 35, 63, 0.08);
  border-radius: 12px;
  background: #fff;
  box-shadow: none;
  transition: border-color 0.15s ease;
}

.guide-figure__caption {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 12px 2px 1px;
  color: rgba(19, 35, 63, 0.58);
  font-size: 13px;
  line-height: 1.55;
  text-align: left;
}

.guide-figure__caption::before {
  flex: 0 0 auto;
  color: var(--guide-blue);
  content: '↗';
  font-size: 14px;
  line-height: 1.45;
}

/* Tables scroll inside their own frame on small screens instead of widening
   the reading surface. The minimum width preserves column rhythm. */
.guide-content__body .guide-table {
  max-width: 100%;
  margin: 16px 0 26px;
  overflow-x: auto;
  border: 1px solid rgba(19, 35, 63, 0.08);
  border-radius: 14px;
  background: #fff;
}

.guide-content__body .guide-table table {
  min-width: 560px;
  margin: 0;
}

/* [!kind] blockquotes in the source become these lightweight semantic cards. */
.guide-content__body blockquote.guide-callout {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  max-width: 680px;
  margin: 20px 0 26px;
  padding: 14px 18px 14px 14px;
  border: 1px solid rgba(49, 100, 232, 0.16);
  border-left: 3px solid var(--guide-blue);
  border-radius: 14px;
  background: #f5f8ff;
  color: rgba(19, 35, 63, 0.78);
}

.guide-content__body blockquote.guide-callout::before {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 9px;
  background: #e7efff;
  color: var(--guide-blue);
  content: 'i';
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
}

.guide-content__body blockquote.guide-callout p {
  grid-column: 2;
  max-width: none;
  margin: 0 0 8px;
}

.guide-content__body blockquote.guide-callout p:last-child {
  margin-bottom: 0;
}

.guide-content__body blockquote.guide-callout--tip {
  border-color: rgba(13, 148, 136, 0.2);
  border-left-color: #0f9f91;
  background: #f0fdfa;
}

.guide-content__body blockquote.guide-callout--tip::before {
  background: #ccfbf1;
  color: #0f766e;
  content: '✦';
}

.guide-content__body blockquote.guide-callout--warning {
  border-color: rgba(217, 119, 6, 0.22);
  border-left-color: #d97706;
  background: #fffaf0;
}

.guide-content__body blockquote.guide-callout--warning::before {
  background: #fef3c7;
  color: #b45309;
  content: '!';
}

.guide-content__body blockquote.guide-callout--success {
  border-color: rgba(22, 163, 74, 0.2);
  border-left-color: #16a34a;
  background: #f0fdf4;
}

.guide-content__body blockquote.guide-callout--success::before {
  background: #dcfce7;
  color: #15803d;
  content: '✓';
}

.guide-content__body blockquote.guide-callout--route {
  border-color: rgba(124, 58, 237, 0.18);
  border-left-color: #7c3aed;
  background: #faf5ff;
}

.guide-content__body blockquote.guide-callout--route::before {
  background: #ede9fe;
  color: #6d28d9;
  content: '↗';
}

/* The chip the renderer appends to a heading whose markdown carried a
   {core}, {deep} or {tips} marker. */
.guide-content__body .guide-tier {
  display: inline-block;
  margin-left: 10px;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: rgba(15, 23, 42, 0.55);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  vertical-align: middle;
  white-space: nowrap;
}

.guide-content__body .guide-tier[data-guide-tier='core'] {
  background: rgba(32, 128, 240, 0.12);
  color: #1d4ed8;
}

.guide-content__body .guide-tier[data-guide-tier='deep'] {
  background: rgba(100, 116, 139, 0.16);
  color: #475569;
}

.guide-content__body .guide-tier[data-guide-tier='tips'] {
  background: rgba(194, 128, 26, 0.14);
  color: #8a5a11;
}

@media (max-width: 767px) {
  .guide-content__body figure.guide-figure {
    margin: 24px 0 30px;
    padding: 10px;
    border-radius: 15px;
  }

  .guide-content__body figure.guide-figure img {
    padding: 6px;
  }

  .guide-content__body .guide-table table {
    min-width: 520px;
  }

  .guide-content__body blockquote.guide-callout {
    grid-template-columns: 26px minmax(0, 1fr);
    gap: 9px;
    padding: 12px 13px 12px 11px;
  }

  .guide-content__body blockquote.guide-callout::before {
    width: 26px;
    height: 26px;
  }
}
</style>
