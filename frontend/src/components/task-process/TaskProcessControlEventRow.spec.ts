import { describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { mount } from '@vue/test-utils'
import type { TaskLog } from '../../api'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    // Keys render verbatim; interpolated messages surface as `key:value` so
    // tests can assert the translated-message shape without pinning locales.
    t: (key: string, named?: Record<string, unknown>) =>
      named === undefined ? key : `${key}:${String(named.message ?? '')}`,
  }),
}))

vi.mock('naive-ui', () => ({
  NIcon: {
    name: 'NIcon',
    inheritAttrs: false,
    setup(_props: unknown, { slots, attrs }: { slots: Record<string, () => unknown>; attrs: Record<string, unknown> }) {
      return () => h('i', { class: 'NIcon', ...attrs }, slots.default?.())
    },
  },
}))

vi.mock('@vicons/ionicons5', () => {
  const icon = { name: 'MockIcon', render: () => h('span') }
  return { ChatbubbleEllipsesOutline: icon }
})

import TaskProcessControlEventRow from './TaskProcessControlEventRow.vue'
import type { NormalizedControlEventRow, ParsedControlEntry } from './taskProcessUtils'

function createRow(
  entry: Partial<ParsedControlEntry>,
  event: Partial<TaskLog> = {},
): NormalizedControlEventRow {
  return {
    kind: 'control_event',
    event: {
      id: 1,
      task_id: 1,
      log_level: 'INFO',
      log_type: 'control_event',
      metadata: null,
      message: '',
      created_at: '2026-09-11T00:44:55Z',
      ...event,
    },
    controlEntry: {
      eventType: 'control.command.delivered',
      commandId: null,
      sequenceNo: 1,
      commandType: 'steer',
      text: '',
      rejectionMessage: null,
      ...entry,
    },
  }
}

describe('TaskProcessControlEventRow', () => {
  it('promotes the steer type and message and hides the command id', () => {
    const wrapper = mount(TaskProcessControlEventRow, {
      props: { row: createRow({ commandId: '<UUID:9f3a>', text: '完成后简要总结即可' }) },
    })

    expect(wrapper.get('.event-control-type').text()).toBe('[taskView.steeringSteer]')
    expect(wrapper.get('.event-name').text()).toBe('taskView.steeringStatusDelivered')
    expect(wrapper.get('.control-pre').text()).toBe('完成后简要总结即可')
    expect(wrapper.get('.control-sequence').text()).toBe('#1')
    expect(wrapper.get('.event-ts').text()).not.toBe('')
    // The pseudonymized UUID offers no user decision value in the main view.
    expect(wrapper.html()).not.toContain('<UUID:9f3a>')
    expect(wrapper.html()).not.toContain('cmd ')
  })

  it('renders a rejected follow-up with its type, message and public reason', () => {
    const wrapper = mount(TaskProcessControlEventRow, {
      props: {
        row: createRow({
          eventType: 'control.command.rejected',
          commandType: 'follow_up',
          sequenceNo: 2,
          text: '完成当前步骤后继续检查测试',
          rejectionMessage: '任务正在收尾，不再接收新命令',
        }),
      },
    })

    expect(wrapper.get('.event-control-type').text()).toBe('[taskView.steeringFollowUp]')
    expect(wrapper.get('.event-name').text()).toBe('taskView.steeringStatusRejected')
    expect(wrapper.get('.control-pre').text()).toBe('完成当前步骤后继续检查测试')
    expect(wrapper.get('.control-rejection').text()).toBe(
      'taskView.steeringRejectionReason:任务正在收尾，不再接收新命令',
    )
    expect(wrapper.get('.control-sequence').text()).toBe('#2')
  })

  it('still shows status and sequence for events without projected command facts', () => {
    const wrapper = mount(TaskProcessControlEventRow, {
      props: {
        row: createRow(
          { commandType: null, text: '', sequenceNo: 4 },
          {},
        ),
      },
    })

    expect(wrapper.get('.event-name').text()).toBe('taskView.steeringStatusDelivered')
    expect(wrapper.get('.control-sequence').text()).toBe('#4')
    expect(wrapper.get('.event-control-type').text()).toBe('control.command.delivered')
    expect(wrapper.find('.control-pre').exists()).toBe(false)
    expect(wrapper.find('.control-rejection').exists()).toBe(false)
  })

  it('preserves newlines and long sanitized text in a wrapping pre block', () => {
    const text = 'line one\nline two [GITLAB_TOKEN]\n' + 'x'.repeat(4000)
    const wrapper = mount(TaskProcessControlEventRow, {
      props: { row: createRow({ text }) },
    })

    const pre = wrapper.get('.control-pre')
    expect(pre.element.tagName).toBe('PRE')
    expect(pre.text()).toBe(text)
    expect(pre.html()).toContain('[GITLAB_TOKEN]')
  })
})
