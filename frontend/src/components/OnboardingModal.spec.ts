import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { h, nextTick, type SetupContext } from 'vue'

const messages: Record<string, string> = {
  'onboarding.modalTitle': 'A short tour of Codify',
  'onboarding.modalDescription': 'See how a request moves from intent to a reviewable change.',
  'onboarding.progressLabel': 'Step {current} of {total}',
  'onboarding.actions.closeOnboarding': 'Close onboarding',
  'onboarding.actions.viewGuide': 'View full guide',
  'onboarding.actions.skip': 'Skip for now',
  'onboarding.actions.close': 'Close',
  'onboarding.actions.previous': 'Previous',
  'onboarding.actions.next': 'Next',
  'onboarding.actions.viewDashboard': 'View Dashboard',
  'onboarding.actions.createIssue': 'Create Issue',
  'onboarding.slides.intent.title': 'Turn a clear goal into a reviewable change',
  'onboarding.slides.issue.title': 'One Issue keeps one line of work moving',
  'onboarding.slides.system.title': 'Tasks run where the system can watch them',
  'onboarding.slides.review.title': 'Every turn leaves something you can review',
  'onboarding.slides.start.title': 'Give the next task a finish line',
}

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => {
      const message = messages[key] ?? key
      return message.replace(/\{(\w+)\}/g, (_match, name: string) => String(values?.[name] ?? `{${name}}`))
    },
  }),
}))

vi.mock('naive-ui', () => ({
  NModal: {
    name: 'NModal',
    props: ['show'],
    setup(props: { show: boolean }, { slots }: SetupContext) {
      return () => props.show ? h('div', { class: 'n-modal' }, slots.default?.()) : null
    },
  },
  NButton: {
    name: 'NButton',
    emits: ['click'],
    setup(_props: unknown, { slots, emit, attrs }: SetupContext) {
      return () => h('button', { ...attrs, class: ['n-button', attrs.class], onClick: () => emit('click') }, slots.default?.())
    },
  },
}))

import OnboardingModal from './OnboardingModal.vue'

const onboardingModalSource = readFileSync(resolve(process.cwd(), 'src/components/OnboardingModal.vue'), 'utf8')
const productSlidesSource = readFileSync(resolve(process.cwd(), 'src/components/ProductSlides.vue'), 'utf8')

function mountComponent() {
  return mount(OnboardingModal, { props: { show: true } })
}

function activeSlide(wrapper: ReturnType<typeof mountComponent>) {
  return wrapper.get('.product-slide.active')
}

describe('OnboardingModal', () => {
  it('renders the product tour as a fixed-stage five-slide deck', () => {
    const wrapper = mountComponent()

    expect(wrapper.find('.onboarding-modal').exists()).toBe(true)
    expect(wrapper.find('.deck-stage').classes()).toContain('product-slides__stage')
    expect(wrapper.findAll('[data-testid="onboarding-slide"]')).toHaveLength(5)
    expect(wrapper.findAll('.product-slide.active')).toHaveLength(1)
    expect(wrapper.findAll('.product-slide.visible')).toHaveLength(1)
    expect(activeSlide(wrapper).find('.product-slide__title').text()).toBe('Turn a clear goal into a reviewable change')
  })

  it('keeps every slide authored at 1920 by 1080 and switches visibility with active classes', () => {
    expect(productSlidesSource).toContain('width: 1920px')
    expect(productSlidesSource).toContain('height: 1080px')
    expect(productSlidesSource).toContain('visibility: hidden')
    expect(productSlidesSource).toContain('{ active: index === currentIndex, visible: index === currentIndex }')
    expect(onboardingModalSource).toContain('<ProductSlides')
  })

  it('navigates forward and backward without changing the modal shell', async () => {
    const wrapper = mountComponent()

    await wrapper.get('[data-testid="onboarding-next"]').trigger('click')
    expect(activeSlide(wrapper).attributes('data-slide')).toBe('issue')
    expect(activeSlide(wrapper).find('.product-slide__title').text()).toBe('One Issue keeps one line of work moving')

    await wrapper.get('[data-testid="onboarding-previous"]').trigger('click')
    expect(activeSlide(wrapper).attributes('data-slide')).toBe('intent')
  })

  it('supports keyboard and slide-dot navigation', async () => {
    const wrapper = mountComponent()
    const viewport = wrapper.get('.product-slides__viewport')

    await viewport.trigger('keydown', { key: 'ArrowRight' })
    expect(activeSlide(wrapper).attributes('data-slide')).toBe('issue')

    await wrapper.findAll('.product-slides__control')[3].trigger('click')
    expect(activeSlide(wrapper).attributes('data-slide')).toBe('review')

    await viewport.trigger('keydown', { key: 'Home' })
    expect(activeSlide(wrapper).attributes('data-slide')).toBe('intent')
  })

  it('resets to the first slide when reopened', async () => {
    const wrapper = mountComponent()

    await wrapper.get('[data-testid="onboarding-next"]').trigger('click')
    await wrapper.get('[data-testid="onboarding-next"]').trigger('click')
    expect(activeSlide(wrapper).attributes('data-slide')).toBe('system')

    await wrapper.setProps({ show: false })
    await wrapper.setProps({ show: true })
    await nextTick()

    expect(activeSlide(wrapper).attributes('data-slide')).toBe('intent')
  })

  it('uses a localized accessibility label for the close button', () => {
    const wrapper = mountComponent()

    expect(wrapper.find('.onboarding-modal__close').attributes('aria-label')).toBe('Close onboarding')
  })

  it('emits close when skip is clicked', async () => {
    const wrapper = mountComponent()

    await wrapper.get('[data-testid="onboarding-skip"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits view-guide from the modal footer', async () => {
    const wrapper = mountComponent()

    await wrapper.get('[data-testid="onboarding-view-guide"]').trigger('click')

    expect(wrapper.emitted('open-guide')).toHaveLength(1)
  })

  it('emits view-dashboard on the final primary action', async () => {
    const wrapper = mountComponent()

    for (let index = 0; index < 4; index += 1) {
      await wrapper.get('[data-testid="onboarding-next"]').trigger('click')
    }
    await wrapper.get('[data-testid="onboarding-view-dashboard"]').trigger('click')

    expect(wrapper.emitted('view-dashboard')).toHaveLength(1)
    expect(wrapper.emitted('complete')).toHaveLength(1)
  })

  it('emits create-issue on the final secondary action', async () => {
    const wrapper = mountComponent()

    for (let index = 0; index < 4; index += 1) {
      await wrapper.get('[data-testid="onboarding-next"]').trigger('click')
    }
    await wrapper.get('[data-testid="onboarding-create-issue"]').trigger('click')

    expect(wrapper.emitted('create-issue')).toHaveLength(1)
    expect(wrapper.emitted('complete')).toHaveLength(1)
  })
})
