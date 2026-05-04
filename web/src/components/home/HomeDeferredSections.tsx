// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import { FeatureShowcase } from '@/components/home/FeatureShowcase'
import { StickyNarrative } from '@/components/home/StickyNarrative'
import { DetailsMatter } from '@/components/home/DetailsMatter'
import { ClosingCTA } from '@/components/home/ClosingCTA'
import { SiteFooter } from '@/components/layout/SiteFooter'

export function HomeDeferredSections() {
  return (
    <>
      <FeatureShowcase />
      <StickyNarrative />
      <DetailsMatter />
      <ClosingCTA />
      <SiteFooter />
    </>
  )
}

export default HomeDeferredSections
