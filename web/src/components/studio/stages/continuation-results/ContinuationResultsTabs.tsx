import { Check, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ContinuationResultsT, VariantState } from './helpers'

interface ContinuationResultsTabsProps {
  tabCount: number
  activeTab: number
  isStreamMode: boolean
  isFallbackMode: boolean
  isLegacyMode: boolean
  variants: VariantState[]
  onSelect: (index: number) => void
  t: ContinuationResultsT
}

export function ContinuationResultsTabs({
  tabCount,
  activeTab,
  isStreamMode,
  isFallbackMode,
  isLegacyMode,
  variants,
  onSelect,
  t,
}: ContinuationResultsTabsProps) {
  if (tabCount <= 0) return null

  return (
    <div className="shrink-0 flex items-center">
      {Array.from({ length: tabCount }, (_, index) => {
        const variant = isStreamMode && !isFallbackMode ? variants[index] : undefined
        const isActive = index === activeTab
        const isVariantStreaming = variant?.isStreaming
        const isVariantDone = isLegacyMode || isFallbackMode || variant?.continuationId != null
        const hasError = variant?.error

        return (
          <button
            key={index}
            type="button"
            onClick={() => onSelect(index)}
            className={cn(
              'px-6 py-2.5 text-sm border-b-2 transition-colors flex items-center gap-2',
              isActive
                ? 'border-b-accent text-foreground font-semibold'
                : 'border-b-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {t('continuation.results.version', { n: index + 1 })}
            {isVariantStreaming ? <Loader2 size={14} className="animate-spin" /> : null}
            {hasError ? <span className="text-destructive text-xs">!</span> : null}
            {isVariantDone && !isVariantStreaming && !hasError && isStreamMode && !isFallbackMode ? (
              <Check size={14} className="text-green-500" />
            ) : null}
          </button>
        )
      })}
    </div>
  )
}
