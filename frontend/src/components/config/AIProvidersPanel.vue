<template>
  <div class="config-layout__main">
    <n-card class="config-form-card" :bordered="false">
      <template #header>
        <div class="config-card-header">
          <div>
            <div class="config-card-header__title">{{ t('config.providers.title') }}</div>
            <div class="config-card-header__subtitle">{{ t('config.providers.subtitle') }}</div>
          </div>
        </div>
      </template>
      <template #header-extra>
        <n-button type="primary" size="small" @click="openCreate">
          {{ t('config.providers.create') }}
        </n-button>
      </template>

      <div
        v-if="!isMobile"
        class="config-table-wrapper ai-providers-table-wrapper"
        data-testid="ai-provider-table"
      >
        <n-data-table
          :columns="columns"
          :data="providers"
          :loading="loading"
          :bordered="false"
          size="small"
          :row-key="(row: AIProvider) => row.id"
        />
      </div>

      <div
        v-else
        class="ai-providers-mobile-list"
        data-testid="ai-provider-mobile-list"
        :aria-busy="loading"
      >
        <div v-if="!loading && providers.length === 0" class="config-empty">
          —
        </div>
        <article
          v-for="provider in providers"
          :key="provider.id"
          class="ai-provider-mobile-card"
          :data-testid="`ai-provider-card-${provider.id}`"
        >
          <div class="ai-provider-mobile-card__top">
            <div class="ai-provider-mobile-card__identity">
              <div class="ai-provider-mobile-card__name">{{ provider.name }}</div>
              <div class="ai-provider-mobile-card__tags">
                <n-tag
                  :type="provider.is_disabled ? 'warning' : 'success'"
                  size="small"
                  round
                >
                  {{ provider.is_disabled ? t('config.providers.disabled') : t('config.providers.enabled') }}
                </n-tag>
                <n-tag v-if="provider.is_default" type="info" size="small" round>
                  {{ t('config.providers.isDefault') }}
                </n-tag>
              </div>
            </div>
            <div class="ai-provider-mobile-card__model" :title="provider.model">
              {{ provider.model }}
            </div>
          </div>

          <div class="ai-provider-mobile-card__details">
            <div class="ai-provider-mobile-card__detail ai-provider-mobile-card__detail--wide">
              <span class="ai-provider-mobile-card__label">{{ t('config.providers.baseUrl') }}</span>
              <span class="ai-provider-mobile-card__value" :title="provider.base_url">
                {{ provider.base_url }}
              </span>
            </div>
            <div class="ai-provider-mobile-card__detail">
              <span class="ai-provider-mobile-card__label">{{ t('config.providers.wireProtocol') }}</span>
              <span class="ai-provider-mobile-card__value">{{ getProtocolLabel(provider.model_protocol) }}</span>
            </div>
            <div class="ai-provider-mobile-card__detail">
              <span class="ai-provider-mobile-card__label">{{ t('config.providers.maxTurns') }}</span>
              <span class="ai-provider-mobile-card__value">{{ provider.max_turns }}</span>
            </div>
            <div class="ai-provider-mobile-card__detail">
              <span class="ai-provider-mobile-card__label">{{ t('config.providers.apiKey') }}</span>
              <n-tag
                :type="provider.api_key_configured ? 'success' : 'warning'"
                size="small"
                round
              >
                {{ provider.api_key_configured
                  ? t('config.providers.apiKeyConfigured')
                  : t('config.providers.apiKeyNotConfigured') }}
              </n-tag>
            </div>
          </div>

          <div v-if="provider.system_prompt" class="ai-provider-mobile-card__prompt">
            <span class="ai-provider-mobile-card__label">{{ t('config.providers.systemPrompt') }}</span>
            <span class="ai-provider-mobile-card__prompt-value">{{ provider.system_prompt }}</span>
          </div>

          <div class="ai-provider-mobile-card__actions">
            <n-button size="small" @click="openEdit(provider)">
              {{ t('common.edit') }}
            </n-button>
            <n-button
              size="small"
              :disabled="provider.is_default"
              @click="handleToggleDisabled(provider)"
            >
              {{ provider.is_disabled ? t('config.providers.enable') : t('config.providers.disable') }}
            </n-button>
            <n-button
              size="small"
              :disabled="provider.is_default || provider.is_disabled"
              @click="handleSetDefault(provider)"
            >
              {{ t('config.providers.setDefault') }}
            </n-button>
            <n-button
              size="small"
              :loading="testingProviderId === provider.id"
              :disabled="testingProviderId !== null && testingProviderId !== provider.id"
              @click="handleTestConnection(provider)"
            >
              {{ t('config.providers.testConnection') }}
            </n-button>
            <n-popconfirm
              :positive-text="t('common.delete')"
              :negative-text="t('common.cancel')"
              @positive-click="handleDelete(provider)"
            >
              <template #trigger>
                <n-button
                  size="small"
                  type="error"
                  :disabled="provider.is_default && providers.length === 1"
                >
                  {{ t('common.delete') }}
                </n-button>
              </template>
              {{ provider.is_default && providers.length === 1
                ? t('config.providers.deleteLast')
                : t('config.providers.deleteConfirm') }}
            </n-popconfirm>
          </div>
        </article>
      </div>
    </n-card>

    <n-modal
      class="config-editor-modal"
      :show="modalVisible"
      preset="card"
      :style="{ width: isMobile ? '96vw' : 'min(880px, calc(100vw - 32px))' }"
      @update:show="handleModalVisibilityChange"
    >
      <template #header>
        <div class="ai-provider-modal__header">
          <div class="ai-provider-modal__title">
            {{ editingProvider ? t('config.providers.edit') : t('config.providers.create') }}
          </div>
          <div v-if="editingProvider" class="ai-provider-modal__subtitle">
            {{ editingProvider.name }} / {{ editingProvider.model }}
          </div>
        </div>
      </template>

      <div class="config-editor-modal__scroll ai-provider-modal__scroll">
        <n-form
          ref="formRef"
          :model="formValue"
          :rules="rules"
          label-placement="top"
          class="config-section-form ai-provider-modal__form"
        >
          <div class="ai-provider-modal__grid">
            <n-form-item :label="t('config.providers.name')" path="name">
              <n-input
                v-model:value="formValue.name"
                placeholder="my-provider"
                class="config-form__input"
              />
              <template #feedback>
                {{ t('config.providers.nameHint') }}
              </template>
            </n-form-item>

            <n-form-item :label="t('config.providers.maxTurns')" path="max_turns">
              <n-input-number
                v-model:value="formValue.max_turns"
                :min="1"
                :max="1000"
                class="config-form__input"
              />
              <template #feedback>
                {{ t('config.providers.maxTurnsHint') }}
              </template>
            </n-form-item>

            <n-form-item :label="t('config.providers.baseUrl')" path="base_url">
              <n-input
                v-model:value="formValue.base_url"
                placeholder="http://host.docker.internal:11434/v1"
                class="config-form__input"
              />
              <template #feedback>
                {{ t('config.providers.baseUrlHint') }}
              </template>
            </n-form-item>

            <n-form-item :label="t('config.providers.model')" path="model">
              <n-input
                v-model:value="formValue.model"
                placeholder="my-model"
                class="config-form__input"
              />
              <template #feedback>
                {{ t('config.providers.modelHint') }}
              </template>
            </n-form-item>

            <n-form-item :label="t('config.providers.providerKind')" path="provider_kind">
              <n-select
                v-model:value="formValue.provider_kind"
                :options="providerKindOptions"
                class="config-form__input"
                @update:value="handleProviderKindChange"
              />
              <template #feedback>
                {{ t('config.providers.providerKindHint') }}
              </template>
            </n-form-item>

            <n-form-item :label="t('config.providers.wireProtocol')" path="model_protocol">
              <n-select
                v-model:value="formValue.model_protocol"
                :options="wireProtocolOptions"
                class="config-form__input"
                @update:value="handleModelProtocolChange"
              />
              <template #feedback>
                {{ t('config.providers.wireProtocolHint') }}
              </template>
            </n-form-item>
          </div>

          <div class="ai-provider-modal__section">
            <n-form-item :label="t('config.providers.apiKey')" path="api_key">
              <n-input
                v-model:value="formValue.api_key"
                type="password"
                show-password-on="click"
                :placeholder="editingProvider ? t('config.providers.apiKeyHint') : ''"
                class="config-form__input"
              />
              <template #feedback>
                <span v-if="editingProvider && editingProvider.api_key_configured">
                  <n-tag size="tiny" type="success" round>{{ t('config.providers.apiKeyConfigured') }}</n-tag>
                </span>
                <span v-else-if="editingProvider">
                  <n-tag size="tiny" type="warning" round>{{ t('config.providers.apiKeyNotConfigured') }}</n-tag>
                </span>
              </template>
            </n-form-item>

            <n-form-item :label="t('config.providers.systemPrompt')" path="system_prompt">
              <n-input
                v-model:value="formValue.system_prompt"
                type="textarea"
                :rows="5"
                :placeholder="t('config.providers.systemPromptHint')"
                class="config-form__input ai-provider-modal__textarea"
              />
            </n-form-item>
          </div>

          <n-collapse
            class="ai-provider-modal__advanced"
            :default-expanded-names="[]"
          >
            <n-collapse-item
              name="provider-options"
              :title="t('config.providers.advancedRequestParams')"
            >
              <n-form-item
                path="provider_options_json"
                :show-label="false"
                :show-feedback="true"
              >
                <n-input
                  v-model:value="formValue.provider_options_json"
                  type="textarea"
                  :rows="8"
                  spellcheck="false"
                  class="config-form__input ai-provider-modal__json"
                  :placeholder="advancedRequestParamsPlaceholder"
                />
                <template #feedback>
                  {{ t('config.providers.advancedRequestParamsHint') }}
                </template>
              </n-form-item>
            </n-collapse-item>
          </n-collapse>

        </n-form>
      </div>

      <template #footer>
        <n-space justify="end">
          <n-button @click="closeModal">{{ t('common.cancel') }}</n-button>
          <n-button type="primary" :loading="saving" @click="handleSave">
            {{ t('common.save') }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NModal,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NSpace,
  NTag,
  useMessage,
  type DataTableColumns,
  type FormInst,
  type FormRules
} from 'naive-ui'
import { useI18n } from 'vue-i18n'
import {
  getProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  setDefaultProvider,
  testProviderConnection,
  type AIProvider,
  type CreateProviderRequest,
  type UpdateProviderRequest
} from '../../api'

