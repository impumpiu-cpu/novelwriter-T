import { describe, expect, it } from 'vitest'
import { homeNarrativeActs } from '@/components/home/homeContent'
import { HOMEPAGE_PRODUCT_STAGE_CAPTURE_TARGETS } from '../../scripts/homepageScreenshotCapture'

describe('homepageScreenshotCapture', () => {
  it('captures one workflow screenshot per homepage narrative act in order', () => {
    expect(HOMEPAGE_PRODUCT_STAGE_CAPTURE_TARGETS).toHaveLength(homeNarrativeActs.length)
    expect(HOMEPAGE_PRODUCT_STAGE_CAPTURE_TARGETS.map((target) => target.actIndex)).toEqual(
      homeNarrativeActs.map((_, index) => index),
    )
    expect(HOMEPAGE_PRODUCT_STAGE_CAPTURE_TARGETS.map((target) => target.outputFile)).toEqual([
      '1.png',
      '2.png',
      '3.png',
      '4.png',
      '5.png',
    ])
  })
})
