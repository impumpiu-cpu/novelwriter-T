import { describe, expect, it } from 'vitest'
import { collectInvalidateQueryKeysForAppliedSuggestions } from '@/hooks/novel-copilot/useNovelCopilotRuns'
import type { CopilotRun } from '@/types/copilot'

describe('collectInvalidateQueryKeysForAppliedSuggestions', () => {
  it('invalidates only the touched world-model query families', () => {
    const suggestions = [
      {
        suggestion_id: 'sg_entity',
        kind: 'update_entity',
        title: '',
        summary: '',
        evidence_ids: [],
        target: { resource: 'entity', resource_id: 101, label: '苏瑶', tab: 'entities', entity_id: 101 },
        preview: { target_label: '', summary: '', field_deltas: [], evidence_quotes: [], actionable: true },
        apply: { type: 'update_entity', entity_id: 101, data: { description: 'x' } },
        status: 'pending',
      },
      {
        suggestion_id: 'sg_rel',
        kind: 'create_relationship',
        title: '',
        summary: '',
        evidence_ids: [],
        target: { resource: 'relationship', resource_id: null, label: '苏瑶 → 宗门', tab: 'relationships' },
        preview: { target_label: '', summary: '', field_deltas: [], evidence_quotes: [], actionable: true },
        apply: { type: 'create_relationship', data: { source_id: 101, target_id: 202, label: '同门' } },
        status: 'pending',
      },
      {
        suggestion_id: 'sg_system',
        kind: 'update_system',
        title: '',
        summary: '',
        evidence_ids: [],
        target: { resource: 'system', resource_id: 303, label: '宗门戒律', tab: 'systems' },
        preview: { target_label: '', summary: '', field_deltas: [], evidence_quotes: [], actionable: true },
        apply: { type: 'update_system', system_id: 303, data: { description: 'y' } },
        status: 'pending',
      },
    ] satisfies CopilotRun['suggestions']

    expect(collectInvalidateQueryKeysForAppliedSuggestions(9, suggestions)).toEqual([
      ['world', 9, 'entities'],
      ['world', 9, 'entities', 101],
      ['world', 9, 'relationships'],
      ['world', 9, 'systems'],
      ['world', 9, 'systems', 303],
    ])
  })
})