const PROVIDER_KIND_PROTOCOLS: Record<string, string[]> = {
  anthropic_compatible: ['anthropic_messages'],
  openai_compatible: ['openai_responses', 'openai_chat_completions'],
}

const PROVIDER_KIND_DEFAULT_PROTOCOL: Record<string, string> = {
  anthropic_compatible: 'anthropic_messages',
  openai_compatible: 'openai_responses',
}

const MODEL_PROTOCOL_PROVIDER_KIND: Record<string, string> = {
  anthropic_messages: 'anthropic_compatible',
  openai_responses: 'openai_compatible',
  openai_chat_completions: 'openai_compatible',
}

// Harness/Model-Endpoint owned request fields. The API rejects them with a
// 422; surfacing the same field names here keeps the modal self-explanatory.
const RESERVED_PROVIDER_OPTION_FIELDS = [
  'model',
  'messages',
  'input',
  'instructions',
  'tools',
  'tool_choice',
  'stream',
  'stream_options'
]

type ProviderOptionsParseResult =
  | { ok: true; value: Record<string, unknown> }
  | { ok: false; message: string }

defineProps<{
  isMobile: boolean
}>()

const { t } = useI18n()
const message = useMessage()

// State
const providers = ref<AIProvider[]>([])
const loading = ref(false)
const testingProviderId = ref<number | null>(null)
const saving = ref(false)
const modalVisible = ref(false)
const editingProvider = ref<AIProvider | null>(null)
const formRef = ref<FormInst | null>(null)

