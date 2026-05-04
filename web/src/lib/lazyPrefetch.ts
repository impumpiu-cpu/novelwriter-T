type NavigatorWithConnection = Navigator & {
  connection?: {
    saveData?: boolean
    effectiveType?: string
  }
}

export function canPrefetchOnCurrentConnection() {
  if (typeof navigator === 'undefined') return false
  const connection = (navigator as NavigatorWithConnection).connection
  if (connection?.saveData) return false
  if (connection?.effectiveType === 'slow-2g' || connection?.effectiveType === '2g') return false
  return true
}

export function scheduleIdleChunkPrefetch(
  load: () => Promise<unknown>,
  {
    idleTimeout = 1600,
    fallbackDelayMs = 900,
  }: {
    idleTimeout?: number
    fallbackDelayMs?: number
  } = {},
) {
  if (typeof window === 'undefined') return () => {}
  if (!canPrefetchOnCurrentConnection()) return () => {}

  let cancelled = false
  const runPrefetch = () => {
    if (cancelled) return
    void load()
  }

  if (typeof window.requestIdleCallback === 'function') {
    const handle = window.requestIdleCallback(runPrefetch, { timeout: idleTimeout })
    return () => {
      cancelled = true
      if (typeof window.cancelIdleCallback === 'function') {
        window.cancelIdleCallback(handle)
      }
    }
  }

  const handle = window.setTimeout(runPrefetch, fallbackDelayMs)
  return () => {
    cancelled = true
    window.clearTimeout(handle)
  }
}
