// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import { Navigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { buildDemoStudioPath, findSeededDemoNovel } from '@/lib/demoProject'
import { buildNovelListQueryOptions } from '@/lib/novelListQuery'

export function DemoEntryPage() {
  const location = useLocation()
  const { isLoggedIn, isLoading } = useAuth()
  const { data: novels, isLoading: novelsLoading, isError } = useQuery({
    ...buildNovelListQueryOptions(),
    enabled: isLoggedIn,
  })

  if (isLoading) return null

  if (!isLoggedIn) {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  }

  if (novelsLoading) return null

  const demoNovel = findSeededDemoNovel(novels)
  if (isError || !demoNovel) {
    return <Navigate to="/library" replace />
  }

  return <Navigate to={buildDemoStudioPath(demoNovel.id, { forceGuideOpen: true })} replace />
}

export default DemoEntryPage
