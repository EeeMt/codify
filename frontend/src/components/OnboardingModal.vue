<template>
  <n-modal :show="show" :mask-closable="false" :close-on-esc="true" @close="emit('close')">
    <div class="onboarding-modal-shell">
      <div class="onboarding-modal">
        <div class="onboarding-modal__header">
          <div>
            <span class="onboarding-modal__eyebrow">{{ t('onboarding.modalTitle') }}</span>
            <p class="onboarding-modal__description">{{ t('onboarding.modalDescription') }}</p>
          </div>
          <n-button
            quaternary
            circle
            class="onboarding-modal__close"
            :aria-label="t('onboarding.actions.closeOnboarding')"
            @click="emit('close')"
          >
            <span aria-hidden="true">×</span>
          </n-button>
        </div>

        <ProductSlides v-model:current="currentStep" variant="onboarding" />

        <footer class="onboarding-modal__footer">
          <div class="onboarding-modal__footer-start">
            <span class="onboarding-modal__progress" aria-live="polite">
              {{ t('onboarding.progressLabel', { current: currentStep + 1, total: totalSteps }) }}
            </span>
            <n-button text data-testid="onboarding-view-guide" @click="emit('open-guide')">
              {{ t('onboarding.actions.viewGuide') }}
            </n-button>
            <n-button text data-testid="onboarding-skip" @click="emit('close')">
              {{ isLastStep ? t('onboarding.actions.close') : t('onboarding.actions.skip') }}
            </n-button>
          </div>

          <div class="onboarding-modal__footer-end">
            <n-button
              v-if="currentStep > 0"
              data-testid="onboarding-previous"
              @click="goToPrevious"
            >
              {{ t('onboarding.actions.previous') }}
            </n-button>
            <n-button
              v-if="!isLastStep"
              type="primary"
              data-testid="onboarding-next"
              @click="goToNext"
            >
              {{ t('onboarding.actions.next') }}
            </n-button>
            <template v-else>
              <n-button data-testid="onboarding-create-issue" @click="handleCreateIssue">
                {{ t('onboarding.actions.createIssue') }}
              </n-button>
              <n-button type="primary" data-testid="onboarding-view-dashboard" @click="handleViewDashboard">
                {{ t('onboarding.actions.viewDashboard') }}
              </n-button>
            </template>
          </div>
        </footer>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton, NModal } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import ProductSlides from './ProductSlides.vue'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'complete'): void
  (event: 'open-guide'): void
  (event: 'view-dashboard'): void
  (event: 'create-issue'): void
}>()

const { t } = useI18n()
const totalSteps = 4
const currentStep = ref(0)
const isLastStep = computed(() => currentStep.value === totalSteps - 1)

watch(() => props.show, (isVisible, wasVisible) => {
  if (isVisible && !wasVisible) currentStep.value = 0
})

function goToNext(): void {
  if (!isLastStep.value) currentStep.value += 1
}

function goToPrevious(): void {
  if (currentStep.value > 0) currentStep.value -= 1
}

function handleViewDashboard(): void {
  emit('complete')
  emit('view-dashboard')
}

function handleCreateIssue(): void {
  emit('complete')
  emit('create-issue')
}
</script>

<style scoped>
/* === MODAL FRAME === */
.onboarding-modal-shell {
  width: min(1120px, calc(100vw - 28px), calc((100vh - 174px) * 16 / 9));
  max-height: calc(100vh - 20px);
  overflow: hidden;
  border-radius: 28px;
}

.onboarding-modal {
  position: relative;
  padding: 14px;
  border: 1px solid rgba(157, 179, 215, 0.24);
  border-radius: 28px;
  background: #07152a;
  box-shadow: 0 32px 90px rgba(4, 14, 29, 0.35);
}

/* === MODAL HEADER === */
.onboarding-modal__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 8px 10px 12px 14px;
  color: #f5f8ff;
}

.onboarding-modal__eyebrow {
  display: block;
  color: #6ee0c1;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.onboarding-modal__description {
  margin: 6px 0 0;
  color: rgba(225, 235, 250, 0.58);
  font-size: 13px;
  line-height: 1.45;
}

.onboarding-modal__close {
  flex: 0 0 auto;
  color: rgba(245, 248, 255, 0.7);
}

/* === MODAL FOOTER === */
.onboarding-modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 12px 2px 14px;
}

.onboarding-modal__footer-start,
.onboarding-modal__footer-end {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.onboarding-modal__progress {
  margin-right: 7px;
  color: rgba(225, 235, 250, 0.44);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.onboarding-modal__footer :deep(.n-button) {
  color: rgba(245, 248, 255, 0.72);
}

.onboarding-modal__footer :deep(.n-button--primary-type) {
  color: #07152a;
  background: #6ee0c1;
}

.onboarding-modal__footer :deep(.n-button--primary-type:hover) {
  background: #8ae8d0;
}

@media (max-width: 640px) {
  .onboarding-modal-shell {
    width: calc(100vw - 14px);
  }

  .onboarding-modal {
    padding: 8px;
    border-radius: 20px;
  }

  .onboarding-modal__header {
    padding: 6px 6px 8px 8px;
  }

  .onboarding-modal__footer {
    align-items: flex-start;
    flex-direction: column;
    padding: 9px 6px 0;
  }

  .onboarding-modal__footer-end {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
