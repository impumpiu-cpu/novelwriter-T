// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import { useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { ComponentType } from 'react'
import { homeNarrativeActs } from '@/components/home/homeContent'
import { StageShell } from '@/components/home/StageShell'
import ImportScene from '@/components/home/scenes/ImportScene'
import SettingsScene from '@/components/home/scenes/SettingsScene'
import GovernanceScene from '@/components/home/scenes/GovernanceScene'
import CopilotScene from '@/components/home/scenes/CopilotScene'
import ContinuationScene from '@/components/home/scenes/ContinuationScene'
import { useUiLocale } from '@/contexts/UiLocaleContext'
import { sceneManifest, type SceneId } from '@/components/home/screenshotManifest'
import { preloadHomeProductStageScreenshots } from '@/components/home/homeScreenshotAssets'
import type { NarrativeActs } from '@/components/home/useNarrativeScroll'

const scenes: Record<SceneId, ComponentType> = {
  import: ImportScene,
  settings: SettingsScene,
  governance: GovernanceScene,
  copilot: CopilotScene,
  continuation: ContinuationScene,
}

type ProductStageProps = {
  activeAct: NarrativeActs
  prefersReducedMotion: boolean
}

export function ProductStage({ activeAct, prefersReducedMotion }: ProductStageProps) {
  const { t } = useUiLocale()
  useEffect(() => {
    void preloadHomeProductStageScreenshots()
  }, [])
  const activeSceneId = homeNarrativeActs[activeAct].sceneId
  const Scene = scenes[activeSceneId]
  const activeScene = sceneManifest[activeSceneId]
  const accent = activeScene.accentHex
  const label = t(activeScene.windowLabelKey)

  return (
    <StageShell
      accentHex={accent}
      className="h-full shadow-[0_32px_72px_rgba(15,23,42,0.10)]"
      headerClassName="transition-colors duration-300"
      bodyClassName="relative min-h-0 flex-1 overflow-hidden bg-white"
      label={(
        <motion.span
          key={label}
          className="ml-auto font-mono text-[11px] uppercase tracking-[0.18em] text-slate-400"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 6 }}
          animate={prefersReducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
          transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.18, ease: 'easeOut' }}
        >
          {label}
        </motion.span>
      )}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeAct}
          className="absolute inset-0 will-change-transform"
          initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: 24, scale: 0.996 }}
          animate={prefersReducedMotion ? { opacity: 1 } : { opacity: 1, x: 0, scale: 1 }}
          exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: -18, scale: 0.996 }}
          transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.24, ease: [0.32, 0.72, 0, 1] }}
        >
          <Scene />
        </motion.div>
      </AnimatePresence>
    </StageShell>
  )
}
