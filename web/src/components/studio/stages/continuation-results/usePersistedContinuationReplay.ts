import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { novelKeys } from '@/hooks/novel/keys'
import { api } from '@/services/api'
import { readGenerationResultsDebug, readGenerationResultsWarnings } from '@/lib/generationResultsDebugStorage'
import type { ContinueDebugSummary, Continuation, PostcheckWarning } from '@/types/api'
import { parsePersistedContinuationIds } from './helpers'

interface UsePersistedContinuationReplayArgs {
  isReloadMode: boolean
  novelId: number
  persisted: string | null
}

interface UsePersistedContinuationReplayResult {
  persistedVersions: Continuation[] | null
  persistedDebug: ContinueDebugSummary | null
  persistedError: string | null
  reloadedWarnings: PostcheckWarning[]
  retryReload: () => void
}

export function usePersistedContinuationReplay({
  isReloadMode,
  novelId,
  persisted,
}: UsePersistedContinuationReplayArgs): UsePersistedContinuationReplayResult {
  const persistedDebug = useMemo<ContinueDebugSummary | null>(() => {
    if (!isReloadMode || !persisted) return null
    return readGenerationResultsDebug(persisted)
  }, [isReloadMode, persisted])

  const reloadedWarnings = useMemo<PostcheckWarning[]>(() => {
    if (!isReloadMode || !persisted) return []
    return readGenerationResultsWarnings(persisted)
  }, [isReloadMode, persisted])

  const continuationIds = useMemo<number[]>(() => {
    if (!isReloadMode || !persisted) return []
    return parsePersistedContinuationIds(persisted)
  }, [isReloadMode, persisted])

  const idsKey = continuationIds.join(',')
  const hasInvalidLink = isReloadMode && !!persisted && continuationIds.length === 0

  const {
    data: persistedVersions,
    error,
    refetch,
  } = useQuery({
    queryKey: novelKeys.continuations(novelId, idsKey),
    queryFn: () => api.getContinuations(novelId, continuationIds),
    enabled: isReloadMode && continuationIds.length > 0,
    retry: false,
  })

  const persistedError = !isReloadMode
    ? null
    : (hasInvalidLink
      ? 'Invalid continuation link'
      : (error instanceof Error ? error.message : null))

  return {
    persistedVersions: isReloadMode ? (persistedVersions ?? null) : null,
    persistedDebug,
    persistedError: isReloadMode ? persistedError : null,
    reloadedWarnings,
    retryReload: () => {
      if (!hasInvalidLink) void refetch()
    },
  }
}
