import { describe, expect, it, vi, afterEach } from 'vitest'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
})

describe('homeScreenshotAssets', () => {
  it('keeps public screenshot paths pluggable while adding a build version', async () => {
    const { homeScreenshotAssets } = await import('@/components/home/homeScreenshotAssets')

    expect(homeScreenshotAssets.library).toMatch(/^\/screenshots\/home\/1\.png\?v=/)
    expect(homeScreenshotAssets.settingsGenerate).toMatch(/^\/screenshots\/home\/2\.png\?v=/)
    expect(homeScreenshotAssets.atlasReview).toMatch(/^\/screenshots\/home\/3\.png\?v=/)
    expect(homeScreenshotAssets.copilotChat).toMatch(/^\/screenshots\/home\/4\.png\?v=/)
    expect(homeScreenshotAssets.studioWrite).toMatch(/^\/screenshots\/home\/5\.png\?v=/)
    expect(homeScreenshotAssets.studioWorkspace).toMatch(/^\/screenshots\/home\/new_studio\.png\?v=/)
    expect(homeScreenshotAssets.atlasWorkspace).toMatch(/^\/screenshots\/home\/new_atlas_overview\.png\?v=/)
    expect(homeScreenshotAssets.atlasSelected).toMatch(/^\/screenshots\/home\/new_atlas_overview\.png\?v=/)
    expect(homeScreenshotAssets.atlasEntityEdit).toMatch(/^\/screenshots\/home\/atlas_entity_edit\.png\?v=/)
  })

  it('preloads each stage screenshot source only once across repeated warmups', async () => {
    const assignedSources: string[] = []

    class MockImage {
      decoding = ''
      onload: null | (() => void) = null
      onerror: null | (() => void) = null

      set src(value: string) {
        assignedSources.push(value)
        queueMicrotask(() => this.onload?.())
      }
    }

    vi.stubGlobal('Image', MockImage)

    const {
      homeProductStageScreenshotPublicPaths,
      preloadHomeProductStageScreenshots,
    } = await import('@/components/home/homeScreenshotAssets')

    await preloadHomeProductStageScreenshots()
    await preloadHomeProductStageScreenshots()

    expect(assignedSources).toEqual([...homeProductStageScreenshotPublicPaths])
  })
})
