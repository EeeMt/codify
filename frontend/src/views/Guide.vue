<template>
  <section class="guide-page">
    <div ref="headerRef" class="guide-page__header">
      <PageHeader :title="t('guide.title')" :subtitle="t('guide.subtitle')">
        <template #actions>
          <div class="guide-search">
            <n-input
              v-model:value="searchQuery"
              class="guide-search__input"
              size="small"
              clearable
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
        </template>
      </PageHeader>
    </div>

    <div class="guide-page__body">
      <aside class="guide-nav" :aria-label="t('guide.tocLabel')">
        <div
          ref="navPanelRef"
          class="guide-nav__panel"
        >
          <div class="guide-nav__scroll">
            <template v-for="section in sections" :key="section.key">
              <p class="guide-nav__section">{{ t(SECTION_LABEL[section.key]) }}</p>
              <ul class="guide-nav__list">
                <li v-for="chapter in section.chapters" :key="chapter.slug">
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
                        {{ heading.text }}
                      </a>
                    </li>
                  </ul>
                </li>
              </ul>
            </template>
          </div>
        </div>
      </aside>

      <article class="guide-content">
        <div
          ref="contentRef"
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
            <span class="guide-pager__direction">{{ t('guide.previous') }}</span>
            <span class="guide-pager__title">{{ previousChapter.title }}</span>
          </RouterLink>
          <span v-else />
          <RouterLink
            v-if="nextChapter"
            class="guide-pager__link guide-pager__link--next"
            :to="{ name: 'Guide', params: { chapter: nextChapter.slug } }"
          >
            <span class="guide-pager__direction">{{ t('guide.next') }}</span>
            <span class="guide-pager__title">{{ nextChapter.title }}</span>
          </RouterLink>
        </nav>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NIcon, NInput } from 'naive-ui'
import { SearchOutline } from '@vicons/ionicons5'

import PageHeader from '../components/PageHeader.vue'
import { useBreakpoints } from '../composables/useBreakpoints'
import { currentLocale, type AppLocale } from '../i18n'
import { guideChapters, guideSections, type GuideSectionKey } from '../guide/guideContent'
import { indexGuideChapter, renderGuideChapter, type GuideChapterIndex, type GuideHeading } from '../guide/renderGuideChapter'

