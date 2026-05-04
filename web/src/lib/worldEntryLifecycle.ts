import type {
  WorldEntryHandoffState,
  WorldEntryPendingState,
} from '@/components/novel-shell/NovelShellRouteState'
import type { UiMessageKey, UiMessageParams } from '@/lib/uiMessages'
import type { CopilotReviewKind } from '@/types/copilot'
import {
  hasWorldEntryReviewAttention,
  normalizeWorldEntryHandoff,
} from '@/lib/worldEntryReview'

export type WorldEntryTranslator = (key: UiMessageKey, params?: UiMessageParams) => string

export type WorldEntryLifecycleFeedback =
  | {
      phase: 'running'
      source: 'extract'
      summary: string
    }
  | {
      phase: 'failed'
      source: 'extract'
      summary: string
    }
  | {
      phase: 'needs_review'
      source: 'generate' | 'extract'
      summary: string
    }
  | {
      phase: 'success'
      source: 'generate' | 'extract'
      summary: string
    }
  | null

export type StudioWorldEntryStage = 'cold_start' | 'attention' | 'routine'
export type StudioWorldEntryProminence = 'prominent' | 'elevated' | 'compact'
export type StudioWorldEntryAttentionTone = 'running' | 'needs_review' | 'failed' | null
export type AtlasAssistStage = 'attention' | 'governance' | 'routine'
export type AtlasAssistGovernanceProminence = 'elevated' | 'default' | 'compact'
export type AtlasAssistAttentionTone = 'running' | 'needs_review' | 'failed' | null

function pickReviewKindFromCounts(
  entityCount: number | null,
  relationshipCount: number | null,
  systemCount: number | null,
  fallback: CopilotReviewKind,
): CopilotReviewKind {
  if ((entityCount ?? 0) > 0) return 'entities'
  if ((relationshipCount ?? 0) > 0) return 'relationships'
  if ((systemCount ?? 0) > 0) return 'systems'
  return fallback
}

export function resolveStudioWorldEntryStage({
  worldEntityCount,
  worldSystemCount,
  handoff,
  pending,
}: {
  worldEntityCount: number
  worldSystemCount: number
  handoff: WorldEntryHandoffState | null
  pending: WorldEntryPendingState | null
}): StudioWorldEntryStage {
  const hasWorldData = worldEntityCount + worldSystemCount > 0
  if (!hasWorldData) return 'cold_start'

  if (pending) return 'attention'

  if (
    hasWorldEntryReviewAttention(handoff)
    || handoff?.kind === 'extract_failed'
  ) {
    return 'attention'
  }

  return 'routine'
}

export function resolveStudioWorldEntryAttentionTone({
  handoff,
  pending,
}: {
  handoff: WorldEntryHandoffState | null
  pending: WorldEntryPendingState | null
}): StudioWorldEntryAttentionTone {
  if (pending) return 'running'
  if (handoff?.kind === 'extract_failed') return 'failed'
  if (hasWorldEntryReviewAttention(handoff)) return 'needs_review'
  return null
}

export function resolveStudioWorldEntryPresentation(params: {
  worldEntityCount: number
  worldSystemCount: number
  handoff: WorldEntryHandoffState | null
  pending: WorldEntryPendingState | null
}): {
  stage: StudioWorldEntryStage
  worldEntryProminence: StudioWorldEntryProminence
} {
  const stage = resolveStudioWorldEntryStage(params)

  if (stage === 'cold_start') {
    return {
      stage,
      worldEntryProminence: 'prominent',
    }
  }

  if (stage === 'attention') {
    return {
      stage,
      worldEntryProminence: 'elevated',
    }
  }

  return {
    stage,
    worldEntryProminence: 'compact',
  }
}

export function resolveAtlasAssistAttentionTone({
  tab,
  handoff,
  pending,
  totalDrafts,
  reviewBacklogCount = totalDrafts,
}: {
  tab: 'systems' | 'entities' | 'relationships' | 'review'
  handoff: WorldEntryHandoffState | null
  pending: WorldEntryPendingState | null
  totalDrafts: number
  reviewBacklogCount?: number | null
}): AtlasAssistAttentionTone {
  if (pending) return 'running'
  if (handoff?.kind === 'extract_failed') return 'failed'
  if (hasWorldEntryReviewAttention(handoff, { reviewBacklogCount })) return 'needs_review'
  if (totalDrafts > 0 && tab !== 'review') return 'needs_review'
  return null
}

export function resolveAtlasAssistPresentation(params: {
  tab: 'systems' | 'entities' | 'relationships' | 'review'
  handoff: WorldEntryHandoffState | null
  pending: WorldEntryPendingState | null
  totalDrafts: number
  reviewBacklogCount?: number | null
}): {
  stage: AtlasAssistStage
  governanceProminence: AtlasAssistGovernanceProminence
  governanceFirst: boolean
} {
  const attentionTone = resolveAtlasAssistAttentionTone(params)

  if (attentionTone) {
    return {
      stage: 'attention',
      governanceProminence: 'elevated',
      governanceFirst: true,
    }
  }

  if (params.tab === 'review') {
    return {
      stage: 'governance',
      governanceProminence: 'default',
      governanceFirst: true,
    }
  }

  return {
    stage: 'routine',
    governanceProminence: 'compact',
    governanceFirst: false,
  }
}

export function buildWorldEntryLifecycleFeedback(
  handoff: WorldEntryHandoffState | null,
  t: WorldEntryTranslator,
  options?: {
    reviewBacklogCount?: number | null
  },
): WorldEntryLifecycleFeedback {
  const normalizedHandoff = normalizeWorldEntryHandoff(handoff, options)
  if (!normalizedHandoff) return null

  if (normalizedHandoff.kind === 'extract_failed') {
    return {
      phase: 'failed',
      source: 'extract',
      summary: t('worldModel.bootstrap.failed'),
    }
  }

  if (normalizedHandoff.kind === 'extract_review' || normalizedHandoff.kind === 'extract_success') {
    return {
      phase: normalizedHandoff.kind === 'extract_review' ? 'needs_review' : 'success',
      source: 'extract',
      summary: t('worldModel.bootstrap.summaryCounts', {
        entities: normalizedHandoff.entityCount ?? 0,
        relationships: normalizedHandoff.relationshipCount ?? 0,
      }),
    }
  }

  return {
    phase: normalizedHandoff.kind === 'generate_review' ? 'needs_review' : 'success',
    source: 'generate',
    summary: t('worldEntry.summary.generated', {
      entityCount: normalizedHandoff.entityCount ?? 0,
      relationshipCount: normalizedHandoff.relationshipCount ?? 0,
      systemCount: normalizedHandoff.systemCount ?? 0,
    }),
  }
}

export function resolveWorldEntryReviewKind(
  handoff: WorldEntryHandoffState | null,
  fallback: CopilotReviewKind = 'entities',
): CopilotReviewKind {
  if (!handoff) return fallback

  if (handoff.kind === 'extract_review' || handoff.kind === 'extract_success') {
    return pickReviewKindFromCounts(
      handoff.entityCount,
      handoff.relationshipCount,
      null,
      fallback,
    )
  }

  if (handoff.kind === 'generate_review' || handoff.kind === 'generate_success') {
    return pickReviewKindFromCounts(
      handoff.entityCount,
      handoff.relationshipCount,
      handoff.systemCount,
      fallback,
    )
  }

  return fallback
}
