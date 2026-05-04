import { copilotDrawerShellClassName } from '@/components/novel-copilot/novelCopilotChrome'
import { cn } from '@/lib/utils'

export function NovelCopilotDrawerFallback({
  width,
}: {
  width: number
}) {
  return (
    <aside
      className={cn(
        'relative shrink-0 overflow-hidden border-l',
        copilotDrawerShellClassName,
      )}
      style={{ width }}
      data-testid="novel-copilot-drawer-fallback"
      aria-label="Loading Copilot"
    >
      <div className="absolute inset-0 bg-[var(--nw-copilot-shell-bg)]" />
      <div className="relative flex h-full flex-col px-4 py-5">
        <div className="h-14 rounded-[18px] border border-[var(--nw-copilot-border)] bg-background/12" />
        <div className="mt-4 h-11 rounded-[18px] border border-[var(--nw-copilot-border)] bg-background/10" />
        <div className="mt-4 space-y-4">
          <div className="h-36 rounded-[24px] border border-[var(--nw-copilot-border)] bg-background/10" />
          <div className="h-44 rounded-[24px] border border-[var(--nw-copilot-border)] bg-background/10" />
        </div>
      </div>
    </aside>
  )
}
