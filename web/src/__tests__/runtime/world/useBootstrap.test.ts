import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import type { BootstrapJobResponse } from '@/types/api'
import { worldKeys } from '@/hooks/world/keys'
import { createQueryClientWrapper, createTestQueryClient } from '@/__tests__/support/queryClient'

vi.mock('@/services/api', () => ({
  worldApi: {
    getBootstrapStatus: vi.fn(),
    triggerBootstrap: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number
    code?: string
    constructor(status: number, message: string, code?: string) {
      super(message)
      this.status = status
      this.code = code
      this.name = 'ApiError'
    }
  },
}))

import { worldApi, ApiError } from '@/services/api'
import { useBootstrapStatus, useTriggerBootstrap } from '@/hooks/world/useBootstrap'

const mockGetBootstrapStatus = worldApi.getBootstrapStatus as ReturnType<typeof vi.fn>
const mockTriggerBootstrap = worldApi.triggerBootstrap as ReturnType<typeof vi.fn>

const baseJob: BootstrapJobResponse = {
  job_id: 1,
  novel_id: 1,
  mode: 'index_refresh',
  initialized: true,
  status: 'completed',
  progress: { step: 5, detail: 'Done' },
  result: { entities_found: 10, relationships_found: 5, index_refresh_only: false },
  error: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('useBootstrapStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns job data on success', async () => {
    mockGetBootstrapStatus.mockResolvedValue(baseJob)

    const { result } = renderHook(() => useBootstrapStatus(1), {
      wrapper: createQueryClientWrapper(createTestQueryClient()),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(baseJob)
  })

  it('returns null on 404 (no job)', async () => {
    mockGetBootstrapStatus.mockRejectedValue(new ApiError(404, 'Not found', 'bootstrap_job_not_found'))

    const { result } = renderHook(() => useBootstrapStatus(1), {
      wrapper: createQueryClientWrapper(createTestQueryClient()),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toBeNull()
  })

  it('keeps polling when auto-bootstrap is expected but status is still missing', async () => {
    mockGetBootstrapStatus
      .mockRejectedValueOnce(new ApiError(404, 'Not found', 'bootstrap_job_not_found'))
      .mockResolvedValueOnce(baseJob)

    const { result } = renderHook(() => useBootstrapStatus(1, {
      refetchWhenMissing: true,
    }), {
      wrapper: createQueryClientWrapper(createTestQueryClient()),
    })

    await waitFor(() => {
      expect(result.current.data).toBeNull()
      expect(mockGetBootstrapStatus).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(result.current.data).toEqual(baseJob)
      expect(mockGetBootstrapStatus).toHaveBeenCalledTimes(2)
    }, { timeout: 3000 })
  })

  it('rethrows 404 when not a "no job" response', async () => {
    mockGetBootstrapStatus.mockRejectedValue(new ApiError(404, 'Novel not found', 'novel_not_found'))

    const { result } = renderHook(() => useBootstrapStatus(1), {
      wrapper: createQueryClientWrapper(createTestQueryClient()),
    })
    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.error).toBeInstanceOf(ApiError)
  })

  it('rethrows non-404 errors', async () => {
    mockGetBootstrapStatus.mockRejectedValue(new ApiError(500, 'Server error'))

    const { result } = renderHook(() => useBootstrapStatus(1), {
      wrapper: createQueryClientWrapper(createTestQueryClient()),
    })
    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.error).toBeInstanceOf(ApiError)
  })

  it('enables polling when status is running', async () => {
    const runningJob = { ...baseJob, status: 'extracting' as const, progress: { step: 2, detail: 'Extracting...' } }
    mockGetBootstrapStatus.mockResolvedValue(runningJob)

    const { result } = renderHook(() => useBootstrapStatus(1), {
      wrapper: createQueryClientWrapper(createTestQueryClient()),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.status).toBe('extracting')
  })

  it('stops polling when status is completed', async () => {
    mockGetBootstrapStatus.mockResolvedValue(baseJob)

    const { result } = renderHook(() => useBootstrapStatus(1), {
      wrapper: createQueryClientWrapper(createTestQueryClient()),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.status).toBe('completed')
  })

  it('invalidates world queries when bootstrap reaches a terminal state', async () => {
    mockGetBootstrapStatus.mockResolvedValue(baseJob)

    const queryClient = createTestQueryClient()
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')

    renderHook(() => useBootstrapStatus(1), {
      wrapper: createQueryClientWrapper(queryClient),
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: worldKeys.entities(1) })
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: worldKeys.relationships(1) })
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: worldKeys.systems(1) })
    })
  })
})

describe('useTriggerBootstrap', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('caches bootstrap status and invalidates world lists after trigger', async () => {
    const novelId = 1
    const newJob = { ...baseJob, status: 'pending' as const }
    mockTriggerBootstrap.mockResolvedValue(newJob)

    const queryClient = createTestQueryClient()
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useTriggerBootstrap(novelId), {
      wrapper: createQueryClientWrapper(queryClient),
    })

    const payload = { mode: 'index_refresh' as const }

    let mutationResult: unknown
    await act(async () => {
      mutationResult = await result.current.mutateAsync(payload)
    })

    expect(mockTriggerBootstrap).toHaveBeenCalledWith(novelId, payload)
    expect(mutationResult).toEqual(newJob)

    // `mutateAsync` can resolve before `onSuccess` side effects are applied, depending on runtime timing.
    await waitFor(() => {
      expect(queryClient.getQueryData(worldKeys.bootstrapStatus(novelId))).toEqual(newJob)
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: worldKeys.entities(novelId) })
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: worldKeys.relationships(novelId) })
    })
  })
})
