// SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
// SPDX-License-Identifier: AGPL-3.0-only

import type { ReactNode } from 'react'
import { StageShell } from '@/components/home/StageShell'
import { ScreenshotStageAsset } from '@/components/home/ScreenshotStageAsset'
import { cn } from '@/lib/utils'

type SceneScreenshotCardProps = {
  src: string
  alt: string
  label: string
  accentHex: string
  objectPosition?: string
  scale?: number
  className?: string
  bodyClassName?: string
  imageClassName?: string
  overlay?: ReactNode
}

export function SceneScreenshotCard({
  src,
  alt,
  label,
  accentHex,
  objectPosition,
  scale,
  className,
  bodyClassName,
  imageClassName,
  overlay,
}: SceneScreenshotCardProps) {
  return (
    <StageShell
      label={label}
      accentHex={accentHex}
      className={cn('h-full shadow-[0_24px_52px_rgba(15,23,42,0.10)]', className)}
      bodyClassName={cn('h-full', bodyClassName)}
    >
      <div className="h-full">
        <ScreenshotStageAsset
          src={src}
          alt={alt}
          objectPosition={objectPosition}
          scale={scale}
          imageClassName={imageClassName}
          overlay={overlay}
        />
      </div>
    </StageShell>
  )
}
