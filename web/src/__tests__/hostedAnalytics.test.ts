import { beforeEach, describe, expect, it, vi } from 'vitest'

const { recordAnalyticsEventMock } = vi.hoisted(() => ({
  recordAnalyticsEventMock: vi.fn().mockResolvedValue({ ok: true }),
}))

vi.mock('@/services/api', () => ({
  api: {
    recordAnalyticsEvent: recordAnalyticsEventMock,
  },
}))

import {
  buildInviteAnalyticsPayload,
  captureHostedAttributionFromLocation,
  trackHostedAnalyticsEvent,
} from '@/lib/hostedAnalytics'

describe('hostedAnalytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubEnv('VITE_DEPLOY_MODE', 'hosted')
    localStorage.clear()
    window.history.replaceState({}, '', '/?channel=longkong&invite_batch=batch-a&utm_medium=dm')
  })

  it('captures and persists hosted attribution context', () => {
    const first = captureHostedAttributionFromLocation()
    expect(first).not.toBeNull()
    expect(first?.channel).toBe('longkong')
    expect(first?.invite_batch).toBe('batch-a')
    expect(first?.entry_path).toBe('/')
    expect(first?.anonymous_id).toBeTruthy()

    window.history.replaceState({}, '', '/login')
    const second = captureHostedAttributionFromLocation()
    expect(second?.anonymous_id).toBe(first?.anonymous_id)
    expect(second?.entry_path).toBe('/')
    expect(second?.channel).toBe('longkong')
  })

  it('builds invite analytics payload and records public events', async () => {
    captureHostedAttributionFromLocation()
    const payload = buildInviteAnalyticsPayload()

    expect(payload.anonymous_id).toBeTruthy()
    expect(payload.attribution).toMatchObject({
      channel: 'longkong',
      invite_batch: 'batch-a',
      entry_path: '/',
    })

    await expect(trackHostedAnalyticsEvent('invite_gate_view', { meta: { method: 'invite' } })).resolves.toBe(true)
    expect(recordAnalyticsEventMock).toHaveBeenCalledWith(expect.objectContaining({
      event: 'invite_gate_view',
      anonymous_id: payload.anonymous_id,
      meta: expect.objectContaining({
        channel: 'longkong',
        invite_batch: 'batch-a',
        entry_path: '/',
        page_path: '/',
        method: 'invite',
      }),
    }))
  })
})