const formValue = ref({
  name: '',
  base_url: '',
  model: '',
  max_turns: 20,
  api_key: '',
  system_prompt: '',
  provider_kind: 'anthropic_compatible',
  model_protocol: 'anthropic_messages',
  provider_options_json: '{}'
})

const providerKindOptions = computed(() => [
  { label: t('config.providers.providerKindAnthropic'), value: 'anthropic_compatible' },
  { label: t('config.providers.providerKindOpenai'), value: 'openai_compatible' },
])

const wireProtocolOptions = computed(() => {
  const protocols = PROVIDER_KIND_PROTOCOLS[formValue.value.provider_kind] ?? []

  return protocols.map(protocol => ({
    label: protocol === 'anthropic_messages'
      ? t('config.providers.wireProtocolAnthropicMessages')
      : protocol === 'openai_responses'
        ? t('config.providers.wireProtocolOpenaiResponses')
        : t('config.providers.wireProtocolOpenaiChatCompletions'),
    value: protocol,
  }))
})

const advancedRequestParamsPlaceholder = computed(() => JSON.stringify({
  chat_template_kwargs: {
    thinking: true,
    reasoning_effort: 'high'
  }
}, null, 2))

function getProtocolLabel(protocol?: string): string {
  if (protocol === 'anthropic_messages') {
    return t('config.providers.wireProtocolAnthropicMessages')
  }
  if (protocol === 'openai_responses') {
    return t('config.providers.wireProtocolOpenaiResponses')
  }
  if (protocol === 'openai_chat_completions') {
    return t('config.providers.wireProtocolOpenaiChatCompletions')
  }
  return protocol || '—'
}

