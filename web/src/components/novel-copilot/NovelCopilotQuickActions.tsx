import { cn } from '@/lib/utils'
import {
  copilotHighlightLineClassName,
  copilotPanelMutedClassName,
} from './novelCopilotChrome'
import type { CopilotQuickActionSpec } from './novelCopilotWorkbench'

export function NovelCopilotQuickActions({
  actions,
  onAction,
  disabled = false,
}: {
  actions: CopilotQuickActionSpec[]
  onAction: (action: string) => void
  disabled?: boolean
}) {
  return (
    <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
      {actions.map((action) => (
        <button
          key={action.id}
          type="button"
          onClick={() => onAction(action.id)}
          disabled={disabled}
          className={cn(
            action.layoutClassName,
            'group relative overflow-hidden rounded-[20px] px-3.5 py-3 text-left transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]',
            copilotPanelMutedClassName,
            'hover:border-[hsl(var(--foreground)/0.15)] hover:[background:var(--nw-copilot-pill-hover-bg)] hover:shadow-[0_12px_32px_rgba(0,0,0,0.08),0_4px_12px_rgba(0,0,0,0.04)] hover:-translate-y-[1px]',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--foreground)/0.2)] focus-visible:ring-offset-1 focus-visible:ring-offset-background',
            disabled &&
              'cursor-not-allowed opacity-50 grayscale hover:border-[var(--nw-copilot-border)] hover:[background:var(--nw-copilot-panel-muted-bg)] hover:shadow-none hover:translate-y-0',
          )}
        >
          <div className={cn('pointer-events-none absolute inset-x-0 top-0 h-14 opacity-75 transition-opacity duration-300 group-hover:opacity-100', action.glowClassName)} />
          <div className={cn('pointer-events-none absolute inset-x-2 top-0 h-px opacity-60 transition-opacity duration-300 group-hover:opacity-100', copilotHighlightLineClassName)} />
          <div className="relative flex items-start gap-3">
            <div className={cn('mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-[18px] shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]', action.iconClassName)}>
              <action.icon className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-foreground/95 transition-colors group-hover:text-foreground">
                {action.label}
              </div>
              <div className="nw-line-clamp-2 mt-1 text-[11px] leading-[1.15rem] text-muted-foreground/76">
                {action.description}
              </div>
            </div>
          </div>
        </button>
      ))}
    </div>
  )
}
