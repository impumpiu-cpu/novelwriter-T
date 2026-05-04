// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

type ScreenshotStageAssetProps = {
  src: string
  alt: string
  className?: string
  imageClassName?: string
  objectPosition?: string
  scale?: number
  overlay?: ReactNode
  loading?: 'eager' | 'lazy'
  fetchPriority?: 'high' | 'low' | 'auto'
}

export function ScreenshotStageAsset({
  src,
  alt,
  className,
  imageClassName,
  objectPosition = 'center top',
  scale = 1,
  overlay,
  loading = 'lazy',
  fetchPriority = 'auto',
}: ScreenshotStageAssetProps) {
  return (
    <div className={cn('relative h-full w-full overflow-hidden bg-white', className)}>
      <img
        src={src}
        alt={alt}
        className={cn('h-full w-full object-cover object-top', imageClassName)}
        style={{ objectPosition, transform: `scale(${scale})`, transformOrigin: objectPosition }}
        loading={loading}
        fetchPriority={fetchPriority}
        decoding="async"
        draggable={false}
      />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0.06)_58%,rgba(255,255,255,0.14))]" />
      {overlay}
    </div>
  )
}
