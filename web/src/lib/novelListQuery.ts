import { novelKeys } from '@/hooks/novel/keys'
import { api } from '@/services/api'

export const NOVEL_LIST_QUERY_STALE_MS = 5 * 60_000
export const NOVEL_LIST_QUERY_GC_MS = 15 * 60_000

export function buildNovelListQueryOptions() {
  return {
    queryKey: novelKeys.all,
    queryFn: () => api.listNovels(),
    staleTime: NOVEL_LIST_QUERY_STALE_MS,
    gcTime: NOVEL_LIST_QUERY_GC_MS,
  }
}
