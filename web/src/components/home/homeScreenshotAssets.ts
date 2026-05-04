// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

const HOME_SCREENSHOT_PUBLIC_DIR = '/screenshots/home' as const
const HOME_SCREENSHOT_BUILD_ID = __NOVWR_BUILD_ID__

const homeScreenshotPreloadCache = new Map<string, Promise<void>>()

function buildVersionedHomeScreenshotUrl(fileName: string): string {
  const search = new URLSearchParams({ v: HOME_SCREENSHOT_BUILD_ID }).toString()
  return `${HOME_SCREENSHOT_PUBLIC_DIR}/${fileName}?${search}`
}

function preloadImage(src: string): Promise<void> {
  const cached = homeScreenshotPreloadCache.get(src)
  if (cached) return cached

  const promise = new Promise<void>((resolve) => {
    if (typeof Image === 'undefined') {
      resolve()
      return
    }

    const image = new Image()
    image.decoding = 'async'
    image.onload = () => resolve()
    image.onerror = () => resolve()
    image.src = src
  })

  homeScreenshotPreloadCache.set(src, promise)
  return promise
}

export const homeScreenshotAssets = {
  // ── Workflow scenes (1–5) ──
  library: buildVersionedHomeScreenshotUrl('1.png'),
  settingsGenerate: buildVersionedHomeScreenshotUrl('2.png'),
  atlasReview: buildVersionedHomeScreenshotUrl('3.png'),
  copilotChat: buildVersionedHomeScreenshotUrl('4.png'),
  studioWrite: buildVersionedHomeScreenshotUrl('5.png'),
  // ── Dedicated non-workflow product surfaces ──
  studioWorkspace: buildVersionedHomeScreenshotUrl('new_studio.png'),
  atlasWorkspace: buildVersionedHomeScreenshotUrl('new_atlas_overview.png'),
  // ── Feature showcase / details ──
  atlasSelected: buildVersionedHomeScreenshotUrl('new_atlas_overview.png'),
  atlasEntityEdit: buildVersionedHomeScreenshotUrl('atlas_entity_edit.png'),
  draftReviewStrip: buildVersionedHomeScreenshotUrl('detail.png'),
  draftReviewHighlight: buildVersionedHomeScreenshotUrl('detail2.png'),
} as const

export const homeProductStageScreenshotPublicPaths = [
  homeScreenshotAssets.library,
  homeScreenshotAssets.settingsGenerate,
  homeScreenshotAssets.atlasReview,
  homeScreenshotAssets.copilotChat,
  homeScreenshotAssets.studioWrite,
  homeScreenshotAssets.studioWorkspace,
  homeScreenshotAssets.atlasWorkspace,
  homeScreenshotAssets.atlasEntityEdit,
  homeScreenshotAssets.draftReviewStrip,
  homeScreenshotAssets.draftReviewHighlight,
] as const

export async function preloadHomeProductStageScreenshots(): Promise<void> {
  await Promise.all(homeProductStageScreenshotPublicPaths.map((src) => preloadImage(src)))
}
