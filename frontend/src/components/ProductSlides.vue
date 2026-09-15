<template>
  <div
    ref="viewportRef"
    class="deck-viewport product-slides__viewport"
    :class="[
      `product-slides__viewport--${variant}`,
      { 'product-slides__viewport--compact': compact },
    ]"
    role="region"
    :aria-label="t('productSlides.controls.deckLabel')"
    tabindex="0"
    @keydown="handleKeydown"
    @pointerdown="handlePointerDown"
    @pointerup="handlePointerUp"
    @pointercancel="handlePointerCancel"
  >
    <main ref="stageRef" class="deck-stage product-slides__stage" :style="stageStyle">
      <section
        v-for="(slide, index) in slides"
        :key="slide.id"
        class="slide product-slide"
        :class="[
          `product-slide--${slide.visual}`,
          `product-slide--${slide.accent}`,
          { active: index === currentIndex, visible: index === currentIndex },
        ]"
        :aria-hidden="index !== currentIndex"
        :data-slide="slide.id"
        :data-testid="variant === 'onboarding' ? 'onboarding-slide' : undefined"
      >
        <div class="product-slide__grid" aria-hidden="true" />
        <div class="product-slide__wash" aria-hidden="true" />

        <header class="product-slide__topbar">
          <div class="product-slide__brand" aria-label="Codify">
            <span class="product-slide__brand-mark">C</span>
            <span class="product-slide__brand-name">CODIFY</span>
          </div>
          <span class="product-slide__context">{{ t(slide.kickerKey) }}</span>
          <span class="product-slide__counter">{{ String(index + 1).padStart(2, '0') }} / {{ String(slides.length).padStart(2, '0') }}</span>
          </header>

          <div class="product-slide__body">
            <div class="product-slide__copy">
            <p class="product-slide__overline">
              <span class="product-slide__overline-rule" aria-hidden="true" />
              {{ t(slide.overlineKey) }}
            </p>
            <h2
              class="product-slide__title"
              :data-testid="variant === 'onboarding' ? 'onboarding-step-title' : undefined"
            >
              {{ t(slide.titleKey) }}
            </h2>
            <p class="product-slide__body-copy">{{ t(slide.bodyKey) }}</p>
            <p class="product-slide__note">
              <span class="product-slide__note-mark" aria-hidden="true">↳</span>
              {{ t(slide.noteKey) }}
            </p>
            </div>

            <div class="product-slide__visual" aria-hidden="true">
              <!-- The visual is deliberately CSS-built: it stays crisp, local, and legible at every stage scale. -->
              <div v-if="slide.visual === 'layers'" class="visual-layers">
                <div class="visual-layers__beam visual-layers__beam--model">
                  <span>01</span>
                  <div><strong>{{ t('productSlides.labels.modelLayer') }}</strong><small>{{ t('productSlides.labels.modelLayerDetail') }}</small></div>
                  <b>token →</b>
                </div>
                <div class="visual-layers__connector"><i />{{ t('productSlides.labels.nextLayer') }}<i /></div>
                <div class="visual-layers__beam visual-layers__beam--harness">
                  <span>02</span>
                  <div><strong>{{ t('productSlides.labels.harnessLayer') }}</strong><small>{{ t('productSlides.labels.harnessLayerDetail') }}</small></div>
                  <b>turn ↻</b>
                </div>
                <div class="visual-layers__connector"><i />{{ t('productSlides.labels.nextLayer') }}<i /></div>
                <div class="visual-layers__beam visual-layers__beam--codify">
                  <span>03</span>
                  <div><strong>{{ t('productSlides.labels.codifyLayer') }}</strong><small>{{ t('productSlides.labels.codifyLayerDetail') }}</small></div>
                  <b>change ✓</b>
                </div>
              </div>

              <div v-else-if="slide.visual === 'model'" class="visual-model">
                <div class="visual-model__context">
                  <div class="visual-model__label"><span>01</span>{{ t('productSlides.labels.contextWindow') }}</div>
                  <div class="visual-model__tokens"><b>{{ t('productSlides.labels.prompt') }}</b><span>→</span><i>{{ t('productSlides.labels.tokens') }}</i><span>→</span><em>{{ t('productSlides.labels.history') }}</em></div>
                </div>
                <div class="visual-model__divider"><i />{{ t('productSlides.labels.nextToken') }}<i /></div>
                <div class="visual-model__prediction">
                  <div class="visual-model__prediction-head"><span>{{ t('productSlides.labels.probability') }}</span><strong>P(next token | context)</strong></div>
                  <div class="visual-model__candidate"><b>{{ t('productSlides.labels.change') }}</b><span><i style="width: 82%" /></span><em>0.82</em></div>
                  <div class="visual-model__candidate"><b>{{ t('productSlides.labels.review') }}</b><span><i style="width: 11%" /></span><em>0.11</em></div>
                  <div class="visual-model__candidate"><b>{{ t('productSlides.labels.delivery') }}</b><span><i style="width: 07%" /></span><em>0.07</em></div>
                </div>
                <div class="visual-model__repeat"><span>↻</span>{{ t('productSlides.labels.appendAndRepeat') }}</div>
              </div>

              <div v-else-if="slide.visual === 'harness'" class="visual-harness">
                <div class="visual-harness__loop">
                  <div class="visual-harness__node visual-harness__node--model"><span>01</span><strong>{{ t('productSlides.labels.model') }}</strong><small>{{ t('productSlides.labels.nextToken') }}</small></div>
                  <b class="visual-harness__arrow">→</b>
                  <div class="visual-harness__node visual-harness__node--request"><span>02</span><strong>{{ t('productSlides.labels.toolRequest') }}</strong><small>{{ t('productSlides.labels.intent') }}</small></div>
                  <b class="visual-harness__arrow">→</b>
                  <div class="visual-harness__node visual-harness__node--tool"><span>03</span><strong>{{ t('productSlides.labels.tool') }}</strong><small>{{ t('productSlides.labels.workspace') }}</small></div>
                  <b class="visual-harness__arrow">→</b>
                  <div class="visual-harness__node visual-harness__node--observation"><span>04</span><strong>{{ t('productSlides.labels.observation') }}</strong><small>{{ t('productSlides.labels.result') }}</small></div>
                </div>
                <div class="visual-harness__return"><span>↺</span>{{ t('productSlides.labels.feedBack') }}</div>
                <div class="visual-harness__state"><b>{{ t('productSlides.labels.session') }}</b><b>{{ t('productSlides.labels.skills') }}</b><b>{{ t('productSlides.labels.capabilityGate') }}</b></div>
              </div>

              <div v-else-if="slide.visual === 'boundary'" class="visual-boundary">
                <div class="visual-boundary__endpoint"><small>{{ t('productSlides.labels.input') }}</small><strong>{{ t('productSlides.labels.prompt') }} + {{ t('productSlides.labels.context') }}</strong></div>
                <b class="visual-boundary__arrow">→</b>
                <div class="visual-boundary__contract">
                  <div class="visual-boundary__contract-head"><span>C</span><strong>{{ t('productSlides.labels.harness') }}</strong></div>
                  <div class="visual-boundary__chips"><b>{{ t('productSlides.labels.adapter') }}</b><b>{{ t('productSlides.labels.protocol') }}</b><b>{{ t('productSlides.labels.session') }}</b><b>{{ t('productSlides.labels.capabilityGate') }}</b></div>
                </div>
                <b class="visual-boundary__arrow">→</b>
                <div class="visual-boundary__endpoint visual-boundary__endpoint--result"><small>{{ t('productSlides.labels.output') }}</small><strong>{{ t('productSlides.labels.events') }} + {{ t('productSlides.labels.result') }}</strong></div>
                <div class="visual-boundary__caption">{{ t('productSlides.labels.harnessBoundary') }}</div>
              </div>

              <div v-else-if="slide.visual === 'codify'" class="visual-codify">
                <div class="visual-codify__path">
                  <div class="visual-codify__node visual-codify__node--issue"><span>01</span><strong>{{ t('productSlides.labels.issue') }}</strong><small>{{ t('productSlides.labels.durableContext') }}</small></div>
                  <b>→</b>
                  <div class="visual-codify__node visual-codify__node--task"><span>02</span><strong>{{ t('productSlides.labels.taskSnapshot') }}</strong><small>{{ t('productSlides.labels.frozenIdentity') }}</small></div>
                  <b>→</b>
                  <div class="visual-codify__node visual-codify__node--worker"><span>03</span><strong>{{ t('productSlides.labels.worker') }}</strong><small>{{ t('productSlides.labels.isolated') }}</small></div>
                </div>
                <div class="visual-codify__branch"><i />{{ t('productSlides.labels.scheduler') }} → {{ t('productSlides.labels.events') }} → {{ t('productSlides.labels.delivery') }}<i /></div>
                <div class="visual-codify__result"><span>04</span><div><small>{{ t('productSlides.labels.reviewableResult') }}</small><strong>{{ t('productSlides.labels.branch') }} → {{ t('productSlides.labels.mergeRequest') }}</strong></div><b>✓</b></div>
              </div>

              <div v-else-if="slide.visual === 'stack'" class="visual-stack">
                <div class="visual-stack__layer visual-stack__layer--codify">
                  <span>03</span><strong>{{ t('productSlides.labels.codifyLayer') }}</strong><small>{{ t('productSlides.labels.issue') }} · {{ t('productSlides.labels.task') }} · {{ t('productSlides.labels.delivery') }}</small>
                  <div class="visual-stack__layer visual-stack__layer--harness">
                    <span>02</span><strong>{{ t('productSlides.labels.harnessLayer') }}</strong><small>{{ t('productSlides.labels.prompt') }} · {{ t('productSlides.labels.tool') }} · {{ t('productSlides.labels.session') }}</small>
                    <div class="visual-stack__layer visual-stack__layer--model">
                      <span>01</span><strong>{{ t('productSlides.labels.modelLayer') }}</strong><small>{{ t('productSlides.labels.tokens') }} · {{ t('productSlides.labels.nextToken') }}</small>
                    </div>
                  </div>
                </div>
                <div class="visual-stack__caption">{{ t('productSlides.labels.lowerLayer') }} → {{ t('productSlides.labels.upperLayer') }} → {{ t('productSlides.labels.reviewableResult') }}</div>
              </div>

              <div v-else-if="slide.visual === 'debug'" class="visual-debug">
                <div class="visual-debug__row"><span>01</span><div><small>{{ t('productSlides.labels.symptom') }}</small><strong>{{ t('productSlides.labels.outputQuality') }}</strong></div><b>→</b><em>{{ t('productSlides.labels.promptModel') }}</em></div>
                <div class="visual-debug__row"><span>02</span><div><small>{{ t('productSlides.labels.symptom') }}</small><strong>{{ t('productSlides.labels.toolOrSession') }}</strong></div><b>→</b><em>{{ t('productSlides.labels.harnessRuntime') }}</em></div>
                <div class="visual-debug__row"><span>03</span><div><small>{{ t('productSlides.labels.symptom') }}</small><strong>{{ t('productSlides.labels.queueOrDelivery') }}</strong></div><b>→</b><em>{{ t('productSlides.labels.codifyWorker') }}</em></div>
              </div>

              <div v-else-if="slide.visual === 'intent'" class="visual-intent">
              <div class="visual-intent__axis visual-intent__axis--vertical" />
              <div class="visual-intent__orbit visual-intent__orbit--outer" />
              <div class="visual-intent__orbit visual-intent__orbit--inner" />
              <div class="visual-intent__core">
                <span class="visual-intent__core-mark">C</span>
                <span class="visual-intent__core-label">{{ t('productSlides.labels.goal') }}</span>
              </div>
              <span class="visual-intent__tag visual-intent__tag--top">{{ t('productSlides.labels.issue') }}</span>
              <span class="visual-intent__tag visual-intent__tag--right">{{ t('productSlides.labels.change') }}</span>
              <span class="visual-intent__tag visual-intent__tag--bottom">{{ t('productSlides.labels.trace') }}</span>
              <span class="visual-intent__arrow">→</span>
            </div>

            <div v-else-if="slide.visual === 'issue'" class="visual-issue">
              <div class="visual-window__bar">
                <span class="visual-window__dots"><i /><i /><i /></span>
                <span>{{ t('productSlides.labels.issue') }} / codify-42</span>
                <span class="visual-window__status">{{ t('productSlides.labels.active') }}</span>
              </div>
              <div class="visual-issue__stack">
                <div class="visual-issue__card visual-issue__card--issue">
                  <span class="visual-issue__index">01</span>
                  <div><strong>{{ t('productSlides.labels.issue') }}</strong><small>{{ t('productSlides.labels.durableContext') }}</small></div>
                  <span class="visual-issue__pill">OPEN</span>
                </div>
                <div class="visual-issue__card visual-issue__card--task">
                  <span class="visual-issue__index">02</span>
                  <div><strong>{{ t('productSlides.labels.task') }}</strong><small>{{ t('productSlides.labels.executionUnit') }}</small></div>
                  <span class="visual-issue__pill visual-issue__pill--mint">P1</span>
                </div>
                <div class="visual-issue__card visual-issue__card--mr">
                  <span class="visual-issue__index">03</span>
                  <div><strong>{{ t('productSlides.labels.mr') }}</strong><small>{{ t('productSlides.labels.reviewableResult') }}</small></div>
                  <span class="visual-issue__pill visual-issue__pill--amber">MR</span>
                </div>
              </div>
              <div class="visual-issue__branch"><span />{{ t('productSlides.labels.sharedBranch') }}<b>codify/issue-42</b></div>
            </div>

            <div v-else-if="slide.visual === 'system'" class="visual-system">
              <div class="visual-window__bar">
                <span class="visual-window__dots"><i /><i /><i /></span>
                <span>{{ t('productSlides.labels.task') }} / 1042</span>
                <span class="visual-window__status visual-window__status--live"><i />{{ t('productSlides.labels.running') }}</span>
              </div>
              <div class="visual-system__track">
                <div class="visual-system__stage visual-system__stage--done"><span>01</span><strong>{{ t('productSlides.labels.queue') }}</strong><small>P0 · P1 · P2</small></div>
                <div class="visual-system__connector" />
                <div class="visual-system__stage visual-system__stage--active"><span>02</span><strong>{{ t('productSlides.labels.isolated') }}</strong><small>Docker</small></div>
                <div class="visual-system__connector" />
                <div class="visual-system__stage"><span>03</span><strong>{{ t('productSlides.labels.harness') }}</strong><small>{{ t('productSlides.labels.toolsAndSkills') }}</small></div>
                <div class="visual-system__connector" />
                <div class="visual-system__stage"><span>04</span><strong>{{ t('productSlides.labels.delivery') }}</strong><small>{{ t('productSlides.labels.commitToMr') }}</small></div>
              </div>
              <div class="visual-system__terminal"><span>›</span><span>worker/task-1042</span><b>{{ t('productSlides.labels.ready') }}</b></div>
            </div>

            <div v-else-if="slide.visual === 'review'" class="visual-review">
              <div class="visual-review__summary">
                <span class="visual-review__check">✓</span>
                <div><strong>{{ t('productSlides.labels.completed') }}</strong><small>task-1042 · 08:42</small></div>
                <span class="visual-review__summary-value">+128 −34</span>
              </div>
              <div class="visual-review__timeline">
                <div class="visual-review__event"><span class="visual-review__event-dot visual-review__event-dot--blue" /><div><small>{{ t('productSlides.labels.eventStream') }}</small><strong>{{ t('productSlides.labels.executionTracked') }}</strong></div><b>✓</b></div>
                <div class="visual-review__event"><span class="visual-review__event-dot visual-review__event-dot--mint" /><div><small>{{ t('productSlides.labels.commit') }}</small><strong>feat: refine task flow</strong></div><b>3</b></div>
                <div class="visual-review__event"><span class="visual-review__event-dot visual-review__event-dot--amber" /><div><small>{{ t('productSlides.labels.mr') }}</small><strong>{{ t('productSlides.labels.reviewableResult') }}</strong></div><b>↗</b></div>
              </div>
              <div class="visual-review__mr"><span>MR</span><div><small>{{ t('productSlides.labels.mergeRequest') }}</small><strong>Draft: refine task flow</strong></div><b>{{ t('productSlides.labels.review') }} ↗</b></div>
            </div>

            <div v-else-if="slide.visual === 'start'" class="visual-start">
              <div class="visual-start__card visual-start__card--prompt">
                <span class="visual-start__label">{{ t('productSlides.labels.whatToWrite') }}</span>
                <strong>{{ t('productSlides.labels.goal') }}</strong>
                <p>{{ t('productSlides.labels.specificOutcome') }}</p>
                <div class="visual-start__cursor" />
              </div>
              <div class="visual-start__handoff"><span />{{ t('productSlides.labels.thenCodify') }}<span /></div>
              <div class="visual-start__returns">
                <span>{{ t('productSlides.labels.whatYouGet') }}</span>
                <div><b>{{ t('productSlides.labels.workspace') }}</b><b>{{ t('productSlides.labels.logs') }}</b><b>{{ t('productSlides.labels.commits') }}</b><b>{{ t('productSlides.labels.mr') }}</b></div>
              </div>
            </div>

            <div v-else-if="slide.visual === 'prompt'" class="visual-prompt">
              <div class="visual-window__bar">
                <span class="visual-window__dots"><i /><i /><i /></span>
                <span>{{ t('productSlides.labels.newTask') }}</span>
                <span class="visual-window__status">P1</span>
              </div>
              <div class="visual-prompt__row"><span>01</span><b>{{ t('productSlides.labels.goal') }}</b><strong>{{ t('productSlides.labels.specificOutcome') }}</strong></div>
              <div class="visual-prompt__row"><span>02</span><b>{{ t('productSlides.labels.scope') }}</b><strong>{{ t('productSlides.labels.concreteScope') }}</strong></div>
              <div class="visual-prompt__row"><span>03</span><b>{{ t('productSlides.labels.verify') }}</b><strong>{{ t('productSlides.labels.acceptanceCriteria') }}</strong></div>
              <div class="visual-prompt__footer"><span>{{ t('productSlides.labels.runInstruction') }}</span><b>{{ t('productSlides.labels.implementation') }}</b><i>→</i></div>
            </div>

            <div v-else-if="slide.visual === 'modes'" class="visual-modes">
              <div class="visual-modes__choice visual-modes__choice--active"><span>01</span><div><strong>{{ t('productSlides.labels.implementation') }}</strong><small>{{ t('productSlides.labels.changeAndCommit') }}</small></div><b>✓</b></div>
              <div class="visual-modes__choice"><span>02</span><div><strong>{{ t('productSlides.labels.analysis') }}</strong><small>{{ t('productSlides.labels.inspectAndReport') }}</small></div><b>○</b></div>
              <div class="visual-modes__choice"><span>03</span><div><strong>{{ t('productSlides.labels.ciRepair') }}</strong><small>{{ t('productSlides.labels.repairFailedPipeline') }}</small></div><b>○</b></div>
              <div class="visual-modes__tip"><span>↳</span>{{ t('productSlides.labels.chooseByOutcome') }}</div>
            </div>

            <div v-else-if="slide.visual === 'followup'" class="visual-followup">
              <div class="visual-followup__branch"><span /><b>codify/issue-42</b><span /></div>
              <div class="visual-followup__tasks">
                <div class="visual-followup__task"><small>{{ t('productSlides.labels.task') }} 01</small><strong>{{ t('productSlides.labels.firstPass') }}</strong><span>✓</span></div>
                <div class="visual-followup__arrow">→</div>
                <div class="visual-followup__task visual-followup__task--active"><small>{{ t('productSlides.labels.task') }} 02</small><strong>{{ t('productSlides.labels.nextPass') }}</strong><span>＋</span></div>
              </div>
              <div class="visual-followup__shared"><b>{{ t('productSlides.labels.sameWorkspace') }}</b><b>{{ t('productSlides.labels.sameSession') }}</b><b>{{ t('productSlides.labels.sameBranch') }}</b></div>
            </div>

            <div v-else class="visual-delivery">
              <div class="visual-delivery__line"><span class="visual-delivery__node visual-delivery__node--done">✓</span><div><small>{{ t('productSlides.labels.commit') }}</small><strong>feat: ship change</strong></div></div>
              <div class="visual-delivery__line"><span class="visual-delivery__node visual-delivery__node--active">MR</span><div><small>{{ t('productSlides.labels.mergeRequest') }}</small><strong>{{ t('productSlides.labels.teamReview') }}</strong></div><b>↗</b></div>
              <div class="visual-delivery__line"><span class="visual-delivery__node">✓</span><div><small>{{ t('productSlides.labels.merge') }}</small><strong>{{ t('productSlides.labels.issueCloses') }}</strong></div></div>
              <div class="visual-delivery__stamp">{{ t('productSlides.labels.reviewable') }}</div>
            </div>
          </div>
        </div>

      </section>
    </main>

    <nav class="product-slides__controls" :aria-label="t('productSlides.controls.slideNavigation')">
      <button
        v-for="(slide, index) in slides"
        :key="`control-${slide.id}`"
        type="button"
        class="product-slides__control"
        :class="{ 'product-slides__control--active': index === currentIndex }"
        :aria-label="t('productSlides.controls.goToSlide', { number: index + 1 })"
        :aria-current="index === currentIndex ? 'step' : undefined"
        @click="goToSlide(index)"
      >
        <span>{{ String(index + 1).padStart(2, '0') }}</span>
      </button>
    </nav>
    <p class="product-slides__keyboard-hint">{{ t('productSlides.controls.keyboardHint') }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export type ProductSlidesVariant = 'onboarding' | 'quick-start' | 'create-task' | 'delivery' | 'how-it-works'
type ProductSlideVisual = 'intent' | 'issue' | 'system' | 'review' | 'start' | 'prompt' | 'modes' | 'followup' | 'delivery' | 'layers' | 'model' | 'harness' | 'boundary' | 'codify' | 'stack' | 'debug'
type ProductSlideAccent = 'blue' | 'mint' | 'amber' | 'violet'

interface ProductSlideDefinition {
  id: string
  visual: ProductSlideVisual
  accent: ProductSlideAccent
  kickerKey: string
  overlineKey: string
  titleKey: string
  bodyKey: string
  noteKey: string
}

const ONBOARDING_SLIDES: ProductSlideDefinition[] = [
  { id: 'intent', visual: 'intent', accent: 'blue', kickerKey: 'onboarding.slides.intent.kicker', overlineKey: 'onboarding.slides.intent.overline', titleKey: 'onboarding.slides.intent.title', bodyKey: 'onboarding.slides.intent.body', noteKey: 'onboarding.slides.intent.note' },
  { id: 'issue', visual: 'issue', accent: 'mint', kickerKey: 'onboarding.slides.issue.kicker', overlineKey: 'onboarding.slides.issue.overline', titleKey: 'onboarding.slides.issue.title', bodyKey: 'onboarding.slides.issue.body', noteKey: 'onboarding.slides.issue.note' },
  { id: 'system', visual: 'system', accent: 'blue', kickerKey: 'onboarding.slides.system.kicker', overlineKey: 'onboarding.slides.system.overline', titleKey: 'onboarding.slides.system.title', bodyKey: 'onboarding.slides.system.body', noteKey: 'onboarding.slides.system.note' },
  { id: 'review', visual: 'review', accent: 'amber', kickerKey: 'onboarding.slides.review.kicker', overlineKey: 'onboarding.slides.review.overline', titleKey: 'onboarding.slides.review.title', bodyKey: 'onboarding.slides.review.body', noteKey: 'onboarding.slides.review.note' },
  { id: 'start', visual: 'start', accent: 'violet', kickerKey: 'onboarding.slides.start.kicker', overlineKey: 'onboarding.slides.start.overline', titleKey: 'onboarding.slides.start.title', bodyKey: 'onboarding.slides.start.body', noteKey: 'onboarding.slides.start.note' },
]

const QUICK_START_SLIDES: ProductSlideDefinition[] = [
  { id: 'issue', visual: 'issue', accent: 'mint', kickerKey: 'guide.slides.quickStart.issue.kicker', overlineKey: 'guide.slides.quickStart.issue.overline', titleKey: 'guide.slides.quickStart.issue.title', bodyKey: 'guide.slides.quickStart.issue.body', noteKey: 'guide.slides.quickStart.issue.note' },
  { id: 'prompt', visual: 'prompt', accent: 'blue', kickerKey: 'guide.slides.quickStart.task.kicker', overlineKey: 'guide.slides.quickStart.task.overline', titleKey: 'guide.slides.quickStart.task.title', bodyKey: 'guide.slides.quickStart.task.body', noteKey: 'guide.slides.quickStart.task.note' },
  { id: 'system', visual: 'system', accent: 'violet', kickerKey: 'guide.slides.quickStart.run.kicker', overlineKey: 'guide.slides.quickStart.run.overline', titleKey: 'guide.slides.quickStart.run.title', bodyKey: 'guide.slides.quickStart.run.body', noteKey: 'guide.slides.quickStart.run.note' },
  { id: 'review', visual: 'review', accent: 'amber', kickerKey: 'guide.slides.quickStart.review.kicker', overlineKey: 'guide.slides.quickStart.review.overline', titleKey: 'guide.slides.quickStart.review.title', bodyKey: 'guide.slides.quickStart.review.body', noteKey: 'guide.slides.quickStart.review.note' },
]

const CREATE_TASK_SLIDES: ProductSlideDefinition[] = [
  { id: 'prompt', visual: 'prompt', accent: 'blue', kickerKey: 'guide.slides.createTask.prompt.kicker', overlineKey: 'guide.slides.createTask.prompt.overline', titleKey: 'guide.slides.createTask.prompt.title', bodyKey: 'guide.slides.createTask.prompt.body', noteKey: 'guide.slides.createTask.prompt.note' },
  { id: 'modes', visual: 'modes', accent: 'mint', kickerKey: 'guide.slides.createTask.mode.kicker', overlineKey: 'guide.slides.createTask.mode.overline', titleKey: 'guide.slides.createTask.mode.title', bodyKey: 'guide.slides.createTask.mode.body', noteKey: 'guide.slides.createTask.mode.note' },
  { id: 'system', visual: 'system', accent: 'violet', kickerKey: 'guide.slides.createTask.run.kicker', overlineKey: 'guide.slides.createTask.run.overline', titleKey: 'guide.slides.createTask.run.title', bodyKey: 'guide.slides.createTask.run.body', noteKey: 'guide.slides.createTask.run.note' },
  { id: 'followup', visual: 'followup', accent: 'amber', kickerKey: 'guide.slides.createTask.followup.kicker', overlineKey: 'guide.slides.createTask.followup.overline', titleKey: 'guide.slides.createTask.followup.title', bodyKey: 'guide.slides.createTask.followup.body', noteKey: 'guide.slides.createTask.followup.note' },
]

const DELIVERY_SLIDES: ProductSlideDefinition[] = [
  { id: 'review', visual: 'review', accent: 'amber', kickerKey: 'guide.slides.delivery.observe.kicker', overlineKey: 'guide.slides.delivery.observe.overline', titleKey: 'guide.slides.delivery.observe.title', bodyKey: 'guide.slides.delivery.observe.body', noteKey: 'guide.slides.delivery.observe.note' },
  { id: 'delivery', visual: 'delivery', accent: 'mint', kickerKey: 'guide.slides.delivery.ship.kicker', overlineKey: 'guide.slides.delivery.ship.overline', titleKey: 'guide.slides.delivery.ship.title', bodyKey: 'guide.slides.delivery.ship.body', noteKey: 'guide.slides.delivery.ship.note' },
  { id: 'followup', visual: 'followup', accent: 'blue', kickerKey: 'guide.slides.delivery.iterate.kicker', overlineKey: 'guide.slides.delivery.iterate.overline', titleKey: 'guide.slides.delivery.iterate.title', bodyKey: 'guide.slides.delivery.iterate.body', noteKey: 'guide.slides.delivery.iterate.note' },
]

const HOW_IT_WORKS_SLIDES: ProductSlideDefinition[] = [
  { id: 'map', visual: 'layers', accent: 'blue', kickerKey: 'guide.slides.howItWorks.map.kicker', overlineKey: 'guide.slides.howItWorks.map.overline', titleKey: 'guide.slides.howItWorks.map.title', bodyKey: 'guide.slides.howItWorks.map.body', noteKey: 'guide.slides.howItWorks.map.note' },
  { id: 'model', visual: 'model', accent: 'violet', kickerKey: 'guide.slides.howItWorks.model.kicker', overlineKey: 'guide.slides.howItWorks.model.overline', titleKey: 'guide.slides.howItWorks.model.title', bodyKey: 'guide.slides.howItWorks.model.body', noteKey: 'guide.slides.howItWorks.model.note' },
  { id: 'harness', visual: 'harness', accent: 'mint', kickerKey: 'guide.slides.howItWorks.harness.kicker', overlineKey: 'guide.slides.howItWorks.harness.overline', titleKey: 'guide.slides.howItWorks.harness.title', bodyKey: 'guide.slides.howItWorks.harness.body', noteKey: 'guide.slides.howItWorks.harness.note' },
  { id: 'boundary', visual: 'boundary', accent: 'amber', kickerKey: 'guide.slides.howItWorks.boundary.kicker', overlineKey: 'guide.slides.howItWorks.boundary.overline', titleKey: 'guide.slides.howItWorks.boundary.title', bodyKey: 'guide.slides.howItWorks.boundary.body', noteKey: 'guide.slides.howItWorks.boundary.note' },
  { id: 'codify', visual: 'codify', accent: 'blue', kickerKey: 'guide.slides.howItWorks.codify.kicker', overlineKey: 'guide.slides.howItWorks.codify.overline', titleKey: 'guide.slides.howItWorks.codify.title', bodyKey: 'guide.slides.howItWorks.codify.body', noteKey: 'guide.slides.howItWorks.codify.note' },
  { id: 'stack', visual: 'stack', accent: 'mint', kickerKey: 'guide.slides.howItWorks.compose.kicker', overlineKey: 'guide.slides.howItWorks.compose.overline', titleKey: 'guide.slides.howItWorks.compose.title', bodyKey: 'guide.slides.howItWorks.compose.body', noteKey: 'guide.slides.howItWorks.compose.note' },
  { id: 'debug', visual: 'debug', accent: 'amber', kickerKey: 'guide.slides.howItWorks.debug.kicker', overlineKey: 'guide.slides.howItWorks.debug.overline', titleKey: 'guide.slides.howItWorks.debug.title', bodyKey: 'guide.slides.howItWorks.debug.body', noteKey: 'guide.slides.howItWorks.debug.note' },
]

const SLIDE_DECKS: Record<ProductSlidesVariant, ProductSlideDefinition[]> = {
  onboarding: ONBOARDING_SLIDES,
  'quick-start': QUICK_START_SLIDES,
  'create-task': CREATE_TASK_SLIDES,
  delivery: DELIVERY_SLIDES,
  'how-it-works': HOW_IT_WORKS_SLIDES,
}

const props = withDefaults(defineProps<{
  variant: ProductSlidesVariant
  current?: number
  initial?: number
  compact?: boolean
}>(), {
  current: undefined,
  initial: 0,
  compact: false,
})

const emit = defineEmits<{
  'update:current': [value: number]
}>()

const { t } = useI18n()
const viewportRef = ref<HTMLElement | null>(null)
const stageRef = ref<HTMLElement | null>(null)
const internalCurrent = ref(props.initial)
const stageStyle = ref<Record<string, string>>({})
const pointerStartX = ref<number | null>(null)
let resizeObserver: ResizeObserver | null = null
let wheelLockedUntil = 0

const slides = computed(() => SLIDE_DECKS[props.variant])
const currentIndex = computed(() => Math.max(0, Math.min(props.current ?? internalCurrent.value, slides.value.length - 1)))

function goToSlide(index: number): void {
  const next = Math.max(0, Math.min(index, slides.value.length - 1))
  if (props.current === undefined) internalCurrent.value = next
  emit('update:current', next)
}

function goToNext(): void {
  goToSlide(currentIndex.value + 1)
}

function goToPrevious(): void {
  goToSlide(currentIndex.value - 1)
}

function handleKeydown(event: KeyboardEvent): void {
  if ((event.target as HTMLElement | null)?.closest('button')) return
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown' || event.key === 'PageDown' || event.key === ' ') {
    event.preventDefault()
    goToNext()
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp' || event.key === 'PageUp') {
    event.preventDefault()
    goToPrevious()
  } else if (event.key === 'Home') {
    event.preventDefault()
    goToSlide(0)
  } else if (event.key === 'End') {
    event.preventDefault()
    goToSlide(slides.value.length - 1)
  }
}