function parseProviderOptionsJson(raw: string): ProviderOptionsParseResult {
  const text = (raw ?? '').trim()
  if (!text) {
    return { ok: true, value: {} }
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return { ok: false, message: t('config.providers.advancedRequestParamsInvalidJson') }
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, message: t('config.providers.advancedRequestParamsNotObject') }
  }
  const reserved = RESERVED_PROVIDER_OPTION_FIELDS.filter(field =>
    Object.prototype.hasOwnProperty.call(parsed, field)
  )
  if (reserved.length > 0) {
    return {
      ok: false,
      message: t('config.providers.advancedRequestParamsReserved', { fields: reserved.join(', ') })
    }
  }
  return { ok: true, value: parsed as Record<string, unknown> }
}

const rules: FormRules = {
  name: [
    {
      required: true,
      message: () => t('config.providers.nameHint'),
      trigger: 'blur'
    },
    {
      pattern: /^[a-zA-Z0-9_-]+$/,
      message: () => t('config.providers.nameHint'),
      trigger: 'blur'
    }
  ],
  base_url: [
    {
      required: true,
      message: () => t('config.providers.baseUrlHint'),
      trigger: 'blur'
    },
    {
      pattern: /^https?:\/\//,
      message: () => t('config.providers.baseUrlHint'),
      trigger: 'blur'
    }
  ],
  model: {
    required: true,
    message: () => t('config.providers.modelHint'),
    trigger: 'blur'
  },
  max_turns: {
    required: true,
    type: 'number',
    min: 1,
    max: 1000,
    message: () => t('config.providers.maxTurnsHint'),
    trigger: 'blur'
  },
  provider_options_json: {
    trigger: ['input', 'blur'],
    validator: (_rule: unknown, value: string) => {
      const result = parseProviderOptionsJson(value)
      return result.ok ? true : new Error(result.message)
    }
  }
}

