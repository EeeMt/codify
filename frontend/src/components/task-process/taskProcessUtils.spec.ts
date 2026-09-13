import { describe, expect, it, vi } from 'vitest'
import { h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import type { TaskLog } from '../../api'
import TaskProcessPanel from '../TaskProcessPanel.vue'
import TaskProcessToolRow from './TaskProcessToolRow.vue'
import { controlEventStatusKey, formatInput, getInputSummary, groupTaskProcessRows, normalizeTaskProcessRows, parseControlEntry, parseTextEntry, summarizeSkillUsage, type NormalizedControlEventRow } from './taskProcessUtils'

vi.mock('vue-i18n', () => ({
  createI18n: () => ({ global: { locale: { value: 'zh-CN' } } }),
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('naive-ui', () => {
  const makePassthrough = (name: string, tag = 'div') => ({
    name,
    inheritAttrs: false,
    setup(_props: unknown, { slots, attrs }: { slots: Record<string, () => unknown>; attrs: Record<string, unknown> }) {
      return () => h(tag, { class: name, ...attrs }, slots.default?.())
    },
  })

  const NCollapseItem = {
    name: 'NCollapseItem',
    inheritAttrs: false,
    setup(_props: unknown, { slots, attrs }: { slots: Record<string, () => unknown>; attrs: Record<string, unknown> }) {
      return () => h('div', { class: 'NCollapseItem', ...attrs }, [
        h('div', { class: 'NCollapseItem__header' }, slots.header?.()),
        h('div', { class: 'NCollapseItem__content' }, slots.default?.()),
      ])
    },
  }

  return {
    NCard: {
      name: 'NCard',
      inheritAttrs: false,
      setup(_props: unknown, { attrs, slots }: { attrs: Record<string, unknown>; slots: Record<string, () => unknown> }) {
        return () => h('section', { class: attrs.class, style: attrs.style }, [
          h('header', { class: 'n-card__header' }, slots.header?.()),
          h('div', { class: 'n-card__content' }, slots.default?.()),
        ])
      },
    },
    NTag: makePassthrough('NTag', 'span'),
    NIcon: makePassthrough('NIcon', 'i'),
    NTabs: makePassthrough('NTabs'),
    NTabPane: makePassthrough('NTabPane'),
    NTab: makePassthrough('NTab', 'button'),
    NEmpty: makePassthrough('NEmpty'),
    NCollapse: makePassthrough('NCollapse'),
    NCollapseItem,
    NButton: makePassthrough('NButton', 'button'),
    NBadge: makePassthrough('NBadge', 'span'),
    NSpin: makePassthrough('NSpin'),
    dateEnUS: {},
    dateZhCN: {},
    enUS: {},
    zhCN: {},
  }
})

vi.mock('../utils/format', () => ({
  formatDurationMs: (value: number) => `${value}ms`,
  formatDurationSec: (value: number) => `${value}s`,
}))

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    getTaskPayload: vi.fn(),
  }
})

vi.mock('@vicons/ionicons5', () => {
  const icon = { name: 'MockIcon', render: () => h('span') }
  return {
    CubeOutline: icon,
    ArrowDownCircleOutline: icon,
    BulbOutline: icon,
    ChatboxOutline: icon,
    ChatbubbleEllipsesOutline: icon,
    TerminalOutline: icon,
    CreateOutline: icon,
    DocumentTextOutline: icon,
    PencilOutline: icon,
    SearchOutline: icon,
    ExtensionPuzzleOutline: icon,
    GitBranchOutline: icon,
    ServerOutline: icon,
    ChevronForward: icon,
  }
})

function createTaskLog(overrides: Partial<TaskLog>): TaskLog {
  return {
    id: 1,
    task_id: 1,
    log_level: 'info',
    log_type: 'tool_call',
    metadata: null,
    message: '',
    created_at: '2026-05-04T10:00:00Z',
    ...overrides,
  }
}

describe('taskProcessUtils', () => {
  it('ignores legacy tool_calls_json batches in the normalized event stream', () => {
    const logs: TaskLog[] = [
      createTaskLog({
        id: 10,
        log_type: 'tool_calls_json',
        metadata: JSON.stringify([
          { name: 'Read', input: { file_path: '/tmp/a' }, output: null, error: false },
        ]),
      }),
      createTaskLog({
        id: 11,
        log_type: 'tool_call',
        metadata: JSON.stringify({ name: 'Bash', input: { command: 'pwd' }, output: '', error: false }),
      }),
    ]

    const rows = normalizeTaskProcessRows(logs)

    expect(rows).toHaveLength(1)
    expect(rows.map((row) => row.kind)).toEqual(['tool_call'])
    expect(rows[0].toolCall.name).toBe('Bash')
  })

  it('normalizes control_event logs into control rows with parsed identity', () => {
    const log = createTaskLog({
      id: 42,
      log_type: 'control_event',
      metadata: JSON.stringify({
        type: 'control.command.delivered',
        command_id: 'cmd-1',
        sequence_no: 7,
        command_type: 'steer',
        text: '先修复并发问题',
        delivered_at: '2026-08-21T10:00:01Z',
      }),
    })
    const rows = normalizeTaskProcessRows([log])
    expect(rows).toHaveLength(1)
    expect(rows[0].kind).toBe('control_event')
    const entry = rows[0].controlEntry
    expect(entry.eventType).toBe('control.command.delivered')
    expect(entry.commandId).toBe('cmd-1')
    expect(entry.sequenceNo).toBe(7)
    expect(entry.commandType).toBe('steer')
    expect(entry.text).toBe('先修复并发问题')
    expect(entry.rejectionMessage).toBeNull()
  })

  it('control rows interleave with other rows in timestamp order', () => {
    const logs: TaskLog[] = [
      createTaskLog({ id: 1, log_type: 'assistant_text', created_at: '2026-05-04T10:00:00Z', metadata: JSON.stringify({ payload_id: null, preview: 'before', truncated: false }) }),
      createTaskLog({ id: 2, log_type: 'control_event', created_at: '2026-05-04T10:00:01Z', metadata: JSON.stringify({ type: 'control.command.rejected', command_id: 'cmd-9', sequence_no: 1, command_type: 'steer', text: 'stop', rejection_code: 'gate', rejection_message: 'gate closed' }) }),
      createTaskLog({ id: 3, log_type: 'assistant_text', created_at: '2026-05-04T10:00:02Z', metadata: JSON.stringify({ payload_id: null, preview: 'after', truncated: false }) }),
    ]
    const rows = normalizeTaskProcessRows(logs)
    expect(rows.map(r => r.kind)).toEqual(['assistant_text', 'control_event', 'assistant_text'])
    expect(rows[1].controlEntry.rejectionMessage).toBe('gate closed')
  })

  it('parses malformed control metadata into an empty event type', () => {
    expect(parseControlEntry(null).eventType).toBe('')
    expect(parseControlEntry('not-json').eventType).toBe('')
    expect(parseControlEntry({ type: 'irrelevant' }).eventType).toBe('')
    expect(parseControlEntry({ type: 'control.queue.updated', queue: [] }).eventType).toBe('control.queue.updated')
    expect(parseControlEntry({ type: 'control.command.delivered' }).text).toBe('')
  })

  it('filters internal control audit events from the visible event stream', () => {
    const log = createTaskLog({
      id: 43,
      log_type: 'control_event',
      metadata: JSON.stringify({ type: 'agent_settled', aborted: false, settled_line: 193 }),
    })

    expect(normalizeTaskProcessRows([log])).toEqual([])
  })

  it('drops control.queue.updated audit rows without hiding command outcomes', () => {
    // One steer produces enqueue + drain queue updates plus one native ACK;
    // only the ACK is a user action.
    const logs: TaskLog[] = [
      createTaskLog({
        id: 50,
        log_type: 'control_event',
        created_at: '2026-09-11T00:44:54Z',
        metadata: JSON.stringify({ type: 'control.queue.updated', queue: [{ id: 'steering[0]', text: '完成后简要总结即可' }] }),
      }),
      createTaskLog({
        id: 51,
        log_type: 'control_event',
        created_at: '2026-09-11T00:44:55Z',
        metadata: JSON.stringify({ type: 'control.command.delivered', command_id: '<UUID:1>', sequence_no: 1, command_type: 'steer', text: '完成后简要总结即可' }),
      }),
      createTaskLog({
        id: 52,
        log_type: 'control_event',
        created_at: '2026-09-11T00:44:56Z',
        metadata: JSON.stringify({ type: 'control.queue.updated', queue: [] }),
      }),
    ]

    const rows = normalizeTaskProcessRows(logs)

    expect(rows).toHaveLength(1)
    expect(rows[0].kind).toBe('control_event')
    expect((rows[0] as NormalizedControlEventRow).controlEntry.eventType).toBe('control.command.delivered')
  })

  it('keeps control rows readable when the projection added no command facts', () => {
    // Events ingested before the projection enhancement carry no type/text;
    // the row must still resolve its status and sequence.
    const log = createTaskLog({
      id: 53,
      log_type: 'control_event',
      metadata: JSON.stringify({ type: 'control.command.outcome_unknown', command_id: '<UUID:2>', sequence_no: 3, code: 'delivery_outcome_unknown' }),
    })

    const rows = normalizeTaskProcessRows([log])

    expect(rows).toHaveLength(1)
    const entry = (rows[0] as NormalizedControlEventRow).controlEntry
    expect(entry.commandType).toBeNull()
    expect(entry.text).toBe('')
    expect(entry.sequenceNo).toBe(3)
    expect(controlEventStatusKey(entry.eventType)).toBe('taskView.steeringStatusOutcomeUnknown')
  })

  it('formats Edit input using old_string and new_string keys', () => {
    const formatted = formatInput({
      name: 'Edit',
      input: {
        file_path: '/tmp/demo.txt',
        old_string: 'before',
        new_string: 'after',
      },
      output: null,
      error: false,
    })

    expect(formatted).toContain('file: /tmp/demo.txt')
    expect(formatted).toContain('--- (old)\nbefore')
    expect(formatted).toContain('+++ (new)\nafter')
  })

  it('prefers input_preview for payload-backed tool calls', () => {
    expect(getInputSummary({
      name: 'Read',
      input: {},
      output: null,
      error: false,
      input_payload_id: 9,
      input_preview: '/tmp/example.txt',
    })).toBe('/tmp/example.txt')
  })

  it('normalizes context_compact log into a NormalizedCompactRow', () => {
    const log = createTaskLog({ id: 42, log_type: 'context_compact', metadata: JSON.stringify({ session_id: 'abc-123' }) })
    const rows = normalizeTaskProcessRows([log])
    expect(rows).toHaveLength(1)
    expect(rows[0].kind).toBe('context_compact')
    expect(rows[0].event).toBe(log)
  })

  it('context_compact rows are interleaved with other rows in timestamp order', () => {
    const logs: TaskLog[] = [
      createTaskLog({ id: 1, log_type: 'assistant_text', created_at: '2026-05-04T10:00:00Z', metadata: JSON.stringify({ payload_id: null, preview: 'before', truncated: false }) }),
      createTaskLog({ id: 2, log_type: 'context_compact', created_at: '2026-05-04T10:00:01Z', metadata: JSON.stringify({ session_id: 'abc' }) }),
      createTaskLog({ id: 3, log_type: 'assistant_text', created_at: '2026-05-04T10:00:02Z', metadata: JSON.stringify({ payload_id: null, preview: 'after', truncated: false }) }),
    ]
    const rows = normalizeTaskProcessRows(logs)
    expect(rows.map(r => r.kind)).toEqual(['assistant_text', 'context_compact', 'assistant_text'])
  })

  it('summarizes skill usage from the same tool events rendered in task process', () => {
    const logs: TaskLog[] = [
      createTaskLog({
        id: 1,
        log_type: 'tool_call',
        metadata: JSON.stringify({ name: 'Skill', input: { skill_name: 'playwright-cli' } }),
      }),
      createTaskLog({
        id: 2,
        log_type: 'tool_call',
        metadata: JSON.stringify({ name: 'Skill', input: { path: '/workspace/.agents/skills/playwright-cli/SKILL.md' } }),
      }),
      createTaskLog({
        id: 3,
        log_type: 'tool_call',
        metadata: JSON.stringify({ name: 'Skill', input: { skills: [{ name: 'openai-docs', count: 3 }, 'imagegen'] }, output: null, error: false }),
      }),
    ]

    expect(summarizeSkillUsage(logs)).toEqual([
      { name: 'openai-docs', count: 3 },
      { name: 'playwright-cli', count: 2 },
      { name: 'imagegen', count: 1 },
    ])
  })

  it('counts Agent subagent_type as skill usage', () => {
    const agentInput = {
      description: 'Explore scheduled task feature',
      prompt: 'Explore the codebase',
      subagent_type: 'Explore',
    }
    const logs: TaskLog[] = [
      createTaskLog({
        id: 1,
        log_type: 'tool_call',
        metadata: JSON.stringify({ name: 'Agent', input: agentInput, output: null, error: false }),
      }),
    ]

    expect(summarizeSkillUsage(logs)).toEqual([
      { name: 'Explore', count: 1 },
    ])
  })

  it('does not deduplicate repeated direct Agent calls with the same input', () => {
    const agentInput = {
      description: 'Explore scheduled task feature',
      prompt: 'Explore the codebase',
      subagent_type: 'Explore',
    }
    const logs: TaskLog[] = [
      createTaskLog({
        id: 1,
        log_type: 'tool_call',
        metadata: JSON.stringify({ name: 'Agent', input: agentInput, output: null, error: false }),
      }),
      createTaskLog({
        id: 2,
        log_type: 'tool_call',
        created_at: '2026-05-04T10:00:01Z',
        metadata: JSON.stringify({ name: 'Agent', input: agentInput, output: null, error: false }),
      }),
    ]

    expect(summarizeSkillUsage(logs)).toEqual([
      { name: 'Explore', count: 2 },
    ])
  })

  it('maps thinking lifecycle keys from object metadata onto ParsedTextEntry', () => {
    const entry = parseTextEntry({
      attempt_id: 'task-1-attempt-1',
      reasoning_id: 'pi-thinking-42',
      status: 'completed',
      started_at: '2026-09-04T01:00:00Z',
      ended_at: '2026-09-04T01:00:48Z',
      duration_ms: 48000,
      payload_id: 7,
      preview: 'final summary',
      char_count: 13,
      truncated: false,
    })

    expect(entry.thinkingStatus).toBe('completed')
    expect(entry.startedAt).toBe('2026-09-04T01:00:00Z')
    expect(entry.endedAt).toBe('2026-09-04T01:00:48Z')
    expect(entry.durationMs).toBe(48000)
    expect(entry.payloadId).toBe(7)
    expect(entry.preview).toBe('final summary')
    expect(entry.text).toBe('')
  })

  it('maps in_progress lifecycle keys from JSON-string metadata', () => {
    const entry = parseTextEntry(JSON.stringify({
      attempt_id: 'task-1-attempt-1',
      reasoning_id: 'pi-thinking-42',
      status: 'in_progress',
      started_at: '2026-09-04T01:00:00Z',
      ended_at: null,
      duration_ms: null,
      payload_id: null,
      preview: '',
      char_count: 0,
      truncated: false,
    }))

    expect(entry.thinkingStatus).toBe('in_progress')
    expect(entry.startedAt).toBe('2026-09-04T01:00:00Z')
    expect(entry.endedAt).toBeNull()
    expect(entry.durationMs).toBeNull()
    expect(entry.payloadId).toBeNull()
  })

  it('maps interrupted status and never coerces invalid duration values', () => {
    const entry = parseTextEntry(JSON.stringify({
      status: 'interrupted',
      started_at: '2026-09-04T01:00:00Z',
      ended_at: '2026-09-04T02:00:00Z',
      duration_ms: 'not-a-number',
    }))

    expect(entry.thinkingStatus).toBe('interrupted')
    expect(entry.startedAt).toBe('2026-09-04T01:00:00Z')
    expect(entry.endedAt).toBe('2026-09-04T02:00:00Z')
    expect(entry.durationMs).toBeNull()

    // Unknown status strings fall back to null rather than an invalid value.
    expect(parseTextEntry(JSON.stringify({ status: 'paused' })).thinkingStatus).toBeNull()
  })

  it('keeps lifecycle fields null when metadata has no lifecycle keys', () => {
    const entry = parseTextEntry(JSON.stringify({
      text: 'static body',
      preview: 'static preview',
      payload_id: 3,
      char_count: 5,
      truncated: false,
    }))

    expect(entry.thinkingStatus).toBeNull()
    expect(entry.startedAt).toBeNull()
    expect(entry.endedAt).toBeNull()
    expect(entry.durationMs).toBeNull()
    // Existing content fields are untouched for legacy static rows.
    expect(entry.text).toBe('static body')
    expect(entry.payloadId).toBe(3)
  })
})

describe('TaskProcessToolRow', () => {
  it('shows an execution spinner for a pending tool while the task is active', () => {
    const wrapper = mount(TaskProcessToolRow, {
      props: {
        row: {
          kind: 'tool_call',
          event: createTaskLog({ metadata: JSON.stringify({ name: 'Bash', input: { command: 'sleep 1' }, error: false }) }),
          toolCall: { name: 'Bash', input: { command: 'sleep 1' }, error: false },
        },
        inputLoaded: false,
        outputLoaded: false,
        inputLoading: false,
        outputLoading: false,
        taskActive: true,
      },
    })

    expect(wrapper.find('.tool-spinner').exists()).toBe(true)
    expect(wrapper.findAll('button').some((button) => button.text().includes('taskView.toolOutput'))).toBe(false)
  })

  it('shows the output section when tool output is an empty string', () => {
    const wrapper = mount(TaskProcessToolRow, {
      props: {
        row: {
          kind: 'tool_call',
          event: createTaskLog({ metadata: JSON.stringify({ name: 'Bash', input: { command: 'true' }, output: '', error: false }) }),
          toolCall: { name: 'Bash', input: { command: 'true' }, output: '', error: false },
        },
        inputLoaded: false,
        outputLoaded: false,
        inputLoading: false,
        outputLoading: false,
      },
    })

    expect(wrapper.text()).toContain('taskView.toolOutput')
    expect(wrapper.text()).not.toContain('taskView.noToolOutputCaptured')
  })

  it('shows input preview in the header and spinner badge (no body content) for payload-backed tool calls while loading', async () => {
    const wrapper = mount(TaskProcessToolRow, {
      props: {
        row: {
          kind: 'tool_call',
          event: createTaskLog({ metadata: JSON.stringify({ name: 'Read', input: {}, output: null, error: false, input_payload_id: 12, input_preview: '/tmp/example.txt' }) }),
          toolCall: { name: 'Read', input: {}, output: null, error: false, input_payload_id: 12, input_preview: '/tmp/example.txt' },
        },
        inputLoaded: false,
        outputLoaded: false,
        inputLoading: false,
        outputLoading: false,
      },
    })

    await wrapper.get('button.tool-badge').trigger('click')

    // Preview still shows in the event header
    expect(wrapper.text()).toContain('/tmp/example.txt')
    // While payload hasn't loaded, content body is hidden (no placeholder text shown)
    expect(wrapper.text()).not.toContain('taskView.archivedInputPending')
    // Badge shows a spinner (busy state) instead of placeholder text in the body
    expect(wrapper.find('.badge-spin-ring').exists()).toBe(true)
  })

  it('shows failure text for tool payload load errors', async () => {
    const wrapper = mount(TaskProcessToolRow, {
      props: {
        row: {
          kind: 'tool_call',
          event: createTaskLog({ metadata: JSON.stringify({ name: 'Bash', input: {}, output: null, error: false, output_payload_id: 18 }) }),
          toolCall: { name: 'Bash', input: {}, output: null, error: false, output_payload_id: 18 },
        },
        inputLoaded: false,
        outputLoaded: false,
        inputLoading: false,
        outputLoading: false,
        outputFailed: true,
      },
    })

    await wrapper.get('button.tool-badge').trigger('click')

    expect(wrapper.text()).toContain('taskView.failedToLoadPayload')
  })
})

describe('TaskProcessPanel raw pane wiring', () => {
  it('renders the raw pane with terminal html', async () => {
    const wrapper = mount(TaskProcessPanel, {
      props: {
        task: {
          id: 1,
          issue_id: 1,
          project_id: 1,
          user_prompt: 'Prompt',
          status: 'completed',
          priority: 0,
          is_retry: false,
          retry_source_task_id: null,
          scheduled_at: null,
          container_id: 'container-1',
          container_name: 'container-1',
          commit_sha: null,
          error_message: null,
          additions: 0,
          deletions: 0,
          total_changes: 0,
          input_tokens: null,
          output_tokens: null,
          provider_id: null,
          created_at: '2026-05-04T10:00:00Z',
          updated_at: '2026-05-04T10:00:00Z',
          started_at: null,
          completed_at: null,
        },
        taskLogs: [],
        isActive: false,
        terminalHtml: '<span>hello</span>',
        taskStatus: 'completed',
      },
    })

    await nextTick()

    // Switch to the raw tab to see the terminal html
    ;(wrapper.vm as any).activeTab = 'raw'
    await nextTick()

    expect(wrapper.html()).toContain('hello')
    expect(wrapper.find('pre.log-content').exists()).toBe(true)
  })

  it('renders container summary in runtime info instead of the event stream', () => {
    const wrapper = mount(TaskProcessPanel, {
      props: {
        task: {
          id: 1,
          issue_id: 1,
          project_id: 1,
          user_prompt: 'Prompt',
          status: 'completed',
          priority: 0,
          is_retry: false,
          retry_source_task_id: null,
          scheduled_at: null,
          container_id: 'container-abcdef123456',
          container_name: 'worker-292',
          commit_sha: null,
          error_message: null,
          additions: 0,
          deletions: 0,
          total_changes: 0,
          input_tokens: null,
          output_tokens: null,
          provider_id: null,
          created_at: '2026-05-04T10:00:00Z',
          updated_at: '2026-05-04T10:00:00Z',
          started_at: null,
          completed_at: null,
        },
        taskLogs: [],
        isActive: false,
        terminalHtml: '',
        taskStatus: 'completed',
      },
    })

    expect(wrapper.text()).toContain('worker-292')
    expect(wrapper.find('.system-init-banner').text()).toContain('worker-292')
    expect(wrapper.find('.empty-state').attributes('description')).toBe('taskView.noLogsAvailable')
    expect(wrapper.find('.event-stream .event-item--container').exists()).toBe(false)
  })
})

describe('subagent attribution', () => {
  const childAgent = (id: string, role: string) => JSON.stringify({ id, parent_id: 'root', role })

  it('orders rows by TaskLog.id so concurrent children sharing a timestamp cannot reorder', () => {
    const logs = [
      createTaskLog({ id: 7, log_type: 'assistant_text', created_at: '2026-05-04T10:00:05Z', metadata: JSON.stringify({ text: 'first' }) }),
      createTaskLog({ id: 4, log_type: 'assistant_text', created_at: '2026-05-04T10:00:05Z', metadata: JSON.stringify({ text: 'second' }) }),
    ]

    expect(normalizeTaskProcessRows(logs).map((row) => row.event.id)).toEqual([4, 7])
  })

  it('carries the agent ref on child rows and leaves root rows null', () => {
    const logs = [
      createTaskLog({ id: 1, log_type: 'assistant_text', metadata: { text: 'root' } }),
      createTaskLog({
        id: 2,
        log_type: 'thinking',
        metadata: { reasoning_id: 'r1', agent: JSON.parse(childAgent('child-a', 'reviewer')) },
      }),
    ]

    const rows = normalizeTaskProcessRows(logs)

    expect(rows[0].kind === 'control_event' ? null : rows[0].agent).toBeNull()
    const childRow = rows[1]
    expect(childRow.kind).toBe('thinking')
    expect(childRow.kind !== 'control_event' && childRow.agent).toEqual({
      id: 'child-a',
      parentId: 'root',
      role: 'reviewer',
      ordinal: null,
    })
  })

  it('numbers same-role children by first appearance and leaves unique roles unnumbered', () => {
    const logs = [
      createTaskLog({ id: 1, log_type: 'assistant_text', metadata: { agent: { id: 'child-b', parent_id: 'root', role: 'reviewer' } } }),
      createTaskLog({ id: 2, log_type: 'assistant_text', metadata: { agent: { id: 'child-a', parent_id: 'root', role: 'reviewer' } } }),
      createTaskLog({ id: 3, log_type: 'assistant_text', metadata: { agent: { id: 'child-c', parent_id: 'root', role: 'explore' } } }),
      createTaskLog({ id: 4, log_type: 'assistant_text', metadata: { agent: { id: 'child-b', parent_id: 'root', role: 'reviewer' } } }),
    ]

    expect(normalizeTaskProcessRows(logs).map((row) => (
      row.kind === 'control_event' ? null : [row.agent?.id, row.agent?.ordinal]
    ))).toEqual([
      ['child-b', 1],
      ['child-a', 2],
      ['child-c', null],
      ['child-b', 1],
    ])
  })

  it('exposes delegation status and detail usage without treating them as tool output', () => {
    const logs = [
      createTaskLog({
        id: 1,
        log_type: 'tool_call',
        metadata: {
          tool_use_id: 'tu-1',
          name: 'Subagent',
          input: { role: 'reviewer', task: 'review auth' },
          subagent: { id: 'child-a', parent_id: 'root', role: 'reviewer' },
        },
      }),
      createTaskLog({
        id: 2,
        log_type: 'tool_call',
        metadata: {
          tool_use_id: 'tu-2',
          name: 'Subagent',
          input: { role: 'explore', task: 'locate auth entry' },
          output_payload_id: 12,
          output_char_count: 40,
          error: false,
          subagent: {
            id: 'child-b',
            parent_id: 'root',
            role: 'explore',
            status: 'completed',
            usage: { input_tokens: 1200, output_tokens: 300 },
          },
        },
      }),
    ]

    const rows = normalizeTaskProcessRows(logs)
    expect(rows).toHaveLength(2)
    expect(rows[0].kind === 'tool_call' && rows[0].subagent?.status).toBe('running')
    expect(rows[0].kind === 'tool_call' && rows[0].subagent?.inputTokens).toBeUndefined()
    const completed = rows[1]
    expect(completed.kind === 'tool_call' && completed.subagent).toEqual({
      id: 'child-b',
      parentId: 'root',
      role: 'explore',
      ordinal: null,
      status: 'completed',
      inputTokens: 1200,
      outputTokens: 300,
    })
  })

  it('keeps each direct child stream contiguous under its delegation row', () => {
    const agent = (id: string) => ({ id, parent_id: 'root', role: 'delegate' })
    const rows = normalizeTaskProcessRows([
      createTaskLog({
        id: 1,
        log_type: 'tool_call',
        metadata: { name: 'Subagent', input: { task: 'alpha' }, subagent: agent('alpha'), error: false },
      }),
      createTaskLog({
        id: 2,
        log_type: 'tool_call',
        metadata: { name: 'Subagent', input: { task: 'beta' }, subagent: agent('beta'), error: false },
      }),
      createTaskLog({
        id: 3,
        log_type: 'tool_call',
        metadata: { name: 'Bash', input: { command: 'beta' }, agent: agent('beta'), output: 'beta', error: false },
      }),
      createTaskLog({
        id: 4,
        log_type: 'assistant_text',
        metadata: { text: 'alpha result', agent: agent('alpha') },
      }),
      createTaskLog({
        id: 5,
        log_type: 'assistant_text',
        metadata: { text: 'beta result', agent: agent('beta') },
      }),
      createTaskLog({
        id: 6,
        log_type: 'assistant_text',
        metadata: { text: 'root continuation' },
      }),
    ])

    const blocks = groupTaskProcessRows(rows)

    expect(blocks.map((block) => block.kind)).toEqual(['subagent_group', 'subagent_group', 'row'])
    const alpha = blocks[0]
    const beta = blocks[1]
    expect(alpha.kind === 'subagent_group' && alpha.delegation?.event.id).toBe(1)
    expect(alpha.kind === 'subagent_group' && alpha.tone).toBe(0)
    expect(alpha.kind === 'subagent_group' && alpha.rows.map((row) => row.event.id)).toEqual([4])
    expect(beta.kind === 'subagent_group' && beta.delegation?.event.id).toBe(2)
    expect(beta.kind === 'subagent_group' && beta.tone).toBe(1)
    expect(beta.kind === 'subagent_group' && beta.rows.map((row) => row.event.id)).toEqual([3, 5])
    expect(blocks[2].kind === 'row' && blocks[2].row.event.id).toBe(6)
  })
})
