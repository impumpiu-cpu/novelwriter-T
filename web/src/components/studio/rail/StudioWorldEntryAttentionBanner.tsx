import { AlertTriangle, ArrowUpRight, Clock3, Sparkles } from 'lucide-react'
import { NwButton } from '@/components/ui/nw-button'
import { cn } from '@/lib/utils'

export type StudioWorldEntryAttentionBannerTone = 'running' | 'needs_review' | 'failed'

const toneClassNames: Record<StudioWorldEntryAttentionBannerTone, string> = {
  running: 'border-[hsl(var(--color-intent-governance)/0.28)] bg-[linear-gradient(145deg,hsl(var(--color-intent-governance)/0.16),transparent_78%)]',
  needs_review: 'border-[hsl(var(--color-intent-governance)/0.32)] bg-[linear-gradient(145deg,hsl(var(--color-intent-governance)/0.18),transparent_76%)]',
  failed: 'border-[hsl(var(--color-warning)/0.30)] bg-[linear-gradient(145deg,hsl(var(--color-warning)/0.14),transparent_78%)]',
}

const badgeClassNames: Record<StudioWorldEntryAttentionBannerTone, string> = {
  running: 'border-[hsl(var(--color-intent-governance)/0.28)] bg-[hsl(var(--color-intent-governance)/0.14)] text-[hsl(var(--color-intent-governance))]',
  needs_review: 'border-[hsl(var(--color-intent-governance)/0.32)] bg-[hsl(var(--color-intent-governance)/0.16)] text-[hsl(var(--color-intent-governance))]',
  failed: 'border-[hsl(var(--color-warning)/0.30)] bg-[hsl(var(--color-warning)/0.14)] text-[hsl(var(--color-warning))]',
}

function ToneIcon({ tone }: { tone: StudioWorldEntryAttentionBannerTone }) {
  if (tone === 'running') return <Clock3 className="h-4 w-4" />
  if (tone === 'failed') return <AlertTriangle className="h-4 w-4" />
  return <Sparkles className="h-4 w-4" />
}

export function StudioWorldEntryAttentionBanner({
  tone,
  eyebrow,
  title,
  description,
  actionLabel,
  onAction,
  onActionWarm,
}: {
  tone: StudioWorldEntryAttentionBannerTone
  eyebrow: string
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  onActionWarm?: () => void
}) {
  return (
    <section
      className={cn(
        'rounded-[18px] border px-3.5 py-3 motion-safe:transition-[border-color,background-color,transform,opacity] motion-safe:duration-300 motion-reduce:transition-none',
        toneClassNames[tone],
      )}
      data-testid="studio-world-entry-attention-banner"
      data-tone={tone}
    >
      <div className="flex items-start gap-3">
        <div className={cn('mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] border', badgeClassNames[tone])}>
          <ToneIcon tone={tone} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-semibold uppercase tracking-[0.20em] text-muted-foreground/72">
            {eyebrow}
          </div>
          <div className="mt-1 text-sm font-semibold text-foreground">
            {title}
          </div>
          <p className="mt-1 text-[12px] leading-5 text-muted-foreground/82">
            {description}
          </p>
        </div>
        {actionLabel && onAction ? (
          <NwButton
            variant={tone === 'needs_review' ? 'accentOutline' : 'glass'}
            className="shrink-0 rounded-full px-3 py-2 text-xs font-semibold"
            onClick={onAction}
            onMouseEnter={onActionWarm}
            onFocus={onActionWarm}
            data-testid="studio-world-entry-attention-action"
          >
            <ArrowUpRight className="h-3.5 w-3.5" />
            {actionLabel}
          </NwButton>
        ) : null}
      </div>
    </section>
  )
}
