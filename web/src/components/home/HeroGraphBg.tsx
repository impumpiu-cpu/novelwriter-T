// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import { motion } from 'framer-motion'

/**
 * Hero background — animated gradient orbs instead of knowledge graph SVG.
 *
 * Design intent: the old SVG graph with labeled nodes was too literal and
 * competed with the product screenshot for attention. These soft gradient
 * orbs provide visual warmth and depth without being "read" as content.
 */
export function HeroGraphBg() {
  return (
    <div className="absolute inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden="true">
      {/* Warm ambient glow — top left */}
      <motion.div
        className="absolute -left-[10%] -top-[20%] h-[600px] w-[600px] rounded-full opacity-[0.07]"
        style={{
          background: 'radial-gradient(circle, #f59e0b 0%, transparent 70%)',
        }}
        animate={{
          x: [0, 30, -10, 0],
          y: [0, -20, 15, 0],
        }}
        transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Cool accent glow — center right */}
      <motion.div
        className="absolute right-[5%] top-[10%] h-[500px] w-[500px] rounded-full opacity-[0.05]"
        style={{
          background: 'radial-gradient(circle, #14b8a6 0%, transparent 70%)',
        }}
        animate={{
          x: [0, -20, 10, 0],
          y: [0, 15, -20, 0],
        }}
        transition={{ duration: 24, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Violet whisper — bottom center */}
      <motion.div
        className="absolute bottom-[5%] left-[30%] h-[400px] w-[400px] rounded-full opacity-[0.04]"
        style={{
          background: 'radial-gradient(circle, #8b5cf6 0%, transparent 70%)',
        }}
        animate={{
          x: [0, 15, -15, 0],
          y: [0, -10, 20, 0],
        }}
        transition={{ duration: 28, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Fine dot grid for texture */}
      <div
        className="absolute inset-0 opacity-[0.025] .light:opacity-[0.025]"
        style={{
          backgroundImage: 'radial-gradient(circle, hsl(var(--foreground)) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />
    </div>
  )
}