function handleWheel(event: WheelEvent): void {
  const now = Date.now()
  if (now < wheelLockedUntil || Math.abs(event.deltaY) < 18) return
  wheelLockedUntil = now + 420
  if (event.deltaY > 0) goToNext()
  else goToPrevious()
}

function handlePointerDown(event: PointerEvent): void {
  pointerStartX.value = event.clientX
}

function handlePointerUp(event: PointerEvent): void {
  if (pointerStartX.value === null) return
  const distance = event.clientX - pointerStartX.value
  pointerStartX.value = null
  if (Math.abs(distance) < 36) return
  if (distance < 0) goToNext()
  else goToPrevious()
}

function handlePointerCancel(): void {
  pointerStartX.value = null
}

function updateStageScale(): void {
  const viewport = viewportRef.value
  if (!viewport) return
  const { width, height } = viewport.getBoundingClientRect()
  if (!width || !height) return
  const scale = Math.min(width / 1920, height / 1080)
  const offsetX = (width - 1920 * scale) / 2
  const offsetY = (height - 1080 * scale) / 2
  stageStyle.value = {
    transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
  }
}

watch(() => props.variant, () => {
  if (props.current === undefined) internalCurrent.value = 0
  updateStageScale()
})

onMounted(() => {
  const viewport = viewportRef.value
  if (!viewport) return
  resizeObserver = new ResizeObserver(updateStageScale)
  resizeObserver.observe(viewport)
  window.addEventListener('resize', updateStageScale)
  viewport.addEventListener('wheel', handleWheel, { passive: true })
  updateStageScale()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', updateStageScale)
  viewportRef.value?.removeEventListener('wheel', handleWheel)
})
</script>

