import type { ReactNode } from 'react'
import { AlertTriangle, ArrowUpRight, CheckCircle2, Clock3, Sparkles } from 'lucide-react'
import { NwButton } from '@/components/ui/nw-button'
import { cn } from '@/lib/utils'

export type WorldEntryLifecycleTone = 'idle' | 'running' | 'needs_review' | 'success' | 'failed'

const toneClassNames: Record<WorldEntryLifecycleTone, string> = {
  idle: 'border-[var(--nw-glass-border)] bg-background/20',
  running: 'border-[hsl(var(--foreground)/0.10)] bg-[hsl(var(--foreground)/0.04)]',
  needs_review: 'border-[hsl(var(--foreground)/0.12)] bg-[hsl(var(--foreground)/0.05)]',
  success: 'border-[hsl(var(--foreground)/0.10)] bg-[hsl(var(--foreground)/0.03)]',
  failed: 'border-[hsl(var(--color-warning)/0.28)] bg-[hsl(var(--color-warning)/0.08)]',
}

const badgeClassNames: Record<WorldEntryLifecycleTone, string> = {
  idle: 'border-[var(--nw-glass-border)] bg-background/18 text-muted-foreground',
  running: 'border-[hsl(var(--foreground)/0.10)] bg-[hsl(var(--foreground)/0.05)] text-foreground/80',
  needs_review: 'border-[hsl(var(--foreground)/0.12)] bg-[hsl(var(--foreground)/0.06)] text-foreground/80',
  success: 'border-[hsl(var(--foreground)/0.10)] bg-[hsl(var(--foreground)/0.04)] text-foreground/72',
  failed: 'border-[hsl(var(--color-warning)/0.3)] bg-[hsl(var(--color-warning)/0.14)] text-[hsl(var(--color-warning))]',
}

function DefaultToneIcon({ tone }: { tone: WorldEntryLifecycleTone }) {
  if (tone === 'running') return <Clock3 className="h-4 w-4" />
  if (tone === 'needs_review') return <Sparkles className="h-4 w-4" />
  if (tone === 'success') return <CheckCircle2 className="h-4 w-4" />
  if (tone === 'failed') return <AlertTriangle className="h-4 w-4" />
  return <ArrowUpRight className="h-4 w-4" />
}

export function WorldEntryLifecycleCard({
  eyebrow,
  title,
  description,
  summary,
  tone = 'idle',
  statusLabel,
  actionLabel,
  onAction,
  onActionWarm,
  actionTestId,
  icon,
  className,
  testId,
}: {
  eyebrow: string
  title: string
  description: string
  summary: string
  tone?: WorldEntryLifecycleTone
  statusLabel?: string
  actionLabel?: string
  onAction?: () => void
  onActionWarm?: () => void
  actionTestId?: string
  icon?: ReactNode
  className?: string
  testId?: string
}) {
  return (
    <section
      className={cn(
        'rounded-[20px] border px-3.5 py-3.5 motion-safe:transition-[border-color,background-color,box-shadow,transform,opacity] motion-safe:duration-300 motion-reduce:transition-none',
        toneClassNames[tone],
        className,
      )}
      data-testid={testId}
      data-tone={tone}
    >
      <div className="flex items-start gap-3">
        <div className={cn(
          'mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-[16px] border text-foreground/88',
          badgeClassNames[tone],
        )}>
          {icon ?? <DefaultToneIcon tone={tone} />}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/74">
              {eyebrow}
            </span>
            {statusLabel ? (
              <span
                className={cn(
                  'inline-flex rounded-full border px-2.5 py-1 text-[10px] font-medium',
                  badgeClassNames[tone],
                )}
              >
                {statusLabel}
              </span>
            ) : null}
          </div>

          <div className="mt-1 text-sm font-semibold text-foreground">{title}</div>
          <p className="mt-1 text-[12px] leading-5 text-muted-foreground/82">{description}</p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex rounded-full border border-[var(--nw-glass-border)] bg-background/18 px-2.5 py-1 text-[11px] text-foreground/88">
              {summary}
            </span>
            {actionLabel && onAction ? (
              <NwButton
                variant="glass"
                className="rounded-full px-3 py-2 text-xs font-semibold"
                onClick={onAction}
                onMouseEnter={onActionWarm}
                onFocus={onActionWarm}
                data-testid={actionTestId}
              >
                <ArrowUpRight className="h-3.5 w-3.5" />
                {actionLabel}
              </NwButton>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  )
}