// Columns
const columns = computed<DataTableColumns<AIProvider>>(() => [
  {
    title: t('config.providers.name'),
    key: 'provider',
    minWidth: 220,
    render: (row: AIProvider) =>
      h('div', { class: 'ai-provider-service-cell' }, [
        h('div', { class: 'ai-provider-service-cell__name' }, row.name),
        h('div', { class: 'ai-provider-service-cell__model', title: row.model }, row.model),
        h('div', { class: 'ai-provider-service-cell__tags' }, [
          h(NTag, {
            type: row.is_disabled ? 'warning' : 'success',
            size: 'small',
            round: true
          }, {
            default: () => row.is_disabled ? t('config.providers.disabled') : t('config.providers.enabled')
          }),
          row.is_default
            ? h(NTag, { type: 'info', size: 'small', round: true }, { default: () => t('config.providers.isDefault') })
            : null
        ])
      ])
  },
  {
    title: t('config.providers.baseUrl'),
    key: 'endpoint',
    minWidth: 240,
    render: (row: AIProvider) =>
      h('div', { class: 'ai-provider-endpoint-cell' }, [
        h('div', { class: 'ai-provider-endpoint-cell__url', title: row.base_url }, row.base_url),
        h('div', { class: 'ai-provider-endpoint-cell__protocol' }, getProtocolLabel(row.model_protocol))
      ])
  },
  {
    title: t('config.providers.configuration'),
    key: 'configuration',
    width: 180,
    render: (row: AIProvider) =>
      h('div', { class: 'ai-provider-configuration-cell' }, [
        h('div', { class: 'ai-provider-configuration-cell__turns' }, [
          h('span', { class: 'ai-provider-cell__label' }, `${t('config.providers.maxTurns')}:`),
          h('strong', String(row.max_turns))
        ]),
        h(NTag, {
          type: row.api_key_configured ? 'success' : 'warning',
          size: 'small',
          round: true
        }, {
          default: () =>
            row.api_key_configured
              ? t('config.providers.apiKeyConfigured')
              : t('config.providers.apiKeyNotConfigured')
        })
      ])
  },
  {
    title: t('config.providers.systemPrompt'),
    key: 'system_prompt',
    minWidth: 180,
    ellipsis: {
      tooltip: {
        style: { maxWidth: '420px', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } as any
    },
    render: (row: AIProvider) =>
      row.system_prompt
        ? h('span', { class: 'ai-providers-system-prompt-preview' }, row.system_prompt)
        : h('span', { style: 'color: rgba(15,23,42,0.38)' }, '—')
  },
  {
    title: t('config.actions'),
    key: 'actions',
    width: 280,
    render: (row: AIProvider) =>
      h(NSpace, { class: 'ai-providers-actions', size: 'small', wrap: true }, {
        default: () => [
          h(NButton, {
            size: 'small',
            onClick: () => openEdit(row)
          }, { default: () => t('common.edit') }),
          h(NButton, {
            size: 'small',
            disabled: row.is_default,
            onClick: () => handleToggleDisabled(row)
          }, { default: () => row.is_disabled ? t('config.providers.enable') : t('config.providers.disable') }),
          h(NButton, {
            size: 'small',
            disabled: row.is_default || row.is_disabled,
            onClick: () => handleSetDefault(row)
          }, { default: () => t('config.providers.setDefault') }),
          h(NButton, {
            size: 'small',
            loading: testingProviderId.value === row.id,
            disabled: testingProviderId.value !== null && testingProviderId.value !== row.id,
            onClick: () => handleTestConnection(row)
          }, { default: () => t('config.providers.testConnection') }),
          h(NPopconfirm, {
            positiveText: t('common.delete'),
            negativeText: t('common.cancel'),
            onPositiveClick: () => handleDelete(row)
          }, {
            trigger: () =>
              h(NButton, {
                size: 'small',
                type: 'error',
                disabled: row.is_default && providers.value.length === 1
              }, { default: () => t('common.delete') }),
            default: () => row.is_default && providers.value.length === 1
              ? t('config.providers.deleteLast')
              : t('config.providers.deleteConfirm')
          })
        ]
      })
  }
])

// Fetch
async function fetchProviders() {
  loading.value = true
  try {
    providers.value = await getProviders()
  } catch (error: any) {
    message.error(error?.response?.data?.detail || 'Failed to load providers')
  } finally {
    loading.value = false
  }
}

// Create / Edit drawer
function resetForm() {
  formValue.value = {
    name: '',
    base_url: '',
    model: '',
    max_turns: 20,
    api_key: '',
    system_prompt: '',
    provider_kind: 'anthropic_compatible',
    model_protocol: 'anthropic_messages',
    provider_options_json: '{}'
  }
}

function clearFormValidation() {
  formRef.value?.restoreValidation?.()
}

function closeModal() {
  modalVisible.value = false
  editingProvider.value = null
  resetForm()
  clearFormValidation()
}

function handleModalVisibilityChange(show: boolean) {
  if (show) {
    modalVisible.value = true
    return
  }
  closeModal()
}

function openCreate() {
  modalVisible.value = true
  editingProvider.value = null
  resetForm()
  clearFormValidation()
}

function openEdit(provider: AIProvider) {
  editingProvider.value = provider
  formValue.value = {
    name: provider.name,
    base_url: provider.base_url,
    model: provider.model,
    max_turns: provider.max_turns,
    api_key: '',
    system_prompt: provider.system_prompt || '',
    provider_kind: provider.provider_kind || 'anthropic_compatible',
    model_protocol: provider.model_protocol || 'anthropic_messages',
    provider_options_json: JSON.stringify(provider.provider_options ?? {}, null, 2)
  }
  modalVisible.value = true
  clearFormValidation()
}

function handleProviderKindChange(kind: string) {
  formValue.value.provider_kind = kind
  const protocols = PROVIDER_KIND_PROTOCOLS[kind] ?? []
  if (!protocols.includes(formValue.value.model_protocol)) {
    formValue.value.model_protocol =
      PROVIDER_KIND_DEFAULT_PROTOCOL[kind] ?? protocols[0] ?? 'anthropic_messages'
  }
}

function handleModelProtocolChange(protocol: string) {
  formValue.value.model_protocol = protocol
  const providerKind = MODEL_PROTOCOL_PROVIDER_KIND[protocol]
  if (providerKind && formValue.value.provider_kind !== providerKind) {
    formValue.value.provider_kind = providerKind
  }
}

async function handleSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const parsedOptions = parseProviderOptionsJson(formValue.value.provider_options_json)
    if (!parsedOptions.ok) {
      message.error(parsedOptions.message)
      return
    }
    if (editingProvider.value) {
      // Update existing
      const req: UpdateProviderRequest = {
        name: formValue.value.name.trim(),
        base_url: formValue.value.base_url.trim(),
        model: formValue.value.model.trim(),
        max_turns: formValue.value.max_turns,
        provider_kind: formValue.value.provider_kind,
        model_protocol: formValue.value.model_protocol,
        provider_options: parsedOptions.value
      }
      if (formValue.value.api_key.trim()) {
        req.api_key = formValue.value.api_key.trim()
      }
      if (formValue.value.system_prompt.trim()) {
        req.system_prompt = formValue.value.system_prompt.trim()
      } else {
        req.clear_system_prompt = true
      }
      await updateProvider(editingProvider.value.id, req)
      message.success(t('config.providers.updated'))
    } else {
      // Create new
      const req: CreateProviderRequest = {
        name: formValue.value.name.trim(),
        base_url: formValue.value.base_url.trim(),
        model: formValue.value.model.trim(),
        max_turns: formValue.value.max_turns,
        provider_kind: formValue.value.provider_kind,
        model_protocol: formValue.value.model_protocol,
        provider_options: parsedOptions.value
      }
      if (formValue.value.api_key.trim()) {
        req.api_key = formValue.value.api_key.trim()
      }
      if (formValue.value.system_prompt.trim()) {
        req.system_prompt = formValue.value.system_prompt.trim()
      }
      await createProvider(req)
      message.success(t('config.providers.created'))
    }

    closeModal()
    await fetchProviders()
  } catch (error: any) {
    message.error(error?.response?.data?.detail || t('config.saveError'))
  } finally {
    saving.value = false
  }
}

