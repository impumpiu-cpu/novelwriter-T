import { describe, it, expect, beforeEach, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import {
  dismissWorldOnboarding,
  isWorldOnboardingDismissed,
  useWorldOnboardingDismissed,
  worldOnboardingDismissKey,
} from '@/lib/worldOnboardingStorage'

describe('worldOnboardingStorage', () => {
  const novelId = 1
  const createdAt = '2026-03-04T00:00:00Z'

  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('uses a createdAt-scoped key when available', () => {
    expect(worldOnboardingDismissKey(novelId, createdAt)).toBe(
      'novwr_world_onboarding_dismissed_1_2026-03-04T00:00:00Z',
    )
  })

  it('does nothing when createdAt is missing', () => {
    dismissWorldOnboarding(novelId, null)
    expect(localStorage.length).toBe(0)
  })

  it('returns false when localStorage.getItem throws (SecurityError)', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })

    expect(isWorldOnboardingDismissed(novelId, createdAt)).toBe(false)
  })

  it('notifies same-tab subscribers immediately after dismissal changes', async () => {
    const { result } = renderHook(() => useWorldOnboardingDismissed(novelId, createdAt))

    expect(result.current).toBe(false)

    act(() => {
      dismissWorldOnboarding(novelId, createdAt)
    })

    await waitFor(() => {
      expect(result.current).toBe(true)
    })
  })
})
