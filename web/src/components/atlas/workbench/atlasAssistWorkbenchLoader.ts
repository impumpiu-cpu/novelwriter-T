import { scheduleIdleChunkPrefetch } from '@/lib/lazyPrefetch'

type AtlasAssistWorkbenchModule = typeof import('@/components/atlas/workbench/AtlasAssistWorkbench')

let atlasAssistWorkbenchModulePromise: Promise<AtlasAssistWorkbenchModule> | null = null

export function loadAtlasAssistWorkbench() {
  if (!atlasAssistWorkbenchModulePromise) {
    atlasAssistWorkbenchModulePromise = import('@/components/atlas/workbench/AtlasAssistWorkbench')
  }

  return atlasAssistWorkbenchModulePromise
}

export function scheduleAtlasAssistWorkbenchPrefetch() {
  return scheduleIdleChunkPrefetch(loadAtlasAssistWorkbench, {
    idleTimeout: 1600,
    fallbackDelayMs: 900,
  })
}