async function handleToggleDisabled(provider: AIProvider) {
  if (provider.is_default) return
  try {
    await updateProvider(provider.id, { is_disabled: !provider.is_disabled })
    message.success(t('config.providers.updated'))
    await fetchProviders()
  } catch (error: any) {
    message.error(error?.response?.data?.detail || t('config.saveError'))
  }
}

async function handleDelete(provider: AIProvider) {
  try {
    await deleteProvider(provider.id)
    message.success(t('config.providers.deleted'))
    await fetchProviders()
  } catch (error: any) {
    message.error(error?.response?.data?.detail || t('config.providers.deleteBlocked'))
  }
}

async function handleSetDefault(provider: AIProvider) {
  try {
    await setDefaultProvider(provider.id)
    message.success(t('config.providers.defaultSet'))
    await fetchProviders()
  } catch (error: any) {
    message.error(error?.response?.data?.detail || 'Failed to set default provider')
  }
}

async function handleTestConnection(provider: AIProvider) {
  if (testingProviderId.value !== null) return
  testingProviderId.value = provider.id
  try {
    const result = await testProviderConnection(provider.id)
    message.success(t('config.providers.connectionTestSucceeded', { latency: result.latency_ms }))
  } catch (error: any) {
    message.error(error?.response?.data?.detail || t('config.providers.connectionTestFailed'))
  } finally {
    testingProviderId.value = null
  }
}

onMounted(() => {
  fetchProviders()
})
</script>

