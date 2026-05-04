import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LABELS } from '@/constants/labels'
import { useStudioWorldOnboardingFlow } from '@/hooks/novel/useStudioWorldOnboardingFlow'
import type { BootstrapJobResponse, Novel } from '@/types/api'

const {
  mockTrackHostedAnalyticsEvent,
  mockGetLlmApiErrorMessage,
  MockApiError,
} = vi.hoisted(() => {
  class HoistedMockApiError extends Error {
    status?: number
    code?: string

    constructor(status?: number, code?: string) {
      super('api error')
      this.status = status
      this.code = code
    }
  }

  return {
    mockTrackHostedAnalyticsEvent: vi.fn(),
    mockGetLlmApiErrorMessage: vi.fn(),
    MockApiError: HoistedMockApiError,
  }
})

vi.mock('@/lib/hostedAnalytics', () => ({
  trackHostedAnalyticsEvent: (...args: unknown[]) => mockTrackHostedAnalyticsEvent(...args),
}))

vi.mock('@/lib/llmErrorMessages', () => ({
  getLlmApiErrorMessage: (...args: unknown[]) => mockGetLlmApiErrorMessage(...args),
}))

vi.mock('@/services/api', () => ({
  ApiError: MockApiError,
}))

function buildBootstrapJob(partial?: Partial<BootstrapJobResponse>): BootstrapJobResponse {
  return {
    job_id: 11,
    novel_id: 7,
    mode: 'initial',
    initialized: false,
    status: 'pending',
    progress: {
      step: 0,
      detail: 'queued',
    },
    result: {
      entities_found: 0,
      relationships_found: 0,
      index_refresh_only: false,
    },
    error: null,
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-01T00:00:00Z',
    ...partial,
  }
}

function buildWindowIndex(overrides?: Partial<NonNullable<Novel['window_index']>>): NonNullable<Novel['window_index']> {
  return {
    status: 'fresh',
    revision: 1,
    built_revision: 1,
    error: null,
    readiness: 'ready',
    capabilities: {
      chapters_available: true,
      whole_book_index_available: true,
      bootstrap_available: true,
      recent_fallback_only: false,
    },
    ingest: null,
    job: null,
    ...overrides,
  }
}

function buildArgs(overrides?: Partial<Parameters<typeof useStudioWorldOnboardingFlow>[0]>) {
  return {
    novelId: 7,
    novelCreatedAt: '2026-03-01T00:00:00Z',
    novelWindowIndex: buildWindowIndex(),
    locale: 'zh' as const,
    worldEntityCount: 0,
    worldSystemCount: 0,
    worldLoading: false,
    bootstrapLoading: false,
    bootstrapJob: null,
    triggerInitialBootstrap: vi.fn(),
    dismissWorldOnboardingRoute: vi.fn(),
    ...overrides,
  }
}

describe('useStudioWorldOnboardingFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    mockTrackHostedAnalyticsEvent.mockResolvedValue(undefined)
    mockGetLlmApiErrorMessage.mockReturnValue(null)
  })

  it('shows onboarding and tracks the first visible view', async () => {
    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs()))

    expect(result.current.showWorldOnboarding).toBe(true)
    expect(result.current.worldEmpty).toBe(true)
    expect(result.current.chaptersAvailable).toBe(true)

    await waitFor(() => {
      expect(mockTrackHostedAnalyticsEvent).toHaveBeenCalledWith('world_onboarding_view', {
        novelId: 7,
        meta: { surface: 'studio' },
      })
    })
  })

  it('maps bootstrap trigger errors into onboarding error copy and analytics', () => {
    const triggerInitialBootstrap = vi.fn((handlers?: { onError?: (error: unknown) => void }) => {
      handlers?.onError?.(new MockApiError(400, 'bootstrap_no_text'))
    })

    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs({
      triggerInitialBootstrap,
      bootstrapJob: buildBootstrapJob({ status: 'failed', error: null }),
    })))

    act(() => {
      result.current.handleTriggerBootstrap()
    })

    expect(triggerInitialBootstrap).toHaveBeenCalledTimes(1)
    expect(result.current.bootstrapError).toBe(LABELS.BOOTSTRAP_NO_TEXT)
    expect(mockTrackHostedAnalyticsEvent).toHaveBeenCalledWith('bootstrap_trigger', {
      novelId: 7,
      meta: {
        mode: 'initial',
        source_surface: 'world_onboarding',
      },
    })
    expect(mockTrackHostedAnalyticsEvent).toHaveBeenCalledWith('bootstrap_failed', {
      novelId: 7,
      meta: {
        mode: 'initial',
        source_surface: 'world_onboarding',
        status: 400,
        error_code: 'bootstrap_no_text',
      },
    })
  })

  it('dismisses onboarding via created-at-scoped storage and route callback', () => {
    const dismissWorldOnboardingRoute = vi.fn()

    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs({
      dismissWorldOnboardingRoute,
    })))

    act(() => {
      result.current.handleDismissWorldOnboarding()
    })

    expect(localStorage.getItem('novwr_world_onboarding_dismissed_7_2026-03-01T00:00:00Z')).toBe('1')
    expect(dismissWorldOnboardingRoute).toHaveBeenCalledTimes(1)
    expect(mockTrackHostedAnalyticsEvent).toHaveBeenCalledWith('world_onboarding_dismissed', {
      novelId: 7,
      meta: { surface: 'studio' },
    })
  })

  it('flips showWorldOnboarding to false on the same render after dismiss', () => {
    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs()))

    expect(result.current.showWorldOnboarding).toBe(true)

    act(() => {
      result.current.handleDismissWorldOnboarding()
    })

    expect(result.current.showWorldOnboarding).toBe(false)
    expect(result.current.worldOnboardingDismissed).toBe(true)
  })

  it('recomputes dismissal synchronously when switching to another novel in the same shell', () => {
    localStorage.setItem('novwr_world_onboarding_dismissed_7_2026-03-01T00:00:00Z', '1')

    const { result, rerender } = renderHook((args) => useStudioWorldOnboardingFlow(args), {
      initialProps: buildArgs(),
    })

    expect(result.current.worldOnboardingDismissed).toBe(true)
    expect(result.current.showWorldOnboarding).toBe(false)

    rerender(buildArgs({
      novelId: 8,
      novelCreatedAt: '2026-03-02T00:00:00Z',
      bootstrapJob: null,
    }))

    expect(result.current.worldOnboardingDismissed).toBe(false)
    expect(result.current.showWorldOnboarding).toBe(true)
  })

  it('keeps onboarding hidden while the bootstrap status query is still loading', () => {
    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs({
      bootstrapLoading: true,
    })))

    expect(result.current.showWorldOnboarding).toBe(false)
  })

  it('hides onboarding when the current Studio entry suppresses it', () => {
    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs({
      suppressWorldOnboarding: true,
    })))

    expect(result.current.showWorldOnboarding).toBe(false)
  })

  it('hides onboarding when the novel has already been bootstrap-initialized', () => {
    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs({
      bootstrapJob: buildBootstrapJob({ status: 'completed', initialized: true }),
    })))

    expect(result.current.showWorldOnboarding).toBe(false)
  })

  it('hides onboarding when a bootstrap job is currently running', () => {
    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs({
      bootstrapJob: buildBootstrapJob({ status: 'extracting' }),
    })))

    expect(result.current.showWorldOnboarding).toBe(false)
  })

  it('short-circuits extract trigger with bootstrap_no_text error when chapters are not yet available', () => {
    const triggerInitialBootstrap = vi.fn()

    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs({
      triggerInitialBootstrap,
      novelWindowIndex: buildWindowIndex({
        capabilities: {
          chapters_available: false,
          whole_book_index_available: false,
          bootstrap_available: false,
          recent_fallback_only: false,
        },
      }),
    })))

    expect(result.current.chaptersAvailable).toBe(false)

    act(() => {
      result.current.handleTriggerBootstrap()
    })

    expect(triggerInitialBootstrap).not.toHaveBeenCalled()
    expect(result.current.bootstrapError).toBe(LABELS.BOOTSTRAP_NO_TEXT)
    expect(mockTrackHostedAnalyticsEvent).not.toHaveBeenCalledWith('bootstrap_trigger', expect.anything())
  })

  it('short-circuits extract trigger when a bootstrap job is still running', () => {
    const triggerInitialBootstrap = vi.fn()

    const { result } = renderHook(() => useStudioWorldOnboardingFlow(buildArgs({
      triggerInitialBootstrap,
      bootstrapJob: buildBootstrapJob({ status: 'extracting' }),
    })))

    act(() => {
      result.current.handleTriggerBootstrap()
    })

    expect(triggerInitialBootstrap).not.toHaveBeenCalled()
    expect(result.current.bootstrapError).toBe(LABELS.BOOTSTRAP_SCANNING)
    expect(mockTrackHostedAnalyticsEvent).not.toHaveBeenCalledWith('bootstrap_trigger', expect.anything())
  })
})
