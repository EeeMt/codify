<template>
  <TaskProcessTextRow
    v-if="isTextRow(row)"
    :row="asTextRow(row)"
    :expanded-text="expandedText"
    :loading="textLoading"
    :show-content="textShowContent"
    :now-ms="nowMs"
    :task-active="taskActive"
    @collapse-change="forwardCollapseChange"
  />
  <TaskProcessToolRow
    v-else-if="isToolRow(row)"
    :row="asToolRow(row)"
    :input-loaded="inputLoaded"
    :output-loaded="outputLoaded"
    :input-loading="inputLoading"
    :output-loading="outputLoading"
    :input-failed="inputFailed"
    :output-failed="outputFailed"
    :input-expanded-text="inputExpandedText"
    :output-expanded-text="outputExpandedText"
    :task-active="taskActive"
    @collapse-change="forwardCollapseChange"
  />
  <div v-else-if="isCompactRow(row)" class="context-compact-divider">
    <span class="context-compact-label">{{ compactLabel }}</span>
  </div>
  <TaskProcessControlEventRow
    v-else-if="isControlEventRow(row)"
    :row="asControlRow(row)"
  />
</template>

<script setup lang="ts">
import { toRefs } from 'vue'
import TaskProcessTextRow from './TaskProcessTextRow.vue'
import TaskProcessToolRow from './TaskProcessToolRow.vue'
import TaskProcessControlEventRow from './TaskProcessControlEventRow.vue'
import {
  isCompactRow,
  isControlEventRow,
  isTextRow,
  isToolRow,
  type NormalizedControlEventRow,
  type NormalizedTaskProcessRow,
  type NormalizedTextEventRow,
  type NormalizedToolEventRow,
} from './taskProcessUtils'

const props = withDefaults(defineProps<{
  row: NormalizedTaskProcessRow
  expandedText?: string
  textLoading?: boolean
  textShowContent?: boolean
  nowMs?: number
  taskActive?: boolean
  inputLoaded?: boolean
  outputLoaded?: boolean
  inputLoading?: boolean
  outputLoading?: boolean
  inputFailed?: boolean
  outputFailed?: boolean
  inputExpandedText?: string
  outputExpandedText?: string
  compactLabel?: string
}>(), {
  expandedText: '',
  textLoading: false,
  textShowContent: true,
  nowMs: () => Date.now(),
  taskActive: false,
  inputLoaded: false,
  outputLoaded: false,
  inputLoading: false,
  outputLoading: false,
  inputFailed: false,
  outputFailed: false,
  inputExpandedText: '',
  outputExpandedText: '',
  compactLabel: 'Context compacted',
})

const emit = defineEmits<{
  (e: 'collapse-change', names: (string | number)[]): void
}>()

const {
  row,
  expandedText,
  textLoading,
  textShowContent,
  nowMs,
  taskActive,
  inputLoaded,
  outputLoaded,
  inputLoading,
  outputLoading,
  inputFailed,
  outputFailed,
  inputExpandedText,
  outputExpandedText,
  compactLabel,
} = toRefs(props)

function asTextRow(value: NormalizedTaskProcessRow): NormalizedTextEventRow {
  return value as NormalizedTextEventRow
}

function asToolRow(value: NormalizedTaskProcessRow): NormalizedToolEventRow {
  return value as NormalizedToolEventRow
}

function asControlRow(value: NormalizedTaskProcessRow): NormalizedControlEventRow {
  return value as NormalizedControlEventRow
}

function forwardCollapseChange(names: (string | number)[]) {
  emit('collapse-change', names)
}
</script>