<style scoped>
/* === FIXED 16:9 STAGE === */
/* Adapted from viewport-base.css for an embedded app surface: the document itself
   must keep scrolling, while the authored slide canvas stays 1920×1080. */
.product-slides__viewport {
  --deck-ink: #09192f;
  --deck-ink-soft: #102746;
  --deck-paper: #f4f7fb;
  --deck-blue: #4b7cff;
  --deck-mint: #6ee0c1;
  --deck-amber: #ffc86b;
  --deck-violet: #b6a7ff;
  --deck-text: #f5f8ff;
  --deck-muted: rgba(225, 235, 250, 0.68);
  --deck-line: rgba(197, 217, 246, 0.18);
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  isolation: isolate;
  background: var(--deck-ink);
  outline: none;
}

.product-slides__stage {
  position: absolute;
  left: 0;
  top: 0;
  width: 1920px;
  height: 1080px;
  overflow: hidden;
  transform-origin: 0 0;
  background: var(--deck-ink);
}

.product-slide {
  position: absolute;
  inset: 0;
  width: 1920px;
  height: 1080px;
  overflow: hidden;
  visibility: hidden;
  opacity: 0;
  pointer-events: none;
  background: var(--deck-ink);
  transform: translateX(34px) scale(0.985);
  transition: opacity 420ms ease, transform 560ms cubic-bezier(0.16, 1, 0.3, 1), visibility 0s linear 560ms;
}

