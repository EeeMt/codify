import { describe, expect, it, vi } from 'vitest'
import { extractSlotErrorMessage } from './slotError'

describe('extractSlotErrorMessage', () => {
  it('localizes a missing Worker Profile runtime verification', () => {
    const t = vi.fn((key: string) => key)
    const error = {
      response: {
        data: {
          detail: { code: 'worker_profile_runtime_not_verified' },
        },
      },
    }

    expect(extractSlotErrorMessage(error, t as any, 'createTask.failedToCreateTask')).toBe(
      'createTask.workerProfileRuntimeNotVerified',
    )
  })
})
