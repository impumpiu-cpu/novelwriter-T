import { cn } from '@/lib/utils'
import {
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
            'group relative overflow-hidden rounded-[20px] px-3.5 py-3 text-left transition-colors duration-200',
            copilotPanelMutedClassName,
            'hover:border-[var(--nw-copilot-border-strong)] hover:bg-[var(--nw-copilot-pill-hover-bg)]',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--foreground)/0.2)] focus-visible:ring-offset-1 focus-visible:ring-offset-background',
            disabled &&
              'cursor-not-allowed opacity-50 grayscale hover:border-[var(--nw-copilot-border)] hover:bg-[var(--nw-copilot-panel-muted-bg)]',
          )}
        >
          <div className="relative flex items-start gap-3">
            <div className={cn('mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-[18px]', action.iconClassName)}>
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