.product-slide.active,
.product-slide.visible {
  visibility: visible;
  opacity: 1;
  pointer-events: auto;
  z-index: 1;
  transform: translateX(0) scale(1);
  transition-delay: 0s;
}

/* === ATMOSPHERE AND GRID === */
.product-slide__grid {
  position: absolute;
  inset: 0;
  opacity: 0.58;
  background-image: linear-gradient(rgba(174, 202, 244, 0.075) 1px, transparent 1px), linear-gradient(90deg, rgba(174, 202, 244, 0.075) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: linear-gradient(90deg, rgba(0, 0, 0, 0.66), transparent 72%);
}

.product-slide__wash {
  position: absolute;
  inset: -180px -100px -180px 44%;
  background: radial-gradient(circle at 52% 44%, rgba(75, 124, 255, 0.26), transparent 52%), radial-gradient(circle at 80% 80%, rgba(110, 224, 193, 0.1), transparent 42%);
  opacity: 0.85;
  pointer-events: none;
}

.product-slide--mint .product-slide__wash {
  background: radial-gradient(circle at 58% 42%, rgba(110, 224, 193, 0.22), transparent 53%), radial-gradient(circle at 86% 80%, rgba(75, 124, 255, 0.12), transparent 42%);
}

.product-slide--amber .product-slide__wash {
  background: radial-gradient(circle at 58% 42%, rgba(255, 200, 107, 0.2), transparent 53%), radial-gradient(circle at 86% 80%, rgba(75, 124, 255, 0.12), transparent 42%);
}

.product-slide--violet .product-slide__wash {
  background: radial-gradient(circle at 58% 42%, rgba(182, 167, 255, 0.2), transparent 53%), radial-gradient(circle at 86% 80%, rgba(110, 224, 193, 0.1), transparent 42%);
}

/* === SLIDE CHROME === */
.product-slide__topbar {
  position: absolute;
  top: 58px;
  left: 72px;
  right: 72px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 28px;
  color: var(--deck-muted);
  font-size: 19px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.product-slide__brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: var(--deck-text);
  font-weight: 700;
  letter-spacing: 0.14em;
}

.product-slide__brand-mark {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.55);
  border-radius: 10px;
  color: var(--deck-mint);
  font-size: 19px;
  letter-spacing: 0;
}