const SECTION_LABEL: Record<GuideSectionKey, string> = {
  user: 'guide.sections.user',
  admin: 'guide.sections.admin',
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const contentRef = ref<HTMLElement | null>(null)
const navPanelRef = ref<HTMLElement | null>(null)
const headerRef = ref<HTMLElement | null>(null)
const searchQuery = ref('')
const searchFocused = ref(false)
const html = ref('')
const headings = ref<GuideHeading[]>([])

// Guards against a slower render of a previous chapter overwriting a newer one.
let renderToken = 0
let hasRendered = false

const { isMobile } = useBreakpoints()

const NAV_STICKY_TOP = 20

/**
 * The app shell nests every page inside layouts that clip overflow — both
 * `n-scrollbar` and `n-layout` set `overflow: hidden` — so `position: sticky`
 * has no scrollport of its own and never sticks. Translate the panel instead:
 * a transform is not constrained by an ancestor's overflow, and the panel stays
 * in flow so its column keeps its width.
 *
 * The host is only used for the reference viewport top; the scroll events
 * themselves are caught on the window (see onMounted).
 */
function findScrollHost(): HTMLElement | null {
  let el: HTMLElement | null = navPanelRef.value?.parentElement ?? null
  while (el) {
    const { overflowY } = getComputedStyle(el)
    if ((overflowY === 'auto' || overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 1) {
      return el
    }
    el = el.parentElement
  }
  return null
}

let scrollHost: HTMLElement | null = null

function resolveScrollHost(): HTMLElement | null {
  if (scrollHost?.isConnected) return scrollHost
  scrollHost = findScrollHost()
  return scrollHost
}

function applyOffset(element: HTMLElement | null, offset: number): void {
  if (!element) return
  const value = `translateY(${offset}px)`
  if (element.style.transform !== value) element.style.transform = value
}

/**
 * Writes the transforms straight to the elements instead of going through
 * reactive bindings: a scroll fires many times per frame, and a render cycle per
 * event lands out of step with the paint, which reads as jitter. One update per
 * animation frame, snapped to whole pixels, is stable.
 *
 * Both the sidebar and the page header float this way because `position: sticky`
 * cannot work here - the shell nests every page in wrappers that clip overflow,
 * so a sticky element has no scrollport of its own.
 */
function syncFloating(): void {
  const host = resolveScrollHost()
  const hostTop = host ? host.getBoundingClientRect().top : 0

  const panel = navPanelRef.value
  const column = panel?.parentElement
  if (!panel || !column || !host || isMobile.value) {
    applyOffset(panel, 0)
  } else {
    const columnTop = column.getBoundingClientRect().top
    const travel = Math.max(0, column.clientHeight - panel.offsetHeight)
    applyOffset(panel, Math.round(Math.min(Math.max(0, hostTop + NAV_STICKY_TOP - columnTop), travel)))
  }

  const header = headerRef.value
  const page = header?.parentElement
  if (!header || !page || !host) {
    applyOffset(header, 0)
    header?.classList.remove('guide-page__header--pinned')
    return
  }
  // The header pins to the top of the scroll viewport and stops at the end of
  // the guide page, so it never covers the footer.
  const pageTop = page.getBoundingClientRect().top
  const travel = Math.max(0, page.clientHeight - header.offsetHeight)
  const offset = Math.round(Math.min(Math.max(0, hostTop - pageTop), travel))
  applyOffset(header, offset)
  header.classList.toggle('guide-page__header--pinned', offset > 0)
}

let floatFrame = 0

function scheduleFloating(): void {
  if (floatFrame) return
  floatFrame = requestAnimationFrame(() => {
    floatFrame = 0
    syncFloating()
  })
}

onMounted(() => {
  // Scroll events do not bubble, and the element the shell actually scrolls is
  // not reliably the first scrolling ancestor. A capture-phase listener on the
  // window sees the event from whichever element scrolls.
  window.addEventListener('scroll', scheduleFloating, { capture: true, passive: true })
  window.addEventListener('resize', scheduleFloating)
  syncFloating()
})

onBeforeUnmount(() => {
  if (floatFrame) cancelAnimationFrame(floatFrame)
  window.removeEventListener('scroll', scheduleFloating, { capture: true })
  window.removeEventListener('resize', scheduleFloating)
})

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

const sections = computed(() => guideSections(currentLocale.value))
const chapters = computed(() => sections.value.flatMap((section) => section.chapters))

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
const previousChapter = computed(() =>
  activeIndex.value > 0 ? chapters.value[activeIndex.value - 1] : null,
)
const nextChapter = computed(() =>
  activeIndex.value >= 0 && activeIndex.value < chapters.value.length - 1
    ? chapters.value[activeIndex.value + 1]
    : null,
)

function revealHeading(id: string): void {
  const target = contentRef.value?.querySelector<HTMLElement>(`#${CSS.escape(id)}`)
  target?.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

function revealChapterStart(): void {
  const id = route.hash.replace(/^#/, '')
  const target = id ? contentRef.value?.querySelector<HTMLElement>(`#${CSS.escape(id)}`) : null
  if (target) {
    target.scrollIntoView({ block: 'start' })
    return
  }
  // Skip the jump on first paint so opening the page does not scroll past its header.
  if (hasRendered) contentRef.value?.scrollIntoView({ block: 'start' })
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

    const rendered = renderGuideChapter(chapter.body, { copyLabel: t('guide.copyCode') })
    if (token !== renderToken) return
    html.value = rendered.html
    headings.value = rendered.headings

    await nextTick()
    if (token !== renderToken) return
    revealChapterStart()
    syncFloating()
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

.guide-nav__scroll {
  /* A native scroll container, not n-scrollbar: the nav can grow past the
     panel (a chapter with many headings expands in place), and naive-ui's
     container sizes to its content instead of filling the panel, so the extra
     entries were clipped with nothing to scroll. */
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
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

  .guide-nav__scroll {
    max-height: 320px;
  }

  .guide-search {
    width: 100%;
  }

  .guide-search__results {
    width: min(92vw, 380px);
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

/* Two measures: prose is capped for a comfortable line, while tables and
   figures use the full column. A single measure cannot serve both: the diagrams
   are sized to the column and must not be scaled down (that is the whole point
   of their size budget), and an 860px line of prose runs to ~99 characters.
   560px is ~74 characters at 15.5px, inside the comfortable band. `ch`
   units are unusable here - Inter's digit advance is ~0.63em, so `82ch`
   resolves to 903px. */
.guide-content__body p,
.guide-content__body ul,
.guide-content__body ol,
.guide-content__body blockquote {
  max-width: 560px;
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
</style>
