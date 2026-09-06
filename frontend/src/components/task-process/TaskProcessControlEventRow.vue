<template>
  <div class="event-item event-item--control">
    <div class="event-header">
      <div class="event-icon event-icon--control">
        <n-icon size="15"><ChatbubbleEllipsesOutline /></n-icon>
      </div>
      <div class="event-info">
        <span class="event-name">{{ statusLabel }}</span>
        <span class="event-control-id">
          <template v-if="row.controlEntry.commandType">{{ typeLabel }} · </template>
          <template v-if="row.controlEntry.sequenceNo !== null">#{{ row.controlEntry.sequenceNo }} · </template>
          <template v-if="row.controlEntry.commandId">cmd {{ row.controlEntry.commandId }}</template>
          <template v-else>{{ row.controlEntry.eventType }}</template>
        </span>
      </div>
      <span class="event-ts">{{ formatTimestamp(row.event.created_at) }}</span>
    </div>
    <div v-if="row.controlEntry.text" class="control-text">
      <pre class="control-pre">{{ row.controlEntry.text }}</pre>
    </div>
    <div v-if="row.controlEntry.rejectionMessage" class="control-rejection">
      {{ row.controlEntry.rejectionMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NIcon } from 'naive-ui'
import { ChatbubbleEllipsesOutline } from '@vicons/ionicons5'
import { useI18n } from 'vue-i18n'
import { controlEventStatusKey, formatTimestamp, type NormalizedControlEventRow } from './taskProcessUtils'

const props = defineProps<{ row: NormalizedControlEventRow }>()

const { t } = useI18n()

const statusLabel = computed(() => {
  const key = controlEventStatusKey(props.row.controlEntry.eventType)
  return key ? t(key) : props.row.controlEntry.eventType
})

const typeLabel = computed(() => {
  return props.row.controlEntry.commandType === 'steer'
    ? t('taskView.steeringSteer')
    : t('taskView.steeringFollowUp')
})
</script>

<style scoped>
.event-item {
  border-bottom: 1px solid var(--n-border-color, rgba(128, 128, 128, 0.1));
  padding: 6px 0;
}
.event-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
}
.event-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.event-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.event-name {
  font-weight: 500;
  font-size: 13px;
  flex-shrink: 0;
}
.event-ts {
  font-size: 11px;
  color: var(--n-text-color-3, #999);
  flex-shrink: 0;
}

.event-item--control {
  --event-accent: #2563eb;
}

.event-icon--control {
  color: var(--event-accent);
}

.event-item--control .event-header .event-name {
  color: var(--event-accent);
}

.event-control-id {
  color: var(--n-text-color-3, #8a8f98);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.control-text {
  margin-top: 6px;
  padding-left: 30px;
}

.control-pre {
  margin: 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(37, 99, 235, 0.06);
  border: 1px solid rgba(37, 99, 235, 0.14);
  font-family: var(--n-font-family-mono, monospace);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: rgba(30, 41, 59, 0.9);
}

.control-rejection {
  margin-top: 4px;
  padding-left: 30px;
  color: #d03050;
  font-size: 12px;
  overflow-wrap: anywhere;
}
</style>