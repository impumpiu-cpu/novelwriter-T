import { scheduleIdleChunkPrefetch } from '@/lib/lazyPrefetch'

type NovelCopilotDrawerModule = typeof import('@/components/novel-copilot/NovelCopilotDrawer')

let novelCopilotDrawerModulePromise: Promise<NovelCopilotDrawerModule> | null = null

export function loadNovelCopilotDrawer() {
  if (!novelCopilotDrawerModulePromise) {
    novelCopilotDrawerModulePromise = import('@/components/novel-copilot/NovelCopilotDrawer')
  }

  return novelCopilotDrawerModulePromise
}

export function scheduleNovelCopilotDrawerPrefetch() {
  return scheduleIdleChunkPrefetch(loadNovelCopilotDrawer, {
    idleTimeout: 2200,
    fallbackDelayMs: 1200,
  })
}
