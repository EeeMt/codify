<template>
  <section class="guide-page">
    <PageHeader :title="t('guide.title')" :subtitle="t('guide.subtitle')">
      <template #actions>
        <n-input
          v-model:value="chapterFilter"
          class="guide-page__filter"
          size="small"
          clearable
          :placeholder="t('guide.filterPlaceholder')"
        >
          <template #prefix>
            <n-icon :component="SearchOutline" />
          </template>
        </n-input>
      </template>
    </PageHeader>

    <div class="guide-page__body">
      <aside class="guide-nav" :aria-label="t('guide.tocLabel')">
        <n-scrollbar class="guide-nav__scroll">
          <template v-for="section in visibleSections" :key="section.key">
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
        </n-scrollbar>
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
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NIcon, NInput, NScrollbar } from 'naive-ui'
import { SearchOutline } from '@vicons/ionicons5'

import PageHeader from '../components/PageHeader.vue'
import { currentLocale } from '../i18n'
import { guideSections, type GuideSectionKey } from '../guide/guideContent'
import { renderGuideChapter, type GuideHeading } from '../guide/renderGuideChapter'
import { hydrateGuideMermaid } from '../guide/hydrateGuideMermaid'

const SECTION_LABEL: Record<GuideSectionKey, string> = {
  user: 'guide.sections.user',
  admin: 'guide.sections.admin',
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const contentRef = ref<HTMLElement | null>(null)
const chapterFilter = ref('')
const html = ref('')
const headings = ref<GuideHeading[]>([])

// Guards against a slower render of a previous chapter overwriting a newer one.
let renderToken = 0
let hasRendered = false

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

const visibleSections = computed(() => {
  const query = chapterFilter.value.trim().toLowerCase()
  if (!query) return sections.value
  return sections.value
    .map((section) => ({
      ...section,
      chapters: section.chapters.filter((chapter) =>
        chapter.title.toLowerCase().includes(query),
      ),
    }))
    .filter((section) => section.chapters.length > 0)
})

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
    void hydrateGuideMermaid(contentRef.value)
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
}

.guide-page__filter {
  width: 220px;
}

.guide-page__body {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 32px;
  align-items: start;
}

.guide-nav {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 140px);
  padding: 4px 4px 4px 0;
  border-right: 1px solid rgba(15, 23, 42, 0.08);
}

.guide-nav__scroll {
  max-height: calc(100vh - 148px);
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

  .guide-nav {
    position: static;
    max-height: none;
    padding: 0 0 12px;
    border-right: none;
    border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  }

  .guide-nav__scroll {
    max-height: 320px;
  }

  .guide-page__filter {
    width: 100%;
  }
}
</style>

<style>
/* v-html content is not scoped: chapter typography is owned here. */
.guide-content__body > :first-child {
  margin-top: 0;
}

.guide-content__body h2 {
  margin: 32px 0 12px;
  font-size: 22px;
  line-height: 1.3;
  color: #0f172a;
}

.guide-content__body h3 {
  margin: 24px 0 10px;
  font-size: 16px;
  line-height: 1.4;
  color: #0f172a;
}

.guide-content__body p,
.guide-content__body li {
  font-size: 14px;
  line-height: 1.75;
  color: rgba(15, 23, 42, 0.78);
}

.guide-content__body ul,
.guide-content__body ol {
  padding-left: 22px;
}

.guide-content__body a {
  color: #1d4ed8;
}

.guide-content__body table {
  width: 100%;
  margin: 12px 0 20px;
  border-collapse: collapse;
  font-size: 13px;
}

.guide-content__body th,
.guide-content__body td {
  padding: 8px 10px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  text-align: left;
  vertical-align: top;
}

.guide-content__body th {
  background: rgba(148, 163, 184, 0.12);
  font-weight: 600;
}

.guide-content__body code {
  padding: 1px 5px;
  border-radius: 5px;
  background: rgba(15, 23, 42, 0.06);
  font-size: 12.5px;
}

.guide-content__body blockquote {
  margin: 16px 0;
  padding: 8px 16px;
  border-left: 3px solid rgba(32, 128, 240, 0.4);
  background: rgba(32, 128, 240, 0.05);
}

.guide-content__body img {
  max-width: 100%;
  height: auto;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 12px;
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

.guide-mermaid {
  margin: 16px 0 24px;
  padding: 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  background: #fff;
  overflow-x: auto;
}

.guide-mermaid[data-guide-mermaid-state='pending']::before {
  content: '';
  display: block;
  height: 96px;
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.12), rgba(148, 163, 184, 0.24), rgba(148, 163, 184, 0.12));
}

.guide-mermaid svg {
  max-width: 100%;
  height: auto;
}

.guide-mermaid__error {
  margin: 0 0 8px;
  color: #b91c1c;
  font-size: 13px;
}
</style>
