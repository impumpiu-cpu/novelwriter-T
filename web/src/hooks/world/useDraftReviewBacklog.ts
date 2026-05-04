import { useWorldEntities } from '@/hooks/world/useEntities'
import { useWorldRelationships } from '@/hooks/world/useRelationships'
import { useWorldSystems } from '@/hooks/world/useSystems'

export function useDraftReviewBacklog(novelId: number) {
  const draftEntitiesQuery = useWorldEntities(novelId, { status: 'draft' })
  const draftRelationshipsQuery = useWorldRelationships(novelId, { status: 'draft' })
  const draftSystemsQuery = useWorldSystems(novelId, { status: 'draft' })

  const draftEntities = draftEntitiesQuery.data ?? []
  const draftRelationships = draftRelationshipsQuery.data ?? []
  const draftSystems = draftSystemsQuery.data ?? []

  return {
    draftEntities,
    draftRelationships,
    draftSystems,
    draftEntityCount: draftEntities.length,
    draftRelationshipCount: draftRelationships.length,
    draftSystemCount: draftSystems.length,
    totalDrafts: draftEntities.length + draftRelationships.length + draftSystems.length,
    isResolved:
      draftEntitiesQuery.isSuccess
      && draftRelationshipsQuery.isSuccess
      && draftSystemsQuery.isSuccess,
  }
}