<style scoped>
:deep(.ai-providers-system-prompt-preview) {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.ai-providers-table-wrapper :deep(.n-data-table-td) {
  white-space: normal;
  vertical-align: middle;
}

.ai-providers-table-wrapper :deep(.n-data-table-th) {
  white-space: nowrap;
}

:deep(.ai-provider-service-cell),
:deep(.ai-provider-endpoint-cell),
:deep(.ai-provider-configuration-cell) {
  display: grid;
  min-width: 0;
  gap: 6px;
}

:deep(.ai-provider-service-cell__name) {
  overflow-wrap: anywhere;
  font-weight: 600;
}

:deep(.ai-provider-service-cell__model),
:deep(.ai-provider-endpoint-cell__url) {
  overflow: hidden;
  color: rgba(15, 23, 42, 0.66);
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.ai-provider-service-cell__tags) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.ai-provider-endpoint-cell__protocol) {
  overflow: hidden;
  color: rgba(15, 23, 42, 0.52);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.ai-provider-configuration-cell__turns) {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

:deep(.ai-provider-cell__label) {
  color: rgba(15, 23, 42, 0.52);
  font-size: 12px;
}

:deep(.ai-providers-actions) {
  width: 100%;
  max-width: 100%;
}

.ai-providers-mobile-list {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}

.ai-provider-mobile-card {
  display: grid;
  min-width: 0;
  gap: 14px;
  padding: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.8);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55);
}

.ai-provider-mobile-card__top {
  display: grid;
  min-width: 0;
  gap: 8px;
}

.ai-provider-mobile-card__identity {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  min-width: 0;
  gap: 12px;
}

.ai-provider-mobile-card__name {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 15px;
  font-weight: 600;
}

.ai-provider-mobile-card__tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.ai-provider-mobile-card__model {
  min-width: 0;
  overflow: hidden;
  color: rgba(15, 23, 42, 0.66);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-provider-mobile-card__details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.ai-provider-mobile-card__detail {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 4px;
}

.ai-provider-mobile-card__detail--wide {
  grid-column: 1 / -1;
}

.ai-provider-mobile-card__label {
  color: rgba(15, 23, 42, 0.52);
  font-size: 11px;
  letter-spacing: 0.03em;
}

.ai-provider-mobile-card__value,
.ai-provider-mobile-card__prompt-value {
  min-width: 0;
  overflow-wrap: anywhere;
  color: rgba(15, 23, 42, 0.74);
  font-size: 13px;
  line-height: 1.45;
}

.ai-provider-mobile-card__value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-provider-mobile-card__prompt {
  display: grid;
  min-width: 0;
  gap: 4px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
}

.ai-provider-mobile-card__prompt-value {
  white-space: pre-wrap;
}

.ai-provider-mobile-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 2px;
}

.ai-provider-mobile-card__actions :deep(.n-button) {
  max-width: 100%;
}

.ai-provider-modal__header {
  display: grid;
  gap: 4px;
}

.ai-provider-modal__title {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.35;
  color: #0f172a;
}

.ai-provider-modal__subtitle {
  max-width: 560px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.4;
  color: rgba(15, 23, 42, 0.54);
}

.ai-provider-modal__scroll {
  max-height: min(68vh, 640px);
}

.ai-provider-modal__form {
  gap: 18px;
}

.ai-provider-modal__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 20px;
  row-gap: 14px;
}

.ai-provider-modal__section {
  display: grid;
  gap: 14px;
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
}

.ai-provider-modal__form :deep(.n-form-item) {
  margin-bottom: 0;
}

.ai-provider-modal__grid :deep(.n-form-item--top-labelled) {
  grid-template-rows: auto auto auto;
  align-content: start;
}

.ai-provider-modal__grid :deep(.n-form-item) {
  align-self: start;
  min-width: 0;
}

.ai-provider-modal__form :deep(.n-form-item-feedback-wrapper) {
  min-height: auto;
  padding-top: 6px;
}

.ai-provider-modal__textarea :deep(textarea) {
  min-height: 132px;
  resize: vertical;
}

.ai-provider-modal__advanced {
  padding-top: 8px;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
}

.ai-provider-modal__json :deep(textarea) {
  min-height: 168px;
  resize: vertical;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 767px) {
  .ai-provider-modal__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .ai-provider-modal__subtitle {
    max-width: calc(96vw - 96px);
  }

  .ai-provider-modal__scroll {
    max-height: min(72vh, 620px);
  }
}

@media (max-width: 480px) {
  .ai-provider-mobile-card__identity {
    display: grid;
  }

  .ai-provider-mobile-card__tags {
    justify-content: flex-start;
  }

  .ai-provider-mobile-card__details {
    grid-template-columns: minmax(0, 1fr);
  }

  .ai-provider-mobile-card__detail--wide {
    grid-column: auto;
  }
}
</style>
