import { useSyncExternalStore } from 'react'

const KEY_PREFIX = 'novwr_world_onboarding_dismissed_'
const CHANGE_EVENT = 'novwr:world-onboarding-dismissed-change'

function emitWorldOnboardingDismissChange(key: string): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent<string>(CHANGE_EVENT, { detail: key }))
}

export function worldOnboardingDismissKey(novelId: number, createdAt?: string | null): string | null {
  if (!Number.isFinite(novelId) || novelId <= 0) return null
  const created = String(createdAt ?? '').trim()
  if (!created) return null
  return `${KEY_PREFIX}${novelId}_${created}`
}

export function isWorldOnboardingDismissed(novelId: number, createdAt?: string | null): boolean {
  try {
    const key = worldOnboardingDismissKey(novelId, createdAt)
    return key ? localStorage.getItem(key) === '1' : false
  } catch {
    return false
  }
}

export function dismissWorldOnboarding(novelId: number, createdAt?: string | null): void {
  const key = worldOnboardingDismissKey(novelId, createdAt)
  try {
    if (!key) return
    localStorage.setItem(key, '1')
    emitWorldOnboardingDismissChange(key)
  } catch {
    // ignore
  }
}

export function clearWorldOnboardingDismissed(novelId: number, createdAt?: string | null): void {
  const key = worldOnboardingDismissKey(novelId, createdAt)
  if (!key) return
  try {
    localStorage.removeItem(key)
    emitWorldOnboardingDismissChange(key)
  } catch {
    // ignore
  }
}

function subscribeWorldOnboardingDismissed(
  key: string | null,
  onStoreChange: () => void,
): () => void {
  if (typeof window === 'undefined' || !key) {
    return () => {}
  }

  const handleStorage = (event: StorageEvent) => {
    if (event.key !== key) return
    onStoreChange()
  }

  const handleCustomChange = (event: Event) => {
    const detail = (event as CustomEvent<string>).detail
    if (detail !== key) return
    onStoreChange()
  }

  window.addEventListener('storage', handleStorage)
  window.addEventListener(CHANGE_EVENT, handleCustomChange)
  return () => {
    window.removeEventListener('storage', handleStorage)
    window.removeEventListener(CHANGE_EVENT, handleCustomChange)
  }
}

export function useWorldOnboardingDismissed(novelId: number, createdAt?: string | null): boolean {
  const key = worldOnboardingDismissKey(novelId, createdAt)

  return useSyncExternalStore(
    (onStoreChange) => subscribeWorldOnboardingDismissed(key, onStoreChange),
    () => (key ? isWorldOnboardingDismissed(novelId, createdAt) : false),
    () => false,
  )
}
