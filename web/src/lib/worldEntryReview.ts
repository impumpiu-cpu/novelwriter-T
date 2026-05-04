import type { WorldEntryHandoffState } from '@/components/novel-shell/NovelShellRouteState'

function isReviewKind(kind: WorldEntryHandoffState['kind']) {
  return kind === 'extract_review' || kind === 'generate_review'
}

function toSuccessKind(kind: WorldEntryHandoffState['kind']) {
  if (kind === 'extract_review') return 'extract_success' as const
  if (kind === 'generate_review') return 'generate_success' as const
  return kind
}

function countReviewableRows(handoff: WorldEntryHandoffState) {
  return (handoff.entityCount ?? 0) + (handoff.relationshipCount ?? 0) + (handoff.systemCount ?? 0)
}

export function normalizeWorldEntryHandoff(
  handoff: WorldEntryHandoffState | null,
  options?: {
    reviewBacklogCount?: number | null
  },
): WorldEntryHandoffState | null {
  if (!handoff || !isReviewKind(handoff.kind)) return handoff

  if (countReviewableRows(handoff) === 0 || options?.reviewBacklogCount === 0) {
    return {
      ...handoff,
      kind: toSuccessKind(handoff.kind),
    }
  }

  return handoff
}

export function hasWorldEntryReviewAttention(
  handoff: WorldEntryHandoffState | null,
  options?: {
    reviewBacklogCount?: number | null
  },
) {
  const normalizedHandoff = normalizeWorldEntryHandoff(handoff, options)
  return normalizedHandoff?.kind === 'extract_review' || normalizedHandoff?.kind === 'generate_review'
}
