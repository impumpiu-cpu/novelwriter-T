import { describe, expect, it } from 'vitest'
import {
  buildStudioHostPath,
  parseNovelShellRouteState,
  readAtlasStudioOriginSearchParams,
  readNovelShellArtifactPanelSearchParams,
  readResultsProvenanceSearchParams,
  readWorldEntryHandoffSearchParams,
  readWorldEntryPendingSearchParams,
  setAtlasStudioOriginSearchParams,
  setAtlasReviewKindSearchParams,
  setNovelShellArtifactPanelSearchParams,
  setAtlasSuggestionTargetSearchParams,
  setResultsProvenanceSearchParams,
  setWorldEntryHandoffSearchParams,
  setWorldEntryPendingSearchParams,
  setAtlasTabSearchParams,
  setStudioChapterSearchParams,
  setStudioEntityStageSearchParams,
  setStudioResultsStageSearchParams,
  setStudioRelationshipStageSearchParams,
  setStudioSystemStageSearchParams,
  setStudioReviewKindSearchParams,
} from '@/components/novel-shell/NovelShellRouteState'

describe('NovelShellRouteState', () => {
  it('parses atlas tab and review state from the current world route', () => {
    const state = parseNovelShellRouteState('/world/42?tab=review&kind=relationships&entity=9')

    expect(state).toMatchObject({
      surface: 'atlas',
      stage: 'review',
      entry: 'atlas',
      novelId: 42,
      entityId: 9,
      worldTab: 'review',
      reviewKind: 'relationships',
    })
  })

  it('parses atlas relationship selection from the URL contract', () => {
    const state = parseNovelShellRouteState('/world/42?tab=relationships&entity=9&relationship=17')

    expect(state).toMatchObject({
      surface: 'atlas',
      stage: 'relationship',
      entry: 'atlas',
      novelId: 42,
      entityId: 9,
      relationshipId: 17,
      worldTab: 'relationships',
    })
  })

  it('keeps atlas search params aligned when tabs or suggestion targets change', () => {
    const baseParams = setAtlasStudioOriginSearchParams(new URLSearchParams('tab=review&kind=systems'), {
      stage: 'entity',
      chapterNum: 7,
      entityId: 12,
      systemId: null,
      reviewKind: null,
      resultsProvenance: {
        chapterNum: 3,
        continuations: '0:15,1:16',
        totalVariants: 2,
      },
      artifactPanelState: { panel: 'injection_summary', injectionCategory: 'entities' },
    })
    const systemsParams = setAtlasTabSearchParams(baseParams, 'systems')

    expect(systemsParams.get('tab')).toBeNull()
    expect(systemsParams.get('kind')).toBeNull()
    expect(systemsParams.get('originStage')).toBe('entity')

    const reviewParams = setAtlasReviewKindSearchParams(baseParams, 'relationships')
    expect(reviewParams.get('tab')).toBe('review')
    expect(reviewParams.get('kind')).toBe('relationships')

    const targetParams = setAtlasSuggestionTargetSearchParams(baseParams, {
      resource: 'relationship',
      resource_id: 12,
      label: '苏瑶 ↔ 太玄宗',
      tab: 'review',
      review_kind: 'relationships',
    })
    expect(targetParams.get('tab')).toBe('review')
    expect(targetParams.get('kind')).toBe('relationships')
    expect(targetParams.get('highlight')).toBe('12')
    expect(targetParams.get('originStage')).toBe('entity')

    const entityTargetParams = setAtlasSuggestionTargetSearchParams(baseParams, {
      resource: 'entity',
      resource_id: 12,
      label: '苏瑶',
      tab: 'entities',
    })
    expect(entityTargetParams.get('tab')).toBe('entities')
    expect(entityTargetParams.get('entity')).toBe('12')
    expect(entityTargetParams.get('relationship')).toBeNull()
    expect(entityTargetParams.get('originStage')).toBe('entity')

    const relationshipTargetParams = setAtlasSuggestionTargetSearchParams(baseParams, {
      resource: 'relationship',
      resource_id: 19,
      label: '苏瑶 ↔ 韩立',
      tab: 'relationships',
      entity_id: 12,
      highlight_id: 19,
    })
    expect(relationshipTargetParams.get('tab')).toBe('relationships')
    expect(relationshipTargetParams.get('entity')).toBe('12')
    expect(relationshipTargetParams.get('relationship')).toBe('19')

    const originCleared = setAtlasStudioOriginSearchParams(entityTargetParams, null)
    expect(originCleared.get('originStage')).toBeNull()
    expect(originCleared.get('originResultsContinuations')).toBeNull()
  })

  it('parses studio write stage from novel host route', () => {
    const state = parseNovelShellRouteState('/novel/42?stage=write')

    expect(state).toMatchObject({
      surface: 'studio',
      stage: 'write',
      entry: 'studio_host',
      novelId: 42,
      chapterNum: null,
      worldTab: null,
    })
  })

  it('builds studio search params for entity and review stages while preserving chapter context', () => {
    const baseParams = new URLSearchParams()
    const chapterParams = setStudioChapterSearchParams(baseParams, 7)

    expect(chapterParams.get('chapter')).toBe('7')
    expect(chapterParams.get('stage')).toBeNull()

    const entityParams = setStudioEntityStageSearchParams(chapterParams, 12)
    expect(entityParams.get('stage')).toBe('entity')
    expect(entityParams.get('entity')).toBe('12')
    expect(entityParams.get('chapter')).toBe('7')

    const relationshipParams = setStudioRelationshipStageSearchParams(entityParams, 12)
    expect(relationshipParams.get('stage')).toBe('relationship')
    expect(relationshipParams.get('entity')).toBe('12')
    expect(relationshipParams.get('chapter')).toBe('7')

    const systemParams = setStudioSystemStageSearchParams(relationshipParams, 19)
    expect(systemParams.get('stage')).toBe('system')
    expect(systemParams.get('system')).toBe('19')
    expect(systemParams.get('chapter')).toBe('7')

    const reviewParams = setStudioReviewKindSearchParams(systemParams, 'relationships')
    expect(reviewParams.get('stage')).toBe('review')
    expect(reviewParams.get('reviewKind')).toBe('relationships')
    expect(reviewParams.get('chapter')).toBe('7')

    const resultsParams = setStudioResultsStageSearchParams(reviewParams, 7)
    expect(resultsParams.get('stage')).toBe('results')
    expect(resultsParams.get('chapter')).toBe('7')
  })

  it('round-trips structured results provenance through the studio host route', () => {
    const provenanceParams = setResultsProvenanceSearchParams(new URLSearchParams('stage=entity&entity=9'), {
      chapterNum: 3,
      continuations: '0:15,1:16',
      totalVariants: 2,
    })

    expect(provenanceParams.get('resultsChapter')).toBe('3')
    expect(provenanceParams.get('resultsContinuations')).toBe('0:15,1:16')
    expect(provenanceParams.get('resultsTotalVariants')).toBe('2')

    const provenance = readResultsProvenanceSearchParams(provenanceParams)
    expect(provenance).toEqual({
      chapterNum: 3,
      continuations: '0:15,1:16',
      totalVariants: 2,
    })
  })

  it('round-trips the shell artifact panel state across the studio host route', () => {
    const panelParams = setNovelShellArtifactPanelSearchParams(new URLSearchParams('chapter=3'), {
      panel: 'injection_summary',
      injectionCategory: 'relationships',
    })

    expect(panelParams.get('artifactPanel')).toBe('injection_summary')
    expect(panelParams.get('summaryCategory')).toBe('relationships')
    expect(readNovelShellArtifactPanelSearchParams(panelParams)).toEqual({
      panel: 'injection_summary',
      injectionCategory: 'relationships',
    })

    expect(buildStudioHostPath(7, {
      stage: 'results',
      chapterNum: 3,
      entityId: null,
      systemId: null,
      reviewKind: null,
      resultsProvenance: {
        chapterNum: 3,
        continuations: '0:15,1:16',
        totalVariants: 2,
      },
      artifactPanelState: {
        panel: 'injection_summary',
        injectionCategory: 'relationships',
      },
    })).toBe('/novel/7?stage=results&chapter=3&continuations=0%3A15%2C1%3A16&total_variants=2&artifactPanel=injection_summary&summaryCategory=relationships')
  })

  it('round-trips structured studio origin through atlas params and rebuilds the studio host path', () => {
    const originParams = setAtlasStudioOriginSearchParams(new URLSearchParams('tab=entities'), {
      stage: 'relationship',
      chapterNum: 7,
      entityId: 12,
      systemId: null,
      reviewKind: null,
      resultsProvenance: {
        chapterNum: 3,
        continuations: '0:15,1:16',
        totalVariants: 2,
      },
      artifactPanelState: { panel: 'injection_summary', injectionCategory: 'relationships' },
    })

    expect(readAtlasStudioOriginSearchParams(originParams)).toEqual({
      stage: 'relationship',
      chapterNum: 7,
      entityId: 12,
      systemId: null,
      reviewKind: null,
      resultsProvenance: {
        chapterNum: 3,
        continuations: '0:15,1:16',
        totalVariants: 2,
      },
      artifactPanelState: { panel: 'injection_summary', injectionCategory: 'relationships' },
    })

    expect(buildStudioHostPath(7, {
      stage: 'relationship',
      chapterNum: 7,
      entityId: 12,
      systemId: null,
      reviewKind: null,
      resultsProvenance: {
        chapterNum: 3,
        continuations: '0:15,1:16',
        totalVariants: 2,
      },
      artifactPanelState: { panel: 'injection_summary', injectionCategory: 'relationships' },
    })).toBe(
      '/novel/7?chapter=7&stage=relationship&entity=12&resultsChapter=3&resultsContinuations=0%3A15%2C1%3A16&resultsTotalVariants=2&artifactPanel=injection_summary&summaryCategory=relationships',
    )
  })

  it('parses and rebuilds the in-shell system stage', () => {
    const state = parseNovelShellRouteState('/novel/42?stage=system&system=19&chapter=7')

    expect(state).toMatchObject({
      surface: 'studio',
      stage: 'system',
      entry: 'studio_host',
      novelId: 42,
      chapterNum: 7,
      systemId: 19,
    })

    expect(buildStudioHostPath(7, {
      stage: 'system',
      chapterNum: 7,
      entityId: null,
      systemId: 19,
      reviewKind: null,
      resultsProvenance: null,
      artifactPanelState: null,
    })).toBe('/novel/7?chapter=7&stage=system&system=19')
  })

  it('parses selected chapter from the studio host route query string', () => {
    const state = parseNovelShellRouteState('/novel/42?chapter=7')

    expect(state).toMatchObject({
      surface: 'studio',
      stage: 'chapter',
      entry: 'studio_host',
      novelId: 42,
      chapterNum: 7,
      worldTab: null,
    })
  })

  it('round-trips world-entry handoff params for browser-back continuity', () => {
    const params = setWorldEntryHandoffSearchParams(
      new URLSearchParams('chapter=7'),
      {
        kind: 'generate_review',
        entityCount: 1,
        relationshipCount: 0,
        systemCount: 2,
      },
    )

    expect(params.get('worldEntryHandoff')).toBe('generate_review')
    expect(params.get('worldEntryEntities')).toBe('1')
    expect(params.get('worldEntryRelationships')).toBe('0')
    expect(params.get('worldEntrySystems')).toBe('2')
    expect(readWorldEntryHandoffSearchParams(params)).toEqual({
      kind: 'generate_review',
      entityCount: 1,
      relationshipCount: 0,
      systemCount: 2,
    })

    const cleared = setWorldEntryHandoffSearchParams(params, null)
    expect(cleared.get('worldEntryHandoff')).toBeNull()
    expect(cleared.get('worldEntryEntities')).toBeNull()
    expect(cleared.get('worldEntrySystems')).toBeNull()
  })

  it('normalizes zero-count review handoffs into success handoffs', () => {
    expect(readWorldEntryHandoffSearchParams(new URLSearchParams(
      'worldEntryHandoff=extract_review&worldEntryEntities=0&worldEntryRelationships=0',
    ))).toEqual({
      kind: 'extract_success',
      entityCount: 0,
      relationshipCount: 0,
      systemCount: null,
    })

    expect(readWorldEntryHandoffSearchParams(new URLSearchParams(
      'worldEntryHandoff=generate_review&worldEntryEntities=0&worldEntryRelationships=0&worldEntrySystems=0',
    ))).toEqual({
      kind: 'generate_success',
      entityCount: 0,
      relationshipCount: 0,
      systemCount: 0,
    })
  })

  it('round-trips pending world-entry params so async completion can upgrade later', () => {
    const params = setWorldEntryPendingSearchParams(
      new URLSearchParams('chapter=7'),
      {
        kind: 'extract',
        startedAtMs: 1_742_000_000_000,
        jobId: 41,
      },
    )

    expect(params.get('worldEntryPending')).toBe('extract')
    expect(params.get('worldEntryPendingAt')).toBe('1742000000000')
    expect(params.get('worldEntryPendingJob')).toBe('41')
    expect(readWorldEntryPendingSearchParams(params)).toEqual({
      kind: 'extract',
      startedAtMs: 1_742_000_000_000,
      jobId: 41,
    })

    const cleared = setWorldEntryPendingSearchParams(params, null)
    expect(cleared.get('worldEntryPending')).toBeNull()
    expect(cleared.get('worldEntryPendingAt')).toBeNull()
    expect(cleared.get('worldEntryPendingJob')).toBeNull()
  })

  it('does not parse the removed legacy write route', () => {
    const state = parseNovelShellRouteState('/novel/42/chapter/7/write')

    expect(state).toMatchObject({
      surface: null,
      stage: null,
      entry: null,
      novelId: null,
      chapterNum: null,
    })
  })
})
