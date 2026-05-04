import { describe, expect, it } from 'vitest'
import {
  buildWorldEntryLifecycleFeedback,
  resolveAtlasAssistPresentation,
  resolveStudioWorldEntryPresentation,
  resolveWorldEntryReviewKind,
} from '@/lib/worldEntryLifecycle'

describe('resolveWorldEntryReviewKind', () => {
  it('prefers entity review when generated drafts include entities', () => {
    expect(resolveWorldEntryReviewKind({
      kind: 'generate_review',
      entityCount: 1,
      relationshipCount: 0,
      systemCount: 2,
    }, 'systems')).toBe('entities')
  })

  it('routes system-only generation handoff into systems review', () => {
    expect(resolveWorldEntryReviewKind({
      kind: 'generate_review',
      entityCount: 0,
      relationshipCount: 0,
      systemCount: 2,
    })).toBe('systems')
  })

  it('routes relationship-only extraction handoff into relationships review', () => {
    expect(resolveWorldEntryReviewKind({
      kind: 'extract_review',
      entityCount: 0,
      relationshipCount: 3,
      systemCount: null,
    })).toBe('relationships')
  })

  it('falls back when the handoff does not identify reviewable drafts', () => {
    expect(resolveWorldEntryReviewKind({
      kind: 'extract_failed',
      entityCount: null,
      relationshipCount: null,
      systemCount: null,
    }, 'systems')).toBe('systems')
  })

  it('keeps cold-start prominence when no world data exists yet', () => {
    expect(resolveStudioWorldEntryPresentation({
      worldEntityCount: 0,
      worldSystemCount: 0,
      handoff: null,
      pending: null,
    })).toMatchObject({
      stage: 'cold_start',
      worldEntryProminence: 'prominent',
    })
  })

  it('temporarily re-elevates world entry when Atlas review attention exists', () => {
    expect(resolveStudioWorldEntryPresentation({
      worldEntityCount: 5,
      worldSystemCount: 2,
      handoff: {
        kind: 'generate_review',
        entityCount: 1,
        relationshipCount: 0,
        systemCount: 1,
      },
      pending: null,
    })).toMatchObject({
      stage: 'attention',
      worldEntryProminence: 'elevated',
    })
  })

  it('returns to routine research-first order after the attention state clears', () => {
    expect(resolveStudioWorldEntryPresentation({
      worldEntityCount: 5,
      worldSystemCount: 2,
      handoff: {
        kind: 'generate_success',
        entityCount: 0,
        relationshipCount: 0,
        systemCount: 0,
      },
      pending: null,
    })).toMatchObject({
      stage: 'routine',
      worldEntryProminence: 'compact',
    })
  })

  it('re-elevates Atlas governance when drafts need review outside the review tab', () => {
    expect(resolveAtlasAssistPresentation({
      tab: 'entities',
      handoff: null,
      pending: null,
      totalDrafts: 3,
    })).toMatchObject({
      stage: 'attention',
      governanceProminence: 'elevated',
      governanceFirst: true,
    })
  })

  it('keeps Atlas in governance-first mode without the attention banner once review is already open', () => {
    expect(resolveAtlasAssistPresentation({
      tab: 'review',
      handoff: null,
      pending: null,
      totalDrafts: 3,
    })).toMatchObject({
      stage: 'governance',
      governanceProminence: 'default',
      governanceFirst: true,
    })
  })

  it('returns Atlas to research-first mode when no governance backlog remains', () => {
    expect(resolveAtlasAssistPresentation({
      tab: 'entities',
      handoff: {
        kind: 'generate_review',
        entityCount: 2,
        relationshipCount: 0,
        systemCount: 1,
      },
      pending: null,
      totalDrafts: 0,
      reviewBacklogCount: 0,
    })).toMatchObject({
      stage: 'routine',
      governanceProminence: 'compact',
      governanceFirst: false,
    })
  })

  it('keeps Atlas in attention mode while review backlog is not yet resolved', () => {
    expect(resolveAtlasAssistPresentation({
      tab: 'entities',
      handoff: {
        kind: 'generate_review',
        entityCount: 2,
        relationshipCount: 0,
        systemCount: 1,
      },
      pending: null,
      totalDrafts: 0,
      reviewBacklogCount: null,
    })).toMatchObject({
      stage: 'attention',
      governanceProminence: 'elevated',
      governanceFirst: true,
    })
  })

  it('downgrades stale review lifecycle feedback to success once Atlas confirms there are no drafts left', () => {
    expect(buildWorldEntryLifecycleFeedback({
      kind: 'generate_review',
      entityCount: 2,
      relationshipCount: 0,
      systemCount: 1,
    }, (key) => key, { reviewBacklogCount: 0 })).toEqual({
      phase: 'success',
      source: 'generate',
      summary: 'worldEntry.summary.generated',
    })
  })
})
