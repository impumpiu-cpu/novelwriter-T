import { Loader2, MessageSquarePlus, Settings } from 'lucide-react'
import { FeedbackForm, type FeedbackAnswers } from '@/components/feedback/FeedbackForm'
import { NwButton } from '@/components/ui/nw-button'
import type { ContinuationResultsT } from './helpers'

export function ContinuationResultsLoadingState({ label }: { label: string }) {
  return (
    <div className="flex flex-1 items-center justify-center flex-col gap-4">
      <Loader2 size={24} className="animate-spin text-muted-foreground" />
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  )
}

interface ContinuationResultsReloadErrorStateProps {
  error: string
  onRetry: () => void
  onBack: () => void
  t: ContinuationResultsT
}

export function ContinuationResultsReloadErrorState({ error, onRetry, onBack, t }: ContinuationResultsReloadErrorStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center flex-col gap-4">
      <span className="text-sm text-destructive">{error}</span>
      <div className="flex items-center gap-3">
        <NwButton
          onClick={onRetry}
          variant="accent"
          className="rounded-[10px] px-5 py-2.5 text-sm font-semibold shadow-[0_0_18px_hsl(var(--accent)/0.25)]"
        >
          {t('continuation.results.retry')}
        </NwButton>
        <NwButton
          onClick={onBack}
          variant="glass"
          className="rounded-[10px] px-5 py-2.5 text-sm font-semibold"
        >
          {t('continuation.results.back')}
        </NwButton>
      </div>
    </div>
  )
}

interface ContinuationResultsEmptyStateProps {
  onBack: () => void
  t: ContinuationResultsT
}

export function ContinuationResultsEmptyState({ onBack, t }: ContinuationResultsEmptyStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center flex-col gap-4">
      <span className="text-sm text-muted-foreground">{t('continuation.results.noResults')}</span>
      <NwButton
        onClick={onBack}
        variant="accent"
        className="rounded-[10px] px-5 py-2.5 text-sm font-semibold shadow-[0_0_18px_hsl(var(--accent)/0.25)]"
      >
        {t('continuation.results.returnToWorkspace')}
      </NwButton>
    </div>
  )
}

interface ContinuationResultsStreamErrorStateProps {
  error: string
  isQuotaExhausted: boolean
  feedbackAlreadySubmitted: boolean
  showFeedbackForm: boolean
  feedbackSubmitting: boolean
  onOpenFeedback: () => void
  onCloseFeedback: () => void
  onSubmitFeedback: (answers: FeedbackAnswers) => Promise<void>
  onRetry: () => void
  onBackToWrite: () => void
  onReturnToWorkspace: () => void
  onGoToSettings: () => void
  t: ContinuationResultsT
}

export function ContinuationResultsStreamErrorState({
  error,
  isQuotaExhausted,
  feedbackAlreadySubmitted,
  showFeedbackForm,
  feedbackSubmitting,
  onOpenFeedback,
  onCloseFeedback,
  onSubmitFeedback,
  onRetry,
  onBackToWrite,
  onReturnToWorkspace,
  onGoToSettings,
  t,
}: ContinuationResultsStreamErrorStateProps) {
  return (
    <>
      <div className="flex flex-1 items-center justify-center flex-col gap-5">
        <span className="text-base font-semibold text-destructive">{error}</span>

        {isQuotaExhausted && !feedbackAlreadySubmitted ? (
          <div className="flex flex-col items-center gap-3 max-w-md text-center">
            <p className="text-sm text-muted-foreground">{t('continuation.results.quotaFeedback')}</p>
            <NwButton
              onClick={onOpenFeedback}
              variant="accent"
              className="rounded-[10px] px-6 py-2.5 text-sm font-semibold shadow-[0_0_18px_hsl(var(--accent)/0.25)]"
            >
              <MessageSquarePlus size={16} />
              {t('continuation.results.submitFeedbackUnlock')}
            </NwButton>
          </div>
        ) : null}

        {isQuotaExhausted && feedbackAlreadySubmitted ? (
          <div className="flex flex-col items-center gap-3 max-w-md text-center">
            <p className="text-sm text-muted-foreground">{t('continuation.results.feedbackAlreadyClaimed')}</p>
            <NwButton
              onClick={onGoToSettings}
              variant="accent"
              className="rounded-[10px] px-6 py-2.5 text-sm font-semibold shadow-[0_0_18px_hsl(var(--accent)/0.25)]"
            >
              <Settings size={16} />
              {t('continuation.results.goToSettings')}
            </NwButton>
          </div>
        ) : null}

        {!isQuotaExhausted ? (
          <div className="flex items-center gap-3">
            <NwButton
              onClick={onRetry}
              variant="accent"
              className="rounded-[10px] px-5 py-2.5 text-sm font-semibold shadow-[0_0_18px_hsl(var(--accent)/0.25)]"
            >
              {t('continuation.results.retry')}
            </NwButton>
            <NwButton
              onClick={onBackToWrite}
              variant="glass"
              className="rounded-[10px] px-5 py-2.5 text-sm font-semibold"
            >
              {t('continuation.results.back')}
            </NwButton>
          </div>
        ) : null}

        {isQuotaExhausted ? (
          <NwButton
            onClick={onReturnToWorkspace}
            variant="glass"
            className="rounded-[10px] px-5 py-2.5 text-sm font-semibold"
          >
            {t('continuation.results.returnToWorkspace')}
          </NwButton>
        ) : null}
      </div>

      {showFeedbackForm ? (
        <FeedbackForm
          onSubmit={onSubmitFeedback}
          onCancel={onCloseFeedback}
          submitting={feedbackSubmitting}
        />
      ) : null}
    </>
  )
}
