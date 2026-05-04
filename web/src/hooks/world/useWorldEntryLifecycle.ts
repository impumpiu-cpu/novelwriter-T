import { useCallback, useMemo, useState } from 'react'
import type { BootstrapLifecycleState } from '@/components/world-model/shared/BootstrapPanel'
import type {
  WorldEntryHandoffState,
  WorldEntryPendingState,
} from '@/components/novel-shell/NovelShellRouteState'
import {
  buildWorldEntryLifecycleFeedback,
  type WorldEntryLifecycleFeedback,
  type WorldEntryTranslator,
} from '@/lib/worldEntryLifecycle'
import { isWorldEntryPendingExpired } from '@/lib/worldEntryHandoff'
import type {
  BootstrapJobResponse,
  WorldGenerateResponse,
  WorldpackImportResponse,
} from '@/types/api'

export function useWorldEntryLifecycle({
  handoff,
  pending,
  reviewBacklogCount,
  onHandoffChange,
  onPendingHandoffChange,
  t,
}: {
  handoff: WorldEntryHandoffState | null
  pending?: WorldEntryPendingState | null
  reviewBacklogCount?: number | null
  onHandoffChange: (handoff: WorldEntryHandoffState | null) => void
  onPendingHandoffChange?: (pending: WorldEntryPendingState | null) => void
  t: WorldEntryTranslator
}) {
  const [runtimeFeedback, setRuntimeFeedback] = useState<WorldEntryLifecycleFeedback>(null)

  const handleBootstrapLifecycleChange = useCallback((state: BootstrapLifecycleState) => {
    if (state.phase === 'idle') {
      setRuntimeFeedback((current) => current?.phase === 'running' ? null : current)
      return
    }

    if (state.phase === 'running') {
      setRuntimeFeedback({
        phase: 'running',
        source: 'extract',
        summary: state.detail,
      })
      return
    }

    setRuntimeFeedback(null)

    if (state.phase === 'failed') {
      onHandoffChange({
        kind: 'extract_failed',
        entityCount: null,
        relationshipCount: null,
        systemCount: null,
      })
      return
    }

    onHandoffChange({
      kind: state.requiresReview ? 'extract_review' : 'extract_success',
      entityCount: state.entityCount,
      relationshipCount: state.relationshipCount,
      systemCount: null,
    })
  }, [onHandoffChange])

  const handleGenerateSuccess = useCallback((response: WorldGenerateResponse) => {
    const totalCreated = response.entities_created + response.relationships_created + response.systems_created
    onHandoffChange({
      kind: totalCreated > 0 ? 'generate_review' : 'generate_success',
      entityCount: response.entities_created,
      relationshipCount: response.relationships_created,
      systemCount: response.systems_created,
    })
  }, [onHandoffChange])

  const handleImportSuccess = useCallback((response: WorldpackImportResponse) => {
    onHandoffChange({
      kind: 'generate_success',
      entityCount: response.counts.entities_created,
      relationshipCount: response.counts.relationships_created,
      systemCount: response.counts.systems_created,
    })
  }, [onHandoffChange])

  const handleBootstrapTriggerStart = useCallback((startedAtMs: number) => {
    onPendingHandoffChange?.({
      kind: 'extract',
      startedAtMs,
      jobId: null,
    })
  }, [onPendingHandoffChange])

  const handleBootstrapAccepted = useCallback((job: BootstrapJobResponse, startedAtMs: number) => {
    onPendingHandoffChange?.({
      kind: 'extract',
      startedAtMs,
      jobId: job.job_id,
    })
  }, [onPendingHandoffChange])

  const handleBootstrapTriggerError = useCallback(() => {
    onPendingHandoffChange?.(null)
  }, [onPendingHandoffChange])

  const feedback = useMemo(() => {
    if (runtimeFeedback?.phase === 'running') return runtimeFeedback
    if (pending && !isWorldEntryPendingExpired(pending)) {
      return {
        phase: 'running' as const,
        source: 'extract' as const,
        summary: t('worldModel.common.processing'),
      }
    }
    return buildWorldEntryLifecycleFeedback(handoff, t, { reviewBacklogCount })
  }, [handoff, pending, reviewBacklogCount, runtimeFeedback, t])

  return {
    feedback,
    handleBootstrapAccepted,
    handleBootstrapLifecycleChange,
    handleBootstrapTriggerError,
    handleBootstrapTriggerStart,
    handleGenerateSuccess,
    handleImportSuccess,
  }
}
