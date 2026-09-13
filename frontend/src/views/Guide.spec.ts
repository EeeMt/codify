import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { h, type SetupContext } from 'vue'
import Guide from './Guide.vue'
import { guideChapters } from '../guide/guideContent'
import { i18n, setAppLocale } from '../i18n'

vi.mock('naive-ui', () => ({
  NIcon: {
    name: 'NIcon',
    setup(_props: unknown, { slots }: SetupContext) {
      return () => h('i', { class: 'n-icon' }, slots.default?.())
    },
  },
  NInput: {
    name: 'NInput',
    props: ['value'],
    emits: ['update:value'],
    setup(props: { value?: string }, { slots, emit }: SetupContext) {
      return () =>
        h('div', { class: 'n-input' }, [
          slots.prefix?.(),
          h('input', {
            class: 'n-input__input',
            value: props.value ?? '',
            onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
            onFocus: () => emit('focus'),
            onBlur: () => emit('blur'),
            onKeydown: (event: KeyboardEvent) => emit(`keydown.${event.key.toLowerCase()}`),
          }),
        ])
    },
  },
  NScrollbar: {
    name: 'NScrollbar',
    setup(_props: unknown, { slots }: SetupContext) {
      return () => h('div', { class: 'n-scrollbar' }, slots.default?.())
    },
  },
}))

function createGuideRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/guide/:chapter?', name: 'Guide', component: Guide },
      { path: '/issues', name: 'Issues', component: { template: '<div class="issues-page" />' } },
    ],
  })
}

async function mountGuide(path = '/guide') {
  const router = createGuideRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(Guide, { global: { plugins: [router, i18n] } })
  await flushPromises()
  return { wrapper, router }
}

afterEach(() => {
  setAppLocale('en')
})

describe('Guide view', () => {
  it('lists every chapter of the active locale in the sidebar, grouped by section', async () => {
    const { wrapper } = await mountGuide()
    const chapters = guideChapters('en')

    expect(wrapper.findAll('.guide-nav__section').map((node) => node.text())).toEqual([
      'User Guide',
      'Admin Guide',
    ])
    expect(wrapper.findAll('.guide-nav__chapter')).toHaveLength(chapters.length)
  })

  it('canonicalises an unknown chapter to the first chapter', async () => {
    const { router } = await mountGuide('/guide/does-not-exist')

    expect(router.currentRoute.value.params.chapter).toBe(guideChapters('en')[0].slug)
  })

  it('renders the active chapter body with its headings anchored', async () => {
    const { wrapper } = await mountGuide()
    const body = wrapper.find('.guide-content__body')

    expect(body.exists()).toBe(true)
    expect(body.findAll('h2').length).toBeGreaterThan(0)

    const anchorIds = body.findAll('h2, h3').map((node) => node.attributes('id'))
    expect(anchorIds.every((id) => Boolean(id))).toBe(true)
    const tocIds = wrapper.findAll('.guide-nav__heading').map((node) => node.attributes('href')?.slice(1))
    expect(tocIds).toEqual(anchorIds)
  })

  it('navigates to another chapter from the sidebar', async () => {
    const { wrapper, router } = await mountGuide()
    const target = guideChapters('en')[1]

    await wrapper.findAll('.guide-nav__chapter')[1].trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.params.chapter).toBe(target.slug)
    expect(router.currentRoute.value.name).toBe('Guide')
  })

  it('renders the chapter in the newly selected locale', async () => {
    const { wrapper } = await mountGuide()
    const englishTitle = guideChapters('en')[0].title

    setAppLocale('zh-CN')
    await flushPromises()

    const chineseTitle = guideChapters('zh-CN')[0].title
    expect(chineseTitle).not.toBe(englishTitle)
    expect(wrapper.find('.guide-nav__chapter').text()).toBe(chineseTitle)
    expect(wrapper.findAll('.guide-nav__section').map((node) => node.text())).toEqual([
      '使用指南',
      '管理指南',
    ])
  })

  it('searches section headings and links a hit to its anchor', async () => {
    const { wrapper, router } = await mountGuide()
    const input = wrapper.find('.n-input__input')

    await input.trigger('focus')
    await input.setValue('Task lifecycle')
    await flushPromises()

    const hits = wrapper.findAll('.guide-search__hit')
    expect(hits.length).toBeGreaterThan(0)
    expect(hits[0].text()).toContain('Task lifecycle')

    await hits[0].trigger('mousedown')
    await flushPromises()

    expect(router.currentRoute.value.params.chapter).toBe('40-run-and-steer')
    expect(router.currentRoute.value.hash).toBe('#task-lifecycle')
  })

  it('finds a chapter by body text when no title matches', async () => {
    const { wrapper } = await mountGuide()
    const input = wrapper.find('.n-input__input')

    await input.trigger('focus')
    await input.setValue('frozen snapshot')
    await flushPromises()

    const hits = wrapper.findAll('.guide-search__hit')
    expect(hits.length).toBeGreaterThan(0)
    expect(hits.some((hit) => hit.text().length > 0)).toBe(true)
  })

  it('reports when nothing matches', async () => {
    const { wrapper } = await mountGuide()
    const input = wrapper.find('.n-input__input')

    await input.trigger('focus')
    await input.setValue('zzzznomatch')
    await flushPromises()

    expect(wrapper.findAll('.guide-search__hit')).toHaveLength(0)
    expect(wrapper.find('.guide-search__empty').exists()).toBe(true)
  })

  it('keeps the results hidden until the field has focus', async () => {
    const { wrapper } = await mountGuide()
    const input = wrapper.find('.n-input__input')

    await input.setValue('Task lifecycle')
    await flushPromises()

    expect(wrapper.find('.guide-search__results').exists()).toBe(false)
  })

  it('offers previous and next chapter links except at the edges', async () => {
    const chapters = guideChapters('en')
    const { wrapper } = await mountGuide(`/guide/${chapters[1].slug}`)

    const pager = wrapper.findAll('.guide-pager__link')
    expect(pager.map((link) => link.text())).toEqual([
      `Previous${chapters[0].title}`,
      `Next${chapters[2].title}`,
    ])
  })
})
