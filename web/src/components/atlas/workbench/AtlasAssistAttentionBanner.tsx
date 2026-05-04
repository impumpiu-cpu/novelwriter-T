import { m, useReducedMotion } from 'framer-motion'
import { AlertTriangle, ArrowUpRight, Clock3, Sparkles } from 'lucide-react'
import { NwButton } from '@/components/ui/nw-button'
import { cn } from '@/lib/utils'

export type AtlasAssistAttentionBannerTone = 'running' | 'needs_review' | 'failed'

const toneClassNames: Record<AtlasAssistAttentionBannerTone, string> = {
  running: 'border-[hsl(var(--foreground)/0.12)] bg-[linear-gradient(145deg,hsl(var(--foreground)/0.06),transparent_78%)]',
  needs_review: 'border-[hsl(var(--foreground)/0.14)] bg-[linear-gradient(145deg,hsl(var(--foreground)/0.08),transparent_76%)]',
  failed: 'border-[hsl(var(--color-warning)/0.30)] bg-[linear-gradient(145deg,hsl(var(--color-warning)/0.14),transparent_78%)]',
}

const badgeClassNames: Record<AtlasAssistAttentionBannerTone, string> = {
  running: 'border-[hsl(var(--foreground)/0.12)] bg-[hsl(var(--foreground)/0.06)] text-foreground/80',
  needs_review: 'border-[hsl(var(--foreground)/0.14)] bg-[hsl(var(--foreground)/0.08)] text-foreground/80',
  failed: 'border-[hsl(var(--color-warning)/0.30)] bg-[hsl(var(--color-warning)/0.14)] text-[hsl(var(--color-warning))]',
}

function ToneIcon({ tone }: { tone: AtlasAssistAttentionBannerTone }) {
  if (tone === 'running') return <Clock3 className="h-4 w-4" />
  if (tone === 'failed') return <AlertTriangle className="h-4 w-4" />
  return <Sparkles className="h-4 w-4" />
}

export function AtlasAssistAttentionBanner({
  tone,
  eyebrow,
  title,
  description,
  actionLabel,
  onAction,
}: {
  tone: AtlasAssistAttentionBannerTone
  eyebrow: string
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
}) {
  const prefersReducedMotion = useReducedMotion()

  return (
    <section
      className={cn(
        'relative overflow-hidden rounded-[18px] border px-3.5 py-3 motion-safe:transition-[border-color,background-color,transform,opacity] motion-safe:duration-300 motion-reduce:transition-none',
        toneClassNames[tone],
      )}
      data-testid="atlas-assist-attention-banner"
      data-tone={tone}
    >
      <m.div
        className="pointer-events-none absolute inset-0"
        initial={false}
        animate={
          prefersReducedMotion
            ? { opacity: 0.65 }
            : {
                opacity: tone === 'failed' ? 0.5 : 0.85,
                backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
              }
        }
        transition={
          prefersReducedMotion
            ? { duration: 0 }
            : { duration: tone === 'running' ? 7.5 : 6.2, repeat: Number.POSITIVE_INFINITY, ease: 'easeInOut' }
        }
        style={{
          backgroundImage: tone === 'failed'
            ? 'linear-gradient(120deg, transparent, hsl(var(--color-warning)/0.12), transparent)'
            : 'linear-gradient(120deg, transparent, hsl(var(--foreground)/0.06), transparent)',
          backgroundSize: '200% 200%',
        }}
      />

      <div className="relative z-10 flex items-start gap-3">
        <div className={cn('mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] border', badgeClassNames[tone])}>
          <ToneIcon tone={tone} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.20em] text-muted-foreground/72">
            <m.span
              className={cn(
                'inline-flex h-1.5 w-1.5 rounded-full',
                tone === 'failed'
                  ? 'bg-[hsl(var(--color-warning))]'
                  : 'bg-foreground/60',
              )}
              initial={false}
              animate={
                prefersReducedMotion
                  ? { opacity: 0.9, scale: 1 }
                  : { opacity: [0.55, 1, 0.55], scale: [0.92, 1.12, 0.92] }
              }
              transition={
                prefersReducedMotion
                  ? { duration: 0 }
                  : { duration: tone === 'running' ? 1.8 : 1.4, repeat: Number.POSITIVE_INFINITY, ease: 'easeInOut' }
              }
            />
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
            variant="glass"
            className="shrink-0 rounded-full px-3 py-2 text-xs font-semibold"
            onClick={onAction}
            data-testid="atlas-assist-attention-action"
          >
            <ArrowUpRight className="h-3.5 w-3.5" />
            {actionLabel}
          </NwButton>
        ) : null}
      </div>
    </section>
  )
}
