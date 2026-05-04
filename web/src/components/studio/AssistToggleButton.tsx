import { Bot } from 'lucide-react'
import { useUiLocale } from '@/contexts/UiLocaleContext'
import { cn } from '@/lib/utils'

export function AssistToggleButton({
  active,
  onClick,
}: {
  active?: boolean
  onClick: () => void
}) {
  const { t } = useUiLocale()
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center justify-center rounded-[10px] h-10 w-10 transition-colors',
        active
          ? 'bg-[var(--nw-glass-bg-hover)] text-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-[var(--nw-glass-bg-hover)]',
      )}
      aria-label={t('studio.assistant.toggleSidebar')}
      title={t('studio.assistant.toggleSidebar')}
    >
      <Bot size={16} />
    </button>
  )
}
