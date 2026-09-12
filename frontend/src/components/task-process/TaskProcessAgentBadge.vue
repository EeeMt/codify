<template>
  <span class="agent-badge" :aria-label="label" :title="label">
    <n-icon size="11" class="agent-badge__icon"><GitBranchOutline /></n-icon>
    <span class="agent-badge__label">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NIcon } from 'naive-ui'
import { GitBranchOutline } from '@vicons/ionicons5'
import { useI18n } from 'vue-i18n'
import { agentDisplayName, type ProcessAgentRef } from './taskProcessUtils'

const props = defineProps<{ agent: ProcessAgentRef }>()

const { t } = useI18n()

const label = computed(() => t('taskView.subagentBadge', { name: agentDisplayName(props.agent) }))
</script>

<style scoped>
.agent-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: 220px;
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--app-surface-muted, rgba(148, 163, 184, 0.16));
  color: var(--app-text-muted, #64748b);
  font-size: 11px;
  line-height: 16px;
  flex-shrink: 0;
}
.agent-badge__icon {
  flex-shrink: 0;
}
.agent-badge__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
