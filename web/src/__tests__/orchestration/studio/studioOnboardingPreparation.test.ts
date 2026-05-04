import { describe, expect, it, vi } from 'vitest'
import { resolveStudioPreparationGate } from '@/hooks/novel/studioOnboardingPreparation'
import type { BootstrapJobResponse, Novel } from '@/types/api'

function buildNovel(partial?: Partial<Novel>): Novel {
  return {
    id: 7,
    title: '测试小说',
    author: '作者',
    language: 'zh',
    total_chapters: 3,
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-01T00:00:00Z',
    ...partial,
  }
}

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

function t(key: string) {
  return key
}

describe('studioOnboardingPreparation', () => {
  it('returns the ingest preparation gate before chapters are available', () => {
    const gate = resolveStudioPreparationGate({
      t,
      novelWindowIndex: buildNovel({
        window_index: {
          status: 'missing',
          revision: 0,
          built_revision: null,
          error: null,
          readiness: 'accepting',
          capabilities: {
            chapters_available: false,
            whole_book_index_available: false,
            bootstrap_available: false,
            recent_fallback_only: false,
          },
          ingest: {
            status: 'queued',
            stage: 'accepted',
            size_tier: 'large',
            source_bytes: 1024,
            source_chars: null,
            chapter_count: null,
            requested_language: 'zh',
            resolved_language: null,
            auto_index_plan: null,
            bootstrap_plan: null,
            readiness_mode: null,
            error: null,
          },
          job: null,
        },
      }).window_index,
      worldLoading: false,
      worldOnboardingDismissed: false,
      worldEmpty: true,
      bootstrapTriggerPending: false,
      bootstrapJob: null,
      bootstrapError: null,
      onRetryBootstrap: vi.fn(),
      onDeferBootstrap: vi.fn(),
    })

    expect(gate).toMatchObject({
      title: 'studio.preparation.title',
      description: 'studio.preparation.uploadDescription',
      detail: 'studio.preparation.stage.accepted',
      error: null,
    })
  })

  it('returns the failed bootstrap gate with retry and defer actions', () => {
    const onRetryBootstrap = vi.fn()
    const onDeferBootstrap = vi.fn()

    const gate = resolveStudioPreparationGate({
      t,
      novelWindowIndex: null,
      worldLoading: false,
      worldOnboardingDismissed: false,
      worldEmpty: true,
      bootstrapTriggerPending: false,
      bootstrapJob: buildBootstrapJob({ status: 'failed', error: 'bootstrap crashed' }),
      bootstrapError: 'mapped failure',
      onRetryBootstrap,
      onDeferBootstrap,
    })

    expect(gate).not.toBeNull()
    expect(gate).toMatchObject({
      title: 'studio.preparation.failedTitle',
      description: 'studio.preparation.failedDescription',
      error: 'mapped failure',
      primaryActionLabel: 'studio.preparation.retry',
      secondaryActionLabel: 'studio.preparation.defer',
    })

    gate?.onPrimaryAction?.()
    gate?.onSecondaryAction?.()

    expect(onRetryBootstrap).toHaveBeenCalledTimes(1)
    expect(onDeferBootstrap).toHaveBeenCalledTimes(1)
  })

  it('surfaces retry/defer actions on the preparation gate after initial extraction fails', () => {
    const gate = resolveStudioPreparationGate({
      t,
      novelWindowIndex: buildNovel({
        window_index: {
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
          ingest: {
            status: 'completed',
            stage: 'completed',
            size_tier: 'small',
            source_bytes: 128,
            source_chars: 64,
            chapter_count: 2,
            requested_language: 'zh',
            resolved_language: 'zh',
            auto_index_plan: 'immediate',
            bootstrap_plan: 'immediate',
            readiness_mode: 'full_target',
            error: null,
          },
          job: null,
        },
      }).window_index,
      worldLoading: false,
      worldOnboardingDismissed: false,
      worldEmpty: true,
      bootstrapTriggerPending: false,
      bootstrapJob: buildBootstrapJob({
        status: 'failed',
        mode: 'initial',
        initialized: false,
        error: 'boom',
      }),
      bootstrapError: 'boom',
      onRetryBootstrap: vi.fn(),
      onDeferBootstrap: vi.fn(),
    })

    expect(gate).toMatchObject({
      title: 'studio.preparation.failedTitle',
      description: 'studio.preparation.failedDescription',
      error: 'boom',
      primaryActionLabel: 'studio.preparation.retry',
      secondaryActionLabel: 'studio.preparation.defer',
    })
  })

  it('keeps the preparation gate up while deferred auto-bootstrap is waiting on whole-book index', () => {
    const gate = resolveStudioPreparationGate({
      t,
      novelWindowIndex: buildNovel({
        window_index: {
          status: 'missing',
          revision: 2,
          built_revision: null,
          error: null,
          readiness: 'processing',
          capabilities: {
            chapters_available: true,
            whole_book_index_available: false,
            bootstrap_available: false,
            recent_fallback_only: true,
          },
          ingest: {
            status: 'completed',
            stage: 'completed',
            size_tier: 'large',
            source_bytes: 1024,
            source_chars: 2048,
            chapter_count: 2,
            requested_language: 'zh',
            resolved_language: 'zh',
            auto_index_plan: 'deferred',
            bootstrap_plan: 'defer_until_index',
            readiness_mode: 'degraded_target',
            error: null,
          },
          job: {
            status: 'running',
            target_revision: 2,
            completed_revision: null,
            error: null,
            created_at: null,
            started_at: null,
            finished_at: null,
            metrics: null,
          },
        },
      }).window_index,
      worldLoading: false,
      worldOnboardingDismissed: false,
      worldEmpty: true,
      bootstrapTriggerPending: false,
      bootstrapJob: null,
      bootstrapError: null,
      onRetryBootstrap: vi.fn(),
      onDeferBootstrap: vi.fn(),
    })

    expect(gate).toMatchObject({
      title: 'studio.preparation.title',
      description: 'studio.preparation.bootstrapDescription',
      detail: 'worldModel.windowIndex.bootstrap.organizingChapters',
      error: null,
    })
  })

  it('keeps the preparation gate up after initial bootstrap completes until world queries refresh', () => {
    const gate = resolveStudioPreparationGate({
      t,
      novelWindowIndex: buildNovel({
        window_index: {
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
          ingest: {
            status: 'completed',
            stage: 'completed',
            size_tier: 'large',
            source_bytes: 1024,
            source_chars: 2048,
            chapter_count: 2,
            requested_language: 'zh',
            resolved_language: 'zh',
            auto_index_plan: 'deferred',
            bootstrap_plan: 'defer_until_index',
            readiness_mode: 'degraded_target',
            error: null,
          },
          job: null,
        },
      }).window_index,
      worldLoading: false,
      worldOnboardingDismissed: false,
      worldEmpty: true,
      bootstrapTriggerPending: false,
      bootstrapJob: buildBootstrapJob({
        status: 'completed',
        result: {
          entities_found: 28,
          relationships_found: 22,
          index_refresh_only: false,
        },
      }),
      bootstrapError: null,
      onRetryBootstrap: vi.fn(),
      onDeferBootstrap: vi.fn(),
    })

    expect(gate).toMatchObject({
      title: 'studio.preparation.title',
      description: 'studio.preparation.bootstrapDescription',
      detail: 'worldModel.common.processing',
      error: null,
    })
  })

  it('drops the preparation gate after initial bootstrap completes with no extracted world data', () => {
    const gate = resolveStudioPreparationGate({
      t,
      novelWindowIndex: buildNovel({
        window_index: {
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
          ingest: {
            status: 'completed',
            stage: 'completed',
            size_tier: 'large',
            source_bytes: 1024,
            source_chars: 2048,
            chapter_count: 2,
            requested_language: 'zh',
            resolved_language: 'zh',
            auto_index_plan: 'deferred',
            bootstrap_plan: 'defer_until_index',
            readiness_mode: 'degraded_target',
            error: null,
          },
          job: null,
        },
      }).window_index,
      worldLoading: false,
      worldOnboardingDismissed: false,
      worldEmpty: true,
      bootstrapTriggerPending: false,
      bootstrapJob: buildBootstrapJob({
        status: 'completed',
        initialized: true,
        result: {
          entities_found: 0,
          relationships_found: 0,
          index_refresh_only: false,
        },
      }),
      bootstrapError: null,
      onRetryBootstrap: vi.fn(),
      onDeferBootstrap: vi.fn(),
    })

    expect(gate).toBeNull()
  })
})
