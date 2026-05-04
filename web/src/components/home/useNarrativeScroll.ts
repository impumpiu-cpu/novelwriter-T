// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import { useRef, useState } from 'react'
import { useScroll, useMotionValueEvent, useReducedMotion } from 'framer-motion'
import { HOME_NARRATIVE_ACT_COUNT } from '@/components/home/homeContent'

export type NarrativeActs = 0 | 1 | 2 | 3 | 4

/**
 * Single source of truth for the sticky narrative stage.
 *
 * Maps section scrollYProgress (0→1) to an active act index (0..4)
 * and per-act sub-progress.  No IntersectionObserver — scroll position
 * is the only state driver, so left text and right mockup always agree.
 */
export function useNarrativeScroll() {
    const sectionRef = useRef<HTMLDivElement>(null)
    const [activeAct, setActiveAct] = useState<NarrativeActs>(0)
    const prefersReducedMotion = useReducedMotion()

    const { scrollYProgress } = useScroll({
        target: sectionRef,
        // "start 0.55" = tracking begins when section top hits 55% of viewport
        // (section is partially visible, not still off-screen at viewport bottom)
        // "end start" = tracking ends when section bottom hits viewport top
        offset: ['start 0.55', 'end start'],
    })

    const segmentSize = 1 / HOME_NARRATIVE_ACT_COUNT
    const actSwitchBias = segmentSize * 0.04

    useMotionValueEvent(scrollYProgress, 'change', (v) => {
        const biasedProgress = Math.min(0.999, Math.max(0, v + actSwitchBias))
        let next: NarrativeActs = 0
        for (let i = HOME_NARRATIVE_ACT_COUNT - 1; i >= 0; i--) {
            if (biasedProgress >= i * segmentSize) {
                next = i as NarrativeActs
                break
            }
        }
        setActiveAct((prev) => (prev !== next ? next : prev))
    })

    return {
        sectionRef,
        activeAct,
        prefersReducedMotion: prefersReducedMotion ?? false,
    }
}