.product-slide__context {
  overflow: hidden;
  color: rgba(225, 235, 250, 0.52);
  font-size: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-slide__counter {
  margin-left: auto;
  color: rgba(225, 235, 250, 0.5);
  font-variant-numeric: tabular-nums;
  font-size: 16px;
}

.product-slide__body {
  position: absolute;
  inset: 190px 72px 142px;
  z-index: 1;
  display: grid;
  grid-template-columns: 0.84fr 1.16fr;
  gap: 76px;
  align-items: center;
}

.product-slide__copy {
  max-width: 690px;
}

.product-slide__overline {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 24px;
  color: var(--deck-mint);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.product-slide--amber .product-slide__overline { color: var(--deck-amber); }
.product-slide--violet .product-slide__overline { color: var(--deck-violet); }

.product-slide__overline-rule {
  width: 54px;
  height: 2px;
  background: currentColor;
  box-shadow: 18px 0 0 rgba(255, 255, 255, 0.2);
}

.product-slide__title {
  max-width: 710px;
  margin: 0;
  color: var(--deck-text);
  font-size: 82px;
  font-weight: 600;
  letter-spacing: -0.055em;
  line-height: 0.99;
}

.product-slide__body-copy {
  max-width: 620px;
  margin: 28px 0 0;
  color: var(--deck-muted);
  font-size: 27px;
  line-height: 1.42;
}

.product-slide__note {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 590px;
  margin: 40px 0 0;
  color: rgba(225, 235, 250, 0.46);
  font-size: 17px;
  line-height: 1.45;
}

.product-slide__note-mark {
  color: var(--deck-blue);
  font-size: 24px;
  line-height: 1;
}

/* === VISUAL: THREE-LAYER MAP === */
.visual-layers { width: 820px; }
.visual-layers__beam { display: grid; grid-template-columns: 58px minmax(0, 1fr) auto; align-items: center; gap: 18px; min-height: 136px; padding: 24px 28px; border: 1px solid rgba(197, 217, 246, 0.17); border-radius: 15px; background: rgba(17, 39, 70, 0.7); }
.visual-layers__beam--model { border-color: rgba(182, 167, 255, 0.5); background: rgba(42, 35, 78, 0.68); }
.visual-layers__beam--harness { border-color: rgba(110, 224, 193, 0.48); background: rgba(17, 59, 62, 0.68); }
.visual-layers__beam--codify { border-color: rgba(75, 124, 255, 0.52); background: rgba(20, 48, 91, 0.74); }
.visual-layers__beam > span { color: rgba(225, 235, 250, 0.42); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 16px; }
.visual-layers__beam strong { display: block; color: var(--deck-text); font-size: 28px; font-weight: 600; }
.visual-layers__beam small { display: block; margin-top: 7px; color: var(--deck-muted); font-size: 15px; }
.visual-layers__beam b { color: var(--deck-mint); font-size: 15px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; }
.visual-layers__beam--model b { color: var(--deck-violet); }
.visual-layers__beam--codify b { color: var(--deck-blue); }
.visual-layers__connector { display: flex; align-items: center; gap: 12px; margin: 12px 34px; color: rgba(225, 235, 250, 0.42); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; }
.visual-layers__connector i { flex: 1; height: 1px; background: linear-gradient(90deg, transparent, var(--deck-line)); }
.visual-layers__connector i:last-child { background: linear-gradient(90deg, var(--deck-line), transparent); }

/* === VISUAL: MODEL PREDICTION LOOP === */
.visual-model { width: 820px; padding: 24px; border: 1px solid rgba(182, 167, 255, 0.32); border-radius: 17px; background: rgba(15, 25, 55, 0.62); box-shadow: 0 24px 64px rgba(0, 0, 0, 0.2); }
.visual-model__context { padding: 20px 22px; border: 1px solid rgba(197, 217, 246, 0.16); border-radius: 11px; background: rgba(17, 39, 70, 0.62); }
.visual-model__label { display: flex; align-items: center; gap: 12px; color: var(--deck-violet); font-size: 14px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }
.visual-model__label span { color: rgba(225, 235, 250, 0.35); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.visual-model__tokens { display: flex; align-items: center; gap: 12px; margin-top: 22px; color: var(--deck-muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 16px; }
.visual-model__tokens b, .visual-model__tokens i, .visual-model__tokens em { padding: 10px 12px; border-radius: 7px; font-style: normal; font-weight: 500; }
.visual-model__tokens b { background: rgba(75, 124, 255, 0.15); color: var(--deck-blue); }
.visual-model__tokens i { background: rgba(110, 224, 193, 0.12); color: var(--deck-mint); }
.visual-model__tokens em { background: rgba(182, 167, 255, 0.12); color: var(--deck-violet); }
.visual-model__divider { display: flex; align-items: center; gap: 14px; margin: 17px 34px; color: var(--deck-amber); font-size: 13px; letter-spacing: 0.1em; text-align: center; text-transform: uppercase; }
.visual-model__divider i { flex: 1; height: 1px; background: linear-gradient(90deg, transparent, rgba(255, 200, 107, 0.5)); }
.visual-model__divider i:last-child { background: linear-gradient(90deg, rgba(255, 200, 107, 0.5), transparent); }
.visual-model__prediction { padding: 21px 22px 16px; border: 1px solid rgba(255, 200, 107, 0.24); border-radius: 11px; background: rgba(59, 47, 28, 0.46); }
.visual-model__prediction-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding-bottom: 13px; border-bottom: 1px solid rgba(255, 200, 107, 0.16); }
.visual-model__prediction-head span { color: rgba(225, 235, 250, 0.5); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; }
.visual-model__prediction-head strong { color: var(--deck-amber); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 16px; font-weight: 500; }
.visual-model__candidate { display: grid; grid-template-columns: 140px minmax(0, 1fr) 48px; align-items: center; gap: 16px; min-height: 42px; }
.visual-model__candidate b { color: var(--deck-text); font-size: 16px; font-weight: 500; }
.visual-model__candidate > span { height: 6px; overflow: hidden; border-radius: 999px; background: rgba(225, 235, 250, 0.12); }
.visual-model__candidate > span i { display: block; height: 100%; border-radius: inherit; background: var(--deck-blue); }
.visual-model__candidate:nth-of-type(3) > span i { background: var(--deck-mint); }
.visual-model__candidate:nth-of-type(4) > span i { background: var(--deck-violet); }
.visual-model__candidate em { color: rgba(225, 235, 250, 0.5); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; font-style: normal; text-align: right; }
.visual-model__repeat { display: flex; align-items: center; justify-content: center; gap: 11px; margin-top: 18px; color: var(--deck-mint); font-size: 14px; letter-spacing: 0.08em; text-transform: uppercase; }
.visual-model__repeat span { font-size: 24px; }

/* === VISUAL: HARNESS AGENT LOOP === */
.visual-harness { width: 840px; }
.visual-harness__loop { display: flex; align-items: stretch; gap: 10px; }
.visual-harness__node { flex: 1 1 0; min-width: 0; min-height: 154px; padding: 20px 16px; border: 1px solid rgba(197, 217, 246, 0.17); border-radius: 13px; background: rgba(17, 39, 70, 0.66); }
.visual-harness__node--model { border-color: rgba(182, 167, 255, 0.5); background: rgba(42, 35, 78, 0.62); }
.visual-harness__node--request { border-color: rgba(75, 124, 255, 0.5); background: rgba(20, 48, 91, 0.7); }
.visual-harness__node--tool { border-color: rgba(110, 224, 193, 0.48); background: rgba(17, 59, 62, 0.68); }
.visual-harness__node--observation { border-color: rgba(255, 200, 107, 0.45); background: rgba(59, 47, 28, 0.54); }
.visual-harness__node > span { color: rgba(225, 235, 250, 0.4); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.visual-harness__node strong { display: block; margin-top: 38px; color: var(--deck-text); font-size: 18px; font-weight: 600; }
.visual-harness__node small { display: block; margin-top: 7px; color: var(--deck-muted); font-size: 13px; }
.visual-harness__arrow { align-self: center; color: var(--deck-mint); font-size: 27px; font-weight: 400; }
.visual-harness__return { display: flex; align-items: center; justify-content: center; gap: 12px; margin: 24px 46px 0; padding: 15px 18px; border-top: 1px solid rgba(110, 224, 193, 0.3); border-bottom: 1px solid rgba(110, 224, 193, 0.18); color: var(--deck-mint); font-size: 14px; letter-spacing: 0.07em; text-align: center; text-transform: uppercase; }
.visual-harness__return span { font-size: 24px; }
.visual-harness__state { display: flex; gap: 10px; margin-top: 23px; }
.visual-harness__state b { flex: 1; padding: 11px 9px; border: 1px solid rgba(197, 217, 246, 0.14); border-radius: 8px; color: rgba(225, 235, 250, 0.64); font-size: 13px; font-weight: 500; text-align: center; }

/* === VISUAL: HARNESS CONTRACT BOUNDARY === */
.visual-boundary { display: grid; grid-template-columns: minmax(0, 1fr) 34px minmax(0, 1.5fr) 34px minmax(0, 1fr); align-items: center; gap: 12px; width: 840px; }
.visual-boundary__endpoint { min-height: 152px; padding: 22px 18px; border: 1px solid rgba(197, 217, 246, 0.17); border-radius: 13px; background: rgba(17, 39, 70, 0.66); }
.visual-boundary__endpoint--result { border-color: rgba(110, 224, 193, 0.36); background: rgba(17, 59, 62, 0.58); }
.visual-boundary__endpoint small { display: block; color: rgba(225, 235, 250, 0.45); font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase; }
.visual-boundary__endpoint strong { display: block; margin-top: 44px; color: var(--deck-text); font-size: 17px; font-weight: 500; line-height: 1.35; }
.visual-boundary__arrow { color: var(--deck-amber); font-size: 27px; font-weight: 400; text-align: center; }
.visual-boundary__contract { min-height: 250px; padding: 23px 22px; border: 1px solid rgba(255, 200, 107, 0.58); border-radius: 14px; background: rgba(59, 47, 28, 0.58); box-shadow: 0 0 0 8px rgba(255, 200, 107, 0.04); }
.visual-boundary__contract-head { display: flex; align-items: center; gap: 12px; padding-bottom: 18px; border-bottom: 1px solid rgba(255, 200, 107, 0.2); }
.visual-boundary__contract-head span { display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid var(--deck-amber); border-radius: 9px; color: var(--deck-amber); font-size: 15px; font-weight: 700; }
.visual-boundary__contract-head strong { color: var(--deck-text); font-size: 20px; font-weight: 600; }
.visual-boundary__chips { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin-top: 21px; }
.visual-boundary__chips b { padding: 11px 8px; border: 1px solid rgba(255, 200, 107, 0.18); border-radius: 7px; color: var(--deck-muted); font-size: 12px; font-weight: 500; text-align: center; }
.visual-boundary__caption { grid-column: 1 / -1; margin-top: 14px; color: rgba(225, 235, 250, 0.46); font-size: 14px; text-align: center; }

/* === VISUAL: CODIFY ORCHESTRATION PATH === */
.visual-codify { width: 840px; }
.visual-codify__path { display: grid; grid-template-columns: minmax(0, 1fr) 32px minmax(0, 1fr) 32px minmax(0, 1fr); align-items: stretch; gap: 10px; }
.visual-codify__path > b { align-self: center; color: var(--deck-blue); font-size: 27px; font-weight: 400; text-align: center; }
.visual-codify__node { min-height: 164px; padding: 21px 18px; border: 1px solid rgba(197, 217, 246, 0.17); border-radius: 13px; background: rgba(17, 39, 70, 0.66); }
.visual-codify__node--issue { border-color: rgba(110, 224, 193, 0.46); background: rgba(17, 59, 62, 0.62); }
.visual-codify__node--task { border-color: rgba(75, 124, 255, 0.48); background: rgba(20, 48, 91, 0.7); }
.visual-codify__node--worker { border-color: rgba(182, 167, 255, 0.44); background: rgba(42, 35, 78, 0.62); }
.visual-codify__node > span { color: rgba(225, 235, 250, 0.4); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.visual-codify__node strong { display: block; margin-top: 37px; color: var(--deck-text); font-size: 18px; font-weight: 600; }
.visual-codify__node small { display: block; margin-top: 7px; color: var(--deck-muted); font-size: 13px; line-height: 1.3; }
.visual-codify__branch { display: flex; align-items: center; gap: 12px; margin: 25px 32px; color: var(--deck-blue); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.visual-codify__branch i { flex: 1; height: 1px; background: linear-gradient(90deg, transparent, var(--deck-blue)); }
.visual-codify__branch i:last-child { background: linear-gradient(90deg, var(--deck-blue), transparent); }
.visual-codify__result { display: flex; align-items: center; gap: 16px; padding: 19px 22px; border: 1px solid rgba(110, 224, 193, 0.33); border-radius: 12px; background: rgba(15, 55, 59, 0.56); }
.visual-codify__result > span { color: var(--deck-mint); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.visual-codify__result small { display: block; color: rgba(225, 235, 250, 0.48); font-size: 13px; }
.visual-codify__result strong { display: block; margin-top: 6px; color: var(--deck-text); font-size: 18px; font-weight: 500; }
.visual-codify__result > b { margin-left: auto; color: var(--deck-mint); font-size: 23px; font-weight: 500; }

/* === VISUAL: LAYER COMPOSITION === */
.visual-stack { width: 820px; }
.visual-stack__layer { position: relative; min-height: 466px; padding: 25px 28px; border: 1px solid rgba(75, 124, 255, 0.5); border-radius: 16px; background: rgba(20, 48, 91, 0.68); }
.visual-stack__layer--harness { min-height: 302px; margin: 27px 0 0 38px; border-color: rgba(110, 224, 193, 0.46); background: rgba(17, 59, 62, 0.64); }
.visual-stack__layer--model { min-height: 140px; margin: 27px 0 0 38px; border-color: rgba(182, 167, 255, 0.5); background: rgba(42, 35, 78, 0.62); }
.visual-stack__layer > span { color: rgba(225, 235, 250, 0.4); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.visual-stack__layer > strong { margin-left: 12px; color: var(--deck-text); font-size: 21px; font-weight: 600; }
.visual-stack__layer > small { display: block; margin-top: 8px; color: var(--deck-muted); font-size: 14px; }
.visual-stack__layer--harness > strong { color: var(--deck-mint); }
.visual-stack__layer--model > strong { color: var(--deck-violet); }
.visual-stack__caption { margin-top: 21px; color: rgba(225, 235, 250, 0.5); font-size: 14px; letter-spacing: 0.06em; text-align: center; }

/* === VISUAL: DEBUG OWNERSHIP === */
.visual-debug { display: grid; gap: 14px; width: 820px; }
.visual-debug__row { display: grid; grid-template-columns: 46px minmax(0, 1fr) 28px 220px; align-items: center; gap: 15px; min-height: 104px; padding: 17px 21px; border: 1px solid rgba(197, 217, 246, 0.17); border-radius: 12px; background: rgba(17, 39, 70, 0.66); }
.visual-debug__row:nth-child(1) { border-color: rgba(182, 167, 255, 0.42); }
.visual-debug__row:nth-child(2) { border-color: rgba(110, 224, 193, 0.42); }
.visual-debug__row:nth-child(3) { border-color: rgba(255, 200, 107, 0.42); }
.visual-debug__row > span { color: rgba(225, 235, 250, 0.4); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.visual-debug__row small { display: block; color: rgba(225, 235, 250, 0.45); font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase; }
.visual-debug__row strong { display: block; margin-top: 7px; color: var(--deck-text); font-size: 17px; font-weight: 500; }
.visual-debug__row > b { color: var(--deck-amber); font-size: 23px; font-weight: 400; }
.visual-debug__row em { padding: 11px 13px; border-radius: 7px; background: rgba(255, 200, 107, 0.1); color: var(--deck-amber); font-size: 13px; font-style: normal; font-weight: 600; text-align: center; }

/* === VISUAL: INTENT ORBIT === */
.visual-intent {
  position: relative;
  width: 760px;
  height: 650px;
}

.visual-intent__axis--vertical {
  position: absolute;
  top: 45px;
  bottom: 45px;
  left: 50%;
  width: 1px;
  background: linear-gradient(transparent, rgba(110, 224, 193, 0.52), transparent);
}

.visual-intent__axis--vertical::after {
  position: absolute;
  top: 50%;
  left: -4px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--deck-mint);
  box-shadow: 0 0 24px rgba(110, 224, 193, 0.9);
  content: '';
}

.visual-intent__orbit {
  position: absolute;
  top: 50%;
  left: 50%;
  border: 1px solid rgba(197, 217, 246, 0.18);
  border-radius: 50%;
  transform: translate(-50%, -50%) rotate(-18deg);
}

.visual-intent__orbit--outer { width: 540px; height: 540px; }
.visual-intent__orbit--inner { width: 318px; height: 318px; border-color: rgba(75, 124, 255, 0.46); transform: translate(-50%, -50%) rotate(32deg); }

.visual-intent__orbit::before,
.visual-intent__orbit::after {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--deck-blue);
  box-shadow: 0 0 22px rgba(75, 124, 255, 0.9);
  content: '';
}

.visual-intent__orbit::before { top: 46px; left: 88px; }
.visual-intent__orbit::after { right: 42px; bottom: 92px; width: 8px; height: 8px; background: var(--deck-amber); box-shadow: 0 0 18px rgba(255, 200, 107, 0.86); }

.visual-intent__core {
  position: absolute;
  top: 50%;
  left: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 170px;
  height: 170px;
  border: 1px solid rgba(110, 224, 193, 0.72);
  border-radius: 50%;
  background: rgba(9, 25, 47, 0.92);
  box-shadow: 0 0 0 18px rgba(110, 224, 193, 0.04), 0 0 70px rgba(75, 124, 255, 0.22);
  transform: translate(-50%, -50%);
}

.visual-intent__core-mark { color: var(--deck-mint); font-size: 56px; font-weight: 700; line-height: 1; }
.visual-intent__core-label { margin-top: 9px; color: var(--deck-muted); font-size: 15px; letter-spacing: 0.16em; text-transform: uppercase; }

.visual-intent__tag {
  position: absolute;
  padding: 10px 14px;
  border: 1px solid rgba(197, 217, 246, 0.18);
  border-radius: 9px;
  background: rgba(13, 33, 61, 0.76);
  color: var(--deck-text);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.visual-intent__tag--top { top: 12px; left: 50%; transform: translateX(-50%); }
.visual-intent__tag--right { top: 47%; right: 2px; color: var(--deck-blue); }
.visual-intent__tag--bottom { bottom: 13px; left: 50%; color: var(--deck-amber); transform: translateX(-50%); }
.visual-intent__arrow { position: absolute; right: 102px; bottom: 194px; color: var(--deck-mint); font-size: 32px; }

/* === VISUAL: ISSUE STACK === */
.visual-issue,
.visual-prompt {
  width: 760px;
  padding: 28px;
  border: 1px solid rgba(197, 217, 246, 0.18);
  border-radius: 18px;
  background: rgba(7, 21, 42, 0.78);
  box-shadow: 0 28px 70px rgba(0, 0, 0, 0.22);
}

.visual-window__bar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 22px;
  border-bottom: 1px solid rgba(197, 217, 246, 0.12);
  color: rgba(225, 235, 250, 0.58);
  font-size: 15px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.visual-window__dots { display: inline-flex; gap: 6px; }
.visual-window__dots i { width: 8px; height: 8px; border-radius: 50%; background: rgba(225, 235, 250, 0.28); }
.visual-window__dots i:first-child { background: var(--deck-mint); }
.visual-window__status { margin-left: auto; color: var(--deck-mint); font-size: 13px; }
.visual-window__status--live { display: inline-flex; align-items: center; gap: 7px; }
.visual-window__status--live i { width: 7px; height: 7px; border-radius: 50%; background: var(--deck-mint); box-shadow: 0 0 12px var(--deck-mint); }

.visual-issue__stack { display: grid; gap: 16px; margin-top: 28px; }

.visual-issue__card {
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  min-height: 92px;
  padding: 16px 18px;
  border: 1px solid rgba(197, 217, 246, 0.14);
  border-radius: 13px;
  background: rgba(17, 39, 70, 0.7);
}

.visual-issue__card--task { margin-left: 44px; border-color: rgba(110, 224, 193, 0.28); }
.visual-issue__card--mr { margin-left: 88px; border-color: rgba(255, 200, 107, 0.26); }
.visual-issue__index { color: rgba(225, 235, 250, 0.42); font-size: 15px; font-variant-numeric: tabular-nums; }
.visual-issue__card strong { display: block; color: var(--deck-text); font-size: 22px; font-weight: 600; }
.visual-issue__card small { display: block; margin-top: 5px; color: var(--deck-muted); font-size: 14px; }
.visual-issue__pill { padding: 7px 9px; border-radius: 6px; background: rgba(75, 124, 255, 0.16); color: var(--deck-blue); font-size: 12px; font-weight: 700; letter-spacing: 0.1em; }
.visual-issue__pill--mint { background: rgba(110, 224, 193, 0.12); color: var(--deck-mint); }
.visual-issue__pill--amber { background: rgba(255, 200, 107, 0.13); color: var(--deck-amber); }
.visual-issue__branch { display: flex; align-items: center; gap: 10px; margin: 28px 0 0 92px; color: rgba(225, 235, 250, 0.5); font-size: 14px; }
.visual-issue__branch span { width: 24px; height: 1px; background: var(--deck-amber); }
.visual-issue__branch b { color: var(--deck-text); font-weight: 500; }

/* === VISUAL: SYSTEM TRACK === */
.visual-system { width: 820px; }
.visual-system .visual-window__bar { padding: 0 0 20px; }
.visual-system__track { display: flex; align-items: stretch; margin-top: 38px; }
.visual-system__stage { position: relative; flex: 1 1 0; min-height: 170px; padding: 22px 18px; border: 1px solid rgba(197, 217, 246, 0.16); border-radius: 12px; background: rgba(17, 39, 70, 0.62); }
.visual-system__stage--done { border-color: rgba(110, 224, 193, 0.32); }
.visual-system__stage--active { border-color: rgba(75, 124, 255, 0.7); background: rgba(30, 60, 107, 0.74); box-shadow: 0 0 0 8px rgba(75, 124, 255, 0.05); }
.visual-system__stage > span { display: block; color: var(--deck-blue); font-size: 14px; font-variant-numeric: tabular-nums; }
.visual-system__stage--done > span { color: var(--deck-mint); }
.visual-system__stage strong { display: block; margin-top: 36px; color: var(--deck-text); font-size: 20px; font-weight: 600; }
.visual-system__stage small { display: block; margin-top: 8px; color: var(--deck-muted); font-size: 14px; }
.visual-system__connector { flex: 0 0 38px; align-self: center; height: 1px; background: linear-gradient(90deg, var(--deck-blue), rgba(197, 217, 246, 0.22)); }
.visual-system__terminal { display: flex; align-items: center; gap: 12px; margin-top: 24px; padding: 15px 17px; border: 1px solid rgba(110, 224, 193, 0.16); border-radius: 8px; background: rgba(4, 14, 29, 0.78); color: rgba(225, 235, 250, 0.62); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.visual-system__terminal > span:first-child { color: var(--deck-mint); font-size: 20px; }
.visual-system__terminal b { margin-left: auto; color: var(--deck-mint); font-weight: 500; }

/* === VISUAL: REVIEW TIMELINE === */
.visual-review { width: 760px; }
.visual-review__summary { display: flex; align-items: center; gap: 16px; padding: 20px 22px; border: 1px solid rgba(110, 224, 193, 0.3); border-radius: 13px; background: rgba(16, 54, 61, 0.62); }
.visual-review__check { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 50%; background: var(--deck-mint); color: var(--deck-ink); font-size: 24px; font-weight: 800; }
.visual-review__summary strong { display: block; color: var(--deck-text); font-size: 22px; font-weight: 600; }
.visual-review__summary small { display: block; margin-top: 5px; color: var(--deck-muted); font-size: 14px; }
.visual-review__summary-value { margin-left: auto; color: var(--deck-mint); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 15px; }
.visual-review__timeline { display: grid; gap: 0; margin: 28px 0 0 20px; padding-left: 28px; border-left: 1px solid rgba(197, 217, 246, 0.22); }
.visual-review__event { position: relative; display: flex; align-items: center; gap: 14px; min-height: 86px; }
.visual-review__event-dot { position: absolute; left: -34px; width: 11px; height: 11px; border: 3px solid var(--deck-ink); border-radius: 50%; background: var(--deck-blue); box-shadow: 0 0 0 1px var(--deck-blue); }
.visual-review__event-dot--mint { background: var(--deck-mint); box-shadow: 0 0 0 1px var(--deck-mint); }
.visual-review__event-dot--amber { background: var(--deck-amber); box-shadow: 0 0 0 1px var(--deck-amber); }
.visual-review__event small { display: block; color: rgba(225, 235, 250, 0.44); font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; }
.visual-review__event strong { display: block; margin-top: 7px; color: var(--deck-text); font-size: 19px; font-weight: 500; }
.visual-review__event > b { margin-left: auto; color: var(--deck-mint); font-size: 16px; font-weight: 500; }
.visual-review__mr { display: flex; align-items: center; gap: 14px; margin-top: 24px; padding: 17px 20px; border: 1px solid rgba(255, 200, 107, 0.3); border-radius: 12px; background: rgba(58, 47, 30, 0.54); }
.visual-review__mr > span { display: grid; width: 38px; height: 38px; place-items: center; border: 1px solid var(--deck-amber); border-radius: 8px; color: var(--deck-amber); font-size: 12px; font-weight: 700; }
.visual-review__mr small { display: block; color: rgba(225, 235, 250, 0.46); font-size: 13px; }
.visual-review__mr strong { display: block; margin-top: 5px; color: var(--deck-text); font-size: 17px; font-weight: 500; }
.visual-review__mr b { margin-left: auto; color: var(--deck-amber); font-size: 13px; font-weight: 600; }

/* === VISUAL: START CARD === */
.visual-start { width: 720px; }
.visual-start__card { padding: 28px 30px; border-radius: 14px; }
.visual-start__card--prompt { position: relative; border: 1px solid rgba(75, 124, 255, 0.42); background: rgba(20, 48, 91, 0.72); box-shadow: 0 22px 58px rgba(0, 0, 0, 0.2); }
.visual-start__label { display: block; color: var(--deck-blue); font-size: 13px; font-weight: 700; letter-spacing: 0.13em; text-transform: uppercase; }
.visual-start__card strong { display: block; margin-top: 24px; color: var(--deck-text); font-size: 33px; font-weight: 600; }
.visual-start__card p { max-width: 520px; margin: 12px 0 0; color: var(--deck-muted); font-size: 20px; line-height: 1.45; }
.visual-start__cursor { width: 2px; height: 27px; margin-top: 24px; background: var(--deck-mint); animation: product-slides-cursor 1.2s steps(2, end) infinite; }
.visual-start__handoff { display: flex; align-items: center; gap: 14px; margin: 24px 0; color: rgba(225, 235, 250, 0.5); font-size: 15px; text-align: center; }
.visual-start__handoff span { flex: 1; height: 1px; background: var(--deck-line); }
.visual-start__returns { padding: 22px 26px; border: 1px solid rgba(110, 224, 193, 0.3); border-radius: 12px; background: rgba(15, 55, 59, 0.56); }
.visual-start__returns > span { color: var(--deck-mint); font-size: 14px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.visual-start__returns div { display: flex; gap: 10px; margin-top: 17px; }
.visual-start__returns b { padding: 9px 11px; border-radius: 7px; background: rgba(110, 224, 193, 0.11); color: var(--deck-text); font-size: 14px; font-weight: 500; }

/* === VISUAL: TASK PROMPT === */
.visual-prompt { width: 760px; }
.visual-prompt__row { display: grid; grid-template-columns: 42px 118px minmax(0, 1fr); align-items: center; gap: 14px; min-height: 88px; border-bottom: 1px solid rgba(197, 217, 246, 0.11); }
.visual-prompt__row > span { color: rgba(225, 235, 250, 0.35); font-size: 14px; font-variant-numeric: tabular-nums; }
.visual-prompt__row b { color: var(--deck-blue); font-size: 14px; letter-spacing: 0.1em; text-transform: uppercase; }
.visual-prompt__row strong { color: var(--deck-text); font-size: 17px; font-weight: 500; }
.visual-prompt__footer { display: flex; align-items: center; gap: 18px; margin-top: 23px; color: rgba(225, 235, 250, 0.45); font-size: 14px; }
.visual-prompt__footer b { color: var(--deck-mint); font-weight: 600; }
.visual-prompt__footer i { margin-left: auto; color: var(--deck-mint); font-size: 24px; font-style: normal; }

/* === VISUAL: TASK MODES === */
.visual-modes { width: 740px; }
.visual-modes__choice { display: flex; align-items: center; gap: 18px; min-height: 105px; margin-bottom: 12px; padding: 18px 22px; border: 1px solid rgba(197, 217, 246, 0.16); border-radius: 12px; background: rgba(17, 39, 70, 0.66); }
.visual-modes__choice--active { border-color: rgba(110, 224, 193, 0.65); background: rgba(17, 59, 62, 0.72); box-shadow: 0 0 0 8px rgba(110, 224, 193, 0.04); }
.visual-modes__choice > span { color: rgba(225, 235, 250, 0.4); font-size: 14px; }
.visual-modes__choice div { flex: 1; }
.visual-modes__choice strong { display: block; color: var(--deck-text); font-size: 21px; font-weight: 600; }
.visual-modes__choice small { display: block; margin-top: 6px; color: var(--deck-muted); font-size: 15px; }
.visual-modes__choice > b { color: var(--deck-mint); font-size: 22px; font-weight: 500; }
.visual-modes__tip { display: flex; gap: 10px; margin-top: 26px; color: rgba(225, 235, 250, 0.5); font-size: 15px; }
.visual-modes__tip span { color: var(--deck-mint); font-size: 22px; line-height: 0.8; }

/* === VISUAL: FOLLOW-UP LOOP === */
.visual-followup { width: 760px; }
.visual-followup__branch { display: flex; align-items: center; gap: 14px; color: var(--deck-blue); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 17px; }
.visual-followup__branch span { width: 56px; height: 1px; background: var(--deck-blue); }
.visual-followup__branch span:last-child { flex: 1; background: linear-gradient(90deg, var(--deck-blue), transparent); }
.visual-followup__branch b { font-weight: 500; }
.visual-followup__tasks { display: flex; align-items: center; gap: 18px; margin-top: 30px; }
.visual-followup__task { flex: 1; min-height: 180px; padding: 24px; border: 1px solid rgba(197, 217, 246, 0.17); border-radius: 13px; background: rgba(17, 39, 70, 0.67); }
.visual-followup__task--active { border-color: rgba(255, 200, 107, 0.58); background: rgba(64, 51, 29, 0.55); }
.visual-followup__task small { display: block; color: rgba(225, 235, 250, 0.45); font-size: 14px; }
.visual-followup__task strong { display: block; margin-top: 46px; color: var(--deck-text); font-size: 22px; font-weight: 600; }
.visual-followup__task span { display: block; margin-top: 17px; color: var(--deck-mint); font-size: 20px; }
.visual-followup__task--active span { color: var(--deck-amber); }
.visual-followup__arrow { color: var(--deck-amber); font-size: 32px; }
.visual-followup__shared { display: flex; gap: 10px; margin-top: 26px; }
.visual-followup__shared b { flex: 1; padding: 11px 9px; border: 1px solid rgba(197, 217, 246, 0.14); border-radius: 8px; color: rgba(225, 235, 250, 0.68); font-size: 13px; font-weight: 500; text-align: center; }

/* === VISUAL: DELIVERY PATH === */
.visual-delivery { position: relative; width: 720px; padding: 20px 0 20px 34px; }
.visual-delivery::before { position: absolute; top: 42px; bottom: 42px; left: 57px; width: 1px; background: linear-gradient(var(--deck-mint), var(--deck-amber), transparent); content: ''; }
.visual-delivery__line { position: relative; display: flex; align-items: center; gap: 20px; min-height: 118px; }
.visual-delivery__node { position: relative; z-index: 1; display: grid; width: 48px; height: 48px; place-items: center; border: 1px solid rgba(197, 217, 246, 0.3); border-radius: 12px; background: var(--deck-ink-soft); color: rgba(225, 235, 250, 0.55); font-size: 13px; font-weight: 700; }
.visual-delivery__node--done { border-color: var(--deck-mint); color: var(--deck-mint); }
.visual-delivery__node--active { width: 58px; height: 58px; margin-left: -5px; border-color: var(--deck-amber); color: var(--deck-amber); box-shadow: 0 0 0 8px rgba(255, 200, 107, 0.05); }
.visual-delivery__line small { display: block; color: rgba(225, 235, 250, 0.45); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; }
.visual-delivery__line strong { display: block; margin-top: 7px; color: var(--deck-text); font-size: 21px; font-weight: 500; }
.visual-delivery__line > b { margin-left: auto; color: var(--deck-amber); font-size: 22px; font-weight: 400; }
.visual-delivery__stamp { position: absolute; right: 10px; bottom: 4px; padding: 12px 16px; border: 1px solid rgba(110, 224, 193, 0.28); border-radius: 8px; color: var(--deck-mint); font-size: 15px; font-weight: 700; letter-spacing: 0.13em; text-transform: uppercase; transform: rotate(-5deg); }

/* === NAVIGATION CONTROLS === */
.product-slides__controls { position: absolute; right: 22px; bottom: 18px; z-index: 10; display: flex; gap: 5px; padding: 5px; border: 1px solid rgba(197, 217, 246, 0.18); border-radius: 11px; background: rgba(6, 20, 40, 0.8); backdrop-filter: blur(12px); }
.product-slides__control { display: grid; width: 38px; height: 28px; place-items: center; border: 0; border-radius: 6px; background: transparent; color: rgba(225, 235, 250, 0.42); cursor: pointer; font-family: inherit; font-size: 11px; font-variant-numeric: tabular-nums; transition: background 180ms ease, color 180ms ease, transform 180ms ease; }
.product-slides__control:hover { color: var(--deck-text); background: rgba(75, 124, 255, 0.18); transform: translateY(-1px); }
.product-slides__control--active { color: var(--deck-ink); background: var(--deck-mint); font-weight: 700; }
.product-slides__control:focus-visible { outline: 2px solid var(--deck-amber); outline-offset: 2px; }
.product-slides__keyboard-hint { position: absolute; bottom: 23px; left: 22px; z-index: 10; margin: 0; color: rgba(225, 235, 250, 0.35); font-size: 11px; letter-spacing: 0.04em; pointer-events: none; }

/* === MOTION === */
.product-slide.active .product-slide__overline,
.product-slide.active .product-slide__title,
.product-slide.active .product-slide__body-copy,
.product-slide.active .product-slide__note,
.product-slide.active .product-slide__visual {
  animation: product-slides-reveal 620ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.product-slide.active .product-slide__title { animation-delay: 80ms; }
.product-slide.active .product-slide__body-copy { animation-delay: 150ms; }
.product-slide.active .product-slide__note { animation-delay: 210ms; }
.product-slide.active .product-slide__visual { animation-delay: 130ms; }

@keyframes product-slides-reveal {
  from { opacity: 0; transform: translateY(22px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes product-slides-cursor {
  0%, 45% { opacity: 1; }
  46%, 100% { opacity: 0; }
}

@media (max-width: 720px) {
  .product-slides__keyboard-hint { display: none; }
  .product-slides__controls { right: 9px; bottom: 9px; }
  .product-slides__control { width: 26px; height: 22px; font-size: 9px; }
}

@media (prefers-reduced-motion: reduce) {
  .product-slide,
  .product-slides__control,
  .product-slide.active .product-slide__overline,
  .product-slide.active .product-slide__title,
  .product-slide.active .product-slide__body-copy,
  .product-slide.active .product-slide__note,
  .product-slide.active .product-slide__visual,
  .visual-start__cursor {
    animation: none !important;
    transition: none !important;
  }
}
</style>
