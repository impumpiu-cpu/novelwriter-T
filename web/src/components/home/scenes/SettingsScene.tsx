// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import { ScreenshotStageAsset } from '@/components/home/ScreenshotStageAsset'
import { sceneManifest } from '@/components/home/screenshotManifest'
import { useUiLocale } from '@/contexts/UiLocaleContext'

/**
 * SettingsScene — Act 2: 从设定生成 / Build
 *
 * Center the full screenshot as a proportionally correct frame so the empty
 * space lives around the image, not inside it.
 */
export default function SettingsScene() {
  const { t } = useUiLocale()

  return (
    <div className="h-full bg-[radial-gradient(circle_at_center,#eff6ff_0%,#f8faff_42%,#ffffff_82%)] p-3 sm:p-4">
      <div className="flex h-full items-center justify-center overflow-hidden rounded-[24px] border border-blue-100/90 bg-[#f7faff] px-4 py-5 shadow-[0_16px_36px_rgba(37,99,235,0.06)] sm:px-5 sm:py-6">
        <div className="aspect-[1760/1003] w-full overflow-hidden rounded-[20px] border border-blue-100/80 bg-white shadow-[0_14px_28px_rgba(37,99,235,0.08)]">
          <ScreenshotStageAsset
            src={sceneManifest.settings.screenshot}
            alt={t(sceneManifest.settings.labelKey)}
            imageClassName="object-cover object-top"
            objectPosition="center top"
            scale={1}
          />
        </div>
      </div>
    </div>
  )
}
