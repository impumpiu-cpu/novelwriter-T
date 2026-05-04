import { useCallback } from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'
import { setResultsProvenanceSearchParams } from '@/components/novel-shell/NovelShellRouteState'
import { saveGenerationResultsDebug } from '@/lib/generationResultsDebugStorage'
import type { PersistResultsToUrl } from './helpers'

interface UseContinuationResultsUrlPersistenceArgs {
  activeChapterNum: number | null
  location: Location
  navigate: NavigateFunction
}

export function useContinuationResultsUrlPersistence({
  activeChapterNum,
  location,
  navigate,
}: UseContinuationResultsUrlPersistenceArgs): PersistResultsToUrl {
  return useCallback((mapping, total, debugSummary) => {
    if (!mapping || !total || activeChapterNum === null) return
    if (debugSummary) saveGenerationResultsDebug(mapping, debugSummary)

    const currentSearchParams = new URLSearchParams(location.search)
    const currentStage = currentSearchParams.get('stage')
    let nextSearchParams = new URLSearchParams(currentSearchParams)

    if (currentStage === 'results' || currentStage == null) {
      nextSearchParams = setResultsProvenanceSearchParams(nextSearchParams, null)
      nextSearchParams.set('continuations', mapping)
      nextSearchParams.set('total_variants', String(total))
    } else {
      nextSearchParams = setResultsProvenanceSearchParams(nextSearchParams, {
        chapterNum: activeChapterNum,
        continuations: mapping,
        totalVariants: total,
      })
    }

    navigate(
      {
        pathname: location.pathname,
        search: nextSearchParams.toString(),
      },
      { replace: true, state: null },
    )
  }, [activeChapterNum, location.pathname, location.search, navigate])
}
