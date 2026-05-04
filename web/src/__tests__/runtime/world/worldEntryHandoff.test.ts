import { describe, expect, it } from 'vitest'
import { buildWorldEntryHandoffFromBootstrapJob } from '@/lib/worldEntryHandoff'
import type { BootstrapJobResponse } from '@/types/api'

function buildCompletedJob(overrides?: Partial<BootstrapJobResponse>): BootstrapJobResponse {
  return {
    job_id: 1,
    novel_id: 1,
    mode: 'initial',
    initialized: true,
    status: 'completed',
    progress: { step: 5, detail: 'Done' },
    result: {
      entities_found: 0,
      relationships_found: 0,
      index_refresh_only: false,
    },
    error: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('worldEntryHandoff', () => {
  it('treats zero-result extraction completion as success instead of review', () => {
    expect(buildWorldEntryHandoffFromBootstrapJob(buildCompletedJob())).toEqual({
      kind: 'extract_success',
      entityCount: 0,
      relationshipCount: 0,
      systemCount: null,
    })
  })

  it('keeps non-empty extraction completion reviewable', () => {
    expect(buildWorldEntryHandoffFromBootstrapJob(buildCompletedJob({
      result: {
        entities_found: 1,
        relationships_found: 0,
        index_refresh_only: false,
      },
    }))).toEqual({
      kind: 'extract_review',
      entityCount: 1,
      relationshipCount: 0,
      systemCount: null,
    })
  })
})
