// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import { ScreenshotStageAsset } from '@/components/home/ScreenshotStageAsset'
import { sceneManifest } from '@/components/home/screenshotManifest'
import { useUiLocale } from '@/contexts/UiLocaleContext'

/**
 * CopilotScene — Act 4: Copilot / 查阅
 *
 * Keep this step proof-led: show the real Copilot surface in full instead of
 * cropping it into a faux cinematic frame.
 */
export default function CopilotScene() {
  const { t } = useUiLocale()

  return (
    <div className="h-full bg-[linear-gradient(180deg,#fcfaff_0%,#ffffff_100%)] p-3 sm:p-4">
      <div className="relative h-full overflow-hidden rounded-[24px] border border-violet-100/80 bg-[#fcfaff] shadow-[0_16px_36px_rgba(124,58,237,0.06)]">
        <div className="absolute inset-x-0 top-0 z-10 h-[2px] bg-gradient-to-r from-violet-400/0 via-violet-400/60 to-violet-400/0" />

        <ScreenshotStageAsset
          src={sceneManifest.copilot.screenshot}
          alt={t(sceneManifest.copilot.labelKey)}
          className="bg-[#fcfaff]"
          imageClassName="object-contain bg-[#fcfaff]"
          objectPosition="center center"
          scale={1}
        />
      </div>
    </div>
  )
}
