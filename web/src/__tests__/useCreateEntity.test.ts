import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { worldKeys } from '@/hooks/world/keys'
import { createQueryClientWrapper, createTestQueryClient } from '@/__tests__/support/queryClient'

vi.mock('@/components/world-model/shared/useToast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

vi.mock('@/services/api', () => ({
  worldApi: {
    createEntity: vi.fn(),
  },
}))

import { worldApi } from '@/services/api'
import { useCreateEntity } from '@/hooks/world/useEntities'

const mockCreateEntity = worldApi.createEntity as ReturnType<typeof vi.fn>

describe('useCreateEntity', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('hydrates matching entity lists immediately after create succeeds', async () => {
    const novelId = 7
    const listKeyAll = [...worldKeys.entities(novelId), undefined]
    const listKeyDraft = [...worldKeys.entities(novelId), { status: 'draft' }]
    const listKeyCharacter = [...worldKeys.entities(novelId), { entity_type: 'Character' }]
    const listKeySystem = [...worldKeys.entities(novelId), { entity_type: 'System' }]

    const createdEntity = {
      id: 59,
      novel_id: novelId,
      name: '新实体',
      entity_type: 'Character',
      description: '',
      aliases: [],
      origin: 'manual',
      worldpack_pack_id: null,
      worldpack_key: null,
      status: 'draft',
      created_at: '2026-02-01T00:00:00Z',
      updated_at: '2026-02-01T00:00:00Z',
    } as const

    mockCreateEntity.mockResolvedValue(createdEntity)

    const queryClient = createTestQueryClient()
    queryClient.setQueryData(listKeyAll, [])
    queryClient.setQueryData(listKeyDraft, [])
    queryClient.setQueryData(listKeyCharacter, [])
    queryClient.setQueryData(listKeySystem, [])

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useCreateEntity(novelId), {
      wrapper: createQueryClientWrapper(queryClient),
    })

    await act(async () => {
      await result.current.mutateAsync({
        name: createdEntity.name,
        entity_type: createdEntity.entity_type,
      })
    })

    expect(mockCreateEntity).toHaveBeenCalledWith(novelId, {
      name: createdEntity.name,
      entity_type: createdEntity.entity_type,
    })
    expect(queryClient.getQueryData(listKeyAll)).toEqual([createdEntity])
    expect(queryClient.getQueryData(listKeyDraft)).toEqual([createdEntity])
    expect(queryClient.getQueryData(listKeyCharacter)).toEqual([createdEntity])
    expect(queryClient.getQueryData(listKeySystem)).toEqual([])
    expect(queryClient.getQueryData(worldKeys.entity(novelId, createdEntity.id))).toMatchObject({
      id: createdEntity.id,
      attributes: [],
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: worldKeys.entities(novelId) })
  })
})
